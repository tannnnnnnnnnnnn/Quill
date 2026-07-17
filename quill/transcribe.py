"""Transcribe me.caf/them.caf with parakeet-mlx, merge into a Me/Them transcript."""

import json
import os
import subprocess
import wave
from pathlib import Path

from . import config


def _ffmpeg() -> str:
    import imageio_ffmpeg
    exe = Path(imageio_ffmpeg.get_ffmpeg_exe())
    # parakeet-mlx shells out to `ffmpeg`, so expose it on PATH
    config.BIN_DIR.mkdir(exist_ok=True)
    link = config.BIN_DIR / "ffmpeg"
    try:
        # replace stale/dangling links (e.g. after the project dir moved)
        if link.is_symlink() and link.readlink() != exe:
            link.unlink()
        if not link.exists():
            link.symlink_to(exe)
    except FileExistsError:
        pass  # another thread fixed it concurrently
    os.environ["PATH"] = f"{config.BIN_DIR}{os.pathsep}{os.environ.get('PATH', '')}"
    return str(exe)


def _to_wav16(src: Path, dst: Path, mic: bool = False) -> float:
    """Convert to 16 kHz mono wav, return duration in seconds (0 if empty).
    mic=True runs the denoise/loudnorm chain (mic audio is the noisy track)."""
    cmd = [_ffmpeg(), "-y", "-nostdin", "-i", str(src)]
    if mic and config.MIC_FILTER:
        cmd += ["-af", config.MIC_FILTER]
    cmd += ["-ar", "16000", "-ac", "1", str(dst)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or not dst.exists():
        return 0.0
    with wave.open(str(dst)) as w:
        return w.getnframes() / w.getframerate()


def _transcribe_track(wav: Path) -> list[dict]:
    """Final-pass ASR: whisper large-v3-turbo (accuracy). Live uses parakeet."""
    import mlx_whisper
    result = mlx_whisper.transcribe(
        str(wav),
        path_or_hf_repo=config.WHISPER_MODEL,
        language="en",
    )
    return [
        {"start": float(s["start"]), "end": float(s["end"]), "text": s["text"].strip()}
        for s in result["segments"]
        if s["text"].strip()
    ]


def _fmt_ts(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def merge(me: list[dict], them: list[dict]) -> str:
    # echo/bleed dedupe: a cross-track fuzzy match with overlapping time span is one
    # utterance captured twice — keep the earlier copy (originals precede
    # echoes; on near-ties the sort prefers Them, the clean system track).
    # Matches farther apart are legitimate verbal repetition — keep both.
    from .textmatch import MAX_ECHO_GAP, norm, similar
    entries = [{**e, "spk": "Me"} for e in me] + [{**e, "spk": "Them"} for e in them]
    entries.sort(key=lambda e: (e["start"], 0 if e["spk"] == "Them" else 1))
    kept = []
    for e in entries:
        n = norm(e["text"])
        dup = False
        for k in reversed(kept):
            if e["start"] - k["start"] > 30:
                break
            if (k["spk"] != e["spk"]
                    and e["start"] <= k["end"] + MAX_ECHO_GAP
                    and similar(n, norm(k["text"]))):
                dup = True
                break
        if not dup:
            kept.append(e)
    entries = kept
    # vocative guard: a "Me" line that addresses the user by name is bleed
    # from the far side that never got a system-track twin to dedupe against
    from .textmatch import vocative
    for e in entries:
        if e["spk"] == "Me" and vocative(config.USER_NAME, e["text"]):
            e["spk"] = "Them"
    entries.sort(key=lambda e: e["start"])
    lines = []
    for e in entries:
        lines.append(f"- **{e['spk']}** [{_fmt_ts(e['start'])}]: {e['text']}")
    return "\n".join(lines)


def run(d: str | Path, progress=print) -> Path:
    """Transcribe a recording dir → <dir>/transcript.md + copy into the vault."""
    d = Path(d)
    tracks = {}
    for name in ("me", "them"):
        src = next((d / f"{name}{ext}" for ext in (".caf", ".m4a")
                    if (d / f"{name}{ext}").exists()), None)
        if src is None:
            continue
        wav = d / f"{name}16.wav"
        dur = _to_wav16(src, wav, mic=(name == "me"))
        if dur > 0.5:
            tracks[name] = wav
        progress(f"{name}: {dur:.0f}s audio")

    if not tracks:
        raise SystemExit("no audio in either track")

    segs = {}
    for name, wav in tracks.items():
        progress(f"transcribing {name} (whisper)...")
        segs[name] = _transcribe_track(wav)

    # acoustic bleed guard: a "Me" segment whose raw-mic audio is a quiet,
    # envelope-correlated copy of the system audio is the speakers, not the
    # user (true even with the app-level mic muted). Relabel to Them when the
    # system-track ASR missed it; drop when it already exists there.
    if segs.get("me") and "them" in tracks:
        from . import bleedguard
        from .textmatch import MAX_ECHO_GAP, norm, similar
        me_src = next((d / f"me{ext}" for ext in (".caf", ".m4a")
                       if (d / f"me{ext}").exists()), None)
        raw = d / "me_raw16.wav"
        if me_src is not None and _to_wav16(me_src, raw, mic=False) > 0:
            micx, sr = bleedguard.load_wav(raw)
            sysx, _ = bleedguard.load_wav(tracks["them"])
            them_idx = [(t["start"], t["end"], norm(t["text"])) for t in segs["them"]]
            keep, flipped, dropped = [], [], 0
            silent = 0
            for e in segs["me"]:
                if bleedguard.is_silent(micx, sr, e["start"], e["end"]):
                    silent += 1        # AEC'd near-silence → ASR hallucination
                    continue
                if bleedguard.is_bleed(micx, sysx, sr, e["start"], e["end"]):
                    n = norm(e["text"])
                    twin = any(ts <= e["end"] + MAX_ECHO_GAP
                               and e["start"] <= te + MAX_ECHO_GAP
                               and similar(n, tn)
                               for ts, te, tn in them_idx)
                    if twin:
                        dropped += 1
                    else:
                        flipped.append(e)
                else:
                    keep.append(e)
            segs["me"] = keep
            segs["them"] = sorted(segs["them"] + flipped, key=lambda x: x["start"])
            progress(f"bleed guard: {len(keep)} Me kept, {len(flipped)} relabeled "
                     f"Them, {dropped} dropped, {silent} silent-gated")
            raw.unlink(missing_ok=True)

    body = merge(segs.get("me", []), segs.get("them", []))

    meta = {}
    mj = d / "meta.json"
    if mj.exists():
        meta = json.loads(mj.read_text())
    header = (
        f"# Transcript: {meta.get('title') or d.name}\n\n"
        f"date: {meta.get('started', '')}  \n"
        f"duration: {meta.get('duration_minutes', '?')} min  \n"
        f"speakers: **Me** = Tanmay, **Them** = other participants\n\n"
    )
    out = d / "transcript.md"
    out.write_text(header + body + "\n")

    config.TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    vault_copy = config.TRANSCRIPTS_DIR / f"{d.name}.md"
    vault_copy.write_text(header + body + "\n")

    _cleanup_audio(d, progress)
    # temp wavs are only needed for transcription
    for name in ("me", "them"):
        (d / f"{name}16.wav").unlink(missing_ok=True)
    progress(f"transcript: {vault_copy}")
    return out


def _cleanup_audio(d: Path, progress=print) -> None:
    if config.KEEP_AUDIO == "raw":
        return
    for name in ("me", "them"):
        caf = d / f"{name}.caf"
        if not caf.exists():
            continue
        if config.KEEP_AUDIO == "m4a":
            r = subprocess.run(
                ["afconvert", "-f", "m4af", "-d", "aac", str(caf), str(d / f"{name}.m4a")],
                capture_output=True,
            )
            if r.returncode != 0:
                progress(f"m4a conversion failed for {name}, keeping caf")
                continue
        caf.unlink()
