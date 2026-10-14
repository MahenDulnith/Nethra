"""L0 Safety Alert & Distance Bucket Contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Tier(str, Enum):
    CRITICAL = "CRITICAL"
    ADVISORY = "ADVISORY"
    SOCIAL = "SOCIAL"
    IGNORE = "IGNORE"


class DirectionSector(str, Enum):
    LEFT = "LEFT"
    CENTRE_LEFT = "CENTRE_LEFT"
    CENTRE = "CENTRE"
    CENTRE_RIGHT = "CENTRE_RIGHT"
    RIGHT = "RIGHT"

    @property
    def clock_face(self) -> str:
        """Returns standard Orientation & Mobility (O&M) clock-face position."""
        mapping = {
            DirectionSector.LEFT: "10 o'clock",
            DirectionSector.CENTRE_LEFT: "11 o'clock",
            DirectionSector.CENTRE: "12 o'clock",
            DirectionSector.CENTRE_RIGHT: "1 o'clock",
            DirectionSector.RIGHT: "2 o'clock",
        }
        return mapping.get(self, "12 o'clock")


class DistanceBucket(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    NEAR = "NEAR"
    MID = "MID"
    FAR = "FAR"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SafetyAlert:
    """Deterministic safety alert emitted by the offline L2 SafetyEngine."""
    tier: Tier
    object_class: str
    direction_sector: DirectionSector
    distance_bucket: DistanceBucket
    ttc_seconds: Optional[float]
    track_age_frames: int
    haptic_pattern_id: str
    speech_key: Optional[str]
    produced_offline: bool
    frame_timestamp_ns: int

    def __post_init__(self) -> None:
        if self.tier == Tier.CRITICAL and not self.produced_offline:
            raise ValueError("CRITICAL safety alerts must be produced 100% offline.")
