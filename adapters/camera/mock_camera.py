"""L1 Synthetic Mock Camera Generator and MockCameraSource."""

from __future__ import annotations

import time
from typing import Optional, Tuple

import cv2
import numpy as np

from adapters.camera.base import CameraSource
from adapters.clock.monotonic_clock import MonotonicClock
from contracts.frame import SourceId


def create_mock_frame(width: int = 640, height: int = 480, frame_count: int = 0) -> np.ndarray:
    """Generates synthetic corridor frames with an oscillating obstacle for headless/mock testing."""
    frame = np.full((height, width, 3), 35, dtype=np.uint8)

    pts = np.array(
        [
            [width * 0.3, height],
            [width * 0.45, height * 0.4],
            [width * 0.55, height * 0.4],
            [width * 0.7, height],
        ],
        np.int32,
    )
    cv2.fillPoly(frame, [pts], (65, 65, 65))

    cycle = (frame_count % 150) / 150.0
    x_pos = int(width * 0.15 + (width * 0.7 * cycle))
    y_pos = int(height * 0.5)
    box_size = int(60 + 50 * np.sin(cycle * np.pi))

    cv2.rectangle(
        frame,
        (x_pos - box_size // 2, y_pos - box_size // 2),
        (x_pos + box_size // 2, y_pos + box_size // 2),
        (0, 180, 255),
        -1,
    )
    cv2.putText(
        frame,
        "Obstacle (Simulated)",
        (x_pos - box_size // 2, y_pos - box_size // 2 - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
    )

    return frame


class MockCameraSource(CameraSource):
    """CameraSource implementation producing synthetic mock corridor frames."""

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        fps: float = 30.0,
        fov_area_scale: float = 1.0,
    ) -> None:
        super().__init__(
            name="Synthetic Mock Stream",
            source_id=SourceId.MOCK,
            width=width,
            height=height,
            fov_area_scale=fov_area_scale,
        )
        self.fps = fps
        self.frame_count = 0
        self.frame_interval_sec = 1.0 / max(1.0, fps)
        self.last_frame_time = 0.0

    def start(self) -> bool:
        self.is_opened = True
        self.frame_count = 0
        self.last_frame_time = time.time()
        print("[MockCamera] Synthetic stream started.")
        return True

    def read(self) -> Tuple[bool, Optional[np.ndarray], int]:
        if not self.is_opened:
            return False, None, 0

        # Frame pacing
        now = time.time()
        elapsed = now - self.last_frame_time
        if elapsed < self.frame_interval_sec:
            time.sleep(self.frame_interval_sec - elapsed)
        self.last_frame_time = time.time()

        self.frame_count += 1
        frame = create_mock_frame(self.width, self.height, self.frame_count)
        ts = MonotonicClock.now_ns()
        return True, frame, ts

    def release(self) -> None:
        self.is_opened = False
