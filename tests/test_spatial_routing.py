"""Unit tests for Nethra L0 contracts, L2 spatial routing, IoU deduplication, and L4 context scene tracking."""

import unittest

from contracts.detection import Detection
from contracts.safety_alert import DirectionSector, DistanceBucket, SafetyAlert, Tier
from features.context_routines.context_tracker import ContextSceneTracker
from services.safety.spatial_router import SpatialRoutingEngine
from services.safety.yolo_ensemble import compute_iou, merge_candidate_detections


class TestSpatialRouting(unittest.TestCase):

    def setUp(self) -> None:
        self.router = SpatialRoutingEngine(min_area_ratio=0.02, max_area_ratio=0.35)
        self.frame_width = 640
        self.frame_height = 480

    def test_zone_division(self) -> None:
        self.assertEqual(self.router.determine_zone(100.0, self.frame_width), "LEFT")
        self.assertEqual(self.router.determine_zone(320.0, self.frame_width), "CENTER")
        self.assertEqual(self.router.determine_zone(550.0, self.frame_width), "RIGHT")

    def test_pwm_calculation(self) -> None:
        self.assertEqual(self.router.calculate_pwm(0.01), 0.0)
        self.assertEqual(self.router.calculate_pwm(0.40), 100.0)

        mid_ratio = (0.02 + 0.35) / 2.0
        pwm = self.router.calculate_pwm(mid_ratio)
        self.assertAlmostEqual(pwm, 50.0, delta=1.0)

    def test_left_obstacle_routing(self) -> None:
        boxes = [(10, 100, 150, 300)]
        scores = [0.9]
        class_ids = [0]
        class_names = {0: "person"}

        dets, state = self.router.process_detections(
            boxes=boxes,
            scores=scores,
            class_ids=class_ids,
            class_names=class_names,
            frame_width=self.frame_width,
            frame_height=self.frame_height,
        )

        self.assertEqual(len(dets), 1)
        self.assertEqual(dets[0].label, "person")
        self.assertEqual(dets[0].zone, "LEFT")
        self.assertGreater(state.left_pwm, 0.0)
        self.assertEqual(state.right_pwm, 0.0)

    def test_right_obstacle_routing(self) -> None:
        boxes = [(450, 100, 600, 300)]
        scores = [0.85]
        class_ids = [56]
        class_names = {56: "chair"}

        dets, state = self.router.process_detections(
            boxes=boxes,
            scores=scores,
            class_ids=class_ids,
            class_names=class_names,
            frame_width=self.frame_width,
            frame_height=self.frame_height,
        )

        self.assertEqual(len(dets), 1)
        self.assertEqual(dets[0].label, "chair")
        self.assertEqual(dets[0].zone, "RIGHT")
        self.assertEqual(state.left_pwm, 0.0)
        self.assertGreater(state.right_pwm, 0.0)

    def test_center_obstacle_triggers_both_wristbands(self) -> None:
        boxes = [(250, 100, 390, 300)]
        scores = [0.92]
        class_ids = [59]
        class_names = {59: "bed"}

        dets, state = self.router.process_detections(
            boxes=boxes,
            scores=scores,
            class_ids=class_ids,
            class_names=class_names,
            frame_width=self.frame_width,
            frame_height=self.frame_height,
        )

        self.assertEqual(len(dets), 1)
        self.assertEqual(dets[0].zone, "CENTER")
        self.assertGreater(state.left_pwm, 0.0)
        self.assertEqual(state.left_pwm, state.right_pwm)

    def test_iou_and_ensemble_deduplication(self) -> None:
        box1 = (100, 100, 200, 200)
        box2 = (105, 105, 205, 205)  # High overlap with box1
        box3 = (400, 100, 500, 200)  # Disjoint box
        self.assertGreater(compute_iou(box1, box2), 0.6)
        self.assertEqual(compute_iou(box1, box3), 0.0)

        candidates = [
            (box1, 0.85, "door"),
            (box2, 0.92, "door-open"),
            (box3, 0.75, "person"),
        ]
        merged = merge_candidate_detections(candidates, iou_thresh=0.45)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0][2], "door-open")
        self.assertEqual(merged[1][2], "person")


class TestContextSceneTracker(unittest.TestCase):

    def test_bed_wake_up_detection(self) -> None:
        tracker = ContextSceneTracker()
        det = Detection(
            label="bed",
            confidence=0.9,
            box=(100, 100, 300, 300),
            center_x=200,
            center_y=200,
            width=200,
            height=200,
            area_ratio=0.13,
            zone="LEFT",
            pwm_intensity=35.0,
        )

        greeting = None
        for _ in range(12):
            greeting = tracker.update([det])
            if greeting:
                break

        self.assertIsNotNone(greeting)
        assert greeting is not None
        self.assertIn("Good morning", greeting)
        self.assertIn("bed", greeting)

    def test_location_query(self) -> None:
        tracker = ContextSceneTracker()
        det = Detection(
            label="chair",
            confidence=0.88,
            box=(50, 50, 150, 150),
            center_x=100,
            center_y=100,
            width=100,
            height=100,
            area_ratio=0.03,
            zone="LEFT",
            pwm_intensity=10.0,
        )
        response = tracker.query_location([det])
        self.assertIn("University of Sri Jayewardenepura", response)
        self.assertIn("chair", response)

    def test_critical_alert_offline_invariant(self) -> None:
        with self.assertRaises(ValueError):
            SafetyAlert(
                tier=Tier.CRITICAL,
                object_class="car",
                direction_sector=DirectionSector.CENTRE,
                distance_bucket=DistanceBucket.IMMEDIATE,
                ttc_seconds=1.2,
                track_age_frames=5,
                haptic_pattern_id="URGENT",
                speech_key="safety.critical.centre",
                produced_offline=False,
                frame_timestamp_ns=1000,
            )


if __name__ == "__main__":
    unittest.main()
