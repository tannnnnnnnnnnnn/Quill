# Quill

Free, local Granola.ai replacement. Records calls (system audio + mic, no bot),
transcribes on-device, then Claude Code turns each meeting into an Obsidian note,
rolling TODO, people notes, and persistent memory.

```
capture (Audiocap.app) ─▶ transcribe (parakeet-mlx) ─▶ claude -p ─▶ AI Brain vault + memory
```

## Layout

- `capture/audiocap.swift` — Core Audio process-tap recorder → `them.caf` (system) + `me.caf` (mic)
- `quill/` — Python pipeline: `record` `transcribe` `process` `cli` `menubar`
- `prompts/meeting.md` — instructions Claude runs per meeting
- Recordings: `~/Meetings/<date>-<title>/` (audio compressed to m4a after transcription)
- Output: `~/Desktop/AI Brain/Meetings/`, `Meetings/Transcripts/`, `People/`, `TODO.md`
- Claude memory: `~/.claude/projects/-Users-tanmayshah-Desktop-Custom-Granola/memory/`

## Setup (already done by Claude)

```sh
make setup          # uv sync + build Audiocap.app
```

One-time permissions, first recording only: allow **Audiocap** for
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
meet ask "what did we decide about X?"   # Q&A over all your meetings
meet transcribe <dir>          # re-run stages on an old recording
meet process <dir>
```

**Call detection:** the menu bar app watches for a meeting — native app
(Teams, Zoom, FaceTime, Webex, Slack, Discord) or a Chrome tab on
teams.cloud.microsoft / teams.microsoft.com / meet.google.com / zoom web —
combined with ~6-9s of sustained mic use. Then a card slides in top-right:
"🎙 Call detected — take notes?" One click starts capture (auto-dismisses in
30s; re-arms after the mic is quiet ~30s). Chrome tab checks need the one-time
Automation permission (python → Chrome). Toggle: menu → "Call Detection".

**Live transcript:** while recording, a floating panel on the right shows
Me/Them lines within a few seconds of speech (12s tail window re-transcribed
every 4s, sentence-settled, deduped). Toggle: menu → "Live Transcript".

**Meeting index:** every processed call adds a one-line summary to
`AI Brain/Meetings/INDEX.md` — glanceable list of which call was about what.

**Ask Quill** (menu bar → Ask Quill…): answers questions from your notes,
transcripts, and TODO — cited by meeting, read-only; every Q&A is logged to
`Questions.md` in the vault. **Open TODO** jumps to the rolling task list in
Obsidian — that file is the single source of truth for tasks.

**Dashboard** (menu bar → Open Dashboard, or `meet dashboard`): meetings with
summaries, ask-anything, and a live todo list — reads/writes the vault directly.
Night mode toggle in the header. Per-meeting **↻ Enhance** re-transcribes old
recordings with the current models; **✕** deletes a meeting everywhere.

Menu bar: `uv run python -m quill.menubar`. Auto-start at login:

```sh
cp launchd/com.tanmay.quill-menubar.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.tanmay.quill-menubar.plist
```

## Config

Edit `quill/config.py`: vault path, model, `KEEP_AUDIO` (`m4a`/`raw`/`delete`), max hours.

## Troubleshooting

- `them` track empty → system-audio permission missing (see Setup) — or nobody spoke.
- Transcription slow first run → 600 MB model download, cached afterwards.
- Claude step fails → read `claude.log` inside the recording dir, re-run with `meet process <dir>`.
- Recorder stuck → `meet status`; stale state clears itself; worst case `pkill audiocap`.

Recording calls may require participant consent in your region/company — check before using on real calls.
