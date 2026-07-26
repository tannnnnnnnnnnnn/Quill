"""Speaker verification for the microphone track.

The mic hears the whole room, and everything it hears is labelled **Me**. Music,
a TV, someone talking nearby — all of it lands in the transcript as if the user
said it. Measured on a real recording, ambient audio arrives at the same
loudness as genuine speech (1200-3700 RMS against 2795), so no amplitude gate
can separate them, and neither can hand-built spectral features: an MFCC
profile scored the ambient audio *higher* than real speech.

What does work is asking the only question that matters — is this the user? —
with a model trained for it. WeSpeaker's VoxCeleb ResNet34 maps a few seconds of
audio to a 256-dim embedding where the same speaker lands close together.
Validated end to end on two known-distinct voices: 0.99 cosine within a speaker,
0.14 across. It needs one clean recording of the user's voice, which `meet
enroll` collects; a profile built from past **Me** lines is worthless, because
those lines carry the contamination this module exists to remove.

Everything runs locally on CPU. The model is ~26 MB, fetched once.
"""

import hashlib
import subprocess
import sys
import urllib.request
import wave
from pathlib import Path

import numpy as np

from . import config

MODEL_URL = (
    "https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM/"
    "resolve/main/voxceleb_resnet34_LM.onnx"
)
MODEL_SHA256 = "7bb2f06e9df17cdf1ef14ee8a15ab08ed28e8d0ef5054ee135741560df2ec068"
MODEL_PATH = config.SETTINGS_PATH.parent / "models" / "voxceleb_resnet34_LM.onnx"
PROFILE_PATH = config.SETTINGS_PATH.parent / "voice-profile.npz"

SR = 16000
ENROLL_SECONDS = 24
MIN_SECONDS = 1.2          # below this an embedding is too noisy to trust
FLOOR, CEILING = 0.30, 0.62  # bounds on the calibrated threshold

ENROLL_SCRIPT = """\
Read this aloud at your normal speaking volume, in your normal voice:

  "This is my voice, recording a short sample so Quill can tell my speech
   apart from whatever else the microphone happens to hear. I might be in
   a meeting, at my desk, or on a call. The room may not be quiet, and
   that is fine — Quill only needs to learn what I sound like."

Keep going until it stops. Silence at the end is fine.
"""

_session = None


# --- feature extraction ----------------------------------------------------
def _mel_filterbank(n_mels=80, n_fft=512, sr=SR, low=20.0):
    def hz2mel(f):
        return 1127.0 * np.log(1 + f / 700.0)

    def mel2hz(m):
        return 700.0 * (np.exp(m / 1127.0) - 1)

    pts = mel2hz(np.linspace(hz2mel(low), hz2mel(sr / 2), n_mels + 2))
    freqs = np.linspace(0, sr / 2, n_fft // 2 + 1)
    fb = np.zeros((n_mels, len(freqs)))
    for i in range(n_mels):
        left, centre, right = pts[i], pts[i + 1], pts[i + 2]
        fb[i] = np.clip(
            np.minimum((freqs - left) / (centre - left),
                       (right - freqs) / (right - centre)),
            0, None)
    return fb


_FB = _mel_filterbank()


def fbank(samples: np.ndarray) -> np.ndarray | None:
    """80-dim log-mel, 25 ms window / 10 ms hop, Povey window, mean-normalised —
    the layout WeSpeaker was trained on."""
    x = samples.astype(np.float64)
    if len(x) < int(MIN_SECONDS * SR) or np.abs(x).max() < 1:
        return None

    n_win, hop = 400, 160
    frames = 1 + (len(x) - n_win) // hop
    if frames < 20:
        return None

    fr = np.lib.stride_tricks.as_strided(
        x, (frames, n_win), (x.strides[0] * hop, x.strides[0])).copy()
    fr -= fr.mean(axis=1, keepdims=True)
    fr = np.concatenate([fr[:, :1], fr[:, 1:] - 0.97 * fr[:, :-1]], axis=1)
    fr *= np.hamming(n_win) ** 0.85
    spec = np.abs(np.fft.rfft(fr, 512)) ** 2
    feats = np.log(np.maximum(spec @ _FB.T, 1e-10))
    return (feats - feats.mean(axis=0, keepdims=True)).astype(np.float32)


# --- model -----------------------------------------------------------------
def ensure_model(progress=print) -> Path:
    if MODEL_PATH.exists():
        return MODEL_PATH
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    progress(f"downloading speaker model (~26 MB) → {MODEL_PATH}")
    tmp = MODEL_PATH.with_suffix(".part")
    urllib.request.urlretrieve(MODEL_URL, tmp)
    digest = hashlib.sha256(tmp.read_bytes()).hexdigest()
    if digest != MODEL_SHA256:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"speaker model checksum mismatch: {digest}")
    tmp.rename(MODEL_PATH)
    return MODEL_PATH


def _get_session():
    global _session
    if _session is None:
        import onnxruntime as ort
        _session = ort.InferenceSession(
            str(ensure_model()), providers=["CPUExecutionProvider"])
    return _session


def embed(samples: np.ndarray) -> np.ndarray | None:
    """L2-normalised speaker embedding, or None if the audio is too short."""
    feats = fbank(samples)
    if feats is None:
        return None
    vec = _get_session().run(None, {"feats": feats[None, :, :]})[0][0]
    norm = np.linalg.norm(vec)
    return vec / norm if norm else None


# --- profile ---------------------------------------------------------------
def calibrate(vectors: list[np.ndarray]) -> tuple[np.ndarray, float]:
    """Average the enrolment windows into a profile, and set the threshold from
    how tightly the user's own windows cluster around it — a steady voice in a
    quiet room earns a stricter gate than a variable one."""
    centroid = np.mean(vectors, axis=0)
    centroid /= np.linalg.norm(centroid)
    sims = np.array([float(v @ centroid) for v in vectors])
    threshold = float(np.clip(sims.mean() - 2 * sims.std(), FLOOR, CEILING))
    return centroid, threshold


def save_profile(centroid: np.ndarray, threshold: float) -> Path:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez(PROFILE_PATH, centroid=centroid, threshold=threshold)
    return PROFILE_PATH


def load_profile() -> tuple[np.ndarray, float] | None:
    if not PROFILE_PATH.exists():
        return None
    try:
        data = np.load(PROFILE_PATH)
        return data["centroid"], float(data["threshold"])
    except (OSError, ValueError, KeyError):
        return None


def is_me(samples: np.ndarray, profile) -> bool | None:
    """True if this sounds like the enrolled speaker, None if undecidable."""
    centroid, threshold = profile
    vec = embed(samples)
    if vec is None:
        return None
    return float(vec @ centroid) >= threshold


# --- enrolment -------------------------------------------------------------
def _record(seconds: int, workdir: Path, progress=print) -> Path:
    """Capture the microphone with Audiocap, the same helper the recorder uses,
    and return the mic track. Audiocap owns both tracks; only `me.caf` matters
    here, and the system track is discarded with the directory."""
    import time

    if not config.APP.exists():
        raise SystemExit(
            f"Audiocap.app missing — run `make build` first ({config.APP})")

    workdir.mkdir(parents=True, exist_ok=True)
    for name in (".ready", ".done", "audiocap.pid"):
        (workdir / name).unlink(missing_ok=True)

    subprocess.run(["open", "-na", str(config.APP), "--args",
                    str(workdir), str(seconds + 5)], check=True)

    for _ in range(120):
        if (workdir / ".ready").exists():
            break
        time.sleep(0.5)
    else:
        raise SystemExit("recorder never became ready — check microphone permission")

    for left in range(seconds, 0, -1):
        progress(f"  recording… {left:>2}s ", end="\r", flush=True)
        time.sleep(1)
    progress(" " * 44, end="\r")

    (workdir / ".done").write_text("")
    for _ in range(60):
        if not (workdir / "audiocap.pid").exists():
            break
        time.sleep(0.5)

    mic = workdir / "me.caf"
    if not mic.exists():
        raise SystemExit("no microphone audio captured — check permissions")
    return mic


def _load_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data.astype(np.float32), sr


def enroll(audio_path: Path | None = None, progress=print) -> tuple[int, float]:
    """Build a voice profile. Returns (windows used, threshold)."""
    ensure_model(progress)

    from . import transcribe
    tmp = config.SETTINGS_PATH.parent / "enroll.wav"
    tmp.parent.mkdir(parents=True, exist_ok=True)

    if audio_path is None:
        progress(ENROLL_SCRIPT)
        raw = config.SETTINGS_PATH.parent / "enroll.caf"
        _record(ENROLL_SECONDS, raw, progress)
        audio_path = raw

    transcribe._to_wav16(audio_path, tmp, mic=False)
    samples, sr = _load_wav(tmp)

    # 3s windows, 1.5s hop; skip the quiet ones, they carry no voice
    win, hop = int(3 * sr), int(1.5 * sr)
    levels, chunks = [], []
    for start in range(0, max(1, len(samples) - win + 1), hop):
        seg = samples[start:start + win]
        levels.append(float(np.sqrt(np.mean(seg.astype(np.float64) ** 2))))
        chunks.append(seg)
    if not chunks:
        raise SystemExit("enrolment audio too short — try again")

    cutoff = max(np.percentile(levels, 45), 150.0)
    vectors = [v for seg, lvl in zip(chunks, levels) if lvl >= cutoff
               for v in [embed(seg)] if v is not None]
    if len(vectors) < 3:
        raise SystemExit(
            "not enough speech in the enrolment recording — re-run `meet enroll` "
            "and read the passage aloud without long pauses")

    centroid, threshold = calibrate(vectors)
    save_profile(centroid, threshold)
    tmp.unlink(missing_ok=True)
    return len(vectors), threshold


def describe() -> str:
    profile = load_profile()
    if profile is None:
        return "no voice profile — run `meet enroll` to filter room audio out of your track"
    return f"voice profile: {PROFILE_PATH} (threshold {profile[1]:.2f})"
