"""L4 User commands: keyboard triggers and natural-language voice intent parser."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional

# Keyboard shortcuts that start a guided search directly
FIND_KEYS: Dict[int, str] = {
    ord("f"): "door",
    ord("b"): "bottle",
    ord("p"): "person",
}

# Spoken synonyms mapped to canonical YOLO COCO-80 / Nethra Doors labels
SPOKEN_TARGET_SYNONYMS: Dict[str, str] = {
    "door": "door",
    "doors": "door",
    "exit": "door",
    "entrance": "door",
    "way out": "door",
    "doorway": "door",
    "bottle": "bottle",
    "water bottle": "bottle",
    "water": "bottle",
    "drink": "bottle",
    "cup": "cup",
    "mug": "cup",
    "glass": "cup",
    "chair": "chair",
    "seat": "chair",
    "stool": "chair",
    "bed": "bed",
    "beds": "bed",
    "mattress": "bed",
    "bunk": "bed",
    "sofa": "sofa",
    "couch": "sofa",
    "settee": "sofa",
    "table": "dining table",
    "dining table": "dining table",
    "desk": "dining table",
    "workstation": "dining table",
    "laptop": "laptop",
    "computer": "laptop",
    "macbook": "laptop",
    "notebook": "laptop",
    "pc": "laptop",
    "phone": "cell phone",
    "cell phone": "cell phone",
    "mobile": "cell phone",
    "mobile phone": "cell phone",
    "iphone": "cell phone",
    "smartphone": "cell phone",
    "tv": "tv",
    "television": "tv",
    "monitor": "tv",
    "screen": "tv",
    "display": "tv",
    "person": "person",
    "people": "person",
    "someone": "person",
    "friend": "person",
    "human": "person",
    "backpack": "backpack",
    "bag": "backpack",
    "school bag": "backpack",
    "rucksack": "backpack",
    "handbag": "handbag",
    "purse": "handbag",
    "suitcase": "suitcase",
    "luggage": "suitcase",
    "wardrobe": "wardrobe",
    "closet": "wardrobe",
    "cupboard": "wardrobe",
    "cabinet": "wardrobe",
    "locker": "wardrobe",
    "window": "window",
    "book": "book",
    "notebook": "book",
    "keyboard": "keyboard",
    "mouse": "mouse",
    "remote": "remote",
    "clock": "clock",
    "plant": "potted plant",
    "potted plant": "potted plant",
    "refrigerator": "refrigerator",
    "fridge": "refrigerator",
    "sink": "sink",
    "umbrella": "umbrella",
}


@dataclass
class Intent:
    """Structured representation of a parsed user voice or text command."""

    action: str  # "find" | "describe_scene" | "where_am_i" | "cancel" | "mute" | "unmute" | "unknown"
    target: Optional[str] = None
    raw_text: str = ""


_FIND_PATTERNS = [
    r"(?:can you |could you |please )?(?:help me )?(?:find|locate|search for|look for|spot|guide me to|take me to|point me to) (?:the |my |a |an |some )?(?P<target>[a-z ]+)",
    r"where(?: is|'s| are) (?:the |my |a |an )?(?P<target>[a-z ]+)",
    r"i(?:'m| am) looking for (?:the |my |a |an )?(?P<target>[a-z ]+)",
    r"i need (?:to find )?(?:the |my |a |an )?(?P<target>[a-z ]+)",
]

_SCENE_PATTERNS = [
    r"\bwhat(?:'s| is) (?:in front of|around|ahead of|near) me\b",
    r"\bwhat (?:do|can) you see\b",
    r"\bdescribe (?:the |this )?(?:room|scene|surroundings|area|view)\b",
    r"\blook around\b",
    r"\bscan (?:the )?(?:room|area|scene)\b",
    r"\bwhat is here\b",
    r"\bwhat objects\b",
]

_LOCATION_PATTERNS = [
    r"\bwhere am i\b",
    r"\bwhat (?:room|place|building|location) (?:is this|am i in)\b",
    r"\bcurrent location\b",
    r"\bmy location\b",
    r"\btell me where i am\b",
]


def normalize_target(raw_target: str) -> str:
    """Normalizes a spoken target phrase into a canonical YOLO class name."""
    cleaned = re.sub(
        r"\b(please|for me|right now|now|over there|in the room|in here|nearby|around here)\b",
        "",
        raw_target,
    ).strip()
    cleaned = re.sub(r"^(?:the|my|a|an|some)\s+", "", cleaned).strip()

    if cleaned in SPOKEN_TARGET_SYNONYMS:
        return SPOKEN_TARGET_SYNONYMS[cleaned]

    # Singularize simple plural ("chairs" -> "chair", "beds" -> "bed")
    if cleaned.endswith("s") and not cleaned.endswith("ss"):
        singular = cleaned[:-1]
        if singular in SPOKEN_TARGET_SYNONYMS:
            return SPOKEN_TARGET_SYNONYMS[singular]
        return singular

    return cleaned


def parse_intent(text: str) -> Intent:
    """Maps a spoken sentence (from microphone STT) to a structured Nethra Intent."""
    raw = (text or "").strip()
    t = re.sub(r"[^a-z0-9' ]", " ", raw.lower())
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return Intent("unknown", raw_text=raw)

    # 1. Cancel / Stop
    if re.search(r"\b(stop|cancel|never mind|nevermind|abort|quit search|exit search)\b", t):
        return Intent("cancel", raw_text=raw)

    # 2. Mute / Unmute
    if re.search(r"\b(unmute|speak again|turn on audio|turn on voice)\b", t):
        return Intent("unmute", raw_text=raw)
    if re.search(r"\b(mute|be quiet|silence|shut up|turn off audio)\b", t):
        return Intent("mute", raw_text=raw)

    # 3. Location / Room query ("Where am I?", "What room is this?")
    for pat in _LOCATION_PATTERNS:
        if re.search(pat, t):
            return Intent("where_am_i", raw_text=raw)

    # 4. Scene description ("What do you see?", "What is in front of me?", "Describe the room")
    for pat in _SCENE_PATTERNS:
        if re.search(pat, t):
            return Intent("describe_scene", raw_text=raw)

    # 5. Guided object search ("Find the door", "Where is my laptop?", etc.)
    for pattern in _FIND_PATTERNS:
        m = re.search(pattern, t)
        if m:
            target = normalize_target(m.group("target"))
            if target:
                return Intent("find", target=target, raw_text=raw)

    # 6. Single-word or two-word direct object command (e.g., user just says "door" or "my bottle")
    direct_candidate = normalize_target(t)
    if direct_candidate in SPOKEN_TARGET_SYNONYMS.values():
        return Intent("find", target=direct_candidate, raw_text=raw)

    return Intent("unknown", raw_text=raw)
