"""Build speaker boxes from the original PDF's positioned text runs."""
import argparse
import base64
import hashlib
import math
import json
import re
import subprocess
from tempfile import TemporaryDirectory
from pathlib import Path

import fitz

LABEL = re.compile(r"[A-Z0-9][A-Z0-9 .+/&’'-]{0,36}:")
PHASES = {
    "ACT I": "act1", "ACT 1": "act1", "ACT ONE": "act1",
    "INTERVAL": "interval", "INTERMISSION": "interval",
    "ACT II": "act2", "ACT 2": "act2", "ACT TWO": "act2",
}
TECHNICAL = re.compile(
    r"(?i)^(?:SFX|TABS|BLACK\s+TABS|FULL\s+TABS|BLUE\s+TABS|FRONT\s+OF\s+TABS"
    r"|MUSIC|SONG\s|UV\s+LIGHTING|BLACKOUT|PAGE\s|ACT\s|SCENE\s)"
)


def scan_brackets(text, start=0):
    """Return (depth after the row, index just after the row last reached zero)."""
    depth = start
    last_zero = None
    for index, char in enumerate(text):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
            if depth <= 0:
                depth = max(depth, 0)
                last_zero = index + 1
    return depth, last_zero


def page_rows(page):
    spans = [
        {**span, "text": span["text"].replace("\u200b", "")}
        for block in page.get_text("dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)["blocks"]
        for line in block.get("lines", [])
        for span in line["spans"]
        if span["text"].replace("\u200b", "").strip()
    ]
    rows = []
    for span in sorted(spans, key=lambda span: span["origin"][1]):
        baseline = span["origin"][1]
        if not rows or baseline - rows[-1][0] > 2:
            rows.append((baseline, []))
        rows[-1][1].append(span)
    return [sorted(row, key=lambda span: span["bbox"][0]) for _, row in rows]


def is_heading(name):
    return name.strip() in {"PROLOGUE", "EPILOGUE", "INTERVAL", "INTERMISSION"} or name.startswith(
        ("SCENE ", "ACT ", "MUSIC", "PAGE ", "SFX", "TABS")
    )


def speaker_on_row(row, width):
    label = row[0]
    if label["bbox"][0] >= width * .35:
        return None, row
    inline = re.match(r"^([A-Z][A-Z0-9 .+/&’'-]{0,36}):\s+\S", label["text"].strip())
    if inline:
        name = inline.group(1)
        if not is_heading(name):
            return name, row
    parts = []
    for index, span in enumerate(row[:-1]):
        parts.append(span["text"].replace("\u200b", "").strip())
        text = " ".join(parts).replace(" :", ":")
        if LABEL.fullmatch(text):
            if not is_heading(text[:-1]) and row[index + 1]["bbox"][0] >= span["bbox"][0]:
                return text[:-1].strip(), row[index + 1:]
            break
        if ":" in text or len(text) > 37:
            break
    return None, row


def add_dialogue(stop, number, spans):
    spoken = [span for span in spans if not span["flags"] & fitz.TEXT_FONT_ITALIC]
    if not spoken:
        return
    rect = fitz.Rect(spoken[0]["bbox"])
    for span in spoken[1:]:
        rect |= fitz.Rect(span["bbox"])
    previous = stop["boxes"][-1] if stop["boxes"] else None
    # Merge only adjacent rows: a far-apart rect on the same page would
    # swallow unrelated cue lines between the two.
    if previous and previous[0] == number and rect.y0 <= previous[1].y1 + 18:
        previous[1] |= rect
    else:
        stop["boxes"].append([number, rect])


def build(pdf, output, cues=(), source=None):
    pages, stops, phases = [], [], []
    phase = "act1"
    has_dialogue = False
    current = None
    dialogue_left = 0
    depth = 0
    with fitz.open(pdf) as doc:
        if doc.needs_pass or not len(doc):
            raise ValueError("Use a nonempty PDF without password protection.")
        for number, page in enumerate(doc):
            if page.rotation:
                page.remove_rotation()
            width, height = page.rect.width, page.rect.height
            pages.append([width, height])
            scale = min(3.2, 2700 / max(width, height))
            page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(output / f"{number}.png")
            for row in page_rows(page):
                first = row[0]
                text = first["text"].strip()
                heading = re.sub(r"\s*\([^)]*\)\s*$", "", text).upper().rstrip(" :")
                next_phase = PHASES.get(heading)
                # Cast and scene lists can mention later acts before the script starts.
                if next_phase and (len(row) == 1 or first["flags"] & fitz.TEXT_FONT_BOLD):
                    if next_phase == "interval" and phase == "act1" and has_dialogue:
                        phase = "interval"
                        stops.append(dict(phase=phase, speaker="Interval", boxes=[[number, fitz.Rect(first["bbox"])]]))
                    elif next_phase == "act2" and (phase == "interval" or (phase == "act1" and has_dialogue)):
                        phase = "act2"
                    current = None
                    depth = 0
                    continue
                if phase == "interval":
                    continue
                speaker, dialogue = speaker_on_row(row, width)
                if speaker:
                    has_dialogue = True
                    current = dict(phase=phase, speaker=speaker, boxes=[])
                    dialogue_left = dialogue[0]["bbox"][0]
                    add_dialogue(current, number, row)
                    if not current["boxes"]:
                        current["boxes"].append([number, fitz.Rect(first["bbox"])])
                    stops.append(current)
                    label_text = " ".join(span["text"].replace("\u200b", "") for span in row).strip()
                    depth = max(scan_brackets(label_text)[0], 0)
                else:
                    row_text = " ".join(span["text"].replace("\u200b", "") for span in row).strip()
                    if TECHNICAL.match(row_text.lstrip(":;.,-–— ")) or row_text.isdigit():
                        # Cue lines and page numbers: keep the speech open, never highlight.
                        continue
                    end_depth, last_zero = scan_brackets(row_text, depth)
                    trailing = row_text[last_zero:].strip() if last_zero is not None else ""
                    if depth or row_text.startswith(("[", "(")):
                        # Inside, opening or closing a bracketed stage direction:
                        # only highlight a row that closes the brackets mid-row
                        # with real dialogue after them.
                        depth = max(end_depth, 0)
                        if current and last_zero is not None and len(trailing) >= 15:
                            add_dialogue(current, number, row)
                    elif (
                        sum(row_text.count(c) for c in "([") < sum(row_text.count(c) for c in ")]")
                        and not trailing
                    ):
                        # A row that ends by closing a bracket opened earlier:
                        # the tail of a wrapped stage direction.
                        continue
                    elif (
                        current
                        and abs(first["bbox"][0] - dialogue_left) < 14
                        and not first["flags"] & (fitz.TEXT_FONT_ITALIC | fitz.TEXT_FONT_BOLD)
                    ):
                        add_dialogue(current, number, row)
                        depth = max(scan_brackets(row_text)[0], 0)
                    else:
                        current = None
            phases.append(phase)

    def page_box(number):
        width, height = pages[number]
        return [number, fitz.Rect(8, 8, width - 8, min(55, height - 8))]

    if not any(stop["phase"] != "interval" for stop in stops):
        print("No speaker labels found. Using page by page navigation.", flush=True)
        stops = [
            dict(phase=phase, speaker=f"Page {number + 1}", boxes=[page_box(number)], pageStop=True)
            for number, phase in enumerate(phases)
        ]
    stops.append(dict(phase="finished", speaker="End of show", boxes=[page_box(len(pages) - 1)]))
    for stop in stops:
        stop["boxes"] = [
            [number, round(rect.x0 - 4, 2), round(rect.y0 - 2, 2),
             round(rect.width + 8, 2), round(rect.height + 4, 2)]
            for number, rect in stop["boxes"]
        ]
    (output / "index.json").write_text(json.dumps(dict(pages=pages, stops=stops, title=pdf.stem, fingerprint=hashlib.sha256((source or pdf).read_bytes()).hexdigest(), cues=normalize_cues(cues, pages))))
    print(f"Loaded {pdf.name}: {len(pages)} pages and {len(stops)} stops.", flush=True)


def normalize_cues(cues, pages):
    result = []
    for cue in cues:
        position = cue.get("cuePosition") or {}
        page = position.get("page")
        x, y = position.get("x"), position.get("y")
        if (type(page) is not int or not 1 <= page <= len(pages)
                or not all(isinstance(value, (float, int)) and math.isfinite(value) for value in (x, y))):
            continue
        width, height = pages[page - 1]
        result.append(dict(
            page=page-1, x=round(max(0,min(1,x/width))*100,2),
            y=round(max(0,min(1,1-y/height))*100,2),
            number=str(cue.get("cueNumber") or ""), notes=str(cue.get("cueNotes") or ""),
            description=str(cue.get("cueDescription") or ""),
        ))
    return sorted(result, key=lambda cue: (cue["page"], cue["y"]))


def load_script(source, output):
    if source.suffix.lower() == ".pdf":
        build(source, output)
        return

    with TemporaryDirectory(prefix="prompt-docx-") as directory:
        work = Path(directory)
        if source.suffix.lower() == ".pcy":
            export = json.loads(source.read_text(encoding="utf-8-sig"))
            encoded_pdf = export.get("pdf")
            if not encoded_pdf:
                raise ValueError("The PromptDesk export must include the script PDF.")
            pdf = work / f"{source.stem}.pdf"
            pdf.write_bytes(base64.b64decode(encoded_pdf, validate=True))
            build(pdf, output, export["showFile"]["cues"], source=source)
            return
        conversion = subprocess.run(
            [
                "soffice",
                f"-env:UserInstallation={(work / 'profile').as_uri()}",
                "--headless", "--convert-to", "pdf:writer_pdf_Export",
                "--outdir", str(work), str(source.resolve()),
            ],
            capture_output=True, text=True, timeout=180,
        )
        pdf = work / f"{source.stem}.pdf"
        if conversion.returncode or not pdf.is_file():
            detail = (conversion.stderr or conversion.stdout).strip()
            raise ValueError(f"Word conversion failed for {source.name}: {detail or 'no PDF produced'}")
        build(pdf, output, source=source)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--filename", default="")
    args = parser.parse_args()
    matches = sorted(path for path in args.folder.iterdir() if path.is_file() and not path.name.startswith("~$") and path.suffix.lower() in {".pdf", ".docx", ".pcy"})
    if args.filename:
        matches = [path for path in matches if path.name == args.filename]
    if len(matches) != 1:
        parser.exit(1, "Mount a folder with exactly one PDF, DOCX or PCY, or set SCRIPT_FILE to the exact filename.\n")
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        load_script(matches[0], args.output)
    except (ValueError, KeyError, TypeError, fitz.FileDataError, OSError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Could not load the script: {error}\n")
