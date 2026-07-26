"""Local HTTP control surface for the Quill browser extension."""

import datetime as dt
import json
import signal
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urlparse

from . import live, process, record, transcribe

HOST = "127.0.0.1"
PORT = 8787
VERSION = "0.1.0"
EXPLICIT_IGNORE_TTL_SECONDS = 6 * 60 * 60
AUTOMATIC_IGNORE_TTL_SECONDS = 5 * 60


class APIError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _recording_id(st: dict) -> str:
    return Path(st["dir"]).name


def _started_at(st: dict) -> int:
    return int(dt.datetime.fromisoformat(st["started"]).timestamp())


def _meeting_key(value: str) -> str:
    """Return the stable meeting identity encoded in a supported meeting URL."""
    url = urlparse(value)
    host = (url.hostname or "").lower()
    path = unquote(url.path)
    parts = [part for part in path.split("/") if part]

    if host == "meet.google.com" and parts:
        code = parts[0].lower()
        if (len(code) == 12 and code[3] == "-" and code[8] == "-"
                and all(part.isalpha() for part in code.split("-"))):
            return f"google-meet:{code}"

    if host.endswith(".zoom.us") and len(parts) >= 2 and parts[0].lower() == "wc":
        meeting_part = parts[1]
        if meeting_part.lower() in {"join", "start"} and len(parts) >= 3:
            meeting_part = parts[2]
        return f"zoom:{host}:{meeting_part}"

    if host in {"teams.microsoft.com", "teams.cloud.microsoft"}:
        # Standard Teams links carry their meeting/thread identity in the path;
        # query parameters are launch context and may vary for the same meeting.
        return f"microsoft-teams:{host}:{path.rstrip('/') or '/'}"

    if host.endswith(".webex.com"):
        query = parse_qs(url.query)
        mtid = next((values[0] for key, values in query.items()
                     if key.lower() == "mtid" and values), None)
        if mtid:
            return f"webex:{host}:mtid:{mtid}"
        return f"webex:{host}:{path.rstrip('/') or '/'}"

    # Preserve the query for unknown/future meeting providers, but sort it so
    # parameter order alone cannot create a different meeting identity.
    query = urlencode(sorted(parse_qs(url.query, keep_blank_values=True).items()),
                      doseq=True)
    normalized = f"{url.scheme.lower()}://{host}{path.rstrip('/') or '/'}"
    return f"url:{normalized}{'?' + query if query else ''}"


class QuillServer:
    """Thread-safe bridge from HTTP requests to the existing Quill pipeline."""

    def __init__(self, *, clock=time.monotonic):
        self._lock = threading.RLock()
        self._clock = clock
        self._ignored_meetings: dict[tuple[int | str, str], float] = {}
        self._starting = False
        self._stopping = False
        self._processing = False
        self._closed = False

        self._recording_id: str | None = None
        self._started_at: int | None = None
        self._stopped_at: float | None = None
        self._lines: list[dict] = []

        self._live_recording_id: str | None = None
        self._live_stop: threading.Event | None = None
        self._live_thread: threading.Thread | None = None
        self._processing_thread: threading.Thread | None = None

    def _ensure_live(self, st: dict) -> None:
        recording_id = _recording_id(st)
        recording_dir = st["dir"]
        started_at = _started_at(st)

        with self._lock:
            if self._recording_id != recording_id:
                self._recording_id = recording_id
                self._started_at = started_at
                self._stopped_at = None
                self._lines = []
            if (self._live_recording_id == recording_id
                    and self._live_thread is not None
                    and self._live_thread.is_alive()):
                return
            old_stop = self._live_stop
            old_thread = self._live_thread
            self._live_recording_id = None
            self._live_stop = None
            self._live_thread = None

        if old_stop is not None:
            old_stop.set()
        if old_thread is not None and old_thread is not threading.current_thread():
            old_thread.join()

        with self._lock:
            if self._closed:
                return
            if (self._live_recording_id == recording_id
                    and self._live_thread is not None
                    and self._live_thread.is_alive()):
                return
            stop = threading.Event()
            thread = threading.Thread(
                target=live.live_loop,
                args=(recording_dir, started_at,
                      lambda line: self._emit_live(recording_id, line), stop),
                name=f"quill-live-{recording_id}",
            )
            self._live_recording_id = recording_id
            self._live_stop = stop
            self._live_thread = thread
            thread.start()

    def _stop_live(self) -> None:
        with self._lock:
            stop = self._live_stop
            thread = self._live_thread
            self._live_recording_id = None
            self._live_stop = None
            self._live_thread = None
        if stop is not None:
            stop.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join()

    def _emit_live(self, recording_id: str, line) -> None:
        line = str(line)
        if line.startswith("Me: "):
            speaker, text = "me", line[4:]
        elif line.startswith("Them: "):
            speaker, text = "them", line[6:]
        else:
            return
        with self._lock:
            if self._recording_id != recording_id or self._started_at is None:
                return
            self._lines.append({
                "i": len(self._lines) + 1,
                "speaker": speaker,
                "text": text,
                "t": round(max(0.0, time.time() - self._started_at), 3),
            })

    def _current(self) -> dict | None:
        st = record.current()
        if st is not None:
            self._ensure_live(st)
        return st

    def health(self) -> dict:
        return {"ok": True, "version": VERSION, "state": self.status()["state"]}

    def _prune_ignored_meetings(self, now: float) -> None:
        expired = [
            key for key, expires_at in self._ignored_meetings.items()
            if expires_at <= now
        ]
        for key in expired:
            del self._ignored_meetings[key]

    def meeting_detected(self, tab_id: int | str, url: str) -> dict:
        state = self.status()["state"]
        key = (tab_id, _meeting_key(url))
        with self._lock:
            now = self._clock()
            self._prune_ignored_meetings(now)
            transitioning = self._starting or self._stopping
            prompt = (state == "idle" and not transitioning
                      and key not in self._ignored_meetings)
        return {"prompt": prompt}

    def ignore(self, tab_id: int | str, url: str, *, automatic: bool) -> dict:
        # An explicit Ignore should cover even a long meeting, while an automatic
        # timeout only means the user did not respond. A five-minute cooldown
        # avoids prompt churn without turning silence into a lasting rejection.
        ttl = (AUTOMATIC_IGNORE_TTL_SECONDS if automatic
               else EXPLICIT_IGNORE_TTL_SECONDS)
        with self._lock:
            now = self._clock()
            self._prune_ignored_meetings(now)
            key = (tab_id, _meeting_key(url))
            self._ignored_meetings[key] = max(
                self._ignored_meetings.get(key, now),
                now + ttl,
            )
        return {"ok": True}

    def clear_tab(self, tab_id: int | str) -> dict:
        with self._lock:
            keys = [key for key in self._ignored_meetings if key[0] == tab_id]
            for key in keys:
                del self._ignored_meetings[key]
        return {"ok": True}

    def start(self, platform: str, title: str, url: str) -> dict:
        del url  # detection context; the established recording metadata stores title
        with self._lock:
            if self._closed:
                raise APIError("server is shutting down", 503)
            if self._processing:
                raise APIError("a recording is processing", 409)
            if self._starting or self._stopping:
                raise APIError("recording transition in progress", 409)
            if record.current() is not None:
                raise APIError("already recording", 409)
            self._starting = True

        try:
            recording_dir = record.start(title.strip() or f"{platform} call")
            st = record.current()
            if st is None:
                raise RuntimeError("recorder started without recording state")
            if st["dir"] != recording_dir:
                raise RuntimeError("recorder state does not match started recording")
        except SystemExit as e:
            raise APIError(str(e), 409) from None
        except Exception as e:
            raise APIError(str(e), 500) from None
        finally:
            with self._lock:
                self._starting = False

        self._ensure_live(st)
        return {
            "ok": True,
            "recordingId": _recording_id(st),
            "startedAt": _started_at(st),
        }

    def stop(self, recording_id: str) -> dict:
        st = self._current()
        with self._lock:
            if self._processing:
                raise APIError("a recording is already processing", 409)
            if self._starting or self._stopping:
                raise APIError("recording transition in progress", 409)
            if st is None:
                raise APIError("not recording", 409)
            if _recording_id(st) != recording_id:
                raise APIError("recordingId does not match active recording", 409)
            self._stopping = True

        try:
            stopped = record.stop()
        except SystemExit as e:
            with self._lock:
                self._stopping = False
            raise APIError(str(e), 409) from None
        except Exception as e:
            with self._lock:
                self._stopping = False
            raise APIError(str(e), 500) from None

        self._stop_live()
        with self._lock:
            self._recording_id = recording_id
            self._started_at = _started_at(stopped)
            self._stopped_at = time.time()
            self._processing = True
            thread = threading.Thread(
                target=self._run_pipeline,
                args=(stopped["dir"],),
                name=f"quill-process-{recording_id}",
            )
            self._processing_thread = thread
            try:
                thread.start()
            except Exception as e:
                self._processing = False
                self._processing_thread = None
                self._stopping = False
                raise APIError(f"could not start processing: {e}", 500) from None
            self._stopping = False
        return {"ok": True, "state": "processing"}

    def _run_pipeline(self, recording_dir: str) -> None:
        try:
            transcribe.run(recording_dir)
            note = process.run(recording_dir)
            process.notify("Meeting processed", note or "see claude.log")
        except BaseException as e:  # SystemExit included — report without killing server
            traceback.print_exc()
            process.notify("Quill — error", str(e)[:120])
        finally:
            with self._lock:
                self._processing = False
                self._processing_thread = None

    def status(self) -> dict:
        st = self._current()
        if st is not None:
            started_at = _started_at(st)
            return {
                "state": "recording",
                "recordingId": _recording_id(st),
                "startedAt": started_at,
                "elapsed": round(max(0.0, time.time() - started_at), 3),
            }

        with self._lock:
            processing = self._processing
            starting = self._starting
            stopping = self._stopping
            recording_id = self._recording_id
            started_at = self._started_at
            stopped_at = self._stopped_at

        if not processing and not starting and not stopping:
            self._stop_live()
        if processing:
            elapsed = ((stopped_at or time.time()) - started_at
                       if started_at is not None else 0.0)
            return {
                "state": "processing",
                "recordingId": recording_id,
                "startedAt": started_at,
                "elapsed": round(max(0.0, elapsed), 3),
            }
        if stopping:
            return {
                "state": "recording",
                "recordingId": recording_id,
                "startedAt": started_at,
                "elapsed": round(max(0.0, time.time() - (started_at or time.time())), 3),
            }
        return {
            "state": "idle",
            "recordingId": None,
            "startedAt": None,
            "elapsed": 0,
        }

    def transcript(self, since: int) -> dict:
        self._current()  # attach to a recording started by CLI or micwatch
        with self._lock:
            lines = [line.copy() for line in self._lines if line["i"] > since]
        return {"cursor": lines[-1]["i"] if lines else since, "lines": lines}

    def close(self) -> None:
        with self._lock:
            self._closed = True
            processing = self._processing_thread
        self._stop_live()
        if processing is not None and processing is not threading.current_thread():
            processing.join()


class _HTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = False
    block_on_close = True


class _Handler(BaseHTTPRequestHandler):
    server: _HTTPServer

    def log_message(self, *args):
        pass

    @property
    def quill(self) -> QuillServer:
        return self.server.quill

    def _send(self, obj: dict, status: int = 200) -> None:
        body = json.dumps(obj, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()
        self.wfile.write(body)

    def send_error(self, code, message=None, explain=None):
        del explain
        self._send({"error": message or self.responses.get(code, ("error",))[0]}, code)

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise APIError("invalid Content-Length") from None
        if length < 0:
            raise APIError("invalid Content-Length")
        if length > 64 * 1024:
            raise APIError("request body too large", 413)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise APIError("invalid JSON") from None
        if not isinstance(body, dict):
            raise APIError("JSON body must be an object")
        return body

    @staticmethod
    def _string(body: dict, name: str, *, allow_empty: bool = False) -> str:
        value = body.get(name)
        if not isinstance(value, str) or (not allow_empty and not value.strip()):
            raise APIError(f"{name} must be a non-empty string")
        return value

    @staticmethod
    def _tab_id(body: dict) -> int | str:
        value = body.get("tabId")
        if isinstance(value, bool) or not isinstance(value, (int, str)) or value == "":
            raise APIError("tabId must be an integer or non-empty string")
        return value

    def do_OPTIONS(self):
        self._send({"ok": True})

    def do_GET(self):
        try:
            url = urlparse(self.path)
            if url.path == "/health":
                self._send(self.quill.health())
            elif url.path == "/recording/status":
                self._send(self.quill.status())
            elif url.path == "/transcript":
                raw = parse_qs(url.query, keep_blank_values=True).get("since", ["0"])[0]
                try:
                    since = int(raw)
                except ValueError:
                    raise APIError("since must be a non-negative integer") from None
                if since < 0:
                    raise APIError("since must be a non-negative integer")
                self._send(self.quill.transcript(since))
            else:
                self._send({"error": "no route"}, 404)
        except APIError as e:
            self._send({"error": str(e)}, e.status)
        except Exception as e:
            traceback.print_exc()
            self._send({"error": str(e)}, 500)

    def do_POST(self):
        try:
            url = urlparse(self.path)
            body = self._body()
            if url.path == "/meeting/detected":
                self._string(body, "platform")
                if "title" in body:
                    self._string(body, "title", allow_empty=True)
                meeting_url = self._string(body, "url")
                self._send(self.quill.meeting_detected(
                    self._tab_id(body), meeting_url))
            elif url.path == "/meeting/ignore":
                meeting_url = self._string(body, "url")
                automatic = body.get("automatic", False)
                if not isinstance(automatic, bool):
                    raise APIError("automatic must be a boolean")
                self._send(self.quill.ignore(
                    self._tab_id(body), meeting_url, automatic=automatic))
            elif url.path == "/meeting/tab-clear":
                self._send(self.quill.clear_tab(self._tab_id(body)))
            elif url.path == "/recording/start":
                platform = self._string(body, "platform")
                title = self._string(body, "title", allow_empty=True)
                url_value = self._string(body, "url")
                self._send(self.quill.start(platform, title, url_value))
            elif url.path == "/recording/stop":
                recording_id = self._string(body, "recordingId")
                self._send(self.quill.stop(recording_id))
            else:
                self._send({"error": "no route"}, 404)
        except APIError as e:
            self._send({"error": str(e)}, e.status)
        except Exception as e:
            traceback.print_exc()
            self._send({"error": str(e)}, 500)


def serve() -> None:
    """Serve the extension API until interrupted. Always binds to loopback."""
    quill = QuillServer()
    httpd = _HTTPServer((HOST, PORT), _Handler)
    httpd.quill = quill

    def _terminate(_signum, _frame):
        threading.Thread(target=httpd.shutdown, name="quill-server-shutdown").start()

    old_term = signal.signal(signal.SIGTERM, _terminate)
    print(f"Quill extension server listening on http://{HOST}:{PORT}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGTERM, old_term)
        httpd.server_close()
        quill.close()


if __name__ == "__main__":
    serve()
