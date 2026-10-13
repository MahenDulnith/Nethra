"""L4 Contextual Scene & Routine Tracker (Wake-up detection & Location queries)."""

from __future__ import annotations

import time
from typing import List, Optional

from contracts.detection import Detection


class ContextSceneTracker:
    """Maintains scene awareness, wake-up recognition, and location context."""

    def __init__(
        self,
        assumed_location: str = "University of Sri Jayewardenepura (Faculty of Applied Sciences)",
        greeting_cooldown_sec: float = 60.0,
    ) -> None:
        self.bed_seen_frames = 0
        self.morning_greeting_active = False
        self.last_greeting_time = 0.0
        self.greeting_cooldown_sec = greeting_cooldown_sec
        self.assumed_location = assumed_location

    def update(self, detections: List[Detection]) -> Optional[str]:
        """Analyzes detected objects to infer context and routine status."""
        labels = [d.label.lower() for d in detections]
        current_time = time.time()

        has_bed = any(lbl == "bed" for lbl in labels)
        if has_bed:
            self.bed_seen_frames += 1
            if self.bed_seen_frames > 10 and (
                current_time - self.last_greeting_time > self.greeting_cooldown_sec
            ):
                self.morning_greeting_active = True
                self.last_greeting_time = current_time
                return "Good morning! You are in your bed right now."
        else:
            self.bed_seen_frames = max(0, self.bed_seen_frames - 1)
            if self.bed_seen_frames == 0:
                self.morning_greeting_active = False

        return None

    def query_location(self, detections: List[Detection]) -> str:
        """Handles conversational 'Where am I?' query."""
        labels = sorted(list({d.label for d in detections}))
        detected_summary = ", ".join(labels) if labels else "no immediate objects"
        return f"Location: {self.assumed_location} | In view: {detected_summary}"
