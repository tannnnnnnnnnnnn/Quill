# Quill

Free, local Granola.ai replacement. Records calls (system audio + mic, no bot),
transcribes on-device, then Claude Code turns each meeting into an Obsidian note,
rolling TODO, people notes, and persistent memory.

```
capture (Audiocap.app) ─▶ transcribe (parakeet-mlx) ─▶ claude -p ─▶ vault + memory
```

Nothing leaves your machine. Audio, transcripts, and notes stay in local
folders; the only network calls are the ones Claude Code makes to write your
note.

> **Consent.** Quill records everyone on the call, not only you. Many places
> require every participant's consent before you may do that, and many
> employers require it regardless of the law. Ask first.

## Requirements

- macOS 14.4 or newer, Apple silicon (transcription runs on MLX)
- [Claude Code](https://claude.com/claude-code) on your PATH, signed in — it
  writes the notes, and it needs a paid Anthropic plan. Quill itself is free;
  this part is not.
- Optional: [Obsidian](https://obsidian.md), to read the notes as a vault

## Install

```sh
curl -fsSL https://tannnnnnnnnnnnn.github.io/Quill/install.sh | sh
```

That installs [uv](https://docs.astral.sh/uv/) if you don't have it, downloads
the prebuilt recorder, installs the pipeline into `~/.local/share/quill`, puts
`meet` on your PATH, and then asks where your notes should go.

It finishes by running `meet doctor`, which records four seconds and checks
what came back — because macOS will not tell you whether a permission was
granted, it will just hand you silence.

<details>
<summary>From source instead</summary>

Needs Xcode Command Line Tools (`xcode-select --install`) to build the recorder.

```sh
git clone https://github.com/tannnnnnnnnnnnn/Quill.git
cd Quill
make setup          # uv sync + build Audiocap.app
uv run meet init    # your name, notes folder, recordings folder, login agent
uv run meet doctor  # prove recording works
```
</details>

`meet init` writes `~/.config/quill/config.json` and, if you want the menu bar
app at login, `~/Library/LaunchAgents/com.quill.menubar.plist`. Nothing about
your machine lives in the repo.

The recorder is signed ad hoc, not with an Apple Developer certificate. The
installer works anyway because `curl` does not set the quarantine attribute a
browser download would, so Gatekeeper never sees it.

## Layout

- `capture/audiocap.swift` — Core Audio process-tap recorder → `them.caf` (system) + `me.caf` (mic)
- `quill/` — Python pipeline: `record` `transcribe` `process` `cli` `menubar`
- `prompts/meeting.md` — instructions Claude runs per meeting
- `extension/` — Chrome extension (MV3) that drives Quill from browser calls
- `docs/` — the landing page (served by GitHub Pages)
- Recordings: `<recordings folder>/<date>-<title>/` (audio compressed to m4a after transcription)
- Output: `<notes folder>/Meetings/`, `Meetings/Transcripts/`, `People/`, `TODO.md`
- Claude memory: `~/.claude/projects/<slugified project path>/memory/`

## Permissions

One-time, first recording only: allow **Audiocap** for
**Microphone** and **System Audio Recording**. The system-audio prompt is easy
to dismiss and macOS never re-asks — grant manually:
System Settings → Privacy & Security → Screen & System Audio Recording →
System Audio Recording Only → enable Audiocap
(`open "x-apple.systempreferences:com.apple.preference.security?Privacy_AudioCapture"`).

> Rebuilding Audiocap.app (adhoc signature) resets the grant — re-allow after `make build`.
> Never double-click Audiocap.app — it's a headless helper ("not responding" is cosmetic).
> While recording, macOS shows an orange mic pill in the menu bar which pushes
> icons left — ⌘-drag the 🎙 icon toward the clock once so it never hides under the notch.

## Use

```sh
meet start --title "Standup"   # or click 🎙 in the menu bar
meet stop                      # stop → transcribe → Claude → note ready
meet status
meet doctor                    # check the install; proves recording works
meet enroll                    # 24s voice sample; keeps room audio off your track
meet ask "what did we decide about X?"   # Q&A over all your meetings
meet transcribe <dir>          # re-run stages on an old recording
meet process <dir>
meet menubar                   # run the menu bar app in this terminal
meet serve                     # browser-extension API, if you aren't running the menu bar app
```

**Call detection:** the menu bar app watches for a meeting — native app
(Teams, Zoom, FaceTime, Webex, Slack, Discord) or a Chrome tab on
teams.cloud.microsoft / teams.microsoft.com / meet.google.com / zoom web —
combined with ~6-9s of sustained mic use. Then a card slides in top-right:
"🎙 Call detected — take notes?" One click starts capture (auto-dismisses in
30s; re-arms after the mic is quiet ~30s). Chrome tab checks need the one-time
Automation permission (python → Chrome). Toggle: menu → "Call Detection".

**Your voice vs. the room** (`meet enroll`): the microphone hears everything
near you — a colleague at the next desk, a TV, a phone call across the office —
and the transcript labels all of it **Me**. None of it is quieter than you are,
so loudness cannot separate them; only the voice itself can. `meet enroll`
records 24 seconds of you reading a short passage, builds a local voice profile
in `~/.config/quill/`, and from then on any **Me** line that does not sound like
you is relabelled **Them** rather than dropped — it was said, just not by you.
First run downloads a ~26 MB speaker model. Optional: skip it and nothing
changes.

**Live transcript:** while recording, a floating panel on the right shows
Me/Them lines within a few seconds of speech (12s tail window re-transcribed
every 4s, sentence-settled, deduped). Toggle: menu → "Live Transcript".

<a id="browser-extension"></a>

**Browser extension:** the menu bar app serves the extension API on
`127.0.0.1:8787` by itself, so if Quill is in your menu bar the extension
works. `meet serve` is only for running it without the menu bar app.

To add the extension: install [Quill from the Chrome Web Store](https://chromewebstore.google.com/detail/quill/mckdigacdodbocengchaeonaamobcnil).
To run a development copy instead, open `chrome://extensions`, turn on
**Developer mode**, click **Load unpacked**, and choose the `extension/`
folder inside your Quill install (`~/.local/share/quill/extension` if you
used the installer).

**Meeting index:** every processed call adds a one-line summary to
`Meetings/INDEX.md` in your notes folder — a glanceable list of which call was
about what.

**Ask Quill** (menu bar → Ask Quill…): answers questions from your notes,
transcripts, and TODO — cited by meeting, read-only; every Q&A is logged to
`Questions.md` in the vault. **Open TODO** jumps to the rolling task list in
Obsidian — that file is the single source of truth for tasks.

**Dashboard** (menu bar → Open Dashboard, or `meet dashboard`): meetings with
summaries, ask-anything, and a live todo list — reads/writes the vault directly.
Night mode toggle in the header. Per-meeting **↻ Enhance** re-transcribes old
recordings with the current models; **✕** deletes a meeting everywhere.

Menu bar: `uv run python -m quill.menubar`. To start it at login, run
`meet init` (which writes the agent) and then:

```sh
launchctl load ~/Library/LaunchAgents/com.quill.menubar.plist
```

## Config

`~/.config/quill/config.json` holds your settings — `user_name`, `vault`, and
`data`. Re-run `meet init` to change them, or edit the file directly.

Everything else lives in `quill/config.py`: models, `KEEP_AUDIO`
(`m4a`/`raw`/`delete`), chunk size, max hours.

## Troubleshooting

- `them` track empty → system-audio permission missing (see Setup) — or nobody spoke.
- Transcription slow first run → 600 MB model download, cached afterwards.
- Room audio still labelled **Me** → run `meet enroll`, then `meet transcribe <dir>` to re-score.
- Claude step fails → read `claude.log` inside the recording dir, re-run with `meet process <dir>`.
- Recorder stuck → `meet status`; stale state clears itself; worst case `pkill audiocap`.
- Notes land in the wrong place → check `~/.config/quill/config.json`, or re-run `meet init`.

## License

MIT — see [LICENSE](LICENSE).
