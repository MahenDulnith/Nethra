"""L1 Haptic pattern engine: turns guidance commands into time-varying wristband PWM levels."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.haptic_command import GuidanceCommand, HapticFeedbackState


@dataclass
class HapticOutput:
    left_pwm: float
    right_pwm: float
    label: str
    source: str  # "guidance" | "obstacle"


class HapticPatternEngine:
    """Pattern vocabulary for Nethra dual wristbands.

    MOVE_LEFT / MOVE_RIGHT : pulses on one band, faster as the error grows
    ALIGNED                : synchronised double pulse on both bands ("da-DUM")
    LOST                   : one long buzz on both bands
    SEARCHING              : faint tick every 2 s so the user knows the search is running
    Obstacle >= override   : always wins over guidance (safety)
    """

    def __init__(
        self,
        override_threshold: float = 80.0,
        pulse_pwm: float = 85.0,
        aligned_pwm: float = 100.0,
        lost_duration: float = 0.6,
    ) -> None:
        self.override_threshold = override_threshold
        self.pulse_pwm = pulse_pwm
        self.aligned_pwm = aligned_pwm
        self.lost_duration = lost_duration
        self._lost_until = 0.0

    @staticmethod
    def pulse_period(magnitude: float) -> float:
        """0.8 s between pulses when nearly on target, down to 0.2 s when far off."""
        m = min(max(magnitude, 0.0), 0.5)
        return 0.8 - 1.2 * m

    @staticmethod
    def aligned_on(now: float) -> bool:
        phase = now % 1.0
        return phase < 0.1 or 0.2 <= phase < 0.3

    def compute(
        self,
        command: GuidanceCommand,
        magnitude: float,
        now: float,
        obstacle: HapticFeedbackState,
        guidance_active: bool,
    ) -> HapticOutput:
        if not guidance_active and command != GuidanceCommand.LOST and now >= self._lost_until:
            return HapticOutput(obstacle.left_pwm, obstacle.right_pwm, "NAVIGATION", "obstacle")

        if max(obstacle.left_pwm, obstacle.right_pwm) >= self.override_threshold:
            return HapticOutput(
                obstacle.left_pwm,
                obstacle.right_pwm,
                f"OBSTACLE: {obstacle.active_threat or 'ahead'}",
                "obstacle",
            )

        if command == GuidanceCommand.LOST:
            self._lost_until = now + self.lost_duration
        if now < self._lost_until:
            return HapticOutput(70.0, 70.0, "TARGET LOST", "guidance")

        if command in (GuidanceCommand.MOVE_LEFT, GuidanceCommand.MOVE_RIGHT):
            period = self.pulse_period(magnitude)
            pwm = self.pulse_pwm if (now % period) < period * 0.45 else 0.0
            if command == GuidanceCommand.MOVE_LEFT:
                return HapticOutput(pwm, 0.0, "MOVE LEFT", "guidance")
            return HapticOutput(0.0, pwm, "MOVE RIGHT", "guidance")

        if command == GuidanceCommand.ALIGNED:
            pwm = self.aligned_pwm if self.aligned_on(now) else 0.0
            return HapticOutput(pwm, pwm, "ON TARGET", "guidance")

        if command == GuidanceCommand.SEARCHING:
            pwm = 25.0 if (now % 2.0) < 0.06 else 0.0
            return HapticOutput(pwm, pwm, "SEARCHING", "guidance")

        return HapticOutput(0.0, 0.0, "GUIDING", "guidance")
