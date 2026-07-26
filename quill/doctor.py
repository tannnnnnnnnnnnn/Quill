"""`meet doctor` — prove Quill can actually record, and say what to fix if not.

macOS will not tell you whether a permission was granted; the TCC database
needs Full Disk Access to read, and asking politely gets you nothing. What it
will do is hand you silence. So this records four seconds while playing a sound
through the speakers, and looks at what arrived:

  mic track silent    → Microphone was denied
  system track silent → System Audio Recording was denied

That is the same test that catches the failure people actually hit, which is
not a missing app but a permission dialog dismissed months ago and never shown
again. The system-audio prompt in particular is easy to miss, and macOS never
re-asks.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from . import config

# the RMS below which a track is silence rather than quiet audio; the loud-ish
# floor is deliberate, since a denied tap yields exact zeros
FLOOR = 20.0
TEST_SOUND = Path("/System/Library/Sounds/Ping.aiff")

PANES = {
    "mic": ("Microphone",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"),
    "sys": ("Screen & System Audio Recording → System Audio Recording Only",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_AudioCapture"),
}


def _rms(caf: Path) -> float:
    from . import bleedguard, transcribe
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "probe.wav"
        if transcribe._to_wav16(caf, wav, mic=False) <= 0:
            return 0.0
        x, _ = bleedguard.load_wav(wav)
        return bleedguard._rms(x)


def _checks() -> list[tuple[bool, str, str]]:
    """(ok, label, remedy) for everything that does not need to record."""
    out = []

    out.append((config.SETTINGS_PATH.exists(), "settings",
                f"run `meet init` — no {config.SETTINGS_PATH}"))
    out.append((config.APP.exists(), "recorder",
                f"run `make build` — no {config.APP}"))
    out.append((config.VAULT.exists(), "notes folder",
                f"run `meet init` — no {config.VAULT}"))

    try:
        from . import transcribe
        transcribe._ffmpeg()
        out.append((True, "ffmpeg", ""))
    except Exception as e:
        out.append((False, "ffmpeg", str(e)))

    try:
        from . import process
        process._claude()
        out.append((True, "claude", ""))
    except SystemExit:
        out.append((False, "claude",
                    "install Claude Code and sign in — https://claude.com/claude-code"))

    return out


def run(progress=print) -> int:
    """Print a report. Returns the number of problems found."""
    results = _checks()
    for ok, label, remedy in results:
        progress(f"{'ok  ' if ok else 'FAIL'}  {label}" + ("" if ok else f" — {remedy}"))

    problems = [r for r in results if not r[0]]
    if any(label == "recorder" for ok, label, _ in results if not ok):
        progress("\nskipping the recording test — there is no recorder to test.")
        return len(problems)

    progress("\nrecording 4s to check permissions (you will hear a ping)...")
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "doctor"
        player = None
        if TEST_SOUND.exists() and shutil.which("afplay"):
            # a sound the tap should hear; looped so it spans the whole capture
            player = subprocess.Popen(
                ["/bin/sh", "-c",
                 f"for i in 1 2 3 4 5 6; do afplay {TEST_SOUND}; done"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            from . import record
            me, them = record.capture(4, d, progress)
        except SystemExit as e:
            progress(f"FAIL  recording — {e}")
            return len(problems) + 1
        finally:
            if player:
                player.terminate()

        mic_rms = _rms(me)
        sys_rms = _rms(them) if them.exists() else 0.0

    for key, rms in (("mic", mic_rms), ("sys", sys_rms)):
        label, url = PANES[key]
        if rms >= FLOOR:
            progress(f"ok    {key} track (level {rms:.0f})")
        else:
            problems.append((False, f"{key} track", label))
            progress(f"FAIL  {key} track is silent — grant {label}")
            progress(f"      open: {url}")

    if not problems:
        progress("\nQuill is ready. Start a call, or run `meet start`.")
    else:
        progress(f"\n{len(problems)} problem(s) to fix, then run `meet doctor` again.")
    return len(problems)
