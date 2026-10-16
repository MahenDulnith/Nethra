"""L3 Conversational Voice Agent Orchestrator for Nethra.

Handles spoken transcripts from the L1 Push-to-Talk microphone adapter,
routes parsed intents to L4 Guided Search, Room/Location Classifier, or
Live Spatial Scene Summarizer, and dispatches safe spoken responses via L3 SpeechDispatcher.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from contracts.detection import Detection
from features.context_routines.context_tracker import ContextSceneTracker
from features.lookaround.commands import Intent, parse_intent
from features.lookaround.guidance import GuidanceStateMachine
from services.voice.speech_dispatcher import SpeechDispatcher


@dataclass
class VoiceAgentResponse:
    """Result of handling a spoken user command."""

    intent: Intent
    spoken_text: str
    hud_toast: str
    location_banner: Optional[str] = None


def _format_count_label(label: str, count: int) -> str:
    clean = label.replace("_", " ")
    if count == 1:
        article = "an" if clean[:1].lower() in "aeiou" else "a"
        return f"{article} {clean}"
    if clean.endswith("s"):
        return f"{count} {clean}"
    return f"{count} {clean}s"


def _join_natural(items: List[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


class VoiceAgent:
    """Interactive voice assistant for hands-free object search and scene description."""

    @staticmethod
    def summarize_scene(detections: Sequence[Detection]) -> Tuple[str, str]:
        """Builds a natural spatial summary of all objects currently in view.

        Returns:
            (spoken_summary, hud_summary)
        """
        if not detections:
            spoken = "I do not see any obstacles in view right now."
            hud = "Scene: No objects in view"
            return spoken, hud

        total_counts = Counter(d.label for d in detections)
        total_parts = [_format_count_label(lbl, cnt) for lbl, cnt in total_counts.most_common(5)]
        overview = f"I see {_join_natural(total_parts)}."

        zone_clauses: List[str] = []
        for zone_key, zone_phrase in (
            ("LEFT", "on your left"),
            ("CENTER", "straight ahead"),
            ("RIGHT", "on your right"),
        ):
            zone_counts = Counter(d.label for d in detections if d.zone == zone_key)
            if zone_counts:
                parts = [_format_count_label(lbl, cnt) for lbl, cnt in zone_counts.most_common(3)]
                zone_clauses.append(f"{_join_natural(parts)} {zone_phrase}")

        if zone_clauses:
            spoken = f"{overview} There is {'; '.join(zone_clauses)}."
        else:
            spoken = overview

        hud_items = [f"{cnt}x {lbl}" for lbl, cnt in total_counts.most_common(4)]
        hud = f"Scene: {', '.join(hud_items)}"
        return spoken, hud

    def handle_transcript(
        self,
        transcript: str,
        detections: Sequence[Detection],
        guidance_sm: GuidanceStateMachine,
        context_tracker: ContextSceneTracker,
        speech: SpeechDispatcher,
        now: Optional[float] = None,
    ) -> VoiceAgentResponse:
        """Parses a spoken transcript and executes the corresponding Nethra workflow."""
        ts = now if now is not None else time.time()
        intent = parse_intent(transcript)

        if intent.action == "find" and intent.target:
            out = guidance_sm.start(intent.target, now=ts)
            spoken = out.speech or f"Looking for the {intent.target}."
            speech.say(spoken, interrupt=True)
            return VoiceAgentResponse(
                intent=intent,
                spoken_text=spoken,
                hud_toast=f'Voice: "{transcript}" -> Find {intent.target.upper()}',
            )

        if intent.action == "describe_scene":
            spoken, hud_scene = self.summarize_scene(detections)
            speech.say(spoken, interrupt=True)
            return VoiceAgentResponse(
                intent=intent,
                spoken_text=spoken,
                hud_toast=f'Voice: "{transcript}"',
                location_banner=hud_scene,
            )

        if intent.action == "where_am_i":
            spoken, hud_loc = context_tracker.query_location_details(list(detections))
            speech.say(spoken, interrupt=True)
            return VoiceAgentResponse(
                intent=intent,
                spoken_text=spoken,
                hud_toast=f'Voice: "{transcript}"',
                location_banner=hud_loc,
            )

        if intent.action == "cancel":
            out_cancel = guidance_sm.cancel(now=ts)
            spoken = out_cancel.speech or "Guidance stopped."
            speech.say(spoken, interrupt=True)
            return VoiceAgentResponse(
                intent=intent,
                spoken_text=spoken,
                hud_toast="Voice: Guidance Cancelled",
            )

        if intent.action == "mute":
            speech.enabled = False
            speech.stop()
            return VoiceAgentResponse(
                intent=intent,
                spoken_text="Audio muted.",
                hud_toast="Voice: Audio Muted",
            )

        if intent.action == "unmute":
            speech.enabled = True
            spoken = "Voice audio active."
            speech.say(spoken, interrupt=True)
            return VoiceAgentResponse(
                intent=intent,
                spoken_text=spoken,
                hud_toast="Voice: Audio Active",
            )

        spoken = (
            f"I heard {transcript}. "
            "You can say find the door, find my bottle, what do you see, or where am I."
        )
        speech.say(spoken, interrupt=True)
        return VoiceAgentResponse(
            intent=intent,
            spoken_text=spoken,
            hud_toast=f'Heard: "{transcript}" (Unrecognized command)',
        )
