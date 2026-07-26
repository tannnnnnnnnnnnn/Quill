"""meet init — write per-user settings and the login agent.

Settings land in ~/.config/quill/config.json (see config.SETTINGS_PATH), so
nothing about a particular machine is baked into the repo.
"""

import json
import shutil
from pathlib import Path

from . import config

AGENT = Path.home() / "Library" / "LaunchAgents" / "com.quill.menubar.plist"

PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
\t<key>Label</key>
\t<string>com.quill.menubar</string>
\t<key>ProgramArguments</key>
\t<array>
\t\t<string>{uv}</string>
\t\t<string>run</string>
\t\t<string>--project</string>
\t\t<string>{project}</string>
\t\t<string>python</string>
\t\t<string>-m</string>
\t\t<string>quill.menubar</string>
\t</array>
\t<key>RunAtLoad</key>
\t<true/>
\t<key>KeepAlive</key>
\t<false/>
\t<key>StandardErrorPath</key>
\t<string>/tmp/quill-menubar.log</string>
</dict>
</plist>
"""


def _ask(label: str, default: str) -> str:
    reply = input(f"{label} [{default}]: ").strip()
    return reply or default


def run(login_agent: bool = True) -> None:
    print("Quill setup — press Enter to accept each default.\n")

    name = _ask("Your first name (used to spot bleed between tracks)", "")
    vault = _ask("Notes folder (an Obsidian vault works well)",
                 str(Path.home() / "Documents" / "Quill"))
    data = _ask("Recordings folder (audio, kept out of the notes folder)",
                str(Path.home() / "Meetings"))

    settings = {"user_name": name, "vault": vault, "data": data}
    config.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.SETTINGS_PATH.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"\nwrote {config.SETTINGS_PATH}")

    for d in (Path(vault).expanduser() / "Meetings" / "Transcripts",
              Path(vault).expanduser() / "People",
              Path(data).expanduser()):
        d.mkdir(parents=True, exist_ok=True)
    print(f"created {vault} and {data}")
    print("\nOptional next step: `meet enroll` records 24 seconds of your voice, "
          "so whatever else the microphone hears in the room is not quoted as you.")

    if not login_agent:
        return
    uv = shutil.which("uv")
    if not uv:
        print("\nuv not found on PATH — skipping the login agent. Install uv, "
              "then re-run `meet init`.")
        return
    AGENT.parent.mkdir(parents=True, exist_ok=True)
    AGENT.write_text(PLIST.format(uv=uv, project=config.PROJECT))
    print(f"wrote {AGENT}\n\nStart the menu bar app at login with:\n"
          f"  launchctl load {AGENT}")
