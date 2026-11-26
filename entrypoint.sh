#!/bin/sh
set -eu
/opt/prompt-python/bin/python /app/build-speaker-index.py /pdfs "$PAGE_DIRECTORY" --filename "${SCRIPT_FILE:-${PDF_FILE:-}}"
/opt/prompt-python/bin/python /app/generate-script-pdf.py /pdfs "$PAGE_DIRECTORY" --filename "${SCRIPT_FILE:-${PDF_FILE:-}}" || echo "Printable script not generated."
exec node /app/prompt-copy.cjs
