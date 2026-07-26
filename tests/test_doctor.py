"""`meet doctor` is what a new install is judged by, so its failure paths matter
more than its happy path — a first-time user meets this command precisely when
something is wrong.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from quill import config, doctor


class TestChecks(unittest.TestCase):
    def test_reports_a_missing_recorder_rather_than_recording(self):
        # capture() would raise SystemExit on a missing app; doctor has to say
        # "run make build" instead of failing inside a recording attempt
        with mock.patch.object(config, "APP", Path("/nonexistent/Audiocap.app")), \
             mock.patch("quill.record.capture") as capture:
            lines = []
            problems = doctor.run(progress=lambda *a, **k: lines.append(" ".join(map(str, a))))
        capture.assert_not_called()
        self.assertGreaterEqual(problems, 1)
        self.assertTrue(any("make build" in ln for ln in lines))
        self.assertTrue(any("skipping the recording test" in ln for ln in lines))

    def test_every_check_carries_a_remedy(self):
        for ok, label, remedy in doctor._checks():
            if not ok:
                self.assertTrue(remedy, f"{label} failed with no remedy")

    def test_both_permission_panes_have_a_settings_url(self):
        for key in ("mic", "sys"):
            label, url = doctor.PANES[key]
            self.assertTrue(label)
            self.assertTrue(url.startswith("x-apple.systempreferences:"))


class TestRms(unittest.TestCase):
    def test_unreadable_audio_scores_zero_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.caf"
            empty.write_bytes(b"")
            self.assertEqual(doctor._rms(empty), 0.0)

    def test_silence_is_below_the_floor(self):
        import wave
        with tempfile.TemporaryDirectory() as tmp:
            quiet = Path(tmp) / "quiet.wav"
            with wave.open(str(quiet), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(16000)
                w.writeframes(b"\x00\x00" * 16000)
            self.assertLess(doctor._rms(quiet), doctor.FLOOR)


if __name__ == "__main__":
    unittest.main()
