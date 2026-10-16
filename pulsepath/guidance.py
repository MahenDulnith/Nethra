"""Guided Search Mode: find an object, then steer the user's head and hand towards it.

Flow: NAVIGATION -> SEARCHING -> HEAD_GUIDE -> HAND_GUIDE <-> ALIGNED -> NAVIGATION

Steering convention (matches the user's mental model):
    target is LEFT of the reference (head centre or hand)  -> LEFT wristband pulses
    target is RIGHT of the reference                       -> RIGHT wristband pulses
    reference is on target                                  -> both bands double-pulse
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Deque, List, Optional, Sequence, Tuple

from .detection import Box, Detection, compute_iou

Point = Tuple[float, float]


class GuidanceState(str, Enum):
    IDLE = "NAVIGATION"
    SEARCHING = "SEARCHING"
    HEAD_GUIDE = "HEAD_GUIDE"
    HAND_GUIDE = "HAND_GUIDE"
    ALIGNED = "ALIGNED"


class GuidanceCommand(str, Enum):
    NONE = "NONE"
    SEARCHING = "SEARCHING"
    MOVE_LEFT = "MOVE_LEFT"
    MOVE_RIGHT = "MOVE_RIGHT"
    ALIGNED = "ALIGNED"
    LOST = "LOST"


# Spoken target name -> detector labels that satisfy it (COCO and HomeObjects use different names)
TARGET_ALIASES = {
    "door": {"door"},
    "sofa": {"sofa", "couch"},
    "couch": {"sofa", "couch"},
    "table": {"table", "dining table"},
    "phone": {"cell phone"},
    "cell phone": {"cell phone"},
    "plant": {"potted plant"},
    "tv": {"tv"},
    "television": {"tv"},
}

# Objects big enough that a rough "N steps away" estimate is meaningful
LARGE_OBJECTS = {"door", "wardrobe", "bed", "sofa", "couch", "table", "dining table",
                 "refrigerator", "person", "chair", "tv"}

ZONE_PHRASES = {"LEFT": "on your left", "RIGHT": "on your right", "CENTER": "straight ahead"}


def labels_for_target(target: str) -> set:
    target = target.lower().strip()
    return TARGET_ALIASES.get(target, {target})


def estimate_steps(area_ratio: float) -> int:
    """Very rough distance estimate in walking steps from how much of the frame a large object fills."""
    if area_ratio <= 0:
        return 99
    return max(1, round(1.6 / math.sqrt(area_ratio) - 1.5))


def with_article(word: str) -> str:
    return f"an {word}" if word[:1].lower() in "aeiou" else f"a {word}"


def natural_list(items: Sequence[str]) -> str:
    items = [with_article(i) for i in items]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


@dataclass
class GuidanceConfig:
    confirm_window: int = 8            # frames considered when confirming a new target
    confirm_hits: int = 5              # detections needed inside that window (filters flicker)
    lost_frames: int = 20              # consecutive misses before the target counts as lost
    head_tolerance: float = 0.12       # |error| (fraction of frame width) to count as centred
    hand_tolerance: float = 0.08       # |error| to count the hand as aligned
    hand_release_tolerance: float = 0.12  # hysteresis: leave ALIGNED only beyond this
    aligned_hold_frames: int = 4       # frames inside tolerance before declaring alignment
    hand_missing_frames: int = 15      # frames without a hand before falling back to head guidance
    arrive_area_ratio: float = 0.40    # target filling this much of the frame means "arrived"
    first_prompt_delay: float = 2.5    # seconds before the first "look around" prompt
    look_around_interval: float = 6.0  # seconds between "look around" prompts
    memory_seconds: float = 20.0       # how long the last-seen position is remembered
    search_timeout: float = 45.0       # give up searching after this many seconds
    smoothing: float = 0.5             # EMA factor for target and hand positions


@dataclass
class GuidanceOutput:
    state: GuidanceState
    command: GuidanceCommand = GuidanceCommand.NONE
    magnitude: float = 0.0              # normalised horizontal error, 0..0.5
    reference: str = ""                 # "head" or "hand"
    target_name: Optional[str] = None
    target: Optional[Detection] = None  # detection matched this frame
    target_box: Optional[Box] = None    # last known box (kept through brief dropouts)
    target_point: Optional[Point] = None
    hand_point: Optional[Point] = None
    speech: Optional[str] = None
    chime: Optional[str] = None         # "found" | "aligned" | "lost" | "done"

    @property
    def active(self) -> bool:
        return self.state != GuidanceState.IDLE


class GuidanceStateMachine:
    """Pure-logic state machine (no I/O) so it can be unit tested with synthetic detections."""

    def __init__(self, config: Optional[GuidanceConfig] = None):
        self.config = config or GuidanceConfig()
        self.state = GuidanceState.IDLE
        self.target_name: Optional[str] = None
        self.memory_target: Optional[str] = None
        self.memory_zone: Optional[str] = None
        self.memory_time: Optional[float] = None
        self._reset_tracking(now=0.0)

    # ------------------------------------------------------------------ public API
    @property
    def active(self) -> bool:
        return self.state != GuidanceState.IDLE

    @property
    def needs_hand_tracking(self) -> bool:
        return self.state in (GuidanceState.HEAD_GUIDE, GuidanceState.HAND_GUIDE, GuidanceState.ALIGNED)

    def start(self, target: str, now: float) -> GuidanceOutput:
        self.target_name = target.lower().strip()
        if self.memory_target != self.target_name:
            self.memory_target = self.memory_zone = self.memory_time = None
        self.state = GuidanceState.SEARCHING
        self._reset_tracking(now)
        return self._output(GuidanceCommand.SEARCHING, speech=f"Looking for the {self.target_name}.")

    def cancel(self, now: float, speech: str = "Guidance stopped.") -> GuidanceOutput:
        self.state = GuidanceState.IDLE
        self._reset_tracking(now)
        return GuidanceOutput(state=GuidanceState.IDLE, speech=speech, target_name=self.target_name)

    def update(
        self,
        detections: Sequence[Detection],
        hand_point: Optional[Point],
        frame_width: int,
        frame_height: int,
        now: float,
    ) -> GuidanceOutput:
        if self.state == GuidanceState.IDLE:
            return GuidanceOutput(state=GuidanceState.IDLE)

        match = self._find_target(detections)
        self.hit_window.append(match is not None)
        if match is not None:
            self.misses = 0
            self.tracked_box = match.box
            self.target_y = match.center_y
            self.target_x = self._smooth(self.target_x, match.center_x)
            self.memory_target, self.memory_zone, self.memory_time = self.target_name, match.zone, now
        else:
            self.misses += 1

        if hand_point is not None:
            self.hand_missing = 0
            self.hand = (self._smooth(self.hand[0] if self.hand else None, hand_point[0]), hand_point[1])
        else:
            self.hand_missing += 1
            self.hand = None

        if self.state == GuidanceState.SEARCHING:
            return self._update_searching(match, detections, frame_width, now)
        return self._update_guiding(match, frame_width, now)

    # ------------------------------------------------------------------ states
    def _update_searching(self, match: Optional[Detection], detections: Sequence[Detection],
                          frame_width: int, now: float) -> GuidanceOutput:
        cfg = self.config
        if match is not None and sum(self.hit_window) >= cfg.confirm_hits:
            self.state = GuidanceState.HEAD_GUIDE
            self.centered_frames = 0
            speech = f"{self.target_name.capitalize()} found {ZONE_PHRASES[match.zone]}{self._distance_phrase(match)}."
            if match.zone != "CENTER":
                speech += f" Turn {match.zone.lower()} slowly."
            out = self._steer(frame_width / 2.0, frame_width, "head", match, speech=speech)
            out.chime = "found"
            return out

        if now - self.search_started > cfg.search_timeout:
            out = self.cancel(now, speech=f"I could not find a {self.target_name}. Stopping the search.")
            out.chime = "lost"
            return out

        speech = None
        if now - self.last_prompt >= cfg.look_around_interval:
            self.last_prompt = now
            speech = self._look_around_message(detections, now)
        return self._output(GuidanceCommand.SEARCHING, speech=speech)

    def _update_guiding(self, match: Optional[Detection], frame_width: int, now: float) -> GuidanceOutput:
        cfg = self.config

        if self.misses >= cfg.lost_frames:
            zone_phrase = ZONE_PHRASES.get(self.memory_zone or "", "nearby")
            self.state = GuidanceState.SEARCHING
            self._reset_tracking(now, keep_box=False)
            return self._output(GuidanceCommand.LOST, chime="lost",
                                speech=f"I lost the {self.target_name}. It was {zone_phrase}.")

        if match is None:
            # Brief dropout: hold the previous command so the vibration does not stutter
            return self._output(self.last_command, magnitude=self.last_magnitude, reference=self.last_reference)

        if match.area_ratio >= cfg.arrive_area_ratio:
            out = self.cancel(now, speech=f"You have reached the {self.target_name}.")
            out.chime = "done"
            return out

        # Hand visible -> precise hand guidance; hand missing for a while -> head guidance
        if self.hand is not None and self.state == GuidanceState.HEAD_GUIDE:
            self.state = GuidanceState.HAND_GUIDE
            self.aligned_frames = 0
            return self._steer(self.hand[0], frame_width, "hand", match,
                               speech="I can see your hand. Follow the vibrations.")
        if self.hand is None and self.state in (GuidanceState.HAND_GUIDE, GuidanceState.ALIGNED):
            if self.hand_missing < cfg.hand_missing_frames:
                return self._output(self.last_command, match=match, magnitude=self.last_magnitude, reference="hand")
            self.state = GuidanceState.HEAD_GUIDE
            self.centered_frames = 0

        if self.state == GuidanceState.HEAD_GUIDE:
            return self._steer(frame_width / 2.0, frame_width, "head", match)
        return self._steer(self.hand[0], frame_width, "hand", match)

    def _steer(self, ref_x: float, frame_width: int, reference: str, match: Detection,
               speech: Optional[str] = None) -> GuidanceOutput:
        cfg = self.config
        error = (self.target_x - ref_x) / float(frame_width)
        magnitude = min(abs(error), 0.5)
        chime = None

        if reference == "head":
            centered = abs(error) <= cfg.head_tolerance
            self.centered_frames = self.centered_frames + 1 if centered else 0
            on_target = self.centered_frames >= cfg.aligned_hold_frames
            if on_target and not self.head_centered_announced:
                self.head_centered_announced = True
                speech = speech or (f"The {self.target_name} is straight ahead{self._distance_phrase(match)}. "
                                    "Raise your hand to point at it.")
        else:
            if self.state == GuidanceState.ALIGNED and abs(error) > cfg.hand_release_tolerance:
                self.state = GuidanceState.HAND_GUIDE
                self.aligned_frames = 0
            if self.state == GuidanceState.HAND_GUIDE:
                self.aligned_frames = self.aligned_frames + 1 if abs(error) <= cfg.hand_tolerance else 0
                if self.aligned_frames >= cfg.aligned_hold_frames:
                    self.state = GuidanceState.ALIGNED
                    chime = "aligned"
                    speech = speech or (f"Your hand is pointing at the {self.target_name}"
                                        f"{self._distance_phrase(match)}. Walk that way.")
            on_target = self.state == GuidanceState.ALIGNED

        if on_target:
            command = GuidanceCommand.ALIGNED
        elif reference == "head" and centered:
            command = GuidanceCommand.NONE
        else:
            command = GuidanceCommand.MOVE_LEFT if error < 0 else GuidanceCommand.MOVE_RIGHT
        return self._output(command, match=match, magnitude=magnitude, reference=reference,
                            speech=speech, chime=chime)

    # ------------------------------------------------------------------ helpers
    def _reset_tracking(self, now: float, keep_box: bool = False) -> None:
        self.hit_window: Deque[bool] = deque(maxlen=self.config.confirm_window)
        self.misses = 0
        self.target_x: Optional[float] = None
        self.target_y: Optional[float] = None
        if not keep_box:
            self.tracked_box: Optional[Box] = None
        self.hand: Optional[Point] = None
        self.hand_missing = 0
        self.centered_frames = 0
        self.aligned_frames = 0
        self.head_centered_announced = False
        self.search_started = now
        # first "look around" prompt arrives first_prompt_delay seconds after starting
        self.last_prompt = now - self.config.look_around_interval + self.config.first_prompt_delay
        self.last_command = GuidanceCommand.NONE
        self.last_magnitude = 0.0
        self.last_reference = ""

    def _smooth(self, previous: Optional[float], value: float) -> float:
        if previous is None:
            return value
        a = self.config.smoothing
        return a * value + (1.0 - a) * previous

    def _find_target(self, detections: Sequence[Detection]) -> Optional[Detection]:
        names = labels_for_target(self.target_name or "")
        candidates = [d for d in detections if d.label.lower() in names]
        if not candidates:
            return None
        if self.tracked_box is not None:
            best = max(candidates, key=lambda d: compute_iou(d.box, self.tracked_box))
            if compute_iou(best.box, self.tracked_box) > 0.1:
                return best  # stick with the same physical object
        return max(candidates, key=lambda d: d.area_ratio)  # otherwise the closest one

    def _distance_phrase(self, match: Detection) -> str:
        if match.label.lower() not in LARGE_OBJECTS:
            return ""
        steps = estimate_steps(match.area_ratio)
        return ", within one step" if steps <= 1 else f", about {steps} steps away"

    def _look_around_message(self, detections: Sequence[Detection], now: float) -> str:
        names = labels_for_target(self.target_name or "")
        seen: List[str] = []
        for det in sorted(detections, key=lambda d: d.area_ratio, reverse=True):
            if det.label.lower() not in names and det.label not in seen:
                seen.append(det.label)
        msg = f"I can't see a {self.target_name} yet."
        if seen:
            msg += f" I can see {natural_list(seen[:3])}."
        if self.memory_time is not None and now - self.memory_time <= self.config.memory_seconds:
            secs = int(now - self.memory_time)
            if self.memory_zone == "CENTER":
                msg += f" It was in front of you {secs} seconds ago."
            else:
                msg += (f" It was {ZONE_PHRASES[self.memory_zone]} {secs} seconds ago. "
                        f"Turn slowly to your {self.memory_zone.lower()}.")
        else:
            msg += " Please turn your head slowly to the left and right."
        return msg

    def _output(self, command: GuidanceCommand, match: Optional[Detection] = None, magnitude: float = 0.0,
                reference: str = "", speech: Optional[str] = None, chime: Optional[str] = None) -> GuidanceOutput:
        if command not in (GuidanceCommand.LOST,):
            self.last_command, self.last_magnitude, self.last_reference = command, magnitude, reference
        target_point = None
        if self.target_x is not None and self.target_y is not None:
            target_point = (self.target_x, self.target_y)
        return GuidanceOutput(
            state=self.state,
            command=command,
            magnitude=magnitude,
            reference=reference,
            target_name=self.target_name,
            target=match,
            target_box=self.tracked_box,
            target_point=target_point,
            hand_point=self.hand,
            speech=speech,
            chime=chime,
        )
