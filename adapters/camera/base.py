"""L1 Camera Hardware Abstraction Layer (iPhone Continuity, Android USB/IP, UVC, Mock)."""

from __future__ import annotations

import platform
from typing import Optional, Tuple, Union

import cv2


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

    # Fallback to alternate local camera indices if a numeric index was requested
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
