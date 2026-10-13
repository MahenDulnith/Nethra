"""L2 Frame Hygiene — Lens Occlusion Heuristic (Finger/pocket/fogged lens)."""

from __future__ import annotations

import cv2
import numpy as np


class OcclusionHeuristic:
    """Detects covered, fogged, or obstructed camera lens using Canny edge density."""

    def __init__(self, max_edge_density: float = 0.012, persist_frames: int = 5) -> None:
        self.max_edge_density = max_edge_density
        self.persist_frames = persist_frames
        self.occluded_streak = 0

    def compute_edge_density(self, image: np.ndarray) -> float:
        """Calculates edge density using Canny edge detection."""
        if image is None or image.size == 0:
            return 0.0
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        edges = cv2.Canny(gray, 50, 150)
        density = float(np.count_nonzero(edges)) / float(edges.size)
        return density

    def update(self, image: np.ndarray) -> bool:
        """Updates streak counter. Returns True if lens is persistently occluded."""
        density = self.compute_edge_density(image)
        if density < self.max_edge_density:
            self.occluded_streak += 1
        else:
            self.occluded_streak = max(0, self.occluded_streak - 1)
        return self.occluded_streak >= self.persist_frames

    def reset(self) -> None:
        self.occluded_streak = 0
