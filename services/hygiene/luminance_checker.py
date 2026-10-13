"""L2 Frame Hygiene — Luminance Darkness Checker (0-255 scale)."""

from __future__ import annotations

import cv2
import numpy as np


class LuminanceChecker:
    """Computes mean frame luminance on a strict 0-255 scale to detect darkness/underexposure."""

    def __init__(self, min_mean_luminance: float = 35.0) -> None:
        self.min_mean_luminance = min_mean_luminance

    def mean_luminance(self, image: np.ndarray) -> float:
        """Returns the mean luminance of the frame (0.0 - 255.0)."""
        if image is None or image.size == 0:
            return 0.0
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        return float(np.mean(gray))

    def is_too_dark(self, image: np.ndarray) -> bool:
        """Returns True if the frame is too dark for vision models to operate safely."""
        return self.mean_luminance(image) < self.min_mean_luminance
