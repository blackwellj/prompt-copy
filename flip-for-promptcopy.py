"""Convert a Stage Copy PCY (cue y measured from page TOP) to Prompt Copy's
convention (cue y measured from page BOTTOM) using the embedded PDF page heights."""
import base64
import json
import sys
from pathlib import Path

import fitz

src, dst = sys.argv[1], sys.argv[2]
doc = json.loads(Path(src).read_text(encoding="utf-8-sig"))

pdf_bytes = base64.b64decode(doc["pdf"], validate=True)
heights = {}
with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
    for number, page in enumerate(pdf, start=1):
        heights[number] = page.rect.height

cues = doc.get("showFile", {}).get("cues") or []
flipped = 0
for cue in cues:
    pos = cue.get("cuePosition") or {}
    page = pos.get("page")
    if page not in heights:
        continue
    try:
        y = float(pos["y"])
    except (KeyError, TypeError, ValueError):
        continue
    pos["y"] = heights[page] - y
    flipped += 1

Path(dst).parent.mkdir(parents=True, exist_ok=True)
Path(dst).write_text(json.dumps(doc), encoding="utf-8")
print(json.dumps({"flipped": flipped, "pages": len(heights)}))
