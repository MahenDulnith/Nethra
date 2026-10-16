"""Unit tests for Nethra Guided Search state machine and multi-bed disambiguation."""

import unittest

from contracts.detection import Detection
from contracts.haptic_command import GuidanceCommand, GuidanceState
from features.lookaround.guidance import (
    GuidanceConfig,
    GuidanceOutput,
    GuidanceStateMachine,
)
from services.safety.yolo_ensemble import (
    disambiguate_multi_bed_candidates,
    merge_candidate_detections,
)


def make_det(
    label: str,
    cx: float,
    cy: float = 240.0,
    w: float = 120.0,
    h: float = 240.0,
    area_ratio: float = 0.10,
    conf: float = 0.85,
    zone: str = "CENTER",
) -> Detection:
    x1 = int(cx - w / 2.0)
    x2 = int(cx + w / 2.0)
    y1 = int(cy - h / 2.0)
    y2 = int(cy + h / 2.0)
    return Detection(
        label=label,
        confidence=conf,
        box=(x1, y1, x2, y2),
        center_x=cx,
        center_y=cy,
        width=w,
        height=h,
        area_ratio=area_ratio,
        zone=zone,
        pwm_intensity=30.0,
    )


class TestGuidanceStateMachine(unittest.TestCase):

    def setUp(self):
        # Deterministic config for fast unit testing
        self.cfg = GuidanceConfig(
            confirm_window=5,
            confirm_hits=3,
            lost_frames=5,
            head_tolerance=0.10,
            hand_tolerance=0.08,
            aligned_hold_frames=2,
            hand_missing_frames=4,
            look_around_interval=2.0,
            first_prompt_delay=0.0,
            smoothing=1.0,  # No smoothing for direct coordinate checks
        )
        self.sm = GuidanceStateMachine(self.cfg)
        self.fw = 640
        self.fh = 480

    def test_start_and_cancel(self):
        out = self.sm.start("door", now=0.0)
        self.assertEqual(out.state, GuidanceState.SEARCHING)
        self.assertIn("door", out.speech.lower())

        out2 = self.sm.cancel(now=1.0)
        self.assertEqual(out2.state, GuidanceState.IDLE)
        self.assertFalse(self.sm.active)

    def test_confirmation_filter(self):
        # Target must be seen at least 3 times in 5 frames
        self.sm.start("door", now=0.0)
        door_det = make_det("door", cx=320.0, zone="CENTER")

        # Frame 1: 1 hit -> still searching
        out1 = self.sm.update([door_det], hand_point=None, frame_width=self.fw, frame_height=self.fh, now=0.1)
        self.assertEqual(out1.state, GuidanceState.SEARCHING)

        # Frame 2: 2 hits -> still searching
        out2 = self.sm.update([door_det], hand_point=None, frame_width=self.fw, frame_height=self.fh, now=0.2)
        self.assertEqual(out2.state, GuidanceState.SEARCHING)

        # Frame 3: 3 hits -> confirmed! Switches to HEAD_GUIDE
        out3 = self.sm.update([door_det], hand_point=None, frame_width=self.fw, frame_height=self.fh, now=0.3)
        self.assertEqual(out3.state, GuidanceState.HEAD_GUIDE)
        self.assertEqual(out3.chime, "found")
        self.assertIn("found", out3.speech.lower())

    def test_look_around_with_memory(self):
        # In SEARCHING state, when target not seen, AI describes what it DOES see
        self.sm.start("door", now=0.0)
        other_dets = [make_det("bed", cx=100.0), make_det("chair", cx=200.0)]

        out = self.sm.update(other_dets, hand_point=None, frame_width=self.fw, frame_height=self.fh, now=2.5)
        self.assertIsNotNone(out.speech)
        self.assertIn("bed", out.speech)
        self.assertIn("chair", out.speech)

    def test_head_guidance_steering(self):
        self.sm.start("door", now=0.0)
        # Door is on the right (cx = 500)
        door_right = make_det("door", cx=500.0, zone="RIGHT")
        for t in [0.1, 0.2, 0.3]:
            out = self.sm.update([door_right], hand_point=None, frame_width=self.fw, frame_height=self.fh, now=t)

        self.assertEqual(out.state, GuidanceState.HEAD_GUIDE)
        # Door is right of frame center (320) -> steer right
        self.assertEqual(out.command, GuidanceCommand.MOVE_RIGHT)

    def test_hand_steering_and_alignment(self):
        self.sm.start("door", now=0.0)
        door_center = make_det("door", cx=320.0, cy=240.0, zone="CENTER")

        # Confirm door into HEAD_GUIDE
        for t in [0.1, 0.2, 0.3]:
            self.sm.update([door_center], hand_point=None, frame_width=self.fw, frame_height=self.fh, now=t)

        # User raises hand at x = 150 (hand is to the left of door at 320)
        # Target (320) is to the RIGHT of hand (150) -> command should be MOVE_RIGHT
        out_hand = self.sm.update([door_center], hand_point=(150.0, 300.0), frame_width=self.fw, frame_height=self.fh, now=0.4)
        self.assertEqual(out_hand.state, GuidanceState.HAND_GUIDE)
        self.assertEqual(out_hand.command, GuidanceCommand.MOVE_RIGHT)

        # User moves hand right to x = 450 (hand is to the right of door at 320)
        # Target (320) is to the LEFT of hand (450) -> command should be MOVE_LEFT
        out_hand_left = self.sm.update([door_center], hand_point=(450.0, 300.0), frame_width=self.fw, frame_height=self.fh, now=0.5)
        self.assertEqual(out_hand_left.command, GuidanceCommand.MOVE_LEFT)

        # User moves hand directly over target (door at 320, hand at 325)
        # error = (320 - 325)/640 = -0.0078 <= hand_tolerance (0.08)
        self.sm.update([door_center], hand_point=(325.0, 240.0), frame_width=self.fw, frame_height=self.fh, now=0.6)
        out_aligned = self.sm.update([door_center], hand_point=(325.0, 240.0), frame_width=self.fw, frame_height=self.fh, now=0.7)

        self.assertEqual(out_aligned.state, GuidanceState.ALIGNED)
        self.assertEqual(out_aligned.command, GuidanceCommand.ALIGNED)
        self.assertEqual(out_aligned.chime, "aligned")

    def test_target_lost_and_arrival(self):
        self.sm.start("door", now=0.0)
        door_det = make_det("door", cx=320.0, zone="CENTER")
        for t in [0.1, 0.2, 0.3]:
            self.sm.update([door_det], hand_point=None, frame_width=self.fw, frame_height=self.fh, now=t)

        # Missing for 5 consecutive frames (lost_frames=5)
        for t in [0.4, 0.5, 0.6, 0.7]:
            out = self.sm.update([], hand_point=None, frame_width=self.fw, frame_height=self.fh, now=t)
            self.assertEqual(out.state, GuidanceState.HEAD_GUIDE)  # Brief dropout held

        # 5th miss -> Target Lost
        out_lost = self.sm.update([], hand_point=None, frame_width=self.fw, frame_height=self.fh, now=0.8)
        self.assertEqual(out_lost.command, GuidanceCommand.LOST)
        self.assertEqual(out_lost.state, GuidanceState.SEARCHING)


class TestMultiBedDisambiguation(unittest.TestCase):

    def test_three_beds_where_second_and_third_misclassified_as_table_and_chair(self):
        # Bed 1: correctly detected as 'bed'
        # Bed 2: misclassified as 'dining table' / 'table'
        # Bed 3: misclassified as 'chair'
        raw_candidates = [
            ((20, 200, 200, 420), 0.78, "bed"),
            ((220, 210, 410, 410), 0.55, "dining table"),
            ((430, 220, 610, 400), 0.48, "chair"),
        ]
        resolved = disambiguate_multi_bed_candidates(
            strong_candidates=raw_candidates,
            weak_bed_boxes=[(20, 200, 200, 420)],
            frame_width=640,
            frame_height=480,
            bedroom_context_active=True,
        )
        merged = merge_candidate_detections(resolved)
        self.assertEqual(len(merged), 3)
        self.assertEqual([c[2] for c in merged], ["bed", "bed", "bed"])

    def test_bed_wins_tie_against_overlapping_table_or_chair(self):
        # Even if 'table' has higher raw score (0.65) than 'bed' (0.45) on the same bed
        candidates = [
            ((100, 150, 350, 400), 0.65, "table"),
            ((105, 155, 345, 395), 0.45, "bed"),
        ]
        merged = merge_candidate_detections(candidates, iou_thresh=0.45)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0][2], "bed")


if __name__ == "__main__":
    unittest.main()
