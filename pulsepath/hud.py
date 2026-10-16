"""HUD and visualization module for PulsePath Assistive Vision.

Renders:
- Top bar: Brand, mode badge (NAVIGATION, SEARCHING, GUIDING HAND, ALIGNED), camera, FPS.
- Dual visual wristband gauges on left and right borders that pulse dynamically with PWM.
- Bounding boxes with threat-color coding.
- Target highlight (crosshair and glowing target box in search mode).
- Hand tracking marker (fingertip circle) and steering vector arrow to target.
- Bottom status bar: active haptic source, threat status, objects seen, shortcut legend.
- Toast notifications and speech subtitle banner.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import cv2
import numpy as np

from .detection import Box, Detection
from .guidance import GuidanceCommand, GuidanceOutput, GuidanceState
from .haptics import HapticOutput

Point = Tuple[float, float]


def draw_dashed_line(img: np.ndarray, pt1: Tuple[int, int], pt2: Tuple[int, int], color: Tuple[int, int, int], thickness: int = 1, gap: int = 10):
    """Draws a dashed vertical line."""
    x1, y1 = pt1
    x2, y2 = pt2
    dist = int(math.hypot(x2 - x1, y2 - y1))
    for i in range(0, dist, gap * 2):
        r1 = i / max(1, dist)
        r2 = min((i + gap) / max(1, dist), 1.0)
        p1 = (int(x1 + (x2 - x1) * r1), int(y1 + (y2 - y1) * r1))
        p2 = (int(x1 + (x2 - x1) * r2), int(y1 + (y2 - y1) * r2))
        cv2.line(img, p1, p2, color, thickness)


def draw_wristband_widget(
    overlay: np.ndarray,
    side: str,  # "LEFT" or "RIGHT"
    pwm: float,
    label: str,
    top_y: int,
    bottom_y: int,
    w: int,
):
    """Renders a tactile wristband icon with live pulsation and intensity meter."""
    widget_w = 48
    widget_h = 100
    mid_y = (top_y + bottom_y) // 2

    x_start = 8 if side == "LEFT" else (w - widget_w - 8)
    y_start = mid_y - (widget_h // 2)

    # Base background (watch strap style)
    cv2.rectangle(overlay, (x_start, y_start), (x_start + widget_w, y_start + widget_h), (25, 25, 30), -1)
    cv2.rectangle(overlay, (x_start, y_start), (x_start + widget_w, y_start + widget_h), (70, 70, 85), 1)

    # Dynamic fill level based on PWM %
    fill_ratio = min(max(pwm / 100.0, 0.0), 1.0)
    fill_h = int((widget_h - 16) * fill_ratio)

    if fill_ratio > 0.6:
        color = (0, 60, 255)    # Red / High alert
    elif fill_ratio > 0.2:
        color = (0, 180, 255)   # Amber / Active guide
    elif fill_ratio > 0.0:
        color = (0, 255, 120)   # Green / Gentle pulse
    else:
        color = (40, 40, 50)

    if fill_h > 0:
        fill_y = y_start + widget_h - 8 - fill_h
        cv2.rectangle(overlay, (x_start + 6, fill_y), (x_start + widget_w - 6, y_start + widget_h - 8), color, -1)

    # Outer glow if active
    if pwm > 10.0:
        cv2.rectangle(overlay, (x_start - 2, y_start - 2), (x_start + widget_w + 2, y_start + widget_h + 2), color, 1)

    # Side text
    side_text = "L" if side == "LEFT" else "R"
    cv2.putText(overlay, side_text, (x_start + 18, y_start + 22), cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    pwm_text = f"{pwm:.0f}%"
    cv2.putText(overlay, pwm_text, (x_start + 8, y_start + widget_h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (220, 220, 220), 1, cv2.LINE_AA)


def render_hud(
    frame: np.ndarray,
    detections: List[Detection],
    haptics: HapticOutput,
    guidance: GuidanceOutput,
    fps: float,
    camera_name: str,
    speech_subtitle: Optional[str] = None,
    toast_msg: Optional[str] = None,
    location_msg: Optional[str] = None,
    metric_mode: bool = False,
) -> np.ndarray:
    """Renders high-contrast, modern visual HUD for PulsePath."""
    h, w = frame.shape[:2]
    overlay = frame.copy()

    one_third = int(w / 3.0)
    two_thirds = int((w * 2.0) / 3.0)

    # 1. TOP HEADER BAR
    top_bar_h = 46
    cv2.rectangle(overlay, (0, 0), (w, top_bar_h), (16, 16, 20), -1)

    # Brand Title
    cv2.putText(overlay, "PulsePath AI", (14, 28), cv2.FONT_HERSHEY_DUPLEX, 0.65, (0, 230, 255), 1, cv2.LINE_AA)

    # Guidance Mode Pill Badge
    mode_text = guidance.state.value
    if guidance.state == GuidanceState.SEARCHING:
        mode_text = f"SEARCHING: {guidance.target_name or 'target'}"
        badge_bg = (180, 100, 0)
    elif guidance.state == GuidanceState.HEAD_GUIDE:
        mode_text = f"GUIDE HEAD -> {guidance.target_name or ''}"
        badge_bg = (180, 60, 0)
    elif guidance.state == GuidanceState.HAND_GUIDE:
        mode_text = f"GUIDE HAND -> {guidance.target_name or ''}"
        badge_bg = (0, 130, 220)
    elif guidance.state == GuidanceState.ALIGNED:
        mode_text = f"ON TARGET: {guidance.target_name or ''} ✓"
        badge_bg = (0, 170, 60)
    else:
        mode_text = "NAVIGATION MODE"
        badge_bg = (45, 45, 55)

    (tw, th), _ = cv2.getTextSize(mode_text, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)
    badge_x = 160
    cv2.rectangle(overlay, (badge_x, 10), (badge_x + tw + 18, 36), badge_bg, -1)
    cv2.putText(overlay, mode_text, (badge_x + 9, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1, cv2.LINE_AA)

    # Camera & FPS
    cv2.putText(overlay, f"{camera_name[:20]}", (w - 200, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (170, 170, 180), 1, cv2.LINE_AA)
    fps_color = (0, 255, 120) if fps >= 20 else ((0, 200, 255) if fps >= 10 else (0, 100, 255))
    cv2.putText(overlay, f"{fps:4.1f} FPS", (w - 75, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.45, fps_color, 1, cv2.LINE_AA)

    # 2. ZONE DIVIDERS
    draw_dashed_line(overlay, (one_third, top_bar_h), (one_third, h - 88), (65, 65, 75), 1, 8)
    draw_dashed_line(overlay, (two_thirds, top_bar_h), (two_thirds, h - 88), (65, 65, 75), 1, 8)

    # Zone Labels
    cv2.putText(overlay, "< LEFT ZONE", (64, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (130, 130, 140), 1, cv2.LINE_AA)
    cv2.putText(overlay, "^ AHEAD", (one_third + 35, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (130, 130, 140), 1, cv2.LINE_AA)
    cv2.putText(overlay, "RIGHT ZONE >", (two_thirds + 20, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (130, 130, 140), 1, cv2.LINE_AA)

    # 3. DETECTIONS BOUNDING BOXES
    for det in detections:
        x1, y1, x2, y2 = det.box
        is_guidance_target = (
            guidance.active
            and guidance.target_box is not None
            and det.box == guidance.target_box
        )

        if is_guidance_target:
            box_color = (0, 240, 255)  # Cyan target
            thickness = 3
        elif det.pwm_intensity > 60:
            box_color = (0, 50, 255)    # Red threat
            thickness = 2
        elif det.pwm_intensity > 25:
            box_color = (0, 165, 255)   # Amber
            thickness = 2
        else:
            box_color = (60, 220, 100)  # Green
            thickness = 2

        cv2.rectangle(overlay, (x1, y1), (x2, y2), box_color, thickness)

        # Label tag
        tag = f"{det.label} {det.confidence:.0%}"
        if getattr(det, "distance_m", None) is not None:
            tag += f" | {det.distance_m:.1f}m"
        elif det.pwm_intensity > 0:
            tag += f" | {det.pwm_intensity:.0f}%"
        (lw, lh), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)
        tag_y = max(top_bar_h + 16, y1 - 6)
        cv2.rectangle(overlay, (x1, tag_y - lh - 4), (x1 + lw + 8, tag_y + 2), box_color, -1)
        cv2.putText(overlay, tag, (x1 + 4, tag_y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 0, 0), 1, cv2.LINE_AA)

    # 4. GUIDANCE OVERLAYS (Target Crosshair, Hand Marker, Steering Arrow)
    if guidance.active and guidance.target_point is not None:
        tx, ty = (int(guidance.target_point[0]), int(guidance.target_point[1]))

        # Reticle on target center
        cv2.circle(overlay, (tx, ty), 16, (0, 240, 255), 2, cv2.LINE_AA)
        cv2.circle(overlay, (tx, ty), 4, (0, 240, 255), -1, cv2.LINE_AA)
        cv2.line(overlay, (tx - 24, ty), (tx + 24, ty), (0, 240, 255), 1, cv2.LINE_AA)
        cv2.line(overlay, (tx, ty - 24), (tx, ty + 24), (0, 240, 255), 1, cv2.LINE_AA)

        # Target label tag above reticle
        target_lbl = f"TARGET: {guidance.target_name.upper() if guidance.target_name else ''}"
        cv2.putText(overlay, target_lbl, (tx - 40, max(top_bar_h + 30, ty - 30)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 240, 255), 1, cv2.LINE_AA)

        # Hand marker and steering vector arrow
        if guidance.hand_point is not None:
            hx, hy = (int(guidance.hand_point[0]), int(guidance.hand_point[1]))
            # Glowing hand fingertip point
            cv2.circle(overlay, (hx, hy), 12, (255, 100, 0), 2, cv2.LINE_AA)
            cv2.circle(overlay, (hx, hy), 5, (255, 180, 50), -1, cv2.LINE_AA)
            cv2.putText(overlay, "HAND", (hx + 14, hy + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 180, 50), 1, cv2.LINE_AA)

            # Steering arrow from hand toward target
            if guidance.command == GuidanceCommand.ALIGNED:
                arrow_color = (0, 255, 100)
            else:
                arrow_color = (0, 200, 255)
            cv2.arrowedLine(overlay, (hx, hy), (tx, ty), arrow_color, 2, tipLength=0.15)

    # 5. DUAL WRISTBAND WIDGETS (Left and Right borders)
    draw_wristband_widget(overlay, "LEFT", haptics.left_pwm, haptics.label, top_bar_h, h - 88, w)
    draw_wristband_widget(overlay, "RIGHT", haptics.right_pwm, haptics.label, top_bar_h, h - 88, w)

    # 6. BOTTOM HUD BAR (Haptic Telemetry & Status)
    hud_h = 88
    cv2.rectangle(overlay, (0, h - hud_h), (w, h), (16, 16, 20), -1)

    # Haptic Feedback Status Banner
    haptic_source_color = (0, 80, 255) if haptics.source == "obstacle" else (0, 220, 200)
    cv2.putText(overlay, f"HAPTIC: {haptics.label}", (70, h - 56), cv2.FONT_HERSHEY_DUPLEX, 0.48, haptic_source_color, 1, cv2.LINE_AA)

    # Pulse rate / pattern state + Distance Mode indicator
    dist_tag = "Dist: METRIC (m)" if metric_mode else "Dist: AREA (%)"
    if guidance.active:
        detail_msg = f"Mode: {guidance.state.value} | Ref: {guidance.reference or 'head'} | {dist_tag}"
    else:
        detail_msg = f"Obstacle Nav Active | {dist_tag}"
    cv2.putText(overlay, detail_msg, (70, h - 34), cv2.FONT_HERSHEY_SIMPLEX, 0.39, (170, 170, 180), 1, cv2.LINE_AA)

    # Objects seen summary
    seen_labels = sorted({d.label for d in detections})
    seen_str = f"Seen: {', '.join(seen_labels)}" if seen_labels else "Seen: None"
    if len(seen_str) > 36:
        seen_str = seen_str[:33] + "..."
    cv2.putText(overlay, seen_str, (w - 280, h - 56), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (160, 160, 175), 1, cv2.LINE_AA)

    # Keyboard shortcut legend at very bottom
    shortcuts = "[F] Door  |  [B] Bottle  |  [O] Dist Mode  |  [X] Cancel  |  [C] Cam  |  [W] Where?  |  [Q] Exit"
    cv2.putText(overlay, shortcuts, (14, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (120, 120, 135), 1, cv2.LINE_AA)

    # 7. NOTIFICATION BANNERS (Toast & Speech subtitle)
    if toast_msg:
        cv2.rectangle(overlay, (w // 8, 54), (7 * w // 8, 90), (20, 120, 220), -1)
        cv2.putText(overlay, toast_msg, (w // 8 + 14, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)

    if speech_subtitle:
        cv2.rectangle(overlay, (w // 8, 96), (7 * w // 8, 132), (30, 30, 40), -1)
        cv2.rectangle(overlay, (w // 8, 96), (7 * w // 8, 132), (0, 220, 200), 1)
        sub_text = f"Voice: {speech_subtitle}"
        if len(sub_text) > 55:
            sub_text = sub_text[:52] + "..."
        cv2.putText(overlay, sub_text, (w // 8 + 12, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 240, 255), 1, cv2.LINE_AA)

    if location_msg:
        cv2.rectangle(overlay, (40, 96), (w - 40, 132), (140, 60, 0), -1)
        cv2.putText(overlay, location_msg, (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)

    return overlay
