"""L2 Time-to-Contact (TTC) Growth Estimator — Measures expansion rate to predict collisions."""

from __future__ import annotations

from typing import Optional

from services.safety.tracker import Track


class GrowthEstimator:
    """Estimates time-to-contact (TTC in seconds) from bounding-box vertical expansion.

    ENFORCES HONESTY CONTROL:
    A track younger than `min_track_age_frames` (default: 4) returns None.
    The system NEVER guesses time-to-contact from a single or noisy frame.
    """

    def __init__(
        self,
        min_track_age_frames: int = 4,
        critical_seconds: float = 2.5,
        advisory_seconds: float = 5.0,
    ) -> None:
        self.min_track_age_frames = min_track_age_frames
        self.critical_seconds = critical_seconds
        self.advisory_seconds = advisory_seconds

    def estimate_ttc(self, track: Track) -> Optional[float]:
        """Calculates Time-to-Contact in seconds. Returns None if track is too young or stationary."""
        # Honesty control: refuse to calculate without sufficient temporal history
        if track.age_frames < self.min_track_age_frames or len(track.box_history) < self.min_track_age_frames:
            return None

        # Compare current bounding-box height to oldest in history
        oldest_box = track.box_history[0]
        current_box = track.box_history[-1]

        old_h = float(max(1, oldest_box[3] - oldest_box[1]))
        curr_h = float(max(1, current_box[3] - current_box[1]))

        dt = track.time_history[-1] - track.time_history[0]
        if dt <= 0.05:  # Less than 50ms interval is too noisy
            return None

        dh = curr_h - old_h
        # If dh <= 0, obstacle is stationary or receding; not approaching
        if dh <= 2.0:
            return None

        dh_dt = dh / dt  # Expansion rate in pixels per second
        ttc = curr_h / dh_dt  # Optical expansion formula for time-to-contact

        return round(float(ttc), 2)
