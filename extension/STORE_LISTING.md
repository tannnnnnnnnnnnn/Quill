# Chrome Web Store listing

Copy for the developer dashboard. Build the upload zip with `make extension-zip`
(writes `dist/quill-extension-<version>.zip`).

Submission needs a Chrome Web Store developer account — a one-time $5 fee — and
takes a few days of review.

Hold off submitting. Two reasons:

1. Zoom, Teams, and Webex detection has not been measured on a real call, and
   the listing claims all four platforms.
2. The extension cannot work without the Quill Mac app, and that app installs
   from source — Xcode tools, uv, `make setup`. Store traffic is one-click
   installers, so most people who find this listing would install it, see
   "Quill isn't running", and never come back. Ship the extension as a
   `Load unpacked` step in the repo README until the Mac app has a real
   installer.

## Fields

**Name:** Quill

**Summary** (132 char max):
Companion for the Quill Mac app (required). Detects your browser calls and
drives the recorder running on your own machine.

**Category:** Productivity / Workflow & Planning

**Language:** English

**Privacy policy URL:** https://tannnnnnnnnnnnn.github.io/Quill/privacy.html

**Homepage URL:** https://tannnnnnnnnnnnn.github.io/Quill/

**Support URL:** https://github.com/tannnnnnnnnnnnn/Quill/issues

## Description

REQUIRES THE QUILL MAC APP. This extension is a remote control — on its own it
does nothing at all. Install Quill first from
github.com/tannnnnnnnnnnnn/Quill (macOS on Apple silicon, built from source).

With the app running, Quill notices when you join a call in your browser,
offers to take notes, and hands the job to the app on your Mac. Audio is
captured and transcribed locally; the extension itself never touches your
microphone.

While you talk, a panel shows the live two-sided transcript. When you hang up,
a summary with action items is waiting in your notes folder.

What makes it different:
• Local by default. No Quill account, no server, no telemetry. The extension
  speaks only to 127.0.0.1 on your own machine.
• No bot joins your meeting. Nobody sees "Quill's Notetaker" in the participant
  list.
• Free and open source, MIT licensed. Read every line at
  github.com/tannnnnnnnnnnnn/Quill

Requires the Quill app on macOS. Setup instructions are in the repository.

Quill records everyone on a call, not only you. Many places require their
consent first — please ask.

## Single-purpose statement

Quill's single purpose is to detect that the user is in a browser meeting and
relay start/stop recording commands, plus live transcript display, to the
user's own locally installed Quill application.

## Permission justifications

**storage** — Persists the user's own settings: the local server address, which
meeting sites are enabled, and whether Quill may prompt automatically. No
meeting content is stored.

**tabs** — The background service worker must follow a meeting tab through
updates, activation, and removal so a recording stays bound to the tab that
started it and stops when that tab closes. `activeTab` is insufficient: a call
frequently continues in a tab the user is not currently viewing, and detection
must keep working there.

**Host access to meet.google.com, \*.zoom.us/wc/\*, teams.microsoft.com,
teams.cloud.microsoft, \*.webex.com** — These are the meeting surfaces Quill
supports. The content script inspects only URL shape and whether in-call
controls are present, then renders Quill's own panel. It does not read chat,
captions, participant names, or any other page content.

**Host access to http://127.0.0.1:8787/\*** — The extension's only network
destination. This is the local Quill application on the user's own computer,
which owns audio capture and transcription. MV3 content scripts inherit page
CORS and cannot reach loopback, so the service worker performs all of this I/O.

**Remote code:** none. All scripts are packaged in the extension.

## Assets checklist

- [x] 128×128 store icon — `icons/icon128.png`
- [ ] At least one 1280×800 or 640×400 screenshot. Suggested set:
      1. The "Take notes?" card on a live Google Meet
      2. The live transcript panel mid-call
      3. The toolbar popup showing a recording in progress
      4. The options page
- [ ] Optional 440×280 small promo tile
