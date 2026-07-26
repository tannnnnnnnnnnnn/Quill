# Quill Chrome extension

Manifest V3 companion for the local Quill macOS meeting scribe. It detects
supported browser calls without AppleScript, asks whether to take notes, starts
and stops the local recorder, and displays the live two-sided transcript in an
isolated Shadow DOM panel.

## Load unpacked

1. Start the Quill menu-bar app and confirm its HTTP server is listening at
   `http://127.0.0.1:8787`.
2. Open `chrome://extensions`.
3. Enable **Developer mode**.
4. Click **Load unpacked** and choose this `extension/` directory.
5. Optionally pin Quill from Chrome's Extensions menu.

Use **Extension settings** in the toolbar popup to change the local server URL,
enable or disable individual meeting platforms, or disable automatic prompts.

## Supported browser meetings

- Google Meet: `meet.google.com`
- Zoom web client: `*.zoom.us/wc/*`
- Microsoft Teams: `teams.microsoft.com` and `teams.cloud.microsoft`
- Webex: `*.webex.com`

The service worker follows tab updates, removals, and activation. The content
script confirms ambiguous meeting URLs using only URL shape and the presence of
active page media elements. It does not read chat, captions, participant names,
or meeting content.

## Permission rationale

- `storage`: stores the server URL, per-site enable switches, and auto-prompt
  preference in `chrome.storage.sync`.
- `tabs`: lets the service worker follow meeting-tab lifecycle and pass the
  tab URL, title, and numeric tab ID required by the detection API. `activeTab`
  would not cover background updates in non-active meeting tabs.
- `https://meet.google.com/*`: detects and renders Quill on Google Meet.
- `https://*.zoom.us/wc/*`: detects and renders Quill in the Zoom web client.
- `https://teams.microsoft.com/*` and
  `https://teams.cloud.microsoft/*`: detect and render Quill in Teams.
- `https://*.webex.com/*`: detects and renders Quill in Webex.
- `http://127.0.0.1:8787/*`: calls the local Quill HTTP API. No internet host,
  `<all_urls>`, scripting, microphone, or page-content permission is requested.

## Local API contract

All requests and responses are JSON. The server supplies permissive CORS
headers and handles `OPTIONS` preflight.

### Health

```http
GET /health
```

```json
{"ok":true,"version":"0.1.0","state":"idle"}
```

`state` is `"idle"`, `"recording"`, or `"processing"`.

### Meeting detected

```http
POST /meeting/detected
Content-Type: application/json
```

```json
{"platform":"google-meet","title":"Weekly sync","url":"https://meet.google.com/abc-defg-hij","tabId":42}
```

```json
{"prompt":true}
```

`prompt` is `false` when Quill is already recording or that meeting was ignored
in that tab. A different meeting URL in the same tab is evaluated independently.

### Ignore meeting

```http
POST /meeting/ignore
Content-Type: application/json
```

```json
{"tabId":42,"url":"https://meet.google.com/abc-defg-hij","automatic":false}
```

```json
{"ok":true}
```

`automatic` is `true` for the call card's 30-second timeout. Explicit ignores
are retained for six hours; automatic timeouts use a five-minute cooldown.

### Tab closed or navigated

```http
POST /meeting/tab-clear
Content-Type: application/json
```

```json
{"tabId":42}
```

Clears all meeting-ignore state for the tab. The service worker sends this when
the tab closes or navigates.

### Start recording

```http
POST /recording/start
Content-Type: application/json
```

```json
{"platform":"google-meet","title":"Weekly sync","url":"https://meet.google.com/abc-defg-hij"}
```

```json
{"ok":true,"recordingId":"recording-id","startedAt":1753520400}
```

`startedAt` is epoch seconds.

### Stop recording

```http
POST /recording/stop
Content-Type: application/json
```

```json
{"recordingId":"recording-id"}
```

```json
{"ok":true,"state":"processing"}
```

### Recording status

```http
GET /recording/status
```

```json
{"state":"recording","recordingId":"recording-id","startedAt":1753520400,"elapsed":74}
```

### Transcript

```http
GET /transcript?since=12
```

```json
{
  "cursor": 14,
  "lines": [
    {"i":13,"speaker":"them","text":"Can we move the pilot?","t":72.4},
    {"i":14,"speaker":"me","text":"Yes, I'll update the plan.","t":75.1}
  ]
}
```

`speaker` is `"me"` or `"them"`. The panel polls about every 1.5 seconds only
while it is open. Failures back off to a maximum 12-second interval; the panel
shows an offline state and reconnects without uncaught errors or console spam.

## Static surface harness

The harness uses a deterministic mock implementing the same client methods and
does not need Chrome APIs or a running Quill server:

```sh
cd extension
python3 -m http.server 8000
```

Open `http://127.0.0.1:8000/harness/`. **Show detected card** tests the real
buttons. **Run full transition** drives:

`idle → detected card → loading panel → live transcript lines → closed`

## Still stubbed or environment-dependent

- The local HTTP server itself is implemented by the separate Quill app task;
  this directory contains only its client.
- Final validation against real Google Meet, Zoom, Teams, and Webex calls
  requires live calls in Chrome. The shipped detector deliberately uses
  lightweight URL/media-state heuristics rather than site-private DOM content,
  so platform navigation changes may require heuristic tuning.
- Real audio capture, transcription readiness, transcript text, and processing
  are supplied by the Quill app and cannot be exercised by the static harness.
