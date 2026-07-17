"""Local dashboard: meetings, summaries, ask, todos — served on localhost,
reading and writing the same vault files Obsidian shows."""

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import config, janitor, process

_enhancing: set = set()

PORT = 8477
URL = f"http://127.0.0.1:{PORT}"


def _meetings():
    idx = config.NOTES_DIR / "INDEX.md"
    out = []
    if idx.exists():
        for line in idx.read_text().splitlines():
            if line.startswith("- ") and "[[" in line and "]]" in line:
                name = line.split("[[")[1].split("]]")[0]
                summary = line.split("]]", 1)[1].lstrip(" —-").strip()
                out.append({"date": line[2:12], "name": name, "summary": summary})
    out.sort(key=lambda m: (m["date"], m["name"]), reverse=True)
    return out


def _safe_read(base, name):
    """Read <base>/<name>.md only if it resolves inside base."""
    p = (base / f"{name}.md").resolve()
    if p.parent != base.resolve() or not p.exists():
        return None
    return p.read_text()


def _todos():
    open_, done = [], []
    if config.TODO.exists():
        for line in config.TODO.read_text().splitlines():
            ls = line.strip()
            if ls.startswith("- [ ]"):
                open_.append(line)
            elif ls.startswith(("- [x]", "- [X]")):
                done.append(line)
    return {"open": open_, "done": done}


def _toggle_todo(line):
    if not config.TODO.exists():
        return False
    lines = config.TODO.read_text().splitlines()
    for i, l in enumerate(lines):
        if l == line:
            if "- [ ]" in l:
                lines[i] = l.replace("- [ ]", "- [x]", 1)
            else:
                lines[i] = l.replace("- [x]", "- [ ]", 1).replace("- [X]", "- [ ]", 1)
            config.TODO.write_text("\n".join(lines) + "\n")
            return True
    return False


def _add_todo(text):
    text = " ".join(text.split())
    if not text:
        return False
    if not config.TODO.exists():
        config.TODO.write_text("# TODO\n\n## Inbox\n")
    lines = config.TODO.read_text().splitlines()
    entry = f"- [ ] {text}"
    for i, l in enumerate(lines):
        if l.strip() == "## Inbox":
            lines.insert(i + 1, entry)
            break
    else:
        lines += ["", "## Inbox", entry]
    config.TODO.write_text("\n".join(lines) + "\n")
    return True


def _delete_todo(line):
    if not config.TODO.exists():
        return False
    lines = config.TODO.read_text().splitlines()
    if line not in lines:
        return False
    lines.remove(line)
    config.TODO.write_text("\n".join(lines) + "\n")
    return True


def _delete_meeting(name):
    """Remove a meeting everywhere: note, transcript, TODO/INDEX lines, audio."""
    note = (config.NOTES_DIR / f"{name}.md").resolve()
    if note.parent != config.NOTES_DIR.resolve() or not note.exists():
        return False
    m = re.search(r"\[\[Transcripts/([^\]]+)\]\]", note.read_text())
    rec = config.DATA / (m.group(1) if m else "__none__")
    janitor.delete_meeting(str(rec), str(note))
    return True


def _enhance_meeting(name):
    """Re-run transcription + processing from the stored audio (better models
    over time). Replaces the note/transcript/TODO/INDEX entries in place."""
    note = (config.NOTES_DIR / f"{name}.md").resolve()
    if note.parent != config.NOTES_DIR.resolve() or not note.exists():
        return "note not found"
    m = re.search(r"\[\[Transcripts/([^\]]+)\]\]", note.read_text())
    if not m:
        return "no transcript link in note"
    rec = config.DATA / m.group(1)
    if not any((rec / f"{t}{ext}").exists()
               for t in ("me", "them") for ext in (".caf", ".m4a")):
        return "audio no longer exists for this meeting"
    if name in _enhancing:
        return "already enhancing"
    _enhancing.add(name)

    def _work():
        from . import transcribe
        try:
            janitor.delete_meeting(str(rec), str(note), keep_audio=True)
            transcribe.run(str(rec), progress=lambda *_: None)
            new_note = process.run(str(rec), progress=lambda *_: None)
            process.notify("Quill", f"enhanced: {new_note or rec.name}")
        except BaseException as e:
            process.notify("Quill — error", f"enhance failed: {str(e)[:100]}")
        finally:
            _enhancing.discard(name)

    threading.Thread(target=_work, daemon=True).start()
    return None


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, obj, code=200, ctype="application/json"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/":
            html = (config.PROJECT / "assets" / "dashboard.html").read_bytes()
            self._send(html, ctype="text/html; charset=utf-8")
        elif u.path == "/api/meetings":
            self._send(_meetings())
        elif u.path == "/api/note":
            c = _safe_read(config.NOTES_DIR, q.get("name", [""])[0])
            self._send({"content": c} if c is not None else {"error": "not found"},
                       200 if c is not None else 404)
        elif u.path == "/api/transcript":
            c = _safe_read(config.TRANSCRIPTS_DIR, q.get("name", [""])[0])
            self._send({"content": c} if c is not None else {"error": "not found"},
                       200 if c is not None else 404)
        elif u.path == "/api/todos":
            self._send(_todos())
        else:
            self._send({"error": "no route"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            self._send({"error": "bad json"}, 400)
            return
        if self.path == "/api/todo":
            self._send({"ok": _toggle_todo(body.get("line", ""))})
        elif self.path == "/api/todo/add":
            self._send({"ok": _add_todo(body.get("text", ""))})
        elif self.path == "/api/todo/delete":
            self._send({"ok": _delete_todo(body.get("line", ""))})
        elif self.path == "/api/meeting/delete":
            self._send({"ok": _delete_meeting(body.get("name", ""))})
        elif self.path == "/api/meeting/enhance":
            err = _enhance_meeting(body.get("name", ""))
            self._send({"ok": err is None, "error": err})
        elif self.path == "/api/ask":
            question = (body.get("q") or "").strip()
            if not question:
                self._send({"error": "empty"}, 400)
                return
            try:
                self._send({"answer": process.ask(question)})
            except Exception as e:
                self._send({"error": str(e)}, 500)
        else:
            self._send({"error": "no route"}, 404)


def serve() -> None:
    """Blocking; run on a daemon thread. Localhost only."""
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), _Handler).serve_forever()
    except OSError as e:
        print(f"dashboard: not started ({e})", flush=True)


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    try:
        ThreadingHTTPServer(("127.0.0.1", port), _Handler).serve_forever()
    except KeyboardInterrupt:
        pass
