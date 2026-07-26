"""Fuzzy text matching shared by live and final transcription for
echo-bleed dedupe (a speaker-audio sentence re-captured by the mic)."""

import difflib


def norm(t: str) -> str:
    return "".join(c for c in t.lower() if c.isalnum() or c == " ").strip()


def similar(a: str, b: str, threshold: float = 0.8) -> bool:
    """a, b already normalized. True when one is a copy/re-rendering of the other."""
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= threshold

# Cross-track copies of one utterance OVERLAP IN TIME (bleed/echo/fragments of
# the same speech), possibly with a small gap from segmentation jitter. Verbal
# repetition happens in a later turn — no overlap. So: dedupe when intervals
# overlap or sit within MAX_ECHO_GAP of each other, keep the earlier utterance.
MAX_ECHO_GAP = 0.5


import re as _re

def vocative(name: str, text: str) -> bool:
    """True when the line ADDRESSES `name` — a greeting or direct question to
    them. People don't address themselves, so a mic-track ("Me") line that
    matches is almost certainly bleed from the other side. Deliberately tight:
    "Hi Tanmay…" / "Tanmay, can you…" match; "This is Tanmay" does not.

    An empty `name` disables the guard — with no name to address, every
    greeting would otherwise match."""
    if not name.strip():
        return False
    name = _re.escape(name.strip())
    pat = _re.compile(
        rf"^\W{{0,4}}(?:(?:hi|hello|hey)[, ]+{name}\b"
        rf"|{name}[, ]+(?:can|could|are|do|did|what|how|is|will|would)\b)",
        _re.IGNORECASE)
    return bool(pat.match(text.strip()))
