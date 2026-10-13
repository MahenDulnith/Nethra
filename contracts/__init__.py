"""Nethra L0 Contracts Package — Platform-free data shapes."""

from contracts.detection import Detection, Zone
from contracts.frame import FrameData, LensStatus, SourceId
from contracts.haptic_command import HapticCommand, HapticFeedbackState, PatternId, Target
from contracts.safety_alert import DirectionSector, DistanceBucket, SafetyAlert, Tier
from contracts.vision_result import CannotSeeReason, VisionResult

__all__ = [
    "Detection",
    "Zone",
    "FrameData",
    "LensStatus",
    "SourceId",
    "HapticCommand",
    "HapticFeedbackState",
    "PatternId",
    "Target",
    "DirectionSector",
    "DistanceBucket",
    "SafetyAlert",
    "Tier",
    "CannotSeeReason",
    "VisionResult",
]
