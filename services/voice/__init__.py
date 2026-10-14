"""Nethra L1/L3 Voice Package — Offline TTS and Spoken Speech Dispatcher."""

from services.voice.offline_tts import OfflineTtsEngine
from services.voice.speech_dispatcher import SpeechDispatcher

__all__ = [
    "OfflineTtsEngine",
    "SpeechDispatcher",
]
