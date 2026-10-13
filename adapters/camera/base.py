"""L1 Camera Hardware Abstraction Layer — Base interfaces and threaded frame grabber."""

from __future__ import annotations

import abc
import platform
import threading
import time
from typing import Optional, Tuple, Union

import cv2
import numpy as np

from adapters.clock.monotonic_clock import MonotonicClock
from contracts.frame import FrameData, LensStatus, SourceId


class ThreadedFrameGrabber:
    """Continuously grabs frames in a background thread to prevent OpenCV FIFO buffering.

    Crucial for IP Webcam and ADB USB network streams: without this, OpenCV buffers
    5-15 stale frames, creating 0.5s - 1.5s lag. This grabber ensures the pipeline
    always receives the latest real-time frame with <15ms latency.
    """

    def __init__(self, capture: cv2.VideoCapture) -> None:
        self.cap = capture
        self.lock = threading.Lock()
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_timestamp_ns: int = 0
        self.running: bool = False
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True, name="ThreadedFrameGrabber")
        self.thread.start()

    def _worker(self) -> None:
        while self.running:
            if not self.cap.isOpened():
                time.sleep(0.01)
                continue

            grabbed = self.cap.grab()
            if grabbed:
                ret, frame = self.cap.retrieve()
                if ret and frame is not None:
                    ts = MonotonicClock.now_ns()
                    with self.lock:
                        self.latest_frame = frame
                        self.latest_timestamp_ns = ts
            else:
                time.sleep(0.005)

    def read_latest(self) -> Tuple[bool, Optional[np.ndarray], int]:
        with self.lock:
            if self.latest_frame is not None:
                return True, self.latest_frame.copy(), self.latest_timestamp_ns
            return False, None, 0

    def stop(self) -> None:
        self.running = False
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=0.5)


class CameraSource(abc.ABC):
    """Abstract interface satisfied by all camera adapters in Nethra."""

    def __init__(
        self,
        name: str,
        source_id: SourceId,
        width: int = 640,
        height: int = 480,
        fov_area_scale: float = 1.0,
    ) -> None:
        self.name = name
        self.source_id = source_id
        self.width = width
        self.height = height
        self.fov_area_scale = fov_area_scale
        self.is_opened = False

    @abc.abstractmethod
    def start(self) -> bool:
        """Initializes the camera connection. Returns True if successful."""
        pass

    @abc.abstractmethod
    def read(self) -> Tuple[bool, Optional[np.ndarray], int]:
        """Reads the newest available BGR frame. Returns (success, frame, timestamp_ns)."""
        pass

    def read_frame_data(self) -> Optional[FrameData]:
        """Convenience method returning a typed L0 FrameData contract."""
        ret, frame, ts = self.read()
        if not ret or frame is None:
            return None
        h, w = frame.shape[:2]
        return FrameData(
            image=frame,
            timestamp_ns=ts,
            width=w,
            height=h,
            source_id=self.source_id,
            lens_status=LensStatus.OK,
            fov_area_scale=self.fov_area_scale,
        )

    @abc.abstractmethod
    def release(self) -> None:
        """Releases the camera and any background threads."""
        pass


def get_camera_name(idx_or_source: Union[int, str]) -> str:
    """Returns a human-friendly camera name across macOS, Windows, and Android streams."""
    if isinstance(idx_or_source, str):
        if "127.0.0.1" in idx_or_source or "localhost" in idx_or_source:
            return f"Android USB (ADB Stream: {idx_or_source})"
        return f"Android IP Camera ({idx_or_source})"

    is_mac = platform.system() == "Darwin"
    if idx_or_source == 1:
        return "iPhone (Continuity Camera / Ultra-Wide)" if is_mac else "External / Android USB Camera (#1)"
    elif idx_or_source == 0:
        return "Mac FaceTime HD Camera" if is_mac else "Laptop Built-in Webcam (#0)"
    elif idx_or_source < 0:
        return "Synthetic Mock Stream"
    return f"Camera #{idx_or_source}"


def open_camera(preferred_idx: Union[int, str]) -> Tuple[Optional[cv2.VideoCapture], Union[int, str]]:
    """Attempts to open the preferred camera (index or stream URL) with automatic fallback."""
    print(f"[Camera] Attempting camera source {preferred_idx} ({get_camera_name(preferred_idx)})...")
    cap = cv2.VideoCapture(preferred_idx)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"[Camera] Successfully opened {get_camera_name(preferred_idx)}.")
            return cap, preferred_idx
        cap.release()

    if isinstance(preferred_idx, int):
        fallbacks = [1, 0, 2]
        if preferred_idx in fallbacks:
            fallbacks.remove(preferred_idx)

        for idx in fallbacks:
            print(f"[Camera] Trying alternate index {idx} ({get_camera_name(idx)})...")
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"[Camera] Successfully opened {get_camera_name(idx)}.")
                    return cap, idx
                cap.release()

    return None, -1
