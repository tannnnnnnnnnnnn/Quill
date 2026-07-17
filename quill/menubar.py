"""Quill menu bar app. Run: uv run python -m quill.menubar

Call detection: Core Audio tells us which process is capturing the mic
(no permissions needed); a known call app sustained for ~6-9s → popup card.
While recording, a floating panel shows the live transcript. After
processing, a card offers Open note / Delete everything."""

import subprocess
import threading
import time
import traceback
from pathlib import Path

import rumps
from PyObjCTools.AppHelper import callAfter

from . import config, dashboard, janitor, live, micwatch, process, record, transcribe


class QuillBar(rumps.App):
    def __init__(self):
        icon = config.PROJECT / "assets" / "menubar.png"
        self.has_icon = icon.exists()
        if self.has_icon:
            super().__init__("Quill", icon=str(icon), template=True,
                             quit_button=rumps.MenuItem("Quit"))
        else:
            super().__init__("Quill", title="🪶", quit_button=rumps.MenuItem("Quit"))
        self.toggle_item = rumps.MenuItem("Start Recording", callback=self.toggle, key="s")
        self.state_item = rumps.MenuItem("idle")
        self.state_item.set_callback(None)
        self.open_item = rumps.MenuItem("Open Meeting Notes", callback=self.open_notes)
        self.dash_item = rumps.MenuItem("Open Dashboard", callback=self.open_dashboard, key="d")
        self.ask_item = rumps.MenuItem("Ask Quill…", callback=self.ask_quill, key="a")
        self.todo_item = rumps.MenuItem("Open TODO", callback=self.open_todo)
        self.detect_item = rumps.MenuItem("Call Detection", callback=self.toggle_detect)
        self.detect_item.state = 1
        self.live_item = rumps.MenuItem("Hide Live Transcript", callback=self.toggle_live)
        self.menu = [self.toggle_item, self.state_item, None,
                     self.dash_item, self.ask_item, self.todo_item, self.open_item, None,
                     self.detect_item, self.live_item]
        threading.Thread(target=dashboard.serve, daemon=True).start()
        self.processing = False
        self.detect_enabled = True
        self.live_visible = True   # auto-open the panel for each new recording
        self.prompt_armed = True
        self.prompting = False
        self.busy_ticks = 0
        self.quiet_ticks = 0
        self.popup = None
        self.note_popup = None
        self.answer_panel = None
        self.last_meeting = None
        self.live_panel = None
        self.live_stop = None
        self._sync()
        threading.Thread(target=self._startup_checks, daemon=True).start()

    def _startup_checks(self):
        problems = []
        try:
            transcribe._ffmpeg()
        except Exception as e:
            problems.append(f"ffmpeg: {e}")
        if not config.APP.exists():
            problems.append("Audiocap.app missing — run `make build`")
        if not config.VAULT.exists():
            problems.append(f"vault missing: {config.VAULT}")
        try:
            process._claude()
        except SystemExit as e:
            problems.append(str(e))
        if problems:
            print("selfcheck FAILED: " + " | ".join(problems), flush=True)
            process.notify("Quill — setup issue", problems[0])
        else:
            print("selfcheck ok", flush=True)
        live.preload_model()

    # ---------- status ----------

    def _set_status_title(self, text, amber_dot=False):
        """Status-item title; amber recording dot + mono digits when possible."""
        self.title = text
        if not text:
            return
        try:
            from Foundation import NSMutableAttributedString, NSAttributedString
            from AppKit import (NSColor, NSFont, NSFontAttributeName,
                                NSForegroundColorAttributeName)
            att = NSMutableAttributedString.alloc().init()
            if amber_dot:
                att.appendAttributedString_(
                    NSAttributedString.alloc().initWithString_attributes_(
                        " ● ", {NSFontAttributeName: NSFont.systemFontOfSize_(10),
                                NSForegroundColorAttributeName:
                                NSColor.colorWithCalibratedRed_green_blue_alpha_(
                                    1.0, 0.77, 0.42, 1.0)}))
            att.appendAttributedString_(
                NSAttributedString.alloc().initWithString_attributes_(
                    text.strip().lstrip("● "),
                    {NSFontAttributeName:
                     NSFont.monospacedDigitSystemFontOfSize_weight_(12, 0.0),
                     NSForegroundColorAttributeName: NSColor.labelColor()}))
            self._nsapp.nsstatusitem.button().setAttributedTitle_(att)
        except Exception:
            pass

    def _sync(self):
        st = record.current()
        if st:
            t0 = time.mktime(time.strptime(st["started"], "%Y-%m-%dT%H:%M:%S"))
            el = int(time.time() - t0)
            clock = (f"{el // 3600}:{el % 3600 // 60:02d}:{el % 60:02d}"
                     if el >= 3600 else f"{el // 60}:{el % 60:02d}")
            self._set_status_title(f" ● {clock}" if self.has_icon else f"🪶 ● {clock}",
                                   amber_dot=True)
            self.toggle_item.title = "Stop & Process"
            t12 = time.strftime("%-I:%M %p", time.strptime(st["started"],
                                                           "%Y-%m-%dT%H:%M:%S"))
            self.state_item.title = f"recording since {t12}"
            if self.live_panel is not None and self.live_stop is not None:
                self.live_panel.setClock_(clock)
        elif self.processing:
            self._set_status_title(" …" if self.has_icon else "🪶 …")
            self.toggle_item.title = "Processing…"
            self.state_item.title = "transcribing / summarizing"
        else:
            self.title = None if self.has_icon else "🪶"
            self.toggle_item.title = "Start Recording"
            self.state_item.title = "idle"

    # ---------- manual control ----------

    def toggle(self, _):
        if self.processing:
            return
        if record.current():
            self._stop_and_process()
        else:
            try:
                record.start()
                self._start_live()
            except SystemExit as e:
                rumps.alert("Quill", str(e))
        self._sync()

    def _stop_and_process(self):
        st = record.stop()
        self._stop_live()
        self.processing = True
        self._sync()
        threading.Thread(target=self._run_pipeline, args=(st["dir"],), daemon=True).start()

    def _run_pipeline(self, d):
        try:
            transcribe.run(d, progress=lambda *_: None)
            note = process.run(d, progress=lambda *_: None)
            if note:
                callAfter(self._show_note_card, d, note)
            else:
                process.notify("Quill — error",
                               "processing produced no note — see claude.log")
        except BaseException as e:  # SystemExit included — surface, don't die
            traceback.print_exc()
            process.notify("Quill — error", str(e)[:120])
        finally:
            self.processing = False
            self._sync()

    def _show_note_card(self, d, note):
        from .panels import NotePopup
        self.last_meeting = (d, note)
        if self.note_popup is None:
            self.note_popup = NotePopup.alloc().initWithCallback_(self._note_action)
        # subtitle: "<title> · 32 min · 6 action items"
        title = Path(note).stem
        if len(title) > 11 and title[:4].isdigit():
            title = title[11:]
        parts = [title]
        try:
            import json
            meta = json.loads((Path(d) / "meta.json").read_text())
            parts.append(f"{meta.get('duration_minutes', 0):g} min")
        except Exception:
            pass
        try:
            n = Path(note).read_text().count("- [ ]")
            parts.append(f"{n} action item{'s' if n != 1 else ''}")
        except Exception:
            pass
        self.note_popup.showWithTitle_(" · ".join(parts))

    def _note_action(self, action):
        if not self.last_meeting:
            return
        d, note = self.last_meeting
        if action == "open":
            subprocess.run(["open", note])
        elif action == "delete":
            threading.Thread(target=self._delete_meeting, args=(d, note),
                             daemon=True).start()

    def _delete_meeting(self, d, note):
        try:
            janitor.delete_meeting(d, note)
            process.notify("Quill", "meeting deleted — note, transcript, todos, audio")
            print(f"deleted meeting {d}", flush=True)
        except Exception as e:
            process.notify("Quill — error", f"delete failed: {e}")

    def open_notes(self, _):
        subprocess.run(["open", str(config.NOTES_DIR)])

    def open_dashboard(self, _):
        subprocess.run(["open", dashboard.URL])

    def open_todo(self, _):
        from urllib.parse import quote
        r = subprocess.run(
            ["open", f"obsidian://open?vault={quote(config.VAULT.name)}&file=TODO"],
            capture_output=True)
        if r.returncode != 0:
            subprocess.run(["open", str(config.TODO)])

    def ask_quill(self, _):
        w = rumps.Window("Ask about your meetings, decisions, or todos:",
                         "Ask Quill", ok="Ask", cancel="Cancel",
                         dimensions=(340, 80))
        resp = w.run()
        if not resp.clicked or not resp.text.strip():
            return
        q = resp.text.strip()
        from .panels import AnswerPanel
        if self.answer_panel is None:
            self.answer_panel = AnswerPanel.alloc().init()
        self.answer_panel.showQuestion_(q)
        threading.Thread(target=self._run_ask, args=(q,), daemon=True).start()

    def _run_ask(self, q):
        try:
            a = process.ask(q)
        except Exception as e:
            a = f"error: {e}"
        callAfter(self.answer_panel.setAnswer_, a)

    def toggle_detect(self, _):
        self.detect_enabled = not self.detect_enabled
        self.detect_item.state = 1 if self.detect_enabled else 0

    def toggle_live(self, _):
        # hide/show ONLY affects visibility — while recording, the loop keeps
        # transcribing in the background so reopen shows full history
        if self.live_visible:
            self.live_visible = False
            if self.live_panel is not None:
                self.live_panel.hide()
        else:
            self.live_visible = True
            if self.live_panel is not None:
                self.live_panel.show()
            if record.current() and self.live_stop is None:
                self._start_live()
        self._live_menu()

    def _live_menu(self):
        self.live_item.title = ("Hide Live Transcript" if self.live_visible
                                else "Show Live Transcript")

    # ---------- live transcript ----------

    def _start_live(self):
        st = record.current()
        if not st or self.live_stop is not None:
            return
        from .panels import LivePanel
        if self.live_panel is None:
            self.live_panel = LivePanel.alloc().initWithCloser_(self._panel_closed)
        self.live_dir = st["dir"]
        t0 = time.mktime(time.strptime(st["started"], "%Y-%m-%dT%H:%M:%S"))
        self.live_panel.reset()
        if self.live_visible:
            self.live_panel.show()
        self.live_stop = threading.Event()
        threading.Thread(target=live.live_loop,
                         args=(st["dir"], t0, self._emit_live, self.live_stop),
                         daemon=True).start()

    def _emit_live(self, line):
        if not str(line).startswith("◌"):   # draft ticks would spam the log
            print(f"live: {line}", flush=True)
        if self.live_panel is not None:
            callAfter(self.live_panel.appendLine_, line)

    def _pause_live(self):
        """Stop transcribing but keep the panel contents for reopening."""
        if self.live_stop is not None:
            self.live_stop.set()
            self.live_stop = None

    def _panel_closed(self):
        # ✕ clicked: hide only — transcription continues in the background
        self.live_visible = False
        self._live_menu()

    def _stop_live(self):
        self._pause_live()
        if self.live_panel is not None:
            self.live_panel.hide()
        self.live_visible = True   # next recording auto-opens again
        self._live_menu()

    # ---------- call detection ----------

    def _detect(self):
        if (not self.detect_enabled or self.processing or self.prompting
                or record.current()):
            return
        caller = micwatch.mic_caller()
        if caller and caller[0] != "?":
            if self.busy_ticks == 0:
                print(f"detect: mic held by {caller[0]} ({caller[1]})", flush=True)
            self.busy_ticks += 1
            self.quiet_ticks = 0
        else:
            if caller and self.quiet_ticks == 0:
                print(f"detect: mic held by unknown app, not prompting: {caller[1]}",
                      flush=True)
            self.quiet_ticks += 1
            self.busy_ticks = 0
            if not self.prompt_armed and self.quiet_ticks >= 10:
                self.prompt_armed = True   # caller gone ~30s → allow next prompt
        if self.prompt_armed and self.busy_ticks >= 2:   # ~6-9s sustained
            ctx = caller[0]
            if ctx == "Chrome":
                # optional refinement via tab URLs; harmless if not authorized
                ctx = micwatch.chrome_meeting() or "Chrome"
            self.prompt_armed = False
            self.prompting = True
            print(f"detect: popup ({ctx})", flush=True)
            from .panels import CallPopup
            if self.popup is None:
                self.popup = CallPopup.alloc().initWithCallback_(self._popup_done)
            self.ctx = ctx
            self.popup.showWithContext_(ctx)

    def _popup_done(self, accepted):
        self.prompting = False
        if accepted and not record.current():
            threading.Thread(target=self._start_from_popup, daemon=True).start()

    def _start_from_popup(self):
        try:
            record.start(f"{self.ctx} call")
            callAfter(self._start_live)
            callAfter(self._sync)
            print("detect: recording started", flush=True)
        except SystemExit as e:
            print(f"detect: start failed: {e}", flush=True)

    @rumps.timer(3)
    def _tick(self, _):
        self._sync()
        st = record.current()
        if st:
            # loop left over from a previous recording → replace it
            if (self.live_stop is not None
                    and getattr(self, "live_dir", None) != st["dir"]):
                self._pause_live()
            # attach the live loop to any recording, however it was started
            # (runs even while the panel is hidden — reopen shows history)
            if self.live_stop is None and not self.processing:
                self._start_live()
        elif self.live_stop is not None and not self.processing:
            # recording ended outside the menu (CLI etc.) → clean up
            print("live: recording ended externally — stopping loop", flush=True)
            self._stop_live()
        self._detect()


def main():
    QuillBar().run()


if __name__ == "__main__":
    main()
