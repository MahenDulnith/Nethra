"""User commands: keyboard triggers now, and an intent parser ready for offline voice input."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Keyboard shortcuts that start a guided search
FIND_KEYS = {
    ord("f"): "door",
    ord("b"): "bottle",
    ord("p"): "person",
}


@dataclass
class Intent:
    action: str  # "find" | "cancel" | "where_am_i" | "unknown"
    target: Optional[str] = None


_FIND_PATTERNS = [
    r"(?:help me )?find (?:the |my |a |an )?(?P<target>[a-z ]+)",
    r"where(?: is|'s) (?:the |my |a |an )?(?P<target>[a-z ]+)",
    r"(?:look for|locate|search for) (?:the |my |a |an )?(?P<target>[a-z ]+)",
]


def parse_intent(text: str) -> Intent:
    """Maps a spoken sentence (e.g. from Whisper) to an action and target object."""
    t = re.sub(r"[^a-z' ]", " ", text.lower())
    t = re.sub(r"\s+", " ", t).strip()
    if re.search(r"\b(stop|cancel|never mind|nevermind)\b", t):
        return Intent("cancel")
    if re.search(r"\bwhere am i\b", t):
        return Intent("where_am_i")
    for pattern in _FIND_PATTERNS:
        m = re.search(pattern, t)
        if m:
            target = re.sub(r"\b(please|for me|now)\b", "", m.group("target")).strip()
            if target.endswith("s") and not target.endswith("ss"):
                target = target[:-1]  # "doors" -> "door"
            if target:
                return Intent("find", target)
    return Intent("unknown")
