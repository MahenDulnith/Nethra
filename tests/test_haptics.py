"""Unit tests for Nethra HapticPatternEngine (L1 adapters.haptic.pattern_engine)."""

import unittest

from adapters.haptic.pattern_engine import HapticOutput, HapticPatternEngine
from contracts.haptic_command import GuidanceCommand, HapticFeedbackState


class TestHapticPatternEngine(unittest.TestCase):

    def setUp(self):
        self.engine = HapticPatternEngine(
            override_threshold=80.0,
            pulse_pwm=85.0,
            aligned_pwm=100.0,
            lost_duration=0.6,
        )
        self.idle_obstacle = HapticFeedbackState(
            left_pwm=0.0, right_pwm=0.0, active_threat=None
        )

    def test_pulse_period_scaling(self):
        # Min error -> 0.8s period (slow pulse)
        self.assertAlmostEqual(self.engine.pulse_period(0.0), 0.8)
        # Max error (clamped at 0.5) -> 0.2s period (rapid pulse)
        self.assertAlmostEqual(self.engine.pulse_period(0.5), 0.2)
        self.assertAlmostEqual(self.engine.pulse_period(0.9), 0.2)
        # Mid error (0.25) -> 0.5s period
        self.assertAlmostEqual(self.engine.pulse_period(0.25), 0.5)

    def test_aligned_double_pulse_timing(self):
        # Phase 0.05 is inside pulse 1 [0.0, 0.1) -> True
        self.assertTrue(self.engine.aligned_on(1.05))
        # Phase 0.15 is between pulses [0.1, 0.2) -> False
        self.assertFalse(self.engine.aligned_on(1.15))
        # Phase 0.25 is inside pulse 2 [0.2, 0.3) -> True
        self.assertTrue(self.engine.aligned_on(1.25))
        # Phase 0.50 is off period [0.3, 1.0) -> False
        self.assertFalse(self.engine.aligned_on(1.50))

    def test_obstacle_safety_override(self):
        # Threat >= 80% MUST override guidance steering immediately
        threat_obstacle = HapticFeedbackState(
            left_pwm=90.0, right_pwm=90.0, active_threat="chair"
        )
        out = self.engine.compute(
            command=GuidanceCommand.MOVE_LEFT,
            magnitude=0.4,
            now=0.01,
            obstacle=threat_obstacle,
            guidance_active=True,
        )
        self.assertEqual(out.source, "obstacle")
        self.assertIn("OBSTACLE", out.label)
        self.assertEqual(out.left_pwm, 90.0)
        self.assertEqual(out.right_pwm, 90.0)

    def test_inactive_guidance_fallback(self):
        nav_obstacle = HapticFeedbackState(
            left_pwm=40.0, right_pwm=20.0, active_threat=None
        )
        out = self.engine.compute(
            command=GuidanceCommand.NONE,
            magnitude=0.0,
            now=1.0,
            obstacle=nav_obstacle,
            guidance_active=False,
        )
        self.assertEqual(out.source, "obstacle")
        self.assertEqual(out.label, "NAVIGATION")
        self.assertEqual(out.left_pwm, 40.0)
        self.assertEqual(out.right_pwm, 20.0)

    def test_steering_left_right(self):
        # Pulse is on during first 45% of period
        # For magnitude 0.0, period = 0.8s, on-window is [0, 0.36s)
        out_left = self.engine.compute(
            command=GuidanceCommand.MOVE_LEFT,
            magnitude=0.0,
            now=0.1,  # Inside on-phase
            obstacle=self.idle_obstacle,
            guidance_active=True,
        )
        self.assertEqual(out_left.source, "guidance")
        self.assertEqual(out_left.label, "MOVE LEFT")
        self.assertEqual(out_left.left_pwm, 85.0)
        self.assertEqual(out_left.right_pwm, 0.0)

        out_right = self.engine.compute(
            command=GuidanceCommand.MOVE_RIGHT,
            magnitude=0.0,
            now=0.1,  # Inside on-phase
            obstacle=self.idle_obstacle,
            guidance_active=True,
        )
        self.assertEqual(out_right.source, "guidance")
        self.assertEqual(out_right.label, "MOVE RIGHT")
        self.assertEqual(out_right.left_pwm, 0.0)
        self.assertEqual(out_right.right_pwm, 85.0)

        # Off-phase of pulse (now = 0.5s in 0.8s period)
        out_left_off = self.engine.compute(
            command=GuidanceCommand.MOVE_LEFT,
            magnitude=0.0,
            now=0.5,
            obstacle=self.idle_obstacle,
            guidance_active=True,
        )
        self.assertEqual(out_left_off.left_pwm, 0.0)
        self.assertEqual(out_left_off.right_pwm, 0.0)

    def test_aligned_pattern(self):
        # Double pulse at t=2.05 (phase 0.05) -> 100% PWM both hands
        out_on = self.engine.compute(
            command=GuidanceCommand.ALIGNED,
            magnitude=0.0,
            now=2.05,
            obstacle=self.idle_obstacle,
            guidance_active=True,
        )
        self.assertEqual(out_on.source, "guidance")
        self.assertEqual(out_on.label, "ON TARGET")
        self.assertEqual(out_on.left_pwm, 100.0)
        self.assertEqual(out_on.right_pwm, 100.0)

        # Between pulses at t=2.15 (phase 0.15) -> 0% PWM both hands
        out_off = self.engine.compute(
            command=GuidanceCommand.ALIGNED,
            magnitude=0.0,
            now=2.15,
            obstacle=self.idle_obstacle,
            guidance_active=True,
        )
        self.assertEqual(out_off.left_pwm, 0.0)
        self.assertEqual(out_off.right_pwm, 0.0)

    def test_target_lost_buzz(self):
        out = self.engine.compute(
            command=GuidanceCommand.LOST,
            magnitude=0.0,
            now=5.0,
            obstacle=self.idle_obstacle,
            guidance_active=True,
        )
        self.assertEqual(out.label, "TARGET LOST")
        self.assertEqual(out.left_pwm, 70.0)
        self.assertEqual(out.right_pwm, 70.0)

        # 0.3s later (still within 0.6s lost_duration)
        out_during = self.engine.compute(
            command=GuidanceCommand.SEARCHING,
            magnitude=0.0,
            now=5.3,
            obstacle=self.idle_obstacle,
            guidance_active=True,
        )
        self.assertEqual(out_during.label, "TARGET LOST")

        # After lost_duration expires at 5.7s
        out_after = self.engine.compute(
            command=GuidanceCommand.SEARCHING,
            magnitude=0.0,
            now=5.7,
            obstacle=self.idle_obstacle,
            guidance_active=True,
        )
        self.assertNotEqual(out_after.label, "TARGET LOST")


if __name__ == "__main__":
    unittest.main()
