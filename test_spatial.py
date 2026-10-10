"""Unit test for spatial routing and context scene tracking logic."""

import unittest
from main import SpatialRoutingEngine, ContextSceneTracker, Detection


class TestSpatialRouting(unittest.TestCase):

    def setUp(self):
        self.router = SpatialRoutingEngine(min_area_ratio=0.02, max_area_ratio=0.35)
        self.frame_width = 640
        self.frame_height = 480

    def test_zone_division(self):
        # Frame width 640:
        # Left zone: < 213.33
        # Center zone: 213.33 to 426.67
        # Right zone: > 426.67
        self.assertEqual(self.router.determine_zone(100.0, self.frame_width), "LEFT")
        self.assertEqual(self.router.determine_zone(320.0, self.frame_width), "CENTER")
        self.assertEqual(self.router.determine_zone(550.0, self.frame_width), "RIGHT")

    def test_pwm_calculation(self):
        # Below min area ratio (0.02)
        self.assertEqual(self.router.calculate_pwm(0.01), 0.0)

        # Above max area ratio (0.35)
        self.assertEqual(self.router.calculate_pwm(0.40), 100.0)

        # Intermediate value
        mid_ratio = (0.02 + 0.35) / 2.0
        pwm = self.router.calculate_pwm(mid_ratio)
        self.assertAlmostEqual(pwm, 50.0, delta=1.0)

    def test_left_obstacle_routing(self):
        # Bounding box in the left third
        boxes = [(10, 100, 150, 300)]  # width 140, height 200, cx = 80 (< 213)
        scores = [0.9]
        class_ids = [0]
        class_names = {0: "person"}

        dets, state = self.router.process_detections(
            boxes, scores, class_ids, class_names, self.frame_width, self.frame_height
        )

        self.assertEqual(len(dets), 1)
        self.assertEqual(dets[0].zone, "LEFT")
        self.assertGreater(state.left_pwm, 0.0)
        self.assertEqual(state.right_pwm, 0.0)

    def test_right_obstacle_routing(self):
        # Bounding box in the right third
        boxes = [(450, 100, 600, 300)]  # cx = 525 (> 426)
        scores = [0.85]
        class_ids = [56]
        class_names = {56: "chair"}

        dets, state = self.router.process_detections(
            boxes, scores, class_ids, class_names, self.frame_width, self.frame_height
        )

        self.assertEqual(len(dets), 1)
        self.assertEqual(dets[0].zone, "RIGHT")
        self.assertEqual(state.left_pwm, 0.0)
        self.assertGreater(state.right_pwm, 0.0)

    def test_center_obstacle_triggers_both_wristbands(self):
        # Bounding box in center third (direct collision course)
        boxes = [(250, 100, 390, 300)]  # cx = 320 (center)
        scores = [0.92]
        class_ids = [59]
        class_names = {59: "bed"}

        dets, state = self.router.process_detections(
            boxes, scores, class_ids, class_names, self.frame_width, self.frame_height
        )

        self.assertEqual(len(dets), 1)
        self.assertEqual(dets[0].zone, "CENTER")
        # Center collision path vibrates both wristbands equally
        self.assertGreater(state.left_pwm, 0.0)
        self.assertEqual(state.left_pwm, state.right_pwm)


class TestContextSceneTracker(unittest.TestCase):

    def test_bed_wake_up_detection(self):
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

        # Simulate consecutive frames seeing bed
        greeting = None
        for _ in range(12):
            greeting = tracker.update([det])
            if greeting:
                break

        self.assertIsNotNone(greeting)
        self.assertIn("Good morning", greeting)
        self.assertIn("bed", greeting)

    def test_location_query(self):
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


if __name__ == "__main__":
    unittest.main()
