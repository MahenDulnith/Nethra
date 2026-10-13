"""L2 Frame Hygiene — FrameSelector (Single entry point for quality gatekeeping)."""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np

from contracts.frame import FrameData, LensStatus
from contracts.vision_result import CannotSeeReason
from services.hygiene.blur_scorer import BlurScorer
from services.hygiene.luminance_checker import LuminanceChecker
from services.hygiene.occlusion_heuristic import OcclusionHeuristic
from services.hygiene.redundancy_filter import RedundancyFilter


class FrameSelector:
    """The single entry point for input frame hygiene.

    Evaluates darkness, blur, occlusion, and redundancy before inference.
    Returns (accepted: bool, reason: Optional[CannotSeeReason], lens_status: LensStatus).
    """

    def __init__(
        self,
        min_laplacian_variance: float = 55.0,
        min_mean_luminance: float = 35.0,
        max_edge_density: float = 0.012,
        occlusion_persist_frames: int = 5,
        min_frame_difference: float = 0.04,
        min_interval_ms: int = 250,
    ) -> None:
        self.blur_scorer = BlurScorer(min_variance=min_laplacian_variance)
        self.luminance_checker = LuminanceChecker(min_mean_luminance=min_mean_luminance)
        self.occlusion_heuristic = OcclusionHeuristic(
            max_edge_density=max_edge_density,
            persist_frames=occlusion_persist_frames,
        )
        self.redundancy_filter = RedundancyFilter(
            min_frame_difference=min_frame_difference,
            min_interval_ms=min_interval_ms,
        )
        self.recent_accepted: List[np.ndarray] = []
        self.max_buffer: int = 10

    def evaluate(
        self, frame: np.ndarray
    ) -> Tuple[bool, Optional[CannotSeeReason], LensStatus]:
        """Evaluates a raw frame and decides whether to accept or reject it."""
        if frame is None or frame.size == 0:
            return False, CannotSeeReason.NOT_PRESENT, LensStatus.UNAVAILABLE

        # 1. Darkness Check (highest safety hazard)
        if self.luminance_checker.is_too_dark(frame):
            return False, CannotSeeReason.TOO_DARK, LensStatus.TOO_DARK

        # 2. Occlusion Check (finger over lens / fogged)
        if self.occlusion_heuristic.update(frame):
            return False, CannotSeeReason.OCCLUDED, LensStatus.OCCLUDED

        # 3. Blur Check (walking shake / quick head turn)
        if self.blur_scorer.is_blurred(frame):
            return False, CannotSeeReason.BLURRED, LensStatus.BLURRED

        # 4. Redundancy Check (stationary user)
        if self.redundancy_filter.is_redundant(frame):
            # Redundant frames are not faulty; they are simply skipped to save compute
            return False, None, LensStatus.OK

        # Accepted frame
        self.redundancy_filter.mark_accepted(frame)
        self.recent_accepted.append(frame.copy())
        if len(self.recent_accepted) > self.max_buffer:
            self.recent_accepted.pop(0)

        return True, None, LensStatus.OK

    def best_recent(self) -> Optional[np.ndarray]:
        """Returns the sharpest recent accepted frame from buffer (useful for Ask/VLM)."""
        if not self.recent_accepted:
            return None
        scores = [self.blur_scorer.score(f) for f in self.recent_accepted]
        best_idx = int(np.argmax(scores))
        return self.recent_accepted[best_idx]
