"""L1 File Replay Camera Adapter for MP4 video benchmarking."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from adapters.camera.base import CameraSource
from adapters.clock.monotonic_clock import MonotonicClock
from contracts.frame import SourceId


class FileCameraSource(CameraSource):
    """Replays an MP4 video file frame-by-frame with target frame pacing."""

    def __init__(
        self,
        file_path: str,
        width: int = 640,
        height: int = 480,
        fps: float = 30.0,
        loop: bool = True,
        fov_area_scale: float = 1.0,
    ) -> None:
        super().__init__(
            name=f"Video Replay ({Path(file_path).name})",
            source_id=SourceId.FILE_REPLAY,
            width=width,
            height=height,
            fov_area_scale=fov_area_scale,
        )
        self.file_path = file_path
        self.target_fps = fps
        self.loop = loop
        self.cap: Optional[cv2.VideoCapture] = None
        self.frame_interval_sec = 1.0 / max(1.0, fps)
        self.last_frame_time = 0.0

    def start(self) -> bool:
        path = Path(self.file_path)
        if not path.exists():
            print(f"[FileCamera Error] Video file not found: {self.file_path}")
            return False

        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            print(f"[FileCamera Error] Could not open video file: {self.file_path}")
            return False

        self.is_opened = True
        self.last_frame_time = time.time()
        print(f"[FileCamera] Ready replaying {self.file_path} at {self.target_fps} FPS.")
        return True

    def read(self) -> Tuple[bool, Optional[np.ndarray], int]:
        if not self.is_opened or self.cap is None:
            return False, None, 0

        # Frame pacing
        now = time.time()
        elapsed = now - self.last_frame_time
        if elapsed < self.frame_interval_sec:
            time.sleep(self.frame_interval_sec - elapsed)
        self.last_frame_time = time.time()

        ret, frame = self.cap.read()
        ts = MonotonicClock.now_ns()

        if not ret or frame is None:
            if self.loop:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    return False, None, ts
            else:
                return False, None, ts

        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = cv2.resize(frame, (self.width, self.height))

        return True, frame, ts

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.is_opened = False
