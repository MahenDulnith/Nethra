"""Unit tests for ContextSceneTracker, room inference, and multi-modal location queries."""

import unittest

from contracts.detection import Detection
from features.context_routines.context_tracker import ContextSceneTracker


def make_det(label: str, cx: float = 320.0, cy: float = 240.0) -> Detection:
    return Detection(
        label=label,
        confidence=0.90,
        box=(int(cx - 50), int(cy - 50), int(cx + 50), int(cy + 50)),
        center_x=cx,
        center_y=cy,
        width=100.0,
        height=100.0,
        area_ratio=0.10,
        zone="CENTER",
        pwm_intensity=40.0,
    )


class TestContextSceneTracker(unittest.TestCase):

    def test_location_resolution(self):
        # 1. Cisco Lab profile
        tracker_cisco = ContextSceneTracker(location="cisco_lab")
        self.assertIn("Cisco", tracker_cisco.location_title)
        self.assertIn("Jayewardenepura", tracker_cisco.location_address)

        # 2. Home profile
        tracker_home = ContextSceneTracker(location="home")
        self.assertEqual(tracker_home.location_title, "Home")
        self.assertIn("Malabe", tracker_home.location_address)

        # 3. Custom free-form location
        tracker_custom = ContextSceneTracker(location="Kandy Railway Station")
        self.assertEqual(tracker_custom.location_title, "Kandy Railway Station")
        self.assertEqual(tracker_custom.location_address, "Kandy Railway Station")

    def test_room_inference_computer_lab(self):
        tracker = ContextSceneTracker(location="cisco_lab")
        # Cisco Lab scenario: multiple laptops, chairs, person
        dets = [
            make_det("laptop", cx=200),
            make_det("laptop", cx=400),
            make_det("chair", cx=250),
            make_det("chair", cx=450),
            make_det("person", cx=300),
        ]
        # Seed history
        for _ in range(5):
            tracker.update(dets)

        room_name, room_desc = tracker.infer_room(dets)
        self.assertEqual(room_name, "Computer Laboratory")
        self.assertIn("computer laboratory", room_desc.lower())

        # Test combined query
        spoken, hud = tracker.query_location_details(dets)
        self.assertIn("Jayewardenepura", spoken)
        self.assertIn("computer laboratory", spoken.lower())
        self.assertIn("Computer Laboratory", hud)

    def test_room_inference_bedroom(self):
        tracker = ContextSceneTracker(location="home")
        dets = [make_det("bed"), make_det("chair")]
        for _ in range(5):
            tracker.update(dets)

        room_name, room_desc = tracker.infer_room(dets)
        self.assertEqual(room_name, "Bedroom")
        self.assertIn("bed", room_desc.lower())

        spoken, hud = tracker.query_location_details(dets)
        self.assertIn("Malabe", spoken)
        self.assertIn("bed", spoken.lower())

    def test_room_inference_living_room(self):
        tracker = ContextSceneTracker(location="home")
        dets = [make_det("sofa"), make_det("tv")]
        for _ in range(5):
            tracker.update(dets)

        room_name, room_desc = tracker.infer_room(dets)
        self.assertEqual(room_name, "Living Room")
        self.assertIn("living room", room_desc.lower())

    def test_room_inference_kitchen(self):
        tracker = ContextSceneTracker(location="home")
        dets = [make_det("refrigerator"), make_det("dining table"), make_det("bottle")]
        for _ in range(5):
            tracker.update(dets)

        room_name, _ = tracker.infer_room(dets)
        self.assertEqual(room_name, "Kitchen Area")

    def test_room_inference_outdoors(self):
        tracker = ContextSceneTracker(location="home")
        dets = [make_det("car"), make_det("traffic light")]
        for _ in range(5):
            tracker.update(dets)

        room_name, _ = tracker.infer_room(dets)
        self.assertEqual(room_name, "Outdoors")


if __name__ == "__main__":
    unittest.main()
