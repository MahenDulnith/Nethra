"""L2 Frame Hygiene — Redundancy Filter (Saves compute on static scenes)."""

from __future__ import annotations

import time
from typing import Optional

import cv2
import numpy as np


class RedundancyFilter:
    """Filters near-identical consecutive frames to save compute when user is stationary."""

    def __init__(self, min_frame_difference: float = 0.04, min_interval_ms: int = 250) -> None:
        self.min_frame_difference = min_frame_difference
        self.min_interval_sec = min_interval_ms / 1000.0
        self.last_accepted_gray: Optional[np.ndarray] = None
        self.last_accepted_time: float = 0.0

    def is_redundant(self, image: np.ndarray) -> bool:
        """Returns True if the frame is virtually identical to the last accepted frame."""
        now = time.time()
        if self.last_accepted_gray is None:
            return False

        # If more than interval has passed, force accept for freshness
        if (now - self.last_accepted_time) > self.min_interval_sec:
            return False

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Resize for ultra-fast diff calculation
        small_curr = cv2.resize(gray, (160, 120))
        small_last = cv2.resize(self.last_accepted_gray, (160, 120))
        diff = np.mean(np.abs(small_curr.astype(float) - small_last.astype(float))) / 255.0

        return diff < self.min_frame_difference

    def mark_accepted(self, image: np.ndarray) -> None:
        """Registers an accepted frame."""
        if len(image.shape) == 3:
            self.last_accepted_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            self.last_accepted_gray = image.copy()
        self.last_accepted_time = time.time()
