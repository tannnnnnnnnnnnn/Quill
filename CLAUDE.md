# Quill

Local meeting recorder → transcriber → Claude processor. Output goes to the
notes folder and recordings folder the user chose during `meet init`, both read
from `~/.config/quill/config.json` — never assume a path, read `quill/config.py`.

- Build recorder: `make build` (Swift → `bin/Audiocap.app`; adhoc re-sign resets TCC grant)
- Pipeline: `quill/record.py` (file-based control: `.ready`/`.done`/`audiocap.pid` in the recording dir) → `transcribe.py` (parakeet-mlx, Me/Them from separate tracks) → `process.py` (headless `claude -p` with `prompts/meeting.md`)
- Run pipeline steps manually: `uv run meet transcribe|process <recording-dir>`
- Recordings live in the recordings folder, never in the notes folder (sync bloat)
- Prompts in `prompts/` are templates: `{{USER}}`, `{{NOTES_DIR}}`, `{{TODO}}` and
  the rest are substituted in `process.py`. Never hardcode a name or a path into
  one — this repo is used by people other than its author.
- When processing meetings here: transcripts are machine-generated — don't treat
  odd words as fact; never invent attendees

Headless runs (`claude -p` from `process.py`) execute with cwd = this project,
so they share this project's memory dir. Meeting facts distilled by those runs
land there — treat them as background truth about whoever is running Quill.
