Put your show script in this folder. One of:

- a PromptDesk `.pcy` export (contains the script PDF plus cue pins),
- a PDF exported from Word,
- a DOCX (converted inside the container with LibreOffice).

If the folder holds more than one script, set `SCRIPT_FILE` in `.env`
to the exact filename and run `docker compose up -d` to apply it.

Scripts stay on your machine: this folder is mounted read-only and is
git-ignored, so nothing you put here is published with the app.
