"""L0 Detection & Spatial Zone Contracts (Depends on nothing)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class Zone(str, Enum):
    LEFT = "LEFT"
    CENTER = "CENTER"
    RIGHT = "RIGHT"


@dataclass
class Detection:
    """Represents a single detected object in the field of view."""
    label: str
    confidence: float
    box: Tuple[int, int, int, int]  # x1, y1, x2, y2
    center_x: float
    center_y: float
    width: float
    height: float
    area_ratio: float
    zone: str  # "LEFT", "CENTER", "RIGHT"
    pwm_intensity: float  # 0.0 to 100.0%
    track_id: int = -1
