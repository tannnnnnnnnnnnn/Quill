"""Live transcription for the floating panel.

Two modes (config.LIVE_MODE):
- "stream": incremental parakeet streaming — finalized sentences appear ~3s
  behind speech and a mutable draft tail ("◌ …") shows words almost instantly.
  Falls back to windowed mode automatically on any error.
- "window": legacy mode — re-transcribe the last 10s file window every cycle.

MLX streams are thread-local, so EVERY model operation runs on one dedicated
worker thread (_on_worker). Streaming state (the two track streams) lives in
module globals that only worker-thread functions touch."""

import contextlib
import queue
import subprocess
import threading
import time
import traceback
import wave
from pathlib import Path

from . import config
from .transcribe import _ffmpeg

# windowed mode — tuned for latency: smaller window transcribes faster,
# shorter cycle + settle get words on screen ~2.5-4s after speech
WINDOW = 8
INTERVAL = 1.75
SETTLE = 0.6

# streaming mode
FEED_INTERVAL = 1.0        # seconds between feed cycles
FEED_LAG = 0.25            # stay this far behind the file tail (still being written)
CTX = (256, 64)            # left ≈20s quality context; right 64×0.08 ≈ 5.1s final lag
SENT_GAP = 1.2             # flush a sentence at this silence gap
SENT_MAX = 12.0            # or when the buffer spans this many seconds
BUF_AGE = 4.0              # or when tokens have waited this long (wall clock)
DRAFT_MIN_CHARS = 2

_model = None
_work_q: queue.Queue = queue.Queue()
_worker = None
_worker_lock = threading.Lock()

# streaming session state — worker thread only
_streams = {}
_stack = None
_fin_seen = {}


def _worker_main():
    while True:
        fn, args, out = _work_q.get()
        try:
            out.put(("ok", fn(*args)))
        except Exception as e:
            out.put(("err", e))


def _on_worker(fn, *args):
    global _worker
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_worker_main, daemon=True)
            _worker.start()
    out = queue.Queue()
    _work_q.put((fn, args, out))
    status, val = out.get()
    if status == "err":
        raise val
    return val


def _get_model():
    global _model
    if _model is None:
        from parakeet_mlx import from_pretrained
        _model = from_pretrained(config.MODEL)
    return _model


def _transcribe_file(path: str):
    return _get_model().transcribe(path)


def preload_model() -> None:
    try:
        _on_worker(_get_model)
        print("live: model preloaded", flush=True)
    except Exception as e:
        print(f"live: model preload failed: {e}", flush=True)


# ---------- streaming session (worker-thread functions) ----------

def _stream_open():
    """Open both track streams together — identical params, shared encoder
    state (see parakeet_mlx: set_attention_model mutates the shared model)."""
    global _stack, _streams, _fin_seen
    model = _get_model()
    _stack = contextlib.ExitStack()
    _streams = {
        t: _stack.enter_context(model.transcribe_stream(context_size=CTX, depth=1))
        for t in ("them", "me")
    }
    _fin_seen = {"them": 0, "me": 0}


def _stream_feed(track, samples):
    """Feed float32 [-1,1] samples; return (new_finalized_tokens, draft_text, draft_end)."""
    import mlx.core as mx
    tr = _streams[track]
    tr.add_audio(mx.array(samples))
    fin = tr.finalized_tokens
    new = [(t.text, float(t.start), float(t.end)) for t in fin[_fin_seen[track]:]]
    _fin_seen[track] = len(fin)
    draft = "".join(t.text for t in tr.draft_tokens).strip()
    draft_end = float(tr.draft_tokens[-1].end) if tr.draft_tokens else 0.0
    return new, draft, draft_end


def _stream_close():
    global _stack, _streams
    if _stack is not None:
        _stack.close()          # exits BOTH streams together; restores attention
    _stack = None
    _streams = {}


# ---------- shared helpers ----------

def _extract(ff, src, dst, start=None, dur=None, mic=False):
    """ffmpeg → 16k mono wav. Returns True on success."""
    cmd = [ff, "-y", "-nostdin"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(src)]
    if dur is not None:
        cmd += ["-t", f"{dur:.3f}"]
    if mic and config.MIC_FILTER:
        cmd += ["-af", config.MIC_FILTER]
    cmd += ["-ar", "16000", "-ac", "1", str(dst)]
    return subprocess.run(cmd, capture_output=True).returncode == 0


def _read_samples(wav_path):
    """wav int16 → float32 numpy in [-1, 1]."""
    import numpy as np
    with wave.open(str(wav_path)) as w:
        data = w.readframes(w.getnframes())
    return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0


class _Dedupe:
    """Same rules as the final merge: interval-overlap cross-track kill,
    fuzzy same-track window kill."""

    def __init__(self):
        from .textmatch import MAX_ECHO_GAP, norm, similar
        self.gap = MAX_ECHO_GAP
        self.norm = norm
        self.similar = similar
        self.recent = []   # (track, norm, start, end)

    def admit(self, track, text, s0, e0):
        n = self.norm(text)
        if not n:
            return False
        for tr, r, ts, te in self.recent[-14:]:
            if tr == track and abs(s0 - ts) <= 6.0 and self.similar(n, r, 0.65):
                return False
            if (tr != track and s0 <= te + self.gap and ts <= e0 + self.gap
                    and self.similar(n, r)):
                return False
        self.recent.append((track, n, s0, e0))
        del self.recent[:-20]
        return True


def live_loop(rec_dir: str, t0: float, emit, stop) -> None:
    try:
        if config.LIVE_MODE == "stream":
            try:
                _run_streaming(rec_dir, t0, emit, stop)
                return
            except Exception as e:
                traceback.print_exc()
                print(f"live: streaming failed ({e}) — falling back to windowed",
                      flush=True)
                try:
                    _on_worker(_stream_close)
                except Exception:
                    pass
                if not stop.is_set():
                    emit("· switched to windowed mode")
                    _run_windowed(rec_dir, t0, emit, stop)
                return
        _run_windowed(rec_dir, t0, emit, stop)
    except Exception as e:
        traceback.print_exc()
        emit(f"⚠ live error: {e} — final transcript is unaffected")


# ---------- streaming mode ----------

def _run_streaming(rec_dir, t0, emit, stop):
    if _model is None:
        emit("… loading model")
    _on_worker(_get_model)
    _on_worker(_stream_open)
    emit("● live")

    ff = _ffmpeg()
    d = Path(rec_dir)
    label = {"me": "Me", "them": "Them"}
    fed = {"me": 0.0, "them": 0.0}       # seconds of audio fed per track
    sent_buf = {"me": [], "them": []}    # buffered finalized tokens
    buf_born = {"me": 0.0, "them": 0.0}  # wall time of first buffered token
    dedupe = _Dedupe()
    last_draft = ""
    missing = 0

    def flush(track, force=False):
        buf = sent_buf[track]
        if not buf:
            return
        text = "".join(t[0] for t in buf).strip()
        s0, e0 = buf[0][1], buf[-1][2]
        end_char = text[-1:] if text else ""
        spans = e0 - s0 > SENT_MAX
        if not (force or end_char in ".?!…" or spans):
            return
        sent_buf[track] = []
        if text and dedupe.admit(track, text, s0, e0):
            emit(f"{label[track]}: {text}")

    try:
        while not stop.is_set():
            if not (d / "me.caf").exists() and not (d / "them.caf").exists():
                missing += 1
                if missing >= 3:
                    print("live: recording dir gone — loop ending", flush=True)
                    return
                stop.wait(FEED_INTERVAL)
                continue
            missing = 0

            elapsed = time.time() - t0
            newest_draft = ("", 0.0, "")
            for track in ("them", "me"):
                caf = d / f"{track}.caf"
                if not caf.exists():
                    continue
                target = elapsed - FEED_LAG
                dur = target - fed[track]
                if dur < 0.4:
                    continue
                wav = d / f".live_{track}.wav"
                if not _extract(ff, caf, wav, start=fed[track], dur=dur,
                                mic=(track == "me")):
                    continue
                try:
                    samples = _read_samples(wav)
                except Exception:
                    continue
                if not len(samples):
                    continue
                fed[track] += len(samples) / 16000.0
                new_fin, draft, draft_end = _on_worker(_stream_feed, track, samples)

                for tok in new_fin:
                    buf = sent_buf[track]
                    if buf and tok[1] - buf[-1][2] > SENT_GAP:
                        flush(track, force=True)
                    if not sent_buf[track]:
                        buf_born[track] = time.time()
                    sent_buf[track].append(tok)
                    flush(track)
                if sent_buf[track] and time.time() - buf_born[track] > BUF_AGE:
                    flush(track, force=True)
                if len(draft) >= DRAFT_MIN_CHARS and draft_end > newest_draft[1]:
                    newest_draft = (draft, draft_end, track)

            draft_text, _, draft_track = newest_draft
            if draft_text:
                line = f"◌ {label[draft_track]}: {draft_text[-140:]}"
                if line != last_draft:
                    last_draft = line
                    emit(line)

            stop.wait(FEED_INTERVAL)
    finally:
        for track in ("them", "me"):
            flush(track, force=True)
        emit("◌")   # clear draft tail
        try:
            _on_worker(_stream_close)
        except Exception:
            pass
        for track in ("me", "them"):
            (d / f".live_{track}.wav").unlink(missing_ok=True)


# ---------- windowed mode (fallback) ----------

def _run_windowed(rec_dir, t0, emit, stop):
    if _model is None:
        emit("… loading model")
    _on_worker(_get_model)
    emit("● live")

    ff = _ffmpeg()
    d = Path(rec_dir)
    shown = {"me": 0.0, "them": 0.0}
    label = {"me": "Me", "them": "Them"}
    dedupe = _Dedupe()
    dead_cycles = 0
    warned = False
    missing_cycles = 0

    while not stop.is_set():
        if not (d / "me.caf").exists() and not (d / "them.caf").exists():
            missing_cycles += 1
            if missing_cycles >= 3:
                print("live: recording dir gone — loop ending", flush=True)
                return
            stop.wait(INTERVAL)
            continue
        missing_cycles = 0
        cand = []
        cycle_audio = False
        windows = {}   # track -> (int16 array, win_start) for the bleed guard
        for track in ("me", "them"):
            caf = d / f"{track}.caf"
            if not caf.exists():
                continue
            if track == "me":
                # unfiltered copy for acoustic classification (loudnorm would
                # erase the level cue the bleed guard relies on)
                raw = d / ".live_me_raw.wav"
                if _extract(ff, caf, raw):
                    subprocess.run([ff, "-y", "-nostdin", "-sseof", f"-{WINDOW}",
                                    "-i", str(caf), "-ar", "16000", "-ac", "1",
                                    str(raw)], capture_output=True)
            wav = d / f".live_{track}.wav"
            cmd = [ff, "-y", "-nostdin", "-sseof", f"-{WINDOW}", "-i", str(caf)]
            if track == "me" and config.MIC_FILTER:
                cmd += ["-af", config.MIC_FILTER]
            cmd += ["-ar", "16000", "-ac", "1", str(wav)]
            r = subprocess.run(cmd, capture_output=True)
            if r.returncode != 0:
                print(f"live: ffmpeg rc={r.returncode} {track}: "
                      f"{r.stderr.decode()[-160:]}", flush=True)
                continue
            try:
                with wave.open(str(wav)) as w:
                    dur = w.getnframes() / 16000
            except Exception:
                continue
            if dur < 1.5:
                continue
            cycle_audio = True
            elapsed = time.time() - t0
            win_start = max(0.0, elapsed - dur)
            try:
                from . import bleedguard
                src_for_guard = d / (".live_me_raw.wav" if track == "me"
                                     else f".live_{track}.wav")
                if src_for_guard.exists():
                    arr, _sr = bleedguard.load_wav(src_for_guard)
                    windows[track] = (arr, win_start)
            except Exception:
                pass
            try:
                result = _on_worker(_transcribe_file, str(wav))
            except Exception as e:
                print(f"live: transcribe failed {track}: {e}", flush=True)
                continue
            for s in result.sentences:
                text = s.text.strip()
                abs_start = win_start + s.start
                abs_end = win_start + s.end
                settled = abs_end < elapsed - SETTLE
                if text and settled and abs_start > shown[track] + 0.25:
                    cand.append((abs_start, 0 if track == "them" else 1,
                                 abs_end, track, text))

        from .textmatch import vocative
        from . import bleedguard
        import numpy as _np
        for abs_start, _, abs_end, track, text in sorted(cand):
            spk = track
            if track == "me":
                # acoustic bleed check: quiet, envelope-correlated copy of the
                # system audio = the speakers, not the user (mute-proof)
                if "me" in windows:
                    mic_arr, ws_me = windows["me"]
                    try:
                        if bleedguard.is_silent(mic_arr, 16000,
                                                abs_start - ws_me, abs_end - ws_me):
                            continue   # AEC'd silence → hallucinated text
                    except Exception:
                        pass
                if "me" in windows and "them" in windows:
                    mic_arr, ws_me = windows["me"]
                    sys_arr, ws_th = windows["them"]
                    off = int(round((ws_me - ws_th) * 16000))
                    sys_al = (sys_arr[off:] if off >= 0 else
                              _np.concatenate([_np.zeros(-off, _np.int16), sys_arr]))
                    try:
                        if bleedguard.is_bleed(mic_arr, sys_al, 16000,
                                               abs_start - ws_me, abs_end - ws_me):
                            spk = "them"
                    except Exception:
                        pass
                if spk == "me" and vocative(config.USER_NAME, text):
                    spk = "them"
            if dedupe.admit(spk, text, abs_start, abs_end):
                shown[track] = max(shown[track], abs_start)
                emit(f"{label[spk]}: {text}")

        dead_cycles = 0 if cycle_audio else dead_cycles + 1
        if dead_cycles == 5 and not warned:
            warned = True
            emit("⚠ no audio flowing — recording may have a problem (see log)")
        stop.wait(INTERVAL)

    for track in ("me", "them"):
        (d / f".live_{track}.wav").unlink(missing_ok=True)
    (d / ".live_me_raw.wav").unlink(missing_ok=True)
