"""L5 OpenCV Heads-Up Display (HUD) for Nethra Assistive Vision Prototype.

High-DPI Retina-ready visual overlay with TrueType typography, anti-aliased
tactile wristband strap gauges, glowing guidance reticles, and high-contrast badges.
"""

from __future__ import annotations

import math
import platform
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from contracts.detection import Detection
from contracts.haptic_command import GuidanceState, HapticFeedbackState
from features.lookaround.guidance import GuidanceOutput

# Cached TrueType fonts for sub-pixel anti-aliased text rendering
_FONT_CACHE: Dict[Tuple[int, bool], ImageFont.FreeTypeFont] = {}


def _find_system_font(bold: bool = False) -> Optional[str]:
    """Finds the best available native sans-serif font on the current operating system."""
    system = platform.system()
    candidates: List[str] = []

    if system == "Darwin":
        if bold:
            candidates = [
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "/System/Library/Fonts/SFNS.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ]
        else:
            candidates = [
                "/System/Library/Fonts/Helvetica.ttc",
                "/System/Library/Fonts/SFNS.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
            ]
    elif system == "Windows":
        candidates = [
            "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]

    for p in candidates:
        if Path(p).exists():
            return p
    return None


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Returns a cached FreeType font at the specified pixel size."""
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    font_path = _find_system_font(bold=bold)
    if font_path:
        try:
            f = ImageFont.truetype(font_path, size=size)
            _FONT_CACHE[key] = f
            return f
        except Exception:
            pass

    default_f = ImageFont.load_default()
    _FONT_CACHE[key] = default_f
    return default_f


def _draw_rounded_rect(
    img: np.ndarray,
    pt1: Tuple[int, int],
    pt2: Tuple[int, int],
    color: Tuple[int, int, int],
    radius: int = 6,
    thickness: int = -1,
) -> None:
    """Draws a rounded rectangle using anti-aliased lines and arcs."""
    x1, y1 = pt1
    x2, y2 = pt2
    w = x2 - x1
    h = y2 - y1
    r = min(radius, w // 2, h // 2)
    if r <= 0:
        cv2.rectangle(img, pt1, pt2, color, thickness, cv2.LINE_AA)
        return

    if thickness == -1:
        cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), color, -1)
        cv2.rectangle(img, (x1, y1 + r), (x2, y2 - r), color, -1)
        cv2.circle(img, (x1 + r, y1 + r), r, color, -1, cv2.LINE_AA)
        cv2.circle(img, (x2 - r, y1 + r), r, color, -1, cv2.LINE_AA)
        cv2.circle(img, (x1 + r, y2 - r), r, color, -1, cv2.LINE_AA)
        cv2.circle(img, (x2 - r, y2 - r), r, color, -1, cv2.LINE_AA)
    else:
        cv2.line(img, (x1 + r, y1), (x2 - r, y1), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x1 + r, y2), (x2 - r, y2), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x1, y1 + r), (x1, y2 - r), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x2, y1 + r), (x2, y2 - r), color, thickness, cv2.LINE_AA)
        cv2.ellipse(img, (x1 + r, y1 + r), (r, r), 180, 0, 90, color, thickness, cv2.LINE_AA)
        cv2.ellipse(img, (x2 - r, y1 + r), (r, r), 270, 0, 90, color, thickness, cv2.LINE_AA)
        cv2.ellipse(img, (x2 - r, y2 - r), (r, r), 0, 0, 90, color, thickness, cv2.LINE_AA)
        cv2.ellipse(img, (x1 + r, y2 - r), (r, r), 90, 0, 90, color, thickness, cv2.LINE_AA)


def _draw_dashed_line(
    img: np.ndarray,
    pt1: Tuple[int, int],
    pt2: Tuple[int, int],
    color: Tuple[int, int, int],
    thickness: int = 1,
    gap: int = 10,
) -> None:
    """Draws an anti-aliased dashed vertical line."""
    x1, y1 = pt1
    x2, y2 = pt2
    dist = int(math.hypot(x2 - x1, y2 - y1))
    for i in range(0, dist, gap * 2):
        r1 = i / max(1, dist)
        r2 = min((i + gap) / max(1, dist), 1.0)
        p1 = (int(x1 + (x2 - x1) * r1), int(y1 + (y2 - y1) * r1))
        p2 = (int(x1 + (x2 - x1) * r2), int(y1 + (y2 - y1) * r2))
        cv2.line(img, p1, p2, color, thickness, cv2.LINE_AA)


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
    guidance: Optional[GuidanceOutput] = None,
    voice_listening: bool = False,
) -> np.ndarray:
    """Renders the high-contrast, razor-sharp Nethra assistive vision HUD overlay."""
    h, w = frame.shape[:2]
    overlay = frame.copy()

    # Dynamic scaling factor (1.0 for 640x480, 2.0 for 1280x960 HD / Retina)
    scale = max(w / 640.0, 1.0)

    one_third = int(w / 3.0)
    two_thirds = int((w * 2.0) / 3.0)

    # Pre-cache TrueType Typography for high-DPI rendering and exact metric bounding
    f_title = _get_font(int(17 * scale), bold=True)
    f_badge = _get_font(int(12 * scale), bold=True)
    f_cam = _get_font(int(12 * scale), bold=False)
    f_fps = _get_font(int(13 * scale), bold=True)
    f_label = _get_font(int(11 * scale), bold=True)
    f_meter_head = _get_font(int(13 * scale), bold=True)
    f_status = _get_font(int(14 * scale), bold=True)
    f_sub = _get_font(int(11 * scale), bold=False)
    f_shortcut = _get_font(int(11 * scale), bold=False)
    f_shortcut_bold = _get_font(int(11 * scale), bold=True)
    f_toast = _get_font(int(13 * scale), bold=True)

    # 1. TOP STATUS BAR & ZONE SUB-HEADER BACKGROUNDS
    top_bar_h = int(44 * scale)
    zone_bar_h = int(24 * scale)
    header_bottom = top_bar_h + zone_bar_h

    cv2.rectangle(overlay, (0, 0), (w, top_bar_h), (22, 18, 18), -1)
    cv2.rectangle(overlay, (0, top_bar_h), (w, header_bottom), (30, 25, 22), -1)
    cv2.line(overlay, (0, top_bar_h), (w, top_bar_h), (50, 42, 38), 1)
    cv2.line(overlay, (0, header_bottom), (w, header_bottom), (55, 48, 42), 1)
    cv2.line(overlay, (one_third, top_bar_h), (one_third, header_bottom), (55, 48, 42), 1)
    cv2.line(overlay, (two_thirds, top_bar_h), (two_thirds, header_bottom), (55, 48, 42), 1)

    # Mode Badge shape (BGR colors)
    badge_x = int(125 * scale)
    badge_y = int(8 * scale)
    badge_h = int(28 * scale)

    if voice_listening:
        badge_text = "MIC LISTENING... SPEAK NOW"
        badge_bg = (220, 40, 90)  # Vivid magenta-purple in BGR
        badge_fg = (255, 255, 255)
    elif guidance and guidance.active:
        badge_text = f"FIND: {(guidance.target_name or '').upper()} [{guidance.state.value}]"
        badge_bg = (255, 140, 0) if guidance.state != GuidanceState.ALIGNED else (80, 200, 40)
        badge_fg = (255, 255, 255) if guidance.state != GuidanceState.ALIGNED else (0, 0, 0)
    else:
        badge_text = f"[{model_mode_label}]"
        badge_bg = (52, 40, 34)
        badge_fg = (200, 225, 255)

    badge_w = int(f_badge.getlength(badge_text)) + int(18 * scale)
    _draw_rounded_rect(
        overlay,
        (badge_x, badge_y),
        (badge_x + badge_w, badge_y + badge_h),
        badge_bg,
        radius=int(6 * scale),
        thickness=-1,
    )

    # Compute active banner list & vertical span so detection label pills never collide with banners
    banner_items: List[Tuple[str, Tuple[int, int, int], bool]] = []
    if toast_msg:
        banner_items.append((toast_msg, (20, 120, 220), False))   # Warm amber-blue in BGR
    if context_msg:
        banner_items.append((context_msg, (35, 140, 40), False))  # Forest green in BGR
    if location_msg:
        banner_items.append((location_msg, (150, 70, 15), True))  # Deep royal blue in BGR

    banner_h = int(30 * scale)
    banner_gap = int(6 * scale)
    active_banners_bottom = header_bottom + (
        len(banner_items) * (banner_h + banner_gap) if banner_items else 0
    )

    # 2. ZONE DIVIDERS
    hud_bar_h = int(96 * scale)
    _draw_dashed_line(
        overlay,
        (one_third, header_bottom + 4),
        (one_third, h - hud_bar_h - 4),
        (75, 68, 65),
        thickness=1,
        gap=int(8 * scale),
    )
    _draw_dashed_line(
        overlay,
        (two_thirds, header_bottom + 4),
        (two_thirds, h - hud_bar_h - 4),
        (75, 68, 65),
        thickness=1,
        gap=int(8 * scale),
    )

    # 3. BOUNDING BOXES & LABELS
    tag_boxes_to_draw: List[Tuple[int, int, int, int, Tuple[int, int, int], str]] = []

    for det in detections:
        x1, y1, x2, y2 = det.box
        is_target = bool(
            guidance
            and guidance.active
            and guidance.target_name
            and det.label.lower() == guidance.target_name.lower()
        )
        if is_target:
            box_color = (255, 220, 0)     # Bright Cyan Target Highlight (BGR)
            th = int(3 * scale)
        elif det.pwm_intensity > 60:
            box_color = (0, 50, 255)      # Urgent Red (BGR)
            th = int(2 * scale)
        elif det.pwm_intensity > 25:
            box_color = (0, 165, 255)     # Amber Orange (BGR)
            th = int(2 * scale)
        else:
            box_color = (50, 220, 100)    # Gentle Green (BGR)
            th = int(2 * scale)

        cv2.rectangle(overlay, (x1, y1), (x2, y2), box_color, th, cv2.LINE_AA)

        tag_text = f" {det.label} {det.confidence:.0%} | {det.pwm_intensity:.0f}% PWM "
        tag_w = int(f_label.getlength(tag_text)) + int(8 * scale)
        tag_h = int(20 * scale)

        # Position pill above box if clear of header & active banners; else place below banners or inside box
        if y1 - tag_h >= active_banners_bottom + 4:
            pill_top = y1 - tag_h - int(2 * scale)
        else:
            pill_top = max(y1 + int(2 * scale), active_banners_bottom + int(4 * scale))
            if pill_top + tag_h > h - hud_bar_h - 4:
                pill_top = max(header_bottom + 4, y2 - tag_h - int(2 * scale))

        _draw_rounded_rect(
            overlay,
            (x1, pill_top),
            (x1 + tag_w, pill_top + tag_h),
            box_color,
            radius=int(3 * scale),
            thickness=-1,
        )
        tag_boxes_to_draw.append((x1 + int(4 * scale), pill_top + int(2 * scale), tag_w, tag_h, box_color, tag_text))

    # 3B. GUIDED SEARCH OVERLAYS (Target Crosshair, Hand Marker & Steering Arrow)
    if guidance and guidance.active:
        if guidance.target_point:
            tx, ty = int(guidance.target_point[0]), int(guidance.target_point[1])
            cv2.circle(overlay, (tx, ty), int(14 * scale), (255, 220, 0), int(2 * scale), cv2.LINE_AA)
            cv2.circle(overlay, (tx, ty), int(4 * scale), (255, 220, 0), -1, cv2.LINE_AA)
            cv2.line(overlay, (tx - int(22 * scale), ty), (tx + int(22 * scale), ty), (255, 220, 0), 1, cv2.LINE_AA)
            cv2.line(overlay, (tx, ty - int(22 * scale)), (tx, ty + int(22 * scale)), (255, 220, 0), 1, cv2.LINE_AA)

        if guidance.hand_point:
            hx, hy = int(guidance.hand_point[0]), int(guidance.hand_point[1])
            cv2.circle(overlay, (hx, hy), int(10 * scale), (255, 0, 255), -1, cv2.LINE_AA)
            cv2.circle(overlay, (hx, hy), int(15 * scale), (255, 255, 255), 1, cv2.LINE_AA)
            if guidance.target_point:
                tx, ty = int(guidance.target_point[0]), int(guidance.target_point[1])
                cv2.arrowedLine(
                    overlay,
                    (hx, hy),
                    (tx, ty),
                    (0, 255, 180),
                    int(2 * scale),
                    cv2.LINE_AA,
                    tipLength=0.08,
                )

    # 4. BOTTOM HUD BAR (Wristband Meters & Telemetry)
    cv2.rectangle(overlay, (0, h - hud_bar_h), (w, h), (18, 18, 22), -1)
    cv2.line(overlay, (0, h - hud_bar_h), (w, h - hud_bar_h), (38, 40, 50), 1)

    meter_w = int(w * 0.28)
    slot_h = int(16 * scale)

    left_x = int(16 * scale)
    left_y_text = h - hud_bar_h + int(12 * scale)
    left_y_slot = left_y_text + int(22 * scale)

    # Left Slot background
    _draw_rounded_rect(
        overlay,
        (left_x, left_y_slot),
        (left_x + meter_w, left_y_slot + slot_h),
        (30, 32, 40),
        radius=int(4 * scale),
        thickness=-1,
    )
    _draw_rounded_rect(
        overlay,
        (left_x, left_y_slot),
        (left_x + meter_w, left_y_slot + slot_h),
        (65, 70, 85),
        radius=int(4 * scale),
        thickness=1,
    )

    left_fill = int(meter_w * (haptics.left_pwm / 100.0))
    if left_fill > 0:
        bar_color = (0, 70, 255) if haptics.left_pwm >= 60 else ((0, 180, 255) if haptics.left_pwm >= 25 else (50, 220, 100))
        _draw_rounded_rect(
            overlay,
            (left_x + 1, left_y_slot + 1),
            (left_x + left_fill, left_y_slot + slot_h - 1),
            bar_color,
            radius=int(3 * scale),
            thickness=-1,
        )

    # Right Slot background
    right_x = w - meter_w - int(16 * scale)
    _draw_rounded_rect(
        overlay,
        (right_x, left_y_slot),
        (right_x + meter_w, left_y_slot + slot_h),
        (30, 32, 40),
        radius=int(4 * scale),
        thickness=-1,
    )
    _draw_rounded_rect(
        overlay,
        (right_x, left_y_slot),
        (right_x + meter_w, left_y_slot + slot_h),
        (65, 70, 85),
        radius=int(4 * scale),
        thickness=1,
    )

    right_fill = int(meter_w * (haptics.right_pwm / 100.0))
    if right_fill > 0:
        bar_color = (0, 70, 255) if haptics.right_pwm >= 60 else ((0, 180, 255) if haptics.right_pwm >= 25 else (50, 220, 100))
        _draw_rounded_rect(
            overlay,
            (right_x + 1, left_y_slot + 1),
            (right_x + right_fill, left_y_slot + slot_h - 1),
            bar_color,
            radius=int(3 * scale),
            thickness=-1,
        )

    # 5. TOAST & NOTIFICATION BANNERS (Shapes drawn below header_bottom)
    banner_w = int(w * 0.76)
    banner_x = (w - banner_w) // 2
    banner_layouts: List[Tuple[int, int, int, str]] = []

    cur_by = header_bottom + banner_gap
    for b_text, b_color_bgr, is_wide in banner_items:
        bx1 = int(20 * scale) if is_wide else banner_x
        bx2 = (w - int(20 * scale)) if is_wide else (banner_x + banner_w)
        _draw_rounded_rect(
            overlay,
            (bx1, cur_by),
            (bx2, cur_by + banner_h),
            b_color_bgr,
            radius=int(6 * scale),
            thickness=-1,
        )
        _draw_rounded_rect(
            overlay,
            (bx1, cur_by),
            (bx2, cur_by + banner_h),
            (220, 220, 230),
            radius=int(6 * scale),
            thickness=1,
        )
        banner_layouts.append((bx1, bx2, cur_by, b_text))
        cur_by += banner_h + banner_gap

    # =========================================================================
    # 6. TRUETYPE SUB-PIXEL TEXT RENDERING (Crisp Anti-Aliased Typography in RGB)
    # =========================================================================
    pil_img = Image.fromarray(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)

    # Top Bar Text
    draw.text((int(14 * scale), int(11 * scale)), "Nethra AI", font=f_title, fill=(0, 230, 255))
    draw.text((badge_x + int(9 * scale), badge_y + int(6 * scale)), badge_text, font=f_badge, fill=badge_fg)

    cam_str = f"Cam: #{camera_idx}" if isinstance(camera_idx, int) else f"Cam: {str(camera_idx)[:16]}"
    cam_color = (50, 225, 120) if (camera_idx == 1 or isinstance(camera_idx, str)) else (185, 190, 200)
    draw.text((w - int(195 * scale), int(13 * scale)), cam_str, font=f_cam, fill=cam_color)

    fps_color = (50, 240, 120) if fps >= 20 else ((255, 200, 0) if fps >= 10 else (255, 80, 60))
    draw.text((w - int(78 * scale), int(13 * scale)), f"{fps:4.1f} FPS", font=f_fps, fill=fps_color)

    # Zone Sub-Header Labels (Dedicated non-overlapping strip)
    left_active = haptics.left_pwm > 0 and haptics.left_pwm != haptics.right_pwm
    center_active = haptics.left_pwm > 0 and haptics.left_pwm == haptics.right_pwm
    right_active = haptics.right_pwm > 0 and haptics.left_pwm != haptics.right_pwm
    zone_text_y = top_bar_h + int(5 * scale)

    draw.text(
        (int(18 * scale), zone_text_y),
        "< LEFT ZONE",
        font=f_label,
        fill=(255, 195, 0) if left_active else (155, 160, 175),
    )
    draw.text(
        (one_third + int(24 * scale), zone_text_y),
        "^ CENTER (AHEAD)",
        font=f_label,
        fill=(255, 95, 50) if center_active else (155, 160, 175),
    )
    draw.text(
        (two_thirds + int(24 * scale), zone_text_y),
        "RIGHT ZONE >",
        font=f_label,
        fill=(255, 195, 0) if right_active else (155, 160, 175),
    )

    # Detection Bounding Box Tags
    for tx, ty, _, _, _, tag_text in tag_boxes_to_draw:
        draw.text((tx, ty), tag_text, font=f_label, fill=(0, 0, 0))

    # Hand Label
    if guidance and guidance.active and guidance.hand_point:
        hx, hy = int(guidance.hand_point[0]), int(guidance.hand_point[1])
        draw.text((hx + int(16 * scale), hy - int(8 * scale)), "HAND", font=f_label, fill=(255, 180, 50))

    # Bottom Left / Right Wristband Text
    draw.text(
        (left_x, left_y_text),
        f"[LEFT WRIST]  {haptics.left_pwm:4.1f}% PWM",
        font=f_meter_head,
        fill=(0, 225, 255) if haptics.left_pwm > 0 else (190, 195, 205),
    )
    draw.text(
        (right_x, left_y_text),
        f"[RIGHT WRIST]  {haptics.right_pwm:4.1f}% PWM",
        font=f_meter_head,
        fill=(0, 225, 255) if haptics.right_pwm > 0 else (190, 195, 205),
    )

    # Bottom Center Status & Telemetry (RGB colors)
    center_x = int(w * 0.33)
    threat_text = haptics.active_threat or "Path Clear"
    threat_color = (255, 90, 45) if haptics.active_threat else (60, 230, 110)
    draw.text((center_x, left_y_text), threat_text, font=f_status, fill=threat_color)

    labels_summary = ", ".join(list({d.label for d in detections})) if detections else "None in view"
    if len(labels_summary) > 34:
        labels_summary = labels_summary[:31] + "..."
    draw.text(
        (center_x, left_y_text + int(20 * scale)),
        f"Seen: {labels_summary}",
        font=f_sub,
        fill=(170, 175, 190),
    )

    # Bottom Shortcut Bar
    shortcut_y = h - int(18 * scale)
    shortcuts = [
        ("[V/Space]", "Voice"),
        ("[D]", "Scene"),
        ("[F]", "Door"),
        ("[B]", "Bottle"),
        ("[X]", "Stop"),
        ("[W]", "Where?"),
        ("[C]", "Cam"),
        ("[M]", "Mute"),
        ("[Q]", "Quit"),
    ]
    cur_x = int(14 * scale)
    for key_tag, act_tag in shortcuts:
        draw.text((cur_x, shortcut_y), key_tag, font=f_shortcut_bold, fill=(0, 230, 255))
        kw = int(draw.textlength(key_tag, font=f_shortcut_bold))
        draw.text((cur_x + kw + 2, shortcut_y), f" {act_tag}  |  ", font=f_shortcut, fill=(135, 140, 155))
        cur_x += kw + int(draw.textlength(f" {act_tag}  |  ", font=f_shortcut))

    # Banner Texts (centered inside each stacked banner)
    for bx1, bx2, by, b_text in banner_layouts:
        tw = int(draw.textlength(b_text, font=f_toast))
        tx = max(bx1 + int(12 * scale), (bx1 + bx2 - tw) // 2)
        draw.text((tx, by + int(6 * scale)), b_text, font=f_toast, fill=(255, 255, 255))

    # Convert back to BGR for OpenCV display
    result_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    return result_bgr
