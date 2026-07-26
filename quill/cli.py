"""meet — record, transcribe, and process meetings.

  meet init
  meet doctor
  meet enroll [--from-file F]
  meet start [--title T] [--max-hours H]
  meet stop [--no-process]
  meet status
  meet transcribe <dir>
  meet process <dir>
  meet serve
"""

import argparse
import sys
from pathlib import Path

from . import config, process, record, transcribe


def _pipeline(d: str) -> None:
    transcribe.run(d)
    note = process.run(d)
    process.notify("Meeting processed",
                   Path(note).stem if note else "see claude.log")
    if note:
        print(f"\nnote ready: {note}")


def main() -> None:
    p = argparse.ArgumentParser(prog="meet", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="write per-user settings and the login agent")
    s.add_argument("--no-login-agent", action="store_true")

    sub.add_parser("doctor", help="check the install and prove recording works")

    s = sub.add_parser("enroll", help="record a voice sample so your track keeps "
                                      "your speech and not the room's")
    s.add_argument("--from-file", default=None,
                   help="use an existing recording instead of the microphone")

    s = sub.add_parser("start", help="start recording")
    s.add_argument("--title", default=None)
    s.add_argument("--max-hours", type=float, default=config.MAX_HOURS)

    s = sub.add_parser("stop", help="stop recording and process")
    s.add_argument("--no-process", action="store_true")

    sub.add_parser("status")
    for name in ("transcribe", "process"):
        s = sub.add_parser(name, help=f"{name} an existing recording dir")
        s.add_argument("dir")

    s = sub.add_parser("ask", help="answer a question from your meeting records")
    s.add_argument("question", nargs="+")

    sub.add_parser("dashboard", help="open the Quill dashboard in your browser")
    sub.add_parser("menubar", help="run the menu bar app in this terminal")
    sub.add_parser("serve", help="serve the local browser-extension API")

    a = p.parse_args()
    if a.cmd == "init":
        from . import init
        init.run(login_agent=not a.no_login_agent)
    elif a.cmd == "doctor":
        from . import doctor
        sys.exit(1 if doctor.run() else 0)
    elif a.cmd == "enroll":
        from . import speaker
        used, threshold = speaker.enroll(
            Path(a.from_file).expanduser() if a.from_file else None)
        print(f"voice profile saved → {speaker.PROFILE_PATH}\n"
              f"{used} windows, match threshold {threshold:.2f}")
    elif a.cmd == "start":
        d = record.start(a.title, a.max_hours)
        print(f"recording → {d}\nstop with: meet stop")
    elif a.cmd == "stop":
        st = record.stop()
        print(f"stopped ({st['duration_minutes']} min)")
        if not a.no_process:
            _pipeline(st["dir"])
    elif a.cmd == "status":
        st = record.current()
        print(f"recording since {st['started']} → {st['dir']}" if st else "idle")
        from . import speaker
        print(speaker.describe())
    elif a.cmd == "transcribe":
        transcribe.run(a.dir)
    elif a.cmd == "process":
        note = process.run(a.dir)
        if note:
            print(f"note: {note}")
    elif a.cmd == "ask":
        print("thinking (30-60s)...")
        print(process.ask(" ".join(a.question)))
    elif a.cmd == "dashboard":
        from . import dashboard
        import subprocess as sp
        sp.run(["open", dashboard.URL])
    elif a.cmd == "menubar":
        from . import menubar
        menubar.main()
    elif a.cmd == "serve":
        from . import server
        server.serve()
    sys.exit(0)


if __name__ == "__main__":
    main()
