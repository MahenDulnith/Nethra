"""L1 Continuity Camera Adapter for macOS + iPhone Ultra-Wide (0.5x)."""

from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np

from adapters.camera.base import CameraSource
from adapters.clock.monotonic_clock import MonotonicClock
from contracts.frame import SourceId


class ContinuityCameraSource(CameraSource):
    """Captures from iPhone via macOS Continuity Camera (default index 1 on Mac)."""

    def __init__(
        self,
        device_index: int = 1,
        width: int = 640,
        height: int = 480,
        fov_area_scale: float = 1.0,
    ) -> None:
        super().__init__(
            name="iPhone (Continuity Camera / Ultra-Wide)",
            source_id=SourceId.IPHONE,
            width=width,
            height=height,
            fov_area_scale=fov_area_scale,
        )
        self.device_index = device_index
        self.cap: Optional[cv2.VideoCapture] = None

    def start(self) -> bool:
        print(f"[ContinuityCamera] Opening device index {self.device_index}...")
        self.cap = cv2.VideoCapture(self.device_index)
        if not self.cap.isOpened():
            print(f"[ContinuityCamera Error] Could not open camera #{self.device_index}.")
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        ret, frame = self.cap.read()
        if not ret or frame is None:
            print("[ContinuityCamera Error] Camera opened but returned empty frame.")
            self.release()
            return False

        self.is_opened = True
        print(f"[ContinuityCamera] Ready ({self.width}x{self.height} @ {self.fov_area_scale}x FOV scale).")
        return True

    def read(self) -> Tuple[bool, Optional[np.ndarray], int]:
        if not self.is_opened or self.cap is None:
            return False, None, 0
        ret, frame = self.cap.read()
        ts = MonotonicClock.now_ns()
        if not ret or frame is None:
            return False, None, ts
        return True, frame, ts

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.is_opened = False
