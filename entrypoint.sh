#!/bin/sh
set -eu
/opt/prompt-python/bin/python /app/build-speaker-index.py /pdfs "$PAGE_DIRECTORY" --filename "${SCRIPT_FILE:-${PDF_FILE:-}}"
exec node /app/prompt-copy.cjs
