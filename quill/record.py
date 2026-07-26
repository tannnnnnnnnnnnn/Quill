"""Start/stop the Audiocap.app recorder. Control is file-based:
audiocap writes <dir>/audiocap.pid and <dir>/.ready on start, <dir>/.done on exit."""

import datetime as dt
import fcntl
import json
import os
import re
import signal
import subprocess
import time
from contextlib import contextmanager

from . import config


@contextmanager
def _control_lock():
    """Serialize recorder transitions across CLI, menu bar, and HTTP server."""
    config.DATA.mkdir(parents=True, exist_ok=True)
    with open(config.STATE.with_suffix(".lock"), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s[:40] or "meeting"


def current() -> dict | None:
    """Return active recording state, clearing stale state from crashes."""
    if not config.STATE.exists():
        return None
    st = json.loads(config.STATE.read_text())
    try:
        os.kill(st["pid"], 0)
        return st
    except (ProcessLookupError, PermissionError):
        config.STATE.unlink(missing_ok=True)
        return None


def start(title: str | None = None, max_hours: float = config.MAX_HOURS) -> str:
    with _control_lock():
        if current():
            raise SystemExit("already recording — run `meet stop` first")
        ts = dt.datetime.now()
        d = config.DATA / f"{ts:%Y-%m-%d-%H%M}-{_slug(title or 'meeting')}"
        d.mkdir(parents=True, exist_ok=True)
        for f in (".ready", ".done", "audiocap.pid"):
            (d / f).unlink(missing_ok=True)

        subprocess.run(
            ["open", "-na", str(config.APP), "--args",
             str(d), str(int(max_hours * 3600))],
            check=True,
        )

        # First-ever run blocks on permission prompts, so wait generously.
        for _ in range(180):
            if (d / ".ready").exists():
                break
            if (d / ".done").exists():
                raise SystemExit("recorder exited immediately — check permissions "
                                 "(System Settings > Privacy & Security)")
            time.sleep(0.5)
        else:
            raise SystemExit(
                "recorder never became ready — is a permission prompt waiting on screen?")

        pid = int((d / "audiocap.pid").read_text().strip())
        config.STATE.write_text(json.dumps({
            "pid": pid,
            "dir": str(d),
            "started": ts.isoformat(timespec="seconds"),
            "title": title or "",
        }))
        return str(d)


def stop() -> dict:
    with _control_lock():
        st = current()
        if not st:
            raise SystemExit("not recording")
        d = st["dir"]
        try:
            os.kill(st["pid"], signal.SIGINT)
        except ProcessLookupError:
            pass
        for _ in range(60):
            if os.path.exists(os.path.join(d, ".done")):
                break
            time.sleep(0.5)
        config.STATE.unlink(missing_ok=True)

        ended = dt.datetime.now()
        started = dt.datetime.fromisoformat(st["started"])
        meta = {
            "title": st["title"],
            "started": st["started"],
            "ended": ended.isoformat(timespec="seconds"),
            "duration_minutes": round((ended - started).total_seconds() / 60, 1),
        }
        with open(os.path.join(d, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)
        return {**st, **meta}
