"""Remove every trace of a processed meeting: vault note, transcript copy,
TODO/INDEX lines that reference it, and the recording directory."""

import shutil
from pathlib import Path

from . import config


def _strip_lines(file: Path, needle: str) -> None:
    if not file.exists():
        return
    lines = [l for l in file.read_text().splitlines() if needle not in l]
    file.write_text("\n".join(lines) + "\n")


def delete_meeting(rec_dir: str, note_path: str | None, keep_audio: bool = False) -> None:
    """keep_audio=True removes only the derived outputs (note, transcript,
    TODO/INDEX lines) so the meeting can be re-processed from its audio."""
    rec = Path(rec_dir)
    if note_path:
        note = Path(note_path)
        needle = f"[[{note.stem}]]"
        note.unlink(missing_ok=True)
        _strip_lines(config.TODO, needle)
        _strip_lines(config.NOTES_DIR / "INDEX.md", needle)
    (config.TRANSCRIPTS_DIR / f"{rec.name}.md").unlink(missing_ok=True)
    if not keep_audio:
        shutil.rmtree(rec, ignore_errors=True)
