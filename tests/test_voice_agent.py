"""Unit tests for Nethra L1 PushToTalkListener, L4 parse_intent, and L3 VoiceAgent."""

from __future__ import annotations

import unittest

from adapters.audio.mic_listener import PushToTalkListener
from contracts.detection import Detection
from features.context_routines.context_tracker import ContextSceneTracker
from features.lookaround.commands import parse_intent
from features.lookaround.guidance import GuidanceStateMachine
from services.agent.voice_agent import VoiceAgent
from services.voice.speech_dispatcher import SpeechDispatcher


def make_det(label: str, zone: str = "CENTER", cx: float = 320.0) -> Detection:
    return Detection(
        label=label,
        confidence=0.90,
        box=(int(cx - 40), 180, int(cx + 40), 340),
        center_x=cx,
        center_y=260.0,
        width=80.0,
        height=160.0,
        area_ratio=0.08,
        zone=zone,
        pwm_intensity=35.0,
    )


class TestVoiceAgentAndCommands(unittest.TestCase):

    def setUp(self) -> None:
        self.agent = VoiceAgent()
        self.guidance_sm = GuidanceStateMachine()
        self.context_tracker = ContextSceneTracker(location="home")
        self.speech = SpeechDispatcher(enabled=False)

    def test_natural_language_find_synonyms(self) -> None:
        cases = [
            ("Can you help me find the door please", "find", "door"),
            ("Where is my water bottle?", "find", "bottle"),
            ("Locate my MacBook", "find", "laptop"),
            ("I am looking for my mobile phone", "find", "cell phone"),
            ("Search for the cupboard", "find", "wardrobe"),
            ("Where are the beds?", "find", "bed"),
            ("door", "find", "door"),
        ]
        for phrase, expected_action, expected_target in cases:
            intent = parse_intent(phrase)
            self.assertEqual(intent.action, expected_action, f"Failed on: {phrase}")
            self.assertEqual(intent.target, expected_target, f"Failed target on: {phrase}")

    def test_scene_location_and_control_intents(self) -> None:
        self.assertEqual(parse_intent("What is in front of me?").action, "describe_scene")
        self.assertEqual(parse_intent("What do you see right now?").action, "describe_scene")
        self.assertEqual(parse_intent("Describe the room").action, "describe_scene")
        self.assertEqual(parse_intent("Where am I?").action, "where_am_i")
        self.assertEqual(parse_intent("What room is this?").action, "where_am_i")
        self.assertEqual(parse_intent("Please stop guidance").action, "cancel")
        self.assertEqual(parse_intent("Mute audio").action, "mute")
        self.assertEqual(parse_intent("Unmute voice").action, "unmute")

    def test_scene_summarizer_zones_and_safety(self) -> None:
        dets = [
            make_det("bed", zone="LEFT", cx=100.0),
            make_det("bed", zone="CENTER", cx=320.0),
            make_det("door", zone="CENTER", cx=350.0),
            make_det("bed", zone="RIGHT", cx=520.0),
        ]
        spoken, hud = self.agent.summarize_scene(dets)
        self.assertIn("3 beds", spoken)
        self.assertIn("a door", spoken)
        self.assertIn("on your left", spoken)
        self.assertIn("straight ahead", spoken)
        self.assertIn("on your right", spoken)
        self.assertTrue(self.speech.is_safe_to_speak(spoken))
        self.assertIn("3x bed", hud)

        empty_spoken, _ = self.agent.summarize_scene([])
        self.assertTrue(self.speech.is_safe_to_speak(empty_spoken))

    def test_voice_agent_workflow_orchestration(self) -> None:
        dets = [make_det("bed", zone="LEFT"), make_det("chair", zone="RIGHT")]

        # 1. Start search via voice
        res_find = self.agent.handle_transcript(
            transcript="Help me find my laptop",
            detections=dets,
            guidance_sm=self.guidance_sm,
            context_tracker=self.context_tracker,
            speech=self.speech,
            now=10.0,
        )
        self.assertEqual(res_find.intent.action, "find")
        self.assertEqual(res_find.intent.target, "laptop")
        self.assertTrue(self.guidance_sm.active)
        self.assertEqual(self.guidance_sm.target_name, "laptop")

        # 2. Describe scene via voice
        res_scene = self.agent.handle_transcript(
            transcript="What do you see?",
            detections=dets,
            guidance_sm=self.guidance_sm,
            context_tracker=self.context_tracker,
            speech=self.speech,
            now=11.0,
        )
        self.assertEqual(res_scene.intent.action, "describe_scene")
        self.assertIn("bed", res_scene.spoken_text)
        self.assertIn("chair", res_scene.spoken_text)

        # 3. Cancel via voice
        res_cancel = self.agent.handle_transcript(
            transcript="Cancel search",
            detections=dets,
            guidance_sm=self.guidance_sm,
            context_tracker=self.context_tracker,
            speech=self.speech,
            now=12.0,
        )
        self.assertEqual(res_cancel.intent.action, "cancel")
        self.assertFalse(self.guidance_sm.active)

    def test_push_to_talk_listener_injection(self) -> None:
        listener = PushToTalkListener()
        listener.inject_transcript("find the door")
        transcript, err = listener.pop_result()
        self.assertEqual(transcript, "find the door")
        self.assertIsNone(err)
        # Second pop should be empty
        t2, e2 = listener.pop_result()
        self.assertIsNone(t2)
        self.assertIsNone(e2)


if __name__ == "__main__":
    unittest.main()
