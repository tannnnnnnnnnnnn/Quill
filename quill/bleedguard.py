"""Acoustic bleed detection: is a mic segment just the speakers playing the
far side (system audio → room → microphone)? Works even when the user's
app-level mic is muted — the OS microphone still hears the room.

Signal: bleed is a time-aligned, attenuated COPY of the system track, so its
20ms loudness envelope correlates strongly with the system envelope over the
same span, and its level is well below the system level. Real user speech is
uncorrelated with the far side and close-mic loud.

IMPORTANT: classify on the RAW mic audio. The ASR mic chain loudness-normalizes
(which would erase the level cue).
"""

import re
import wave
from pathlib import Path

import numpy as np

FRAME = 0.02        # envelope frame (s)
MAX_LAG = 0.20      # timestamp slack between tracks (s)
CORR_THRESH = 0.55  # envelope correlation → same audio
RATIO_THRESH = 0.60 # mic must be this much quieter than system to be bleed
SYS_FLOOR = 60.0    # int16 RMS below which the system track is "silent"
SILENCE_RMS = 110.0 # raw-mic RMS below this = no speech; ASR on loudnorm-boosted
                    # noise hallucinates ("cop cop cop"), so gate these segments

# Separately from level: the decoder sometimes falls into a loop and emits one
# token for the whole segment. Measured on a real call (2026-07-26) — a segment
# at 0:00 was the word "Jon" repeated 200 times, at a mic level indistinguishable
# from speech, so no amplitude gate can catch it. The text gives it away.
DEGENERATE_MIN_WORDS = 6    # below this, repetition is normal ("okay, okay")
DEGENERATE_VARIETY = 0.25   # unique/total words at or under this = a loop
DEGENERATE_ECHOES = 3       # identical consecutive segments before dropping


def load_wav(path: str | Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return x, sr


def _envelope(x: np.ndarray, sr: int) -> np.ndarray:
    n = int(sr * FRAME)
    m = len(x) // n
    if n <= 0 or m == 0:
        return np.zeros(0, dtype=np.float32)
    return np.abs(x[: m * n].astype(np.float32)).reshape(m, n).mean(axis=1)


def _rms(x: np.ndarray) -> float:
    if not len(x):
        return 0.0
    return float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))


def is_bleed(mic: np.ndarray, sys_: np.ndarray, sr: int,
             start: float, end: float) -> bool:
    """Classify mic[start:end] (seconds, same clock as sys_)."""
    a, b = int(start * sr), int(end * sr)
    pad = int(MAX_LAG * sr)
    mic_seg = mic[max(0, a): b]
    sys_seg = sys_[max(0, a - pad): b + pad]
    if len(mic_seg) < sr // 2 or len(sys_seg) < len(mic_seg):
        return False

    sys_rms = _rms(sys_seg)
    if sys_rms < SYS_FLOOR:
        return False                      # nothing playing → can't be bleed
    if _rms(mic_seg) / (sys_rms + 1e-9) > RATIO_THRESH:
        return False                      # mic too loud relative to system → user

    me_env = _envelope(mic_seg, sr)
    sy_env = _envelope(sys_seg, sr)
    if len(me_env) < 5 or len(sy_env) < len(me_env):
        return False
    me_n = me_env - me_env.mean()
    dm = np.linalg.norm(me_n)
    if dm == 0:
        return False
    best = -1.0
    for off in range(len(sy_env) - len(me_env) + 1):
        win = sy_env[off: off + len(me_env)]
        w_n = win - win.mean()
        dw = np.linalg.norm(w_n)
        if dw == 0:
            continue
        best = max(best, float(np.dot(me_n, w_n) / (dm * dw)))
    return best >= CORR_THRESH


def is_silent(mic: np.ndarray, sr: int, start: float, end: float) -> bool:
    """No real speech in mic[start:end] (RAW audio — loudnorm masks the cue)."""
    seg = mic[max(0, int(start * sr)): int(end * sr)]
    return _rms(seg) < SILENCE_RMS


def is_degenerate(text: str) -> bool:
    """A decoder loop rather than speech: the same word over and over, or one
    phrase repeated back to back for the whole segment."""
    words = [w for w in re.findall(r"[\w']+", text.lower()) if w]
    if len(words) < DEGENERATE_MIN_WORDS:
        return False

    if len(set(words)) / len(words) <= DEGENERATE_VARIETY:
        return True

    # a phrase looping to fill the segment: "<p> <p> <p>" for some phrase p
    for size in range(1, len(words) // DEGENERATE_ECHOES + 1):
        if len(words) % size:
            continue
        phrase = words[:size]
        if all(words[i:i + size] == phrase for i in range(0, len(words), size)):
            return True
    return False


def drop_echoes(segments: list[dict]) -> list[dict]:
    """Drop runs of DEGENERATE_ECHOES or more segments with identical text.
    Someone may well say "okay" twice; they do not say the same sentence four
    times in a row while the mic hears nothing else."""
    keep, run_text, run = [], None, []
    for seg in segments + [None]:
        text = None if seg is None else " ".join(
            re.findall(r"[\w']+", seg["text"].lower()))
        if text is not None and text == run_text:
            run.append(seg)
            continue
        if len(run) < DEGENERATE_ECHOES:
            keep.extend(run)
        run_text, run = text, ([] if seg is None else [seg])
    return keep
