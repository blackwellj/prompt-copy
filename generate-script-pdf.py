"""Generate the printable script PDF: original pages + numbered cue margin boxes
with leader lines, and a cue legend band under each page that has cues."""
import argparse
import base64
import json
from pathlib import Path

import fitz

BOX_W, BOX_H, BOX_GAP = 44, 13, 15          # cue number box in the page margin
LEGEND_FONT, LEGEND_LEAD = 9, 11.5          # legend band text size / line height


def wrap(text, width, font, size):
    words, lines, line = text.split(), [], ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if fitz.get_text_length(candidate, fontname=font, fontsize=size) <= width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def generate(source, output):
    if source.suffix.lower() == ".pcy":
        export = json.loads(source.read_text(encoding="utf-8-sig"))
        encoded = export.get("pdf")
        if not encoded:
            raise ValueError("The PromptDesk export must include the script PDF.")
        pdf_bytes = base64.b64decode(encoded, validate=True)
        cues = export.get("showFile", {}).get("cues") or []
    elif source.suffix.lower() == ".pdf":
        pdf_bytes = source.read_bytes()
        cues = []
    else:
        raise ValueError("The printable script needs a PCY export (with cues) or a PDF.")

    with fitz.open(stream=pdf_bytes, filetype="pdf") as src:
        doc = fitz.open()
        for number, page in enumerate(src):
            W, H = page.rect.width, page.rect.height
            page_cues = []
            for cue in cues:
                pos = cue.get("cuePosition") or {}
                if pos.get("page") != number + 1:
                    continue
                if not all(isinstance(v, (int, float)) for v in (pos.get("x"), pos.get("y"))):
                    continue
                page_cues.append(dict(
                    number=str(cue.get("cueNumber") or ""),
                    notes=str(cue.get("cueNotes") or ""),
                    description=str(cue.get("cueDescription") or ""),
                    x=pos["x"], top=H - pos["y"],  # pcy y is measured from the page bottom
                ))
            page_cues.sort(key=lambda c: c["top"])

            legends = []
            for cue in page_cues:
                label = " · ".join(part for part in (cue["notes"], cue["description"]) if part)
                legends.append((cue["number"], wrap(label, W - 96, "helv", LEGEND_FONT)))

            band = 0
            if legends:
                band = 16 + sum(len(lines) for _, lines in legends) * LEGEND_LEAD + 4

            new = doc.new_page(width=W, height=H + band)
            new.show_pdf_page(fitz.Rect(0, 0, W, H), src, number)

            if not page_cues:
                continue

            # margin boxes, nudged apart when cues land close together
            placed = []
            for cue in page_cues:
                y = min(max(cue["top"], BOX_H + 6), H - BOX_H - 6)
                while any(abs(y - other) < BOX_GAP for other in placed):
                    y += 4
                placed.append(y)
                cue["box_y"] = y

            for cue, y in zip(page_cues, placed):
                box = fitz.Rect(W - BOX_W - 6, y - BOX_H / 2, W - 6, y + BOX_H / 2)
                new.draw_rect(box, color=(0, 0, 0), fill=(0.87, 0.87, 0.87), width=0.6)
                number = cue["number"]
                number_width = fitz.get_text_length(number, fontname="hebo", fontsize=8.5)
                new.insert_text((box.x0 + (box.width - number_width) / 2, y + 3), number,
                                fontname="hebo", fontsize=8.5)
                pin_y = min(max(cue["top"], 6), H - 6)
                new.draw_line((box.x0 - 2, y), (min(cue["x"] + 7, box.x0 - 2), y), width=0.5)
                new.draw_circle((cue["x"], pin_y), 2.4, fill=(0, 0, 0))

            # legend band
            rule_y = H + 6
            if band:
                new.draw_line((36, rule_y), (W - 36, rule_y), width=0.6, color=(0.55, 0.55, 0.55))
            cursor = rule_y + 6
            for index, (num, lines) in enumerate(legends):
                if index:
                    cursor += 3
                new.insert_text((40, cursor + LEGEND_FONT - 1.5), f"Q{num}",
                                 fontname="hebo", fontsize=LEGEND_FONT)
                text_y = cursor
                for line in lines:
                    new.insert_text((72, text_y + LEGEND_FONT - 1.5), line,
                                    fontname="helv", fontsize=LEGEND_FONT)
                    text_y += LEGEND_LEAD
                cursor = text_y

        output.mkdir(parents=True, exist_ok=True)
        dest = output / "script.pdf"
        doc.save(dest, garbage=3, deflate=True)
        print(f"Printable script: {dest} ({len(doc)} pages, {len(cues)} cues)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--filename", default="")
    args = parser.parse_args()
    matches = sorted(path for path in args.folder.iterdir()
                     if path.is_file() and not path.name.startswith("~$")
                     and path.suffix.lower() in {".pdf", ".docx", ".pcy"})
    if args.filename:
        matches = [path for path in matches if path.name == args.filename]
    if len(matches) != 1:
        parser.exit(1, "Mount a folder with exactly one PDF, DOCX or PCY, or set SCRIPT_FILE to the exact filename.\n")
    try:
        generate(matches[0], args.output)
    except (ValueError, KeyError, TypeError, fitz.FileDataError, OSError) as error:
        parser.exit(1, f"Could not generate the printable script: {error}\n")
