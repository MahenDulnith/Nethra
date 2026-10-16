"""L2 Safety Engine — The single offline entry point combining YOLO, Tracking, TTC, and Haptics."""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np

from contracts.detection import Detection
from contracts.frame import FrameData, LensStatus
from contracts.haptic_command import HapticFeedbackState
from contracts.safety_alert import DirectionSector, DistanceBucket, SafetyAlert, Tier
from services.hygiene.frame_selector import FrameSelector
from services.safety.growth_estimator import GrowthEstimator
from services.safety.mappers import BucketMapper, DirectionMapper
from services.safety.spatial_router import SpatialRoutingEngine
from services.safety.tracker import MultiObjectTracker, Track
from services.safety.yolo_ensemble import YoloEnsembleDetector


class SafetyEngine:
    """The unified offline L2 safety processor.

    Frame -> Hygiene Gate -> YOLO Ensemble -> Temporal Tracker -> TTC Estimator -> Spatial PWM + SafetyAlerts.
    Guaranteed 100% offline, zero network imports (enforces Rule R1).
    """

    def __init__(
        self,
        detector: Optional[YoloEnsembleDetector] = None,
        frame_selector: Optional[FrameSelector] = None,
        tracker: Optional[MultiObjectTracker] = None,
        growth_estimator: Optional[GrowthEstimator] = None,
        spatial_router: Optional[SpatialRoutingEngine] = None,
    ) -> None:
        self.detector = detector or YoloEnsembleDetector()
        self.frame_selector = frame_selector or FrameSelector()
        self.tracker = tracker or MultiObjectTracker()
        self.growth_estimator = growth_estimator or GrowthEstimator()
        self.spatial_router = spatial_router or SpatialRoutingEngine()
        self.direction_mapper = DirectionMapper()
        self.bucket_mapper = BucketMapper()
        self._last_detections: List[Detection] = []
        self._last_haptics: HapticFeedbackState = HapticFeedbackState()
        self._last_alerts: List[SafetyAlert] = []
        self._blur_grace: int = 0

    def process(
        self,
        frame: np.ndarray,
        timestamp_ns: int,
        conf: float = 0.35,
    ) -> Tuple[List[Detection], HapticFeedbackState, List[SafetyAlert], LensStatus]:
        """Processes a frame completely offline and produces detections, haptics, and safety alerts."""
        # 1. Hygiene Gate
        accepted, reject_reason, lens_status = self.frame_selector.evaluate(frame)
        if not accepted:
            # If rejected purely because scene is static/redundant, preserve last known detections
            if lens_status == LensStatus.OK:
                return self._last_detections, self._last_haptics, self._last_alerts, lens_status

            # Allow up to 3 frames grace for momentary walking blur before clearing
            if lens_status == LensStatus.BLURRED and self._blur_grace < 3 and self._last_detections:
                self._blur_grace += 1
                return self._last_detections, self._last_haptics, self._last_alerts, lens_status

            # Clear state on darkness or occlusion
            self._blur_grace = 0
            self._last_detections = []
            self._last_haptics = HapticFeedbackState()
            self._last_alerts = []
            return [], self._last_haptics, [], lens_status

        self._blur_grace = 0
        fh, fw = frame.shape[:2]

        # 2. YOLO Ensemble Inference
        boxes, scores, labels = self.detector.detect(frame, conf=conf)

        # 3. Temporal Tracking
        active_tracks = self.tracker.update(boxes, scores, labels)

        # 4. Spatial Routing (Left/Center/Right PWM)
        detections, haptic_state = self.spatial_router.process_detections(
            boxes=boxes,
            scores=scores,
            labels=labels,
            frame_width=fw,
            frame_height=fh,
        )

        # Associate track IDs to detections by box identity (not list order)
        track_by_box = {t.box: t for t in active_tracks}
        for det in detections:
            matched = track_by_box.get(det.box)
            if matched is not None:
                det.track_id = matched.track_id

        # 5. TTC and Candidate Safety Alerts
        candidate_alerts: List[SafetyAlert] = []
        total_frame_area = float(max(1, fw * fh))

        for track in active_tracks:
            # Honesty gate: speech/alerts only from tracks seen on enough frames,
            # so one-frame misclassifications never reach the user.
            # (Haptic PWM above still reacts immediately: safety first.)
            if track.hits < self.tracker.min_hits:
                continue
            x1, y1, x2, y2 = track.box
            w = max(0, x2 - x1)
            h = max(0, y2 - y1)
            cx = x1 + (w / 2.0)
            area_ratio = float(w * h) / total_frame_area

            sector = self.direction_mapper.map_sector(cx, fw)
            bucket = self.bucket_mapper.map_bucket(area_ratio)
            ttc = self.growth_estimator.estimate_ttc(track)

            # Classify Tier
            tier = Tier.IGNORE
            haptic_pattern = "OBSTACLE_NEAR"
            speech_key = None

            if (ttc is not None and ttc < 2.5) or bucket == DistanceBucket.IMMEDIATE:
                tier = Tier.CRITICAL
                haptic_pattern = "URGENT"
                speech_key = f"safety.critical.{sector.value.lower()}"
            elif (ttc is not None and ttc < 5.0) or bucket == DistanceBucket.NEAR:
                tier = Tier.ADVISORY
                haptic_pattern = "OBSTACLE_NEAR"
                speech_key = f"safety.advisory.{sector.value.lower()}"
            elif track.label in ("door", "handle", "stairs", "person"):
                tier = Tier.SOCIAL

            alert = SafetyAlert(
                tier=tier,
                object_class=track.label,
                direction_sector=sector,
                distance_bucket=bucket,
                ttc_seconds=ttc,
                track_age_frames=track.age_frames,
                haptic_pattern_id=haptic_pattern,
                speech_key=speech_key,
                produced_offline=True,  # 100% offline invariant
                frame_timestamp_ns=timestamp_ns,
            )
            candidate_alerts.append(alert)

        self._last_detections = detections
        self._last_haptics = haptic_state
        self._last_alerts = candidate_alerts
        return detections, haptic_state, candidate_alerts, lens_status
