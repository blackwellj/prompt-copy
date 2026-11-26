# Prompt Copy

A web-based prompt copy for theatre shows: the script becomes a live prompt
desk that the operator drives and cast and crew follow from their own
devices, over WiFi or the internet.

1. Put one PDF, DOCX or PromptDesk `.pcy` export into the included `pdfs` folder.
2. Run `docker compose up --build` from this folder.
3. Open http://localhost:3000/control for Control and http://localhost:3000/ for Viewer. From another device use the Docker host's IP address instead of localhost.

To change shows, swap the script file and run `docker compose restart`. The app reads the folder whenever it starts. If the folder contains several scripts, set `SCRIPT_FILE` to the exact filename in a Compose `.env` file and run `docker compose up -d` to apply it.

Text PDFs with uppercase `NAME:` speaker labels get speech highlights. PDFs without detectable labels, including scans without a text layer, use page by page navigation. Recognised act and interval headings switch the timers. Other PDFs time the script under Act 1. Restarting the container resets the live position and timers.

The first Space press or tap on Start Show starts timing and holds the opening position. Subsequent presses advance. Shift+Space goes back. Press I on the Viewer to invert the PDF.

Phase boundaries — Start Show, Start Interval, Start Act 2 and End Show —
need a second confirming press on the amber button before anything happens,
so a bumped button cannot skip a phase or its timer. Pressing Back, Restart
or waiting six seconds cancels the confirmation.

DOCX files are converted inside the container with LibreOffice. Page breaks and fonts can differ from Word. Use a PDF exported from Word if you need the exact printed layout. The existing `PDF_FILE` setting is still accepted when `SCRIPT_FILE` is unset.

Add `?invert=1` to the Viewer URL for inverted colours or `?invert=0` for normal colours. These set the initial view without changing the saved preference.

Before the show, open Control and wait for **Offline ready**. Keep that tab open.
The script, navigation and timers keep working during a network interruption.
Viewer screens catch up when Control can reach the same server again.
Reloading the page or closing the tab while offline loses the in-memory copy.

Open `/timings` to see completed shows with their date, UK start and finish times,
and the Act 1, Interval, Act 2 and Total durations, with an average row across
runs and per-act green or amber deltas versus the average once two runs exist. Advance to End of show to save
the run. If offline at the finish, keep Control open until it reconnects.
The Docker volume keeps records across rebuilds and restarts.

Open a character name as a URL, for example `/KING` or `/QUEEN`.
Links match the detected speaker label regardless of case. Use `%20` for
spaces in a name. The full script is scrollable with only that role's
speech highlighted. Character views have no timers and do not join live sync.

On Control, use the large Back and Next buttons at the bottom in portrait or landscape. Touch scrolling on the script does not advance the cue.

For PromptDesk cues, put a `.pcy` export containing the embedded PDF in
`pdfs` and select it with `SCRIPT_FILE` if other scripts are present.
All views use that export's PDF so cue positions match its pagination.
Open `/stage` for the live viewer with right margin cue labels connected to their saved PromptDesk anchors. Full descriptions are always visible in the margin. The stage bar also shows the next cue and how far ahead it is — from "just ahead" to a page count. Stage opens inverted by default. Add `?invert=0`
for normal colours. Scroll to
browse independently and tap **Resync** to jump back and follow live.

Open `/script.pdf` for a printable copy of the script with every cue: a numbered
box in the margin level with its line, a leader to the exact pin position, and a
cue legend under each page. Vector-quality, black on white for clean printing.

Screens stay awake while a view is open, where the browser supports wake locks.

For iPad Home Screen use, open the view you want in Safari before adding it.
If an existing shortcut still shows the old icon after updating, remove the
shortcut and add it again. Stage cue descriptions are visible on load.

## Optional camera on Stage and Viewer

Set `CAMERA_URL` in `.env` to a browser-accessible feed URL. Use
`CAMERA_MODE=image` for an MJPEG feed, or `CAMERA_MODE=embed` for an
embeddable player page. Stage and Viewer show a camera toggle when configured.
Camera starts hidden. Append `?camera=1` (or `&camera=1` after other options)
to open it automatically in OBS. Hiding the camera stops loading the feed.

The viewing device connects directly to the feed. The server does not proxy it.
A local-only camera is reachable only on the LAN or an appropriate VPN.
If Prompt Copy is served over HTTPS, use an HTTPS feed or player. An RTSP
URL needs a separate browser-compatible player or relay on the camera network.
The configured URL is visible to browsers loading the app.

The active show position and timers are saved in the existing Docker volume
when a cue or timer changes. The same script resumes after a server restart.
A running timer includes the downtime. If Control had unsent changes before
Safari reloaded, choose **Resume Show** to restore them, or **Use server
position** to discard the local copy. A reload still needs a connection to
load the app and script again.
