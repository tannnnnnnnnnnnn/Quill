import json
import os
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
APP = PROJECT / "bin" / "Audiocap.app"
BIN_DIR = PROJECT / "bin"
PROMPT = PROJECT / "prompts" / "meeting.md"

# User settings: ~/.config/quill/config.json, or $QUILL_CONFIG. Written by
# `meet init`. Keys: vault, data, user_name. Missing file = defaults below.
SETTINGS_PATH = Path(
    os.environ.get("QUILL_CONFIG", Path.home() / ".config" / "quill" / "config.json")
)
try:
    _settings = json.loads(SETTINGS_PATH.read_text())
except (OSError, ValueError):
    _settings = {}

# Obsidian vault
VAULT = Path(_settings.get("vault", Path.home() / "Desktop" / "AI Brain")).expanduser()
NOTES_DIR = VAULT / "Meetings"
TRANSCRIPTS_DIR = VAULT / "Meetings" / "Transcripts"
PEOPLE_DIR = VAULT / "People"
TODO = VAULT / "TODO.md"

# Claude Code project memory for this project dir
MEMORY_DIR = (
    Path.home()
    / ".claude"
    / "projects"
    / re.sub(r"[^A-Za-z0-9]", "-", str(PROJECT))
    / "memory"
)

# Recording data (audio stays out of the vault)
DATA = Path(_settings.get("data", Path.home() / "Meetings")).expanduser()
STATE = DATA / ".recording.json"

# vocative guard: lines addressing this name are Them
USER_NAME = _settings.get("user_name", "")

MODEL = "mlx-community/parakeet-tdt-0.6b-v2"            # live panel (speed)
LIVE_MODE = "window"       # "window" = proven accurate; "stream" = experimental draft-tail mode
# denoise + loudness-normalize the mic track before ASR (validated: fixes
# noise-induced ASR errors, no artifacts on clean speech, ~40x realtime)
MIC_FILTER = "highpass=f=80,afftdn=nr=12:nf=-30,loudnorm=I=-19:LRA=7:TP=-2"
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"  # final transcript (accuracy)
CHUNK_SECONDS = 120.0
MAX_HOURS = 4
# after transcription: "m4a" = compress, "raw" = keep caf, "delete" = remove audio
KEEP_AUDIO = "m4a"
