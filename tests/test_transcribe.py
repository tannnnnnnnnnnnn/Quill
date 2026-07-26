"""The speaker gate's wiring into the transcript run.

The gate's accuracy belongs to the model; what is tested here is that a
non-matching Me segment actually reaches the transcript as Them, that an
unenrolled machine is left completely alone, and that a short segment the
model cannot judge is kept rather than guessed at.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from quill import bleedguard, config, speaker, transcribe

ME = [{"start": 0.0, "end": 4.0, "text": "This is the user speaking."},
      {"start": 10.0, "end": 14.0, "text": "Someone else across the room."}]


class GateHarness(unittest.TestCase):
    """Run transcribe.run() with the audio stack stubbed out, so only the
    Me/Them routing is exercised."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name) / "rec"
        self.d.mkdir()
        (self.d / "me.caf").touch()
        # 20s of raw mic audio, well above the silence floor
        mic = np.full(20 * 16000, 4000, dtype=np.int16)

        self._patches = [
            mock.patch.object(transcribe, "_to_wav16", return_value=30.0),
            mock.patch.object(transcribe, "_transcribe_track",
                              side_effect=lambda wav: [dict(s) for s in ME]),
            mock.patch.object(bleedguard, "load_wav", return_value=(mic, 16000)),
            mock.patch.object(transcribe, "_cleanup_audio"),
            mock.patch.object(config, "TRANSCRIPTS_DIR",
                              Path(self._tmp.name) / "vault"),
            mock.patch.object(config, "USER_NAME", ""),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    def speakers(self) -> list[str]:
        transcribe.run(self.d, progress=lambda *a, **k: None)
        return [line.split("**")[1]
                for line in (self.d / "transcript.md").read_text().splitlines()
                if line.startswith("- **")]


class TestSpeakerGate(GateHarness):
    def test_a_voice_that_is_not_the_user_becomes_them(self):
        with mock.patch.object(speaker, "load_profile",
                               return_value=(np.zeros(256), 0.5)), \
             mock.patch.object(speaker, "is_me",
                               side_effect=[True, False]):
            self.assertEqual(self.speakers(), ["Me", "Them"])

    def test_no_profile_leaves_the_track_alone(self):
        with mock.patch.object(speaker, "load_profile", return_value=None), \
             mock.patch.object(speaker, "is_me") as is_me:
            self.assertEqual(self.speakers(), ["Me", "Me"])
        is_me.assert_not_called()

    def test_undecidable_audio_is_kept(self):
        # too short to embed → the gate must not guess the user away
        with mock.patch.object(speaker, "load_profile",
                               return_value=(np.zeros(256), 0.5)), \
             mock.patch.object(speaker, "is_me", return_value=None):
            self.assertEqual(self.speakers(), ["Me", "Me"])


if __name__ == "__main__":
    unittest.main()
