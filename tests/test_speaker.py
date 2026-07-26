"""Speaker verification: feature layout, threshold calibration, profile I/O.

The model itself is not exercised here — it is a 26 MB download and its
accuracy was measured separately (0.99 cosine within a speaker, 0.14 across
two distinct voices). What these tests protect is the code around it, where a
silent mistake would poison every profile.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from quill import speaker


def _speech(seconds=3.0, sr=speaker.SR, f0=120.0):
    """A voiced-sounding tone stack — enough structure for the filterbank."""
    t = np.arange(int(seconds * sr)) / sr
    x = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in (1, 2, 3, 4))
    return (x * 6000).astype(np.float32)


class TestFbank(unittest.TestCase):
    def test_shape_is_80_dim_at_10ms_hop(self):
        feats = speaker.fbank(_speech(3.0))
        self.assertIsNotNone(feats)
        self.assertEqual(feats.shape[1], 80)
        self.assertEqual(feats.shape[0], 1 + (3 * speaker.SR - 400) // 160)
        self.assertEqual(feats.dtype, np.float32)

    def test_mean_normalised_per_band(self):
        feats = speaker.fbank(_speech(3.0))
        np.testing.assert_allclose(feats.mean(axis=0), 0, atol=1e-3)

    def test_too_short_is_undecidable(self):
        self.assertIsNone(speaker.fbank(_speech(speaker.MIN_SECONDS / 2)))

    def test_silence_is_undecidable(self):
        self.assertIsNone(speaker.fbank(np.zeros(3 * speaker.SR, dtype=np.float32)))

    def test_filterbank_covers_the_band(self):
        # every bin from the low edge up is reachable, no dead mel channels
        self.assertTrue((speaker._FB.sum(axis=1) > 0).all())


class TestCalibrate(unittest.TestCase):
    def _unit(self, *vals):
        v = np.array(vals, dtype=np.float64)
        return v / np.linalg.norm(v)

    def test_centroid_is_unit_length(self):
        centroid, _ = speaker.calibrate(
            [self._unit(1, 0.1, 0), self._unit(1, 0, 0.1), self._unit(0.9, 0.1, 0.1)])
        self.assertAlmostEqual(float(np.linalg.norm(centroid)), 1.0, places=6)

    def test_threshold_stays_within_bounds(self):
        tight = [self._unit(1, 0, 0)] * 5                    # identical windows
        loose = [self._unit(1, 0, 0), self._unit(0, 1, 0),
                 self._unit(0, 0, 1), self._unit(1, 1, 1)]   # scattered
        for vectors in (tight, loose):
            _, threshold = speaker.calibrate(vectors)
            self.assertGreaterEqual(threshold, speaker.FLOOR)
            self.assertLessEqual(threshold, speaker.CEILING)

    def test_a_variable_voice_earns_a_looser_gate(self):
        tight = [self._unit(1, 0.02 * i, 0) for i in range(5)]
        loose = [self._unit(1, 0, 0), self._unit(0, 1, 0),
                 self._unit(0, 0, 1), self._unit(1, 1, 1)]
        self.assertGreater(speaker.calibrate(tight)[1], speaker.calibrate(loose)[1])


class TestProfile(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = mock.patch.object(
            speaker, "PROFILE_PATH", Path(self._tmp.name) / "voice-profile.npz")
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_missing_profile_is_none(self):
        self.assertIsNone(speaker.load_profile())

    def test_round_trip(self):
        centroid = np.arange(256, dtype=np.float32)
        centroid /= np.linalg.norm(centroid)
        speaker.save_profile(centroid, 0.47)
        loaded, threshold = speaker.load_profile()
        np.testing.assert_allclose(loaded, centroid)
        self.assertAlmostEqual(threshold, 0.47, places=6)

    def test_corrupt_profile_is_none_not_a_crash(self):
        # a truncated write must disable the gate, never abort transcription
        speaker.PROFILE_PATH.write_bytes(b"not an npz")
        self.assertIsNone(speaker.load_profile())

    def test_describe_points_at_enroll_when_unenrolled(self):
        self.assertIn("meet enroll", speaker.describe())


class TestIsMe(unittest.TestCase):
    """is_me routes the embedding, so stub the model and check the decision."""

    def _profile(self):
        centroid = np.zeros(256, dtype=np.float32)
        centroid[0] = 1.0
        return centroid, 0.5

    def test_match_above_threshold(self):
        vec = np.zeros(256, dtype=np.float32)
        vec[0] = 1.0
        with mock.patch.object(speaker, "embed", return_value=vec):
            self.assertTrue(speaker.is_me(_speech(), self._profile()))

    def test_other_voice_below_threshold(self):
        vec = np.zeros(256, dtype=np.float32)
        vec[1] = 1.0
        with mock.patch.object(speaker, "embed", return_value=vec):
            self.assertFalse(speaker.is_me(_speech(), self._profile()))

    def test_unusable_audio_is_undecidable(self):
        with mock.patch.object(speaker, "embed", return_value=None):
            self.assertIsNone(speaker.is_me(_speech(0.2), self._profile()))


if __name__ == "__main__":
    unittest.main()
