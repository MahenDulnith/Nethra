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
