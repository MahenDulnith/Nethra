"""L0 Haptic Feedback & BLE Wristband Command Contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Target(str, Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    BOTH = "BOTH"


class PatternId(str, Enum):
    TURN_LEFT = "TURN_LEFT"
    TURN_RIGHT = "TURN_RIGHT"
    FOUND = "FOUND"
    OBSTACLE_NEAR = "OBSTACLE_NEAR"
    URGENT = "URGENT"
    FAULT = "FAULT"
    LOW_BATTERY = "LOW_BATTERY"


@dataclass
class HapticFeedbackState:
    """Dual-wristband (Left & Right) PWM vibration state."""
    left_pwm: float = 0.0   # 0.0 to 100.0%
    right_pwm: float = 0.0  # 0.0 to 100.0%
    active_threat: Optional[str] = None
    closest_distance_ratio: float = 0.0


@dataclass(frozen=True)
class HapticCommand:
    """Frozen 8-byte BLE GATT command format shared with ESP32 wristband firmware."""
    format_version: int
    target: Target
    pattern_id: PatternId
    intensity: int  # 0..100 (capped independently by firmware)
    pulse_hz: int
    duration_ms: int
    scheduled_at_ms: int
