"""L4 Contextual Scene & Routine Tracker (Wake-up detection, Room Classifier & Location queries)."""

from __future__ import annotations

import json
import time
from collections import Counter, deque
from pathlib import Path
from typing import Deque, List, Optional, Set, Tuple

from contracts.detection import Detection

DEFAULT_LOCATIONS_FILE = Path(__file__).resolve().parents[2] / "config" / "locations.json"


class ContextSceneTracker:
    """Maintains scene awareness, micro-location room inference, and macro location context."""

    def __init__(
        self,
        location: Optional[str] = None,
        assumed_location: Optional[str] = None,
        greeting_cooldown_sec: float = 60.0,
    ) -> None:
        self.bed_seen_frames = 0
        self.morning_greeting_active = False
        self.last_greeting_time = 0.0
        self.greeting_cooldown_sec = greeting_cooldown_sec

        # Rolling history of recent detected labels (last 30 frames ~ 1 sec)
        self._history: Deque[Set[str]] = deque(maxlen=30)

        self.location_profiles = self._load_profiles()
        initial_loc = location or assumed_location or "cisco_lab"
        self.current_location_key = initial_loc
        self.location_title, self.location_address = self._resolve_location(initial_loc)
        self.assumed_location = self.location_address

    def _load_profiles(self) -> dict:
        if DEFAULT_LOCATIONS_FILE.exists():
            try:
                with open(DEFAULT_LOCATIONS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("profiles", {})
            except Exception:
                pass
        return {}

    def _resolve_location(self, loc_input: str) -> Tuple[str, str]:
        """Resolves location key (e.g. 'cisco_lab', 'home') or direct string into (title, spoken_address)."""
        if loc_input in self.location_profiles:
            p = self.location_profiles[loc_input]
            title = p.get("title", loc_input)
            addr = p.get("address", "")
            campus = p.get("campus", "")
            full = f"{addr}, {campus}" if campus else addr
            return title, full
        return loc_input, loc_input

    def set_location(self, loc_input: str) -> None:
        """Dynamically switches location profile."""
        self.current_location_key = loc_input
        self.location_title, self.location_address = self._resolve_location(loc_input)
        self.assumed_location = self.location_address

    def update(self, detections: List[Detection]) -> Optional[str]:
        """Analyzes detected objects to update history and scene status."""
        current_time = time.time()
        labels_in_frame = {d.label.lower() for d in detections}
        self._history.append(labels_in_frame)

        has_bed = "bed" in labels_in_frame
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

    def infer_room(self, detections: List[Detection]) -> Tuple[str, str]:
        """Infers the room / micro-space from current and recent detections."""
        recent_counts: Counter[str] = Counter()
        for frame_set in self._history:
            recent_counts.update(frame_set)

        current_labels = [d.label.lower() for d in detections]
        current_counts = Counter(current_labels)
        unique_labels = sorted(set(current_labels))

        laptop_count = current_counts.get("laptop", 0)
        chair_count = current_counts.get("chair", 0)
        person_count = current_counts.get("person", 0)

        # 1. Computer / Networking Lab (USJ Cisco Lab archetype)
        has_lab_hardware = any(recent_counts[k] > 3 for k in ("laptop", "keyboard", "mouse", "tv"))
        if (laptop_count >= 2) or (has_lab_hardware and (chair_count >= 2 or person_count >= 2)):
            return (
                "Computer Laboratory",
                "It looks like you are inside a computer laboratory, because I can see multiple workstations, chairs, and people around you.",
            )

        # 2. Study Room / Single Desk Workspace
        if (laptop_count == 1 or "keyboard" in current_labels or "book" in current_labels) and (
            "chair" in current_labels or "dining table" in current_labels
        ):
            return (
                "Study Workspace",
                "It looks like you are at your study desk, because I can see a laptop and a chair.",
            )

        # 3. Bedroom
        if any(recent_counts[k] > 2 for k in ("bed", "wardrobe", "pillow")):
            return (
                "Bedroom",
                "It looks like you are in your room, because I can see a bed around you.",
            )

        # 4. Living Room
        if any(recent_counts[k] > 2 for k in ("sofa", "couch")) or (
            "tv" in current_labels and "laptop" not in current_labels
        ):
            return (
                "Living Room",
                "It looks like you are in the living room, because I can see a sofa and television.",
            )

        # 5. Kitchen / Dining Area
        if any(recent_counts[k] > 2 for k in ("refrigerator", "microwave", "oven", "sink")):
            return (
                "Kitchen Area",
                "It looks like you are in the kitchen or dining area.",
            )

        # 6. Outdoors
        if any(
            recent_counts[k] > 2
            for k in ("car", "bus", "traffic light", "stop sign", "motorcycle", "bicycle")
        ):
            return (
                "Outdoors",
                "You appear to be outdoors near the street, because I can see road vehicles and signs.",
            )

        if unique_labels:
            items_str = ", ".join(unique_labels[:4])
            return ("Indoor Space", f"I can see a {items_str} around you.")
        return ("Indoor Space", "I cannot identify distinct furniture around you yet.")

    def query_location_details(self, detections: List[Detection]) -> Tuple[str, str]:
        """Returns (full_spoken_sentence, compact_hud_banner) for 'Where am I?' query."""
        room_name, room_desc = self.infer_room(detections)
        spoken_text = f"Your location is {self.location_address}. {room_desc}"
        hud_text = f"Location: {self.location_title} | {room_name}"
        return spoken_text, hud_text

    def query_location(self, detections: List[Detection]) -> str:
        """Handles conversational 'Where am I?' query (returns summary string)."""
        room_name, _ = self.infer_room(detections)
        labels = sorted(list({d.label for d in detections}))
        detected_summary = ", ".join(labels) if labels else "no immediate objects"
        return f"Location: {self.location_address} ({room_name}) | In view: {detected_summary}"
