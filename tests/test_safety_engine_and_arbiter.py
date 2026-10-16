"""Unit tests for Nethra Phase 3: Frame Hygiene, Safety Engine, Tracker, TTC, and Arbiter."""

import unittest

import numpy as np

from contracts.frame import LensStatus
from contracts.safety_alert import DirectionSector, DistanceBucket, SafetyAlert, Tier
from services.arbiter.channel_policy import ChannelPolicy, DispatchChannel
from services.arbiter.cooldown_registry import CooldownRegistry
from services.arbiter.duplicate_suppressor import DuplicateSuppressor
from services.arbiter.priority_matrix import PriorityMatrix
from services.arbiter.rule_arbiter import RuleArbiter
from services.hygiene.blur_scorer import BlurScorer
from services.hygiene.frame_selector import FrameSelector
from services.hygiene.luminance_checker import LuminanceChecker
from services.hygiene.occlusion_heuristic import OcclusionHeuristic
from services.safety.growth_estimator import GrowthEstimator
from services.safety.mappers import BucketMapper, DirectionMapper
from services.safety.safety_engine import SafetyEngine
from services.safety.tracker import MultiObjectTracker, Track


class TestHygieneAndSafetyEngine(unittest.TestCase):

    def test_luminance_checker_darkness(self) -> None:
        checker = LuminanceChecker(min_mean_luminance=35.0)
        dark_frame = np.full((100, 100, 3), 15, dtype=np.uint8)
        bright_frame = np.full((100, 100, 3), 120, dtype=np.uint8)

        self.assertTrue(checker.is_too_dark(dark_frame))
        self.assertFalse(checker.is_too_dark(bright_frame))

    def test_blur_scorer(self) -> None:
        scorer = BlurScorer(min_variance=55.0)
        # Uniform solid image has 0 variance (completely blurry)
        solid_frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        self.assertTrue(scorer.is_blurred(solid_frame))

    def test_frame_selector_darkness_rejection(self) -> None:
        selector = FrameSelector(min_mean_luminance=35.0)
        dark_frame = np.full((100, 100, 3), 10, dtype=np.uint8)
        accepted, reason, lens_status = selector.evaluate(dark_frame)

        self.assertFalse(accepted)
        self.assertEqual(lens_status, LensStatus.TOO_DARK)

    def test_multi_object_tracker_consistency(self) -> None:
        tracker = MultiObjectTracker()
        boxes_f1 = [(100, 100, 200, 200)]
        scores_f1 = [0.9]
        labels_f1 = ["person"]

        tracks_1 = tracker.update(boxes_f1, scores_f1, labels_f1)
        self.assertEqual(len(tracks_1), 1)
        initial_id = tracks_1[0].track_id

        # Second frame slightly moved box
        boxes_f2 = [(105, 102, 205, 202)]
        tracks_2 = tracker.update(boxes_f2, [0.92], ["person"])
        self.assertEqual(len(tracks_2), 1)
        self.assertEqual(tracks_2[0].track_id, initial_id)
        self.assertEqual(tracks_2[0].age_frames, 2)

    def test_multi_object_tracker_class_stability_filter(self) -> None:
        """Transient single-frame misclassifications must be filtered out by class stability."""
        tracker = MultiObjectTracker()
        box = [(100, 100, 200, 200)]

        # 3 frames of sofa
        tracker.update(box, [0.9], ["sofa"])
        tracker.update(box, [0.9], ["sofa"])
        tracks = tracker.update(box, [0.9], ["sofa"])
        self.assertEqual(tracks[0].label, "sofa")
        self.assertTrue(tracks[0].is_confirmed)

        # 1-frame transient flicker to traffic light (e.g. YOLO misclassification)
        tracks_flicker = tracker.update(box, [0.9], ["traffic light"])
        # Must retain stable label "sofa" (filtering out the 1-frame noise)
        self.assertEqual(tracks_flicker[0].label, "sofa")

        # Returns to sofa
        tracks_back = tracker.update(box, [0.9], ["sofa"])
        self.assertEqual(tracks_back[0].label, "sofa")

    def test_growth_estimator_honesty_control(self) -> None:
        estimator = GrowthEstimator(min_track_age_frames=4)
        young_track = Track(
            track_id=1,
            label="car",
            box=(100, 100, 200, 200),
            confidence=0.9,
            age_frames=2,  # Younger than 4 frames
            box_history=[(100, 100, 200, 200), (95, 95, 205, 205)],
            time_history=[1.0, 1.1],
        )
        # Must return None for young tracks (honesty control invariant)
        ttc = estimator.estimate_ttc(young_track)
        self.assertIsNone(ttc)

    def test_direction_and_bucket_mappers(self) -> None:
        dir_mapper = DirectionMapper()
        self.assertEqual(dir_mapper.map_sector(50, 640), DirectionSector.LEFT)
        self.assertEqual(dir_mapper.map_sector(320, 640), DirectionSector.CENTRE)
        self.assertEqual(dir_mapper.map_sector(600, 640), DirectionSector.RIGHT)

        bucket_mapper = BucketMapper()
        self.assertEqual(bucket_mapper.map_bucket(0.50), DistanceBucket.IMMEDIATE)
        self.assertEqual(bucket_mapper.map_bucket(0.25), DistanceBucket.NEAR)
        self.assertEqual(bucket_mapper.map_bucket(0.10), DistanceBucket.MID)


class TestRuleArbiter(unittest.TestCase):

    def test_priority_matrix_ranking(self) -> None:
        alert_social = SafetyAlert(
            tier=Tier.SOCIAL,
            object_class="person",
            direction_sector=DirectionSector.LEFT,
            distance_bucket=DistanceBucket.MID,
            ttc_seconds=None,
            track_age_frames=5,
            haptic_pattern_id="OBSTACLE_NEAR",
            speech_key=None,
            produced_offline=True,
            frame_timestamp_ns=1000,
        )
        alert_critical = SafetyAlert(
            tier=Tier.CRITICAL,
            object_class="car",
            direction_sector=DirectionSector.CENTRE,
            distance_bucket=DistanceBucket.IMMEDIATE,
            ttc_seconds=1.2,
            track_age_frames=5,
            haptic_pattern_id="URGENT",
            speech_key="safety.critical.centre",
            produced_offline=True,
            frame_timestamp_ns=1000,
        )

        ranked = PriorityMatrix.rank_candidates([alert_social, alert_critical])
        # CRITICAL must always be ranked first
        self.assertEqual(ranked[0].tier, Tier.CRITICAL)

    def test_channel_policy_ears_free(self) -> None:
        alert_critical = SafetyAlert(
            tier=Tier.CRITICAL,
            object_class="bus",
            direction_sector=DirectionSector.CENTRE,
            distance_bucket=DistanceBucket.IMMEDIATE,
            ttc_seconds=1.0,
            track_age_frames=5,
            haptic_pattern_id="URGENT",
            speech_key="safety.critical.centre",
            produced_offline=True,
            frame_timestamp_ns=1000,
        )
        alert_advisory = SafetyAlert(
            tier=Tier.ADVISORY,
            object_class="chair",
            direction_sector=DirectionSector.RIGHT,
            distance_bucket=DistanceBucket.NEAR,
            ttc_seconds=4.0,
            track_age_frames=5,
            haptic_pattern_id="OBSTACLE_NEAR",
            speech_key=None,
            produced_offline=True,
            frame_timestamp_ns=1000,
        )

        # Critical alert triggers BOTH haptic and speech
        self.assertEqual(ChannelPolicy.select_channels(alert_critical), DispatchChannel.BOTH)
        # Advisory obstacle triggers HAPTIC_ONLY (ears-free navigation)
        self.assertEqual(ChannelPolicy.select_channels(alert_advisory), DispatchChannel.HAPTIC_ONLY)

    def test_arbiter_cooldown_and_determinism(self) -> None:
        arbiter = RuleArbiter()
        alert = SafetyAlert(
            tier=Tier.CRITICAL,
            object_class="car",
            direction_sector=DirectionSector.CENTRE,
            distance_bucket=DistanceBucket.IMMEDIATE,
            ttc_seconds=1.5,
            track_age_frames=5,
            haptic_pattern_id="URGENT",
            speech_key="safety.critical.centre",
            produced_offline=True,
            frame_timestamp_ns=1000,
        )

        # First arbitrate: should fire alert
        winning_1, chan_1 = arbiter.arbitrate([alert])
        self.assertIsNotNone(winning_1)
        self.assertEqual(chan_1, DispatchChannel.BOTH)

        # Immediate second arbitrate with same alert: suppressed by cooldown/duplicate
        winning_2, chan_2 = arbiter.arbitrate([alert])
        self.assertIsNone(winning_2)
        self.assertEqual(chan_2, DispatchChannel.SILENCE)


if __name__ == "__main__":
    unittest.main()
