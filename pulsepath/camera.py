"""Camera helpers: device naming, opening with fallback, and synthetic frames."""

from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np


import sys


def get_camera_name(idx: int) -> str:
    """Returns human-friendly camera name."""
    if idx < 0:
        return "Synthetic Mock Stream"
    if sys.platform == "darwin":
        if idx == 1:
            return "iPhone (Continuity Camera)"
        if idx == 0:
            return "Mac FaceTime HD Camera"
    elif sys.platform == "win32":
        if idx == 0:
            return "Integrated Webcam (Index 0)"
        if idx == 1:
            return "External Camera (Index 1)"
    return f"Camera #{idx}"


def _try_open(idx: int) -> Optional[cv2.VideoCapture]:
    cap = None
    if sys.platform == "win32":
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(idx)
    else:
        cap = cv2.VideoCapture(idx)

    if cap is not None and cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            return cap
        cap.release()
    return None


def open_camera(preferred_idx: int) -> Tuple[Optional[cv2.VideoCapture], int]:
    """Attempts to open the preferred camera with automatic fallback."""
    priority = (1, 0, 2) if sys.platform == "darwin" else (0, 1, 2)
    search_order = [preferred_idx] + [i for i in priority if i != preferred_idx]
    for idx in search_order:
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
