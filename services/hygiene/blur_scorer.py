"""L2 Frame Hygiene — Laplacian Variance Blur Scorer."""

from __future__ import annotations

import cv2
import numpy as np


class BlurScorer:
    """Measures frame sharpness using the variance of the Laplacian operator."""

    def __init__(self, min_variance: float = 55.0) -> None:
        self.min_variance = min_variance

    def score(self, image: np.ndarray) -> float:
        """Calculates Laplacian variance score. Higher is sharper."""
        if image is None or image.size == 0:
            return 0.0
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = float(laplacian.var())
        return variance

    def is_blurred(self, image: np.ndarray) -> bool:
        """Returns True if the frame is too blurry for reliable detection."""
        return self.score(image) < self.min_variance
