"""Run headless Claude Code over a transcript: meeting note, TODO merge,
People notes, memory distill. Runs with cwd = this project so Claude sees
the same persistent memory directory."""

import datetime as dt
import json
import shutil
import subprocess
from pathlib import Path

from . import config


def _claude() -> str:
    # menubar/launchd runs get a minimal PATH, so check known installs too
    nvm = sorted(Path.home().glob(".nvm/versions/node/*/bin/claude"), reverse=True)
    for cand in ([shutil.which("claude")]
                 + [str(p) for p in nvm]
                 + [str(Path.home() / ".claude" / "local" / "claude")]):
        if cand and Path(cand).exists():
            return cand
    raise SystemExit("claude CLI not found on PATH")


def _notify_sender() -> str | None:
    """`display notification` is attributed to whichever app ran the script, and
    clicking it activates that app. Plain `osascript` means Script Editor opens,
    which is confusing and useless. Wrapping the call in `tell application X`
    hands the notification — and the click — to X instead. Obsidian is the right
    landing place, since that is where the note is; Finder is the fallback."""
    for app, path in (("Obsidian", "/Applications/Obsidian.app"),
                      ("Finder", "/System/Library/CoreServices/Finder.app")):
        if Path(path).exists():
            return app
    return None


def _applescript_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def notify(title: str, msg: str) -> None:
    script = (f"display notification {_applescript_str(msg)} "
              f"with title {_applescript_str(title)}")
    sender = _notify_sender()
    if sender:
        script = f"tell application {_applescript_str(sender)} to {script}"
    subprocess.run(["osascript", "-e", script], capture_output=True)


def ask(question: str) -> str:
    """Answer a question from the meeting records via read-only headless Claude.
    Appends the Q&A to the vault's Questions.md log."""
    prompt = (config.PROJECT / "prompts" / "ask.md").read_text()
    for k, v in {
        "{{QUESTION}}": question,
        "{{NOTES_DIR}}": str(config.NOTES_DIR),
        "{{TRANSCRIPTS_DIR}}": str(config.TRANSCRIPTS_DIR),
        "{{TODO}}": str(config.TODO),
        "{{PEOPLE_DIR}}": str(config.PEOPLE_DIR),
    }.items():
        prompt = prompt.replace(k, v)
    r = subprocess.run(
        [_claude(), "-p", "--allowedTools", "Read,Glob,Grep"],
        input=prompt, capture_output=True, text=True,
        cwd=config.PROJECT, timeout=300,
    )
    answer = r.stdout.strip() or f"(no answer — claude exited {r.returncode})"
    try:
        qlog = config.VAULT / "Questions.md"
        stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        header = "" if qlog.exists() else "# Questions\n"
        with open(qlog, "a") as f:
            f.write(f"{header}\n## {stamp} — {question}\n\n{answer}\n")
    except Exception:
        pass
    return answer


def run(d: str | Path, progress=print) -> str | None:
    d = Path(d)
    transcript = d / "transcript.md"
    if not transcript.exists():
        raise SystemExit(f"no transcript in {d} — run `meet transcribe {d}` first")

    meta = {}
    if (d / "meta.json").exists():
        meta = json.loads((d / "meta.json").read_text())
    started = meta.get("started") or dt.datetime.now().isoformat(timespec="seconds")
    date = started[:10]

    tokens = {
        "{{TRANSCRIPT_PATH}}": str(transcript),
        "{{TRANSCRIPT_NAME}}": d.name,
        "{{DATE}}": date,
        "{{DATETIME}}": started,
        "{{DURATION_MIN}}": str(meta.get("duration_minutes", "?")),
        "{{TITLE_HINT}}": meta.get("title", ""),
        "{{NOTES_DIR}}": str(config.NOTES_DIR),
        "{{TODO}}": str(config.TODO),
        "{{PEOPLE_DIR}}": str(config.PEOPLE_DIR),
        "{{MEMORY_DIR}}": str(config.MEMORY_DIR),
    }
    prompt = config.PROMPT.read_text()
    for k, v in tokens.items():
        prompt = prompt.replace(k, v)

    for p in (config.NOTES_DIR, config.PEOPLE_DIR):
        p.mkdir(parents=True, exist_ok=True)
    if not config.TODO.exists():
        config.TODO.write_text("# TODO\n\n## Inbox\n")

    progress("processing with Claude (1-3 min)...")
    r = subprocess.run(
        [_claude(), "-p",
         "--allowedTools", "Read,Write,Edit,Glob,Grep"],
        input=prompt,
        capture_output=True,
        text=True,
        cwd=config.PROJECT,
        timeout=1200,
    )
    (d / "claude.log").write_text(r.stdout + "\n--- stderr ---\n" + r.stderr)

    note = None
    for line in reversed(r.stdout.splitlines()):
        if line.startswith("NOTE: "):
            note = line[6:].strip()
            break
    if r.returncode != 0:
        progress(f"claude exited {r.returncode} — see {d / 'claude.log'}")
        return None
    progress(f"note: {note or 'not reported — see claude.log'}")
    return note
