"""Scene context: wake-up recognition and location queries."""

from __future__ import annotations

import time
from typing import List, Optional

from .detection import Detection


class ContextSceneTracker:
    """Maintains scene awareness, wake-up recognition, and location context."""

    def __init__(self):
        self.bed_seen_frames = 0
        self.morning_greeting_active = False
        self.last_greeting_time = 0.0
        self.greeting_cooldown_sec = 60.0  # Announce once per minute max
        self.assumed_location = "University of Sri Jayewardenepura (Faculty of Applied Sciences)"

    def update(self, detections: List[Detection]) -> Optional[str]:
        """Analyzes detected objects to infer context and scene status."""
        current_time = time.time()
        has_bed = any(d.label.lower() == "bed" for d in detections)
        if has_bed:
            self.bed_seen_frames += 1
            if self.bed_seen_frames > 10 and current_time - self.last_greeting_time > self.greeting_cooldown_sec:
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
        labels = sorted({d.label for d in detections})
        detected_summary = ", ".join(labels) if labels else "no immediate objects"
        return f"Location: {self.assumed_location} | In view: {detected_summary}"
