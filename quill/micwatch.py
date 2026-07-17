"""Call detection: is the default input device live, and which meeting app is running."""

import ctypes
import subprocess

_ca = ctypes.CDLL("/System/Library/Frameworks/CoreAudio.framework/CoreAudio")


class _AOPA(ctypes.Structure):
    _fields_ = [
        ("mSelector", ctypes.c_uint32),
        ("mScope", ctypes.c_uint32),
        ("mElement", ctypes.c_uint32),
    ]


_SYSTEM_OBJECT = 1
_GLOBAL = int.from_bytes(b"glob", "big")


def _get_u32(obj_id: int, selector: bytes):
    addr = _AOPA(int.from_bytes(selector, "big"), _GLOBAL, 0)
    val = ctypes.c_uint32(0)
    size = ctypes.c_uint32(4)
    err = _ca.AudioObjectGetPropertyData(
        obj_id, ctypes.byref(addr), 0, None, ctypes.byref(size), ctypes.byref(val))
    return None if err else val.value


def mic_in_use() -> bool:
    """True when any process is pulling from the default input device."""
    dev = _get_u32(_SYSTEM_OBJECT, b"dIn ")   # kAudioHardwarePropertyDefaultInputDevice
    if not dev:
        return False
    return bool(_get_u32(dev, b"gone"))       # kAudioDevicePropertyDeviceIsRunningSomewhere


def _mic_pids() -> list[int]:
    """PIDs currently capturing audio input (Core Audio process objects).
    Needs no permissions and attributes the mic to a specific process."""
    sel = int.from_bytes(b"prs#", "big")      # kAudioHardwarePropertyProcessObjectList
    addr = _AOPA(sel, _GLOBAL, 0)
    size = ctypes.c_uint32(0)
    if _ca.AudioObjectGetPropertyDataSize(_SYSTEM_OBJECT, ctypes.byref(addr),
                                          0, None, ctypes.byref(size)):
        return []
    n = size.value // 4
    if not n:
        return []
    arr = (ctypes.c_uint32 * n)()
    addr = _AOPA(sel, _GLOBAL, 0)
    size = ctypes.c_uint32(ctypes.sizeof(arr))
    if _ca.AudioObjectGetPropertyData(_SYSTEM_OBJECT, ctypes.byref(addr),
                                      0, None, ctypes.byref(size), ctypes.byref(arr)):
        return []
    pids = []
    for oid in arr:
        running = _get_u32(oid, b"piri")      # kAudioProcessPropertyIsRunningInput
        if not running:
            continue
        pid = ctypes.c_int32(0)
        a = _AOPA(int.from_bytes(b"ppid", "big"), _GLOBAL, 0)
        s = ctypes.c_uint32(4)
        if _ca.AudioObjectGetPropertyData(oid, ctypes.byref(a), 0, None,
                                          ctypes.byref(s), ctypes.byref(pid)) == 0:
            pids.append(pid.value)
    return pids


# hold the mic legitimately but are never a call
IGNORE_SUBSTRINGS = ("corespeechd", "Audiocap", "Wispr", "assistantd",
                     "siriactionsd", "mediaanalysisd", "Voice Memos")

CALLER_SUBSTRINGS = (
    ("Google Chrome", "Chrome"),
    ("Microsoft Teams", "Teams"),
    ("zoom.us", "Zoom"),
    ("FaceTime", "FaceTime"),
    ("Safari", "Safari"),
    ("Microsoft Edge", "Edge"),
    ("firefox", "Firefox"),
    ("Arc.app", "Arc"),
    ("Discord", "Discord"),
    ("Slack", "Slack"),
    ("Webex", "Webex"),
    ("WhatsApp", "WhatsApp"),
    ("Telegram", "Telegram"),
)


def _proc_paths(pids: list[int]) -> dict[int, str]:
    if not pids:
        return {}
    r = subprocess.run(["ps", "-p", ",".join(map(str, pids)), "-o", "pid=,comm="],
                       capture_output=True, text=True)
    out = {}
    for line in r.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            out[int(parts[0])] = parts[1]
    return out


def mic_caller() -> tuple[str, str] | None:
    """(label, exe_path) of the call app using the mic; label '?' if the app is
    unknown. None = mic idle or held only by ignorable processes."""
    paths = _proc_paths(_mic_pids())
    unknown = None
    for path in paths.values():
        if any(ig in path for ig in IGNORE_SUBSTRINGS):
            continue
        for pat, lab in CALLER_SUBSTRINGS:
            if pat in path:
                return lab, path
        unknown = path
    return ("?", unknown) if unknown else None


MEETING_APPS = {
    "us.zoom.xos": "Zoom",
    "com.microsoft.teams2": "Teams",
    "com.microsoft.teams": "Teams",
    "com.apple.FaceTime": "FaceTime",
    "Cisco-Systems.Spark": "Webex",
    "com.webex.meetingmanager": "Webex",
    "com.hnc.Discord": "Discord",
    "com.tinyspeck.slackmacgap": "Slack",
}


def meeting_app() -> str | None:
    from AppKit import NSWorkspace
    for app in NSWorkspace.sharedWorkspace().runningApplications():
        name = MEETING_APPS.get(app.bundleIdentifier() or "")
        if name:
            return name
    return None


CHROME_MEETING_HOSTS = (
    ("teams.cloud.microsoft", "Teams (web)"),
    ("teams.microsoft.com", "Teams (web)"),
    ("teams.live.com", "Teams (web)"),
    ("meet.google.com", "Meet"),
    ("zoom.us/wc", "Zoom (web)"),
    ("app.zoom.us", "Zoom (web)"),
)

_CHROME_TABS_SCRIPT = '''tell application "Google Chrome"
	if it is not running then return ""
	set out to ""
	repeat with w in windows
		repeat with t in tabs of w
			set out to out & (URL of t) & linefeed
		end repeat
	end repeat
	return out
end tell'''


def chrome_meeting() -> str | None:
    """Meeting label if a Chrome tab is on a known meeting site. Needs the
    one-time Automation permission (python → Chrome)."""
    try:
        r = subprocess.run(["osascript", "-e", _CHROME_TABS_SCRIPT],
                           capture_output=True, text=True, timeout=6)
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0:
        return None
    for host, label in CHROME_MEETING_HOSTS:
        if host in r.stdout:
            return label
    return None


def detect_call() -> str | None:
    """Context label when a call seems active alongside the live mic."""
    return meeting_app() or chrome_meeting()
