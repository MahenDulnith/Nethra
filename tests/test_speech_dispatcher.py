"""Unit tests for Nethra Phase 4 Voice Subsystem (TTS & SpeechDispatcher)."""

import unittest
from contracts.safety_alert import DirectionSector, DistanceBucket, SafetyAlert, Tier
from services.voice.offline_tts import OfflineTtsEngine
from services.voice.speech_dispatcher import SpeechDispatcher


class MockTtsEngine(OfflineTtsEngine):
    """Mock TTS Engine that records spoken utterances without invoking audio hardware."""

    def __init__(self) -> None:
        self.spoken_phrases = []
        self._is_speaking = False

    def speak(self, text: str, interrupt: bool = False) -> None:
        if interrupt:
            self.spoken_phrases.clear()
        self.spoken_phrases.append(text)

    def stop(self) -> None:
        self.spoken_phrases.clear()

    def shutdown(self) -> None:
        pass


class TestSpeechDispatcher(unittest.TestCase):

    def setUp(self) -> None:
        self.mock_tts = MockTtsEngine()
        self.dispatcher = SpeechDispatcher(
            phrasebook_path="config/phrasebook.yaml",
            tts_engine=self.mock_tts,
            enabled=True,
        )

    def test_phrasebook_lookup(self) -> None:
        phrase = self.dispatcher.lookup_phrase("safety.critical.LEFT", obj="Car")
        self.assertEqual(phrase, "Car, left.")

        phrase_adv = self.dispatcher.lookup_phrase("safety.advisory.CENTRE", obj="Chair")
        self.assertEqual(phrase_adv, "Chair ahead.")

    def test_forbidden_safety_assurance_denied(self) -> None:
        # Assurance phrases must be strictly blocked by SpeechDispatcher
        self.assertFalse(self.dispatcher.is_safe_to_speak("It is safe to cross the road now."))
        self.assertFalse(self.dispatcher.is_safe_to_speak("All clear, you can walk."))
        self.assertTrue(self.dispatcher.is_safe_to_speak("Door on your left."))

        # Verify that forbidden phrases are NOT sent to TTS
        res = self.dispatcher.say("It is safe to cross")
        self.assertIsNone(res)
        self.assertEqual(len(self.mock_tts.spoken_phrases), 0)

    def test_dispatch_critical_alert(self) -> None:
        alert = SafetyAlert(
            tier=Tier.CRITICAL,
            object_class="car",
            direction_sector=DirectionSector.LEFT,
            distance_bucket=DistanceBucket.IMMEDIATE,
            ttc_seconds=1.2,
            track_age_frames=5,
            haptic_pattern_id="URGENT",
            speech_key="safety.critical.LEFT",
            produced_offline=True,
            frame_timestamp_ns=1000,
        )

        # Default clock-face format (10 o'clock for LEFT)
        spoken = self.dispatcher.dispatch_alert(alert)
        self.assertEqual(spoken, "Warning: Car at 10 o'clock.")
        self.assertIn("Warning: Car at 10 o'clock.", self.mock_tts.spoken_phrases)

        # Relative directions format
        relative_dispatcher = SpeechDispatcher(
            tts_engine=self.mock_tts,
            use_clock_face=False,
        )
        spoken_rel = relative_dispatcher.dispatch_alert(alert)
        self.assertEqual(spoken_rel, "Warning: Car, left.")

    def test_cooldown_suppression(self) -> None:
        alert = SafetyAlert(
            tier=Tier.ADVISORY,
            object_class="obstacle",
            direction_sector=DirectionSector.CENTRE,
            distance_bucket=DistanceBucket.NEAR,
            ttc_seconds=3.5,
            track_age_frames=4,
            haptic_pattern_id="OBSTACLE_NEAR",
            speech_key="safety.advisory.CENTRE",
            produced_offline=True,
            frame_timestamp_ns=1000,
        )

        # First alert speaks
        first = self.dispatcher.dispatch_alert(alert, cooldown_sec=5.0)
        self.assertIsNotNone(first)

        # Immediate repeat should be suppressed by cooldown
        second = self.dispatcher.dispatch_alert(alert, cooldown_sec=5.0)
        self.assertIsNone(second)


if __name__ == "__main__":
    unittest.main()
