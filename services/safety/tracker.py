"""L2 Multi-Object Temporal Tracker — Stabilizes detections and assigns track IDs."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from services.safety.yolo_ensemble import compute_iou


@dataclass
class Track:
    """Represents a temporally tracked object over consecutive frames."""
    track_id: int
    label: str
    box: Tuple[int, int, int, int]  # Current x1, y1, x2, y2
    confidence: float
    age_frames: int = 1
    hits: int = 1
    time_since_update: int = 0
    box_history: List[Tuple[int, int, int, int]] = field(default_factory=list)
    time_history: List[float] = field(default_factory=list)

    @property
    def is_confirmed(self) -> bool:
        """Returns True if track has persisted enough frames to eliminate noise."""
        return self.hits >= 3


class MultiObjectTracker:
    """Associates frame detections with existing tracks using IoU matching."""

    def __init__(
        self,
        max_age_frames: int = 12,
        min_hits: int = 3,
        iou_match_threshold: float = 0.3,
    ) -> None:
        self.max_age_frames = max_age_frames
        self.min_hits = min_hits
        self.iou_match_threshold = iou_match_threshold
        self.next_track_id = 1
        self.tracks: Dict[int, Track] = {}

    def update(
        self,
        boxes: List[Tuple[int, int, int, int]],
        scores: List[float],
        labels: List[str],
    ) -> List[Track]:
        """Matches incoming detections to active tracks and creates/retires tracks."""
        now = time.time()
        unmatched_dets = set(range(len(boxes)))
        unmatched_tracks = set(self.tracks.keys())

        # Match existing tracks with detections via highest IoU
        matches: List[Tuple[int, int]] = []
        for tid in list(unmatched_tracks):
            track = self.tracks[tid]
            best_iou = self.iou_match_threshold
            best_idx = -1
            for d_idx in unmatched_dets:
                # Same label preferred, or high geometric overlap
                if labels[d_idx] == track.label or compute_iou(track.box, boxes[d_idx]) > 0.5:
                    iou = compute_iou(track.box, boxes[d_idx])
                    if iou > best_iou:
                        best_iou = iou
                        best_idx = d_idx

            if best_idx != -1:
                matches.append((tid, best_idx))
                unmatched_tracks.remove(tid)
                unmatched_dets.remove(best_idx)

        # Update matched tracks
        for tid, d_idx in matches:
            t = self.tracks[tid]
            t.box = boxes[d_idx]
            t.confidence = scores[d_idx]
            t.label = labels[d_idx]
            t.age_frames += 1
            t.hits += 1
            t.time_since_update = 0
            t.box_history.append(boxes[d_idx])
            t.time_history.append(now)
            if len(t.box_history) > 30:
                t.box_history.pop(0)
                t.time_history.pop(0)

        # Create new tracks for unmatched detections
        for d_idx in unmatched_dets:
            new_t = Track(
                track_id=self.next_track_id,
                label=labels[d_idx],
                box=boxes[d_idx],
                confidence=scores[d_idx],
                age_frames=1,
                hits=1,
                time_since_update=0,
                box_history=[boxes[d_idx]],
                time_history=[now],
            )
            self.tracks[self.next_track_id] = new_t
            self.next_track_id += 1

        # Age unmatched tracks and prune old ones
        for tid in unmatched_tracks:
            t = self.tracks[tid]
            t.age_frames += 1
            t.time_since_update += 1
            if t.time_since_update > self.max_age_frames:
                del self.tracks[tid]

        # Return active tracks that have met minimum hit criteria or are newly tracked
        return [t for t in self.tracks.values() if t.time_since_update == 0]
