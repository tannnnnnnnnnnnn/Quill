"""Decoder-loop gating, keyed to lines measured on a real silent-mic call
(~/Meetings/2026-07-26-2105-meet). Room noise sat above SILENCE_RMS, so the
level gate passed it through and the loops reached the meeting note.
"""

import unittest

from quill import bleedguard


class TestIsDegenerate(unittest.TestCase):
    def test_single_word_loop(self):
        self.assertTrue(bleedguard.is_degenerate("Jon " * 200))

    def test_phrase_loop(self):
        self.assertTrue(
            bleedguard.is_degenerate(
                "I'll give her my risk of that. " * 4))

    def test_short_repetition_is_speech(self):
        # people really do say this; too short to judge
        self.assertFalse(bleedguard.is_degenerate("Okay, okay, okay."))
        self.assertFalse(bleedguard.is_degenerate("No no no"))

    def test_real_speech_survives(self):
        for line in (
            "Let us lock the launch date before we wrap.",
            "The quarterly report is due on Thursday afternoon.",
            "I will send the timeline tonight and loop in the design team.",
            "Okay, I want to check if the transcript is actually good and if "
            "you're able to understand what I'm saying properly.",
        ):
            self.assertFalse(bleedguard.is_degenerate(line), line)

    def test_emphatic_repetition_survives(self):
        # varied enough to be speech, long enough to be judged
        self.assertFalse(
            bleedguard.is_degenerate(
                "I really really really think we should ship this today"))


class TestDropEchoes(unittest.TestCase):
    def _segs(self, *texts):
        return [{"text": t, "start": i, "end": i + 1}
                for i, t in enumerate(texts)]

    def test_drops_a_run_of_identical_lines(self):
        kept = bleedguard.drop_echoes(
            self._segs("I'll be right back.", "I'll be right back.",
                       "I'll be right back.", "Ship it."))
        self.assertEqual([s["text"] for s in kept], ["Ship it."])

    def test_keeps_a_pair(self):
        texts = ["Okay.", "Okay.", "Ship it."]
        kept = bleedguard.drop_echoes(self._segs(*texts))
        self.assertEqual([s["text"] for s in kept], texts)

    def test_keeps_non_adjacent_repeats(self):
        texts = ["Okay.", "Ship it.", "Okay.", "Ship it.", "Okay."]
        kept = bleedguard.drop_echoes(self._segs(*texts))
        self.assertEqual([s["text"] for s in kept], texts)

    def test_ignores_punctuation_and_case(self):
        kept = bleedguard.drop_echoes(
            self._segs("Okay, okay", "okay okay!", "OKAY OKAY.", "Ship it."))
        self.assertEqual([s["text"] for s in kept], ["Ship it."])

    def test_empty(self):
        self.assertEqual(bleedguard.drop_echoes([]), [])


if __name__ == "__main__":
    unittest.main()
