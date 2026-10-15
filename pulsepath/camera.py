"""Camera helpers: device naming, opening with fallback, and synthetic frames."""

from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np


def get_camera_name(idx: int) -> str:
    """Returns human-friendly camera name on macOS."""
    if idx == 1:
        return "iPhone (Continuity Camera)"
    if idx == 0:
        return "Mac FaceTime HD Camera"
    if idx < 0:
        return "Synthetic Mock Stream"
    return f"Camera #{idx}"


def _try_open(idx: int) -> Optional[cv2.VideoCapture]:
    cap = cv2.VideoCapture(idx)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            return cap
    cap.release()
    return None


def open_camera(preferred_idx: int) -> Tuple[Optional[cv2.VideoCapture], int]:
    """Attempts to open the preferred camera with automatic fallback."""
    for idx in [preferred_idx] + [i for i in (1, 0, 2) if i != preferred_idx]:
        print(f"[Camera] Trying index {idx} ({get_camera_name(idx)})...")
        cap = _try_open(idx)
        if cap is not None:
            print(f"[Camera] Opened {get_camera_name(idx)}.")
            return cap, idx
    return None, -1


def create_mock_frame(width: int = 640, height: int = 480, frame_count: int = 0) -> np.ndarray:
    """Generates synthetic frames for headless testing or when camera is unavailable."""
    frame = np.full((height, width, 3), 35, dtype=np.uint8)
    pts = np.array([[width * 0.3, height], [width * 0.45, height * 0.4],
                    [width * 0.55, height * 0.4], [width * 0.7, height]], np.int32)
    cv2.fillPoly(frame, [pts], (65, 65, 65))

    cycle = (frame_count % 150) / 150.0
    x_pos = int(width * 0.15 + width * 0.7 * cycle)
    y_pos = int(height * 0.5)
    size = int(60 + 50 * np.sin(cycle * np.pi))
    cv2.rectangle(frame, (x_pos - size // 2, y_pos - size // 2), (x_pos + size // 2, y_pos + size // 2), (0, 180, 255), -1)
    return frame
