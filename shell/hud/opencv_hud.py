"""L5 OpenCV Heads-Up Display (HUD) for Nethra Assistive Vision Prototype."""

from __future__ import annotations

from typing import List, Optional, Union

import cv2
import numpy as np

from adapters.camera.base import get_camera_name
from contracts.detection import Detection
from contracts.haptic_command import HapticFeedbackState


def render_hud(
    frame: np.ndarray,
    detections: List[Detection],
    haptics: HapticFeedbackState,
    context_msg: Optional[str],
    fps: float,
    camera_idx: Union[int, str],
    location_msg: Optional[str] = None,
    toast_msg: Optional[str] = None,
    model_mode_label: str = "Ensemble: COCO-80 + Doors",
) -> np.ndarray:
    """Renders the high-contrast Nethra assistive vision HUD overlay."""
    h, w, _ = frame.shape
    overlay = frame.copy()

    one_third = int(w / 3.0)
    two_thirds = int((w * 2.0) / 3.0)

    # 1. TOP STATUS BAR (Semi-transparent dark header)
    top_bar_h = 44
    cv2.rectangle(overlay, (0, 0), (w, top_bar_h), (18, 18, 22), -1)

    # Title & Brand (Standardized to Nethra AI)
    cv2.putText(
        overlay,
        "Nethra AI",
        (14, 27),
        cv2.FONT_HERSHEY_DUPLEX,
        0.62,
        (0, 230, 255),
        1,
        cv2.LINE_AA,
    )

    # Model Badge
    cv2.putText(
        overlay,
        f"[{model_mode_label}]",
        (135, 27),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.40,
        (200, 220, 255),
        1,
        cv2.LINE_AA,
    )

    # Camera Device Badge
    cam_badge_color = (0, 200, 100) if camera_idx == 1 or isinstance(camera_idx, str) else (180, 180, 180)
    cam_label = f"Cam: #{camera_idx}" if isinstance(camera_idx, int) else "Cam: Android"
    cv2.putText(
        overlay,
        cam_label,
        (w - 190, 27),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        cam_badge_color,
        1,
        cv2.LINE_AA,
    )

    # FPS Indicator
    fps_color = (0, 255, 120) if fps >= 20 else ((0, 200, 255) if fps >= 10 else (0, 100, 255))
    cv2.putText(
        overlay,
        f"{fps:4.1f} FPS",
        (w - 85, 27),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        fps_color,
        1,
        cv2.LINE_AA,
    )

    # 2. ZONE DIVIDERS & LABELS
    cv2.line(overlay, (one_third, top_bar_h), (one_third, h - 88), (80, 80, 95), 1)
    cv2.line(overlay, (two_thirds, top_bar_h), (two_thirds, h - 88), (80, 80, 95), 1)

    left_active = haptics.left_pwm > 0 and haptics.left_pwm != haptics.right_pwm
    center_active = haptics.left_pwm > 0 and haptics.left_pwm == haptics.right_pwm
    right_active = haptics.right_pwm > 0 and haptics.left_pwm != haptics.right_pwm

    cv2.putText(
        overlay,
        "< LEFT ZONE",
        (18, 62),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.44,
        (0, 180, 255) if left_active else (140, 140, 150),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        overlay,
        "^ CENTER (AHEAD)",
        (one_third + 20, 62),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.44,
        (0, 100, 255) if center_active else (140, 140, 150),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        overlay,
        "RIGHT ZONE >",
        (two_thirds + 20, 62),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.44,
        (0, 180, 255) if right_active else (140, 140, 150),
        1,
        cv2.LINE_AA,
    )

    # 3. BOUNDING BOXES
    for det in detections:
        x1, y1, x2, y2 = det.box
        if det.pwm_intensity > 60:
            box_color = (0, 50, 255)    # Urgent Red
        elif det.pwm_intensity > 25:
            box_color = (0, 165, 255)   # Amber Orange
        else:
            box_color = (50, 220, 100)  # Gentle Green

        cv2.rectangle(overlay, (x1, y1), (x2, y2), box_color, 2)

        tag_text = f"{det.label} {det.confidence:.0%} | {det.pwm_intensity:.0f}% PWM"
        (tw, th), _ = cv2.getTextSize(tag_text, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
        tag_y = max(top_bar_h + 16, y1 - 6)
        cv2.rectangle(overlay, (x1, tag_y - th - 4), (x1 + tw + 8, tag_y + 2), box_color, -1)
        cv2.putText(
            overlay,
            tag_text,
            (x1 + 4, tag_y - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )

    # 4. BOTTOM HUD BAR (Haptic Vibration Meters & Telemetry)
    hud_bar_h = 88
    cv2.rectangle(overlay, (0, h - hud_bar_h), (w, h), (18, 18, 22), -1)

    meter_w = int(w * 0.32)
    left_fill = int(meter_w * (haptics.left_pwm / 100.0))
    cv2.putText(
        overlay,
        f"LEFT WRIST: {haptics.left_pwm:4.1f}% PWM",
        (16, h - 58),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (210, 210, 220),
        1,
        cv2.LINE_AA,
    )
    cv2.rectangle(overlay, (16, h - 48), (16 + meter_w, h - 30), (50, 50, 60), 1)
    if left_fill > 0:
        cv2.rectangle(
            overlay,
            (16, h - 48),
            (16 + left_fill, h - 30),
            (0, 180, 255) if haptics.left_pwm < 50 else (0, 70, 255),
            -1,
        )

    right_x = w - meter_w - 16
    right_fill = int(meter_w * (haptics.right_pwm / 100.0))
    cv2.putText(
        overlay,
        f"RIGHT WRIST: {haptics.right_pwm:4.1f}% PWM",
        (right_x, h - 58),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (210, 210, 220),
        1,
        cv2.LINE_AA,
    )
    cv2.rectangle(overlay, (right_x, h - 48), (right_x + meter_w, h - 30), (50, 50, 60), 1)
    if right_fill > 0:
        cv2.rectangle(
            overlay,
            (right_x, h - 48),
            (right_x + right_fill, h - 30),
            (0, 180, 255) if haptics.right_pwm < 50 else (0, 70, 255),
            -1,
        )

    threat_text = haptics.active_threat or "Path Clear"
    threat_color = (0, 80, 255) if haptics.active_threat else (50, 220, 100)
    cv2.putText(
        overlay,
        threat_text,
        (int(w * 0.36), h - 55),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.44,
        threat_color,
        1,
        cv2.LINE_AA,
    )

    labels_summary = ", ".join(list({d.label for d in detections})) if detections else "None in view"
    if len(labels_summary) > 28:
        labels_summary = labels_summary[:25] + "..."
    cv2.putText(
        overlay,
        f"Seen: {labels_summary}",
        (int(w * 0.36), h - 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.38,
        (160, 160, 175),
        1,
        cv2.LINE_AA,
    )

    cv2.putText(
        overlay,
        "[C] Switch Camera   |   [W] Where Am I?   |   [Q] Exit",
        (16, h - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.38,
        (120, 120, 135),
        1,
        cv2.LINE_AA,
    )

    # 5. TOAST & NOTIFICATION BANNERS
    if toast_msg:
        cv2.rectangle(overlay, (w // 8, 50), (7 * w // 8, 86), (20, 120, 220), -1)
        cv2.putText(
            overlay,
            toast_msg,
            (w // 8 + 14, 74),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    if context_msg:
        cv2.rectangle(overlay, (w // 8, 92), (7 * w // 8, 128), (40, 140, 40), -1)
        cv2.putText(
            overlay,
            context_msg,
            (w // 8 + 14, 116),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    if location_msg:
        cv2.rectangle(overlay, (40, 92), (w - 40, 128), (140, 60, 0), -1)
        cv2.putText(
            overlay,
            location_msg,
            (50, 116),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.44,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    return overlay
