"""The prompts are templates, and every user is a different person.

A hardcoded name here does not fail loudly — it produces a perfectly readable
meeting note written for the wrong person, in someone else's vault. Same for a
token that no longer gets substituted: `{{USER}}` reaching Claude verbatim is
silent, so it has to be caught here.
"""

import re
import unittest

from quill import config, process

PROMPTS = sorted((config.PROJECT / "prompts").glob("*.md"))
TOKEN = re.compile(r"\{\{[A-Z_]+\}\}")
# the tokens process.py knows how to fill, read off its own source
SUBSTITUTED = set(TOKEN.findall(
    (config.PROJECT / "quill" / "process.py").read_text()))


class TestPrompts(unittest.TestCase):
    def test_there_are_prompts_to_check(self):
        self.assertTrue(PROMPTS)

    def test_every_token_is_substituted(self):
        for p in PROMPTS:
            for token in TOKEN.findall(p.read_text()):
                self.assertIn(token, SUBSTITUTED, f"{p.name}: {token}")

    def test_no_hardcoded_person(self):
        # the author's name is the one that was actually in here; a generic
        # check is not possible, so guard the regression that happened
        for p in PROMPTS:
            self.assertNotIn("tanmay", p.read_text().lower(), p.name)

    def test_the_user_is_named_by_token_not_by_pronoun_guesswork(self):
        meeting = (config.PROJECT / "prompts" / "meeting.md").read_text()
        self.assertIn("{{USER}}", meeting)


class TestWho(unittest.TestCase):
    def test_falls_back_when_the_name_was_left_blank(self):
        # `meet init` accepts an empty name; the prompts still have to read
        self.assertTrue(config.WHO)

    def test_reads_correctly_in_a_possessive(self):
        # the prompts say "{{USER}}'s action items"
        self.assertFalse(config.WHO.endswith("s'"))
        self.assertFalse(config.WHO[0].isspace())


class TestSubstitution(unittest.TestCase):
    def test_ask_leaves_nothing_unfilled(self):
        prompt = (config.PROJECT / "prompts" / "ask.md").read_text()
        for k, v in {
            "{{QUESTION}}": "what did we decide?",
            "{{USER}}": config.WHO,
            "{{NOTES_DIR}}": str(config.NOTES_DIR),
            "{{TRANSCRIPTS_DIR}}": str(config.TRANSCRIPTS_DIR),
            "{{TODO}}": str(config.TODO),
            "{{PEOPLE_DIR}}": str(config.PEOPLE_DIR),
        }.items():
            prompt = prompt.replace(k, v)
        self.assertNotIn("{{", prompt)

    def test_process_exposes_a_user_token(self):
        self.assertIn("{{USER}}", SUBSTITUTED)
        self.assertIs(process.config, config)


if __name__ == "__main__":
    unittest.main()
