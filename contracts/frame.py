"""L0 Sensor Frame Contract (Depends on nothing)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class SourceId(str, Enum):
    IPHONE = "IPHONE"
    ANDROID_USB = "ANDROID_USB"
    ANDROID_IP = "ANDROID_IP"
    GLASSES = "GLASSES"
    WEBCAM = "WEBCAM"
    FILE_REPLAY = "FILE_REPLAY"
    MOCK = "MOCK"


class LensStatus(str, Enum):
    OK = "OK"
    OCCLUDED = "OCCLUDED"
    TOO_DARK = "TOO_DARK"
    BLURRED = "BLURRED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class FrameData:
    """Platform-free camera frame representation."""
    image: Any  # numpy.ndarray (H, W, 3) BGR
    timestamp_ns: int
    width: int
    height: int
    source_id: SourceId = SourceId.WEBCAM
    lens_status: LensStatus = LensStatus.OK
    fov_area_scale: float = 1.0
