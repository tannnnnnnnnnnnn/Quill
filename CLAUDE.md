# Quill

Local meeting recorder → transcriber → Claude processor. Output goes to the
Obsidian vault at `~/Desktop/AI Brain` and to this project's persistent memory.

- Build recorder: `make build` (Swift → `bin/Audiocap.app`; adhoc re-sign resets TCC grant)
- Pipeline: `quill/record.py` (file-based control: `.ready`/`.done`/`audiocap.pid` in the recording dir) → `transcribe.py` (parakeet-mlx, Me/Them from separate tracks) → `process.py` (headless `claude -p` with `prompts/meeting.md`)
- Run pipeline steps manually: `uv run meet transcribe|process <recording-dir>`
- Recordings live in `~/Meetings/`, never in the vault (sync bloat)
- When processing meetings here: transcripts are machine-generated — don't treat odd words as fact; never invent attendees

Headless runs (`claude -p` from `process.py`) execute with cwd = this project, so
they share this project's memory dir. Meeting facts distilled by those runs land
there — treat them as background truth about Tanmay's work.
