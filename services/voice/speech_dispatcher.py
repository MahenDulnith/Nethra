"""L1/L3 Speech Dispatcher — Single exit point for spoken audio.

Enforces:
1. phrasebook.yaml key lookups and forbidden phrases check (no 'safe to cross' assurances).
2. Cooldown timer management (prevents chatter and alert fatigue).
3. Ears-Free policy enforcement.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from contracts.safety_alert import SafetyAlert, Tier
from services.voice.offline_tts import OfflineTtsEngine


class SpeechDispatcher:
    """The unified, single exit point for all synthesized speech across Nethra."""

    FORBIDDEN_PHRASES = [
        "safe to cross",
        "safe to go",
        "it's safe",
        "it is safe",
        "you can cross",
        "you can go now",
        "road is clear",
        "nothing is coming",
        "all clear",
        "as you can see",
        "look at",
        "over there",
        "you can walk",
        "path is clear",
        "nothing in your way",
    ]

    def __init__(
        self,
        phrasebook_path: str = "config/phrasebook.yaml",
        tts_engine: Optional[OfflineTtsEngine] = None,
        enabled: bool = True,
        use_clock_face: bool = True,
        max_staleness_sec: float = 1.0,
    ) -> None:
        self.enabled = enabled
        self.use_clock_face = use_clock_face
        self.max_staleness_sec = max_staleness_sec
        self.tts = tts_engine or OfflineTtsEngine()
        self.phrasebook: Dict[str, Any] = self._load_phrasebook(phrasebook_path)
        self.last_speech_time: Dict[str, float] = {}
        self.last_spoken_text: Optional[str] = None

    def _load_phrasebook(self, path: str) -> Dict[str, Any]:
        p = Path(path)
        if not p.exists():
            return {}
        try:
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as exc:
            print(f"[SpeechDispatcher] Warning: Could not read phrasebook: {exc}")
            return {}

    def lookup_phrase(self, speech_key: str, **kwargs: Any) -> Optional[str]:
        """Resolves a dot-separated or direct speech_key against phrasebook.yaml."""
        if not speech_key or not self.phrasebook:
            return None

        # 1. Direct safety/critical keys (e.g. safety.critical.left -> safety.critical_LEFT)
        parts = speech_key.split(".")
        if len(parts) >= 2:
            section = parts[0]
            sub = parts[1]
            rest = "_".join(parts[2:]).upper() if len(parts) > 2 else ""

            if section in self.phrasebook and isinstance(self.phrasebook[section], dict):
                cat = self.phrasebook[section]
                direct_candidate = f"{sub}_{rest}" if rest else sub
                if direct_candidate in cat:
                    text = cat[direct_candidate]
                    return text.format(**kwargs) if kwargs else text
                if sub in cat:
                    text = cat[sub]
                    return text.format(**kwargs) if kwargs else text

        return None

    def is_safe_to_speak(self, text: str) -> bool:
        """Verifies text against forbidden safety phrases."""
        lower = text.lower()
        for forbidden in self.FORBIDDEN_PHRASES:
            if forbidden in lower:
                print(f"[SpeechDispatcher BLOCKED] Forbidden safety assurance detected: '{forbidden}'")
                return False
        return True

    def dispatch_alert(
        self, alert: SafetyAlert, cooldown_sec: float = 3.0
    ) -> Optional[str]:
        """Dispatches a SafetyAlert to speech if eligible under Ears-Free policy."""
        if not self.enabled:
            return None

        # Drop stale frames to prevent speaking outdated safety alerts (for epoch timestamps > 2001)
        if alert.frame_timestamp_ns > 1_000_000_000_000_000_000:
            staleness = (time.time_ns() - alert.frame_timestamp_ns) / 1e9
            if staleness > self.max_staleness_sec:
                return None

        now = time.time()
        direction = alert.direction_sector.value.lower()
        obj = alert.object_class.lower()

        # Cooldown by object + sector (e.g. "door_centre_left" or "table_right")
        obj_sector_key = f"{obj}_{direction}"
        last_obj_time = self.last_speech_time.get(obj_sector_key, 0.0)

        key = alert.speech_key or f"safety.{alert.tier.value.lower()}.{direction}"
        last_time = self.last_speech_time.get(key, 0.0)

        # Critical alerts override cooldown after 1.5s; advisory/social obeys configured cooldown
        effective_cooldown = 1.5 if alert.tier == Tier.CRITICAL else cooldown_sec
        if (now - last_time) < effective_cooldown or (now - last_obj_time) < effective_cooldown:
            return None

        # Construct natural, real-time alert directly from the detected live object
        clean_obj = alert.object_class.replace("_", " ").capitalize()

        if self.use_clock_face:
            clock = alert.direction_sector.clock_face
            if alert.tier == Tier.CRITICAL:
                phrase = f"Warning: {clean_obj} at {clock}."
            elif alert.tier == Tier.ADVISORY:
                phrase = f"{clean_obj} at {clock}."
            elif alert.tier == Tier.SOCIAL:
                phrase = f"{clean_obj} at {clock}."
            else:
                phrase = f"{clean_obj} at {clock}."
        else:
            dir_label = direction.replace("_", " ")
            if alert.tier == Tier.CRITICAL:
                phrase = f"Warning: {clean_obj}, {dir_label}."
            elif alert.tier == Tier.ADVISORY:
                phrase = f"{clean_obj} ahead on your {dir_label}."
            elif alert.tier == Tier.SOCIAL:
                phrase = f"{clean_obj} detected {dir_label}."
            else:
                phrase = f"{clean_obj}, {dir_label}."

        spoken = self.say(phrase, key=key, interrupt=(alert.tier == Tier.CRITICAL))
        if spoken:
            self.last_speech_time[obj_sector_key] = now
        return spoken

    def say(
        self, text: str, key: Optional[str] = None, interrupt: bool = False
    ) -> Optional[str]:
        """Validates and sends text to the TTS engine."""
        if not self.enabled or not text:
            return None

        now = time.time()
        # Suppress identical consecutive phrases spoken within 3.0 seconds
        if text == self.last_spoken_text and (now - self.last_speech_time.get(text, 0.0)) < 3.0:
            return None

        if not self.is_safe_to_speak(text):
            return None

        self.tts.speak(text, interrupt=interrupt)
        now_ts = time.time()
        if key:
            self.last_speech_time[key] = now_ts
        self.last_speech_time[text] = now_ts
        self.last_spoken_text = text
        return text

    def stop(self) -> None:
        """Stops ongoing speech."""
        self.tts.stop()

    def shutdown(self) -> None:
        """Shuts down speech subsystem."""
        self.tts.shutdown()
