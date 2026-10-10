#!/usr/bin/env python3
"""Assistive Vision Prototype (PulsePath)

Real-time Edge-AI spatial obstacle detection, haptic wristband routing,
and contextual scene awareness for the visually impaired.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


@dataclass
class Detection:
    """Represents a single detected object."""
    label: str
    confidence: float
    box: Tuple[int, int, int, int]  # x1, y1, x2, y2
    center_x: float
    center_y: float
    width: float
    height: float
    area_ratio: float
    zone: str  # "LEFT", "CENTER", "RIGHT"
    pwm_intensity: float  # 0.0 to 100.0%


@dataclass
class HapticFeedbackState:
    """Simulated Left and Right wristband vibration states."""
    left_pwm: float = 0.0   # 0.0 to 100.0%
    right_pwm: float = 0.0  # 0.0 to 100.0%
    active_threat: Optional[str] = None
    closest_distance_ratio: float = 0.0


class SpatialRoutingEngine:
    """Divides the field of view into spatial zones and calculates haptic intensity."""

    def __init__(self, min_area_ratio: float = 0.02, max_area_ratio: float = 0.35):
        self.min_area_ratio = min_area_ratio
        self.max_area_ratio = max_area_ratio

    def calculate_pwm(self, area_ratio: float) -> float:
        """Maps bounding box area ratio to motor PWM duty cycle (0.0% - 100.0%)."""
        if area_ratio <= self.min_area_ratio:
            return 0.0
        if area_ratio >= self.max_area_ratio:
            return 100.0
        intensity = ((area_ratio - self.min_area_ratio) / (self.max_area_ratio - self.min_area_ratio)) * 100.0
        return round(float(np.clip(intensity, 0.0, 100.0)), 1)

    def determine_zone(self, center_x: float, frame_width: int) -> str:
        """Determines the horizontal zone for a given x-coordinate."""
        one_third = frame_width / 3.0
        two_thirds = (frame_width * 2.0) / 3.0

        if center_x < one_third:
            return "LEFT"
        elif center_x > two_thirds:
            return "RIGHT"
        else:
            return "CENTER"

    def process_detections(
        self,
        boxes: List[Tuple[int, int, int, int]],
        scores: List[float],
        class_ids: List[int],
        class_names: Dict[int, str],
        frame_width: int,
        frame_height: int,
    ) -> Tuple[List[Detection], HapticFeedbackState]:
        """Processes raw model detections into spatial cues and dual wristband signals."""
        total_frame_area = float(max(1, frame_width * frame_height))
        detections: List[Detection] = []

        max_left_pwm = 0.0
        max_right_pwm = 0.0
        highest_threat_label = None
        max_threat_area = 0.0

        for box, score, cls_id in zip(boxes, scores, class_ids):
            x1, y1, x2, y2 = box
            w = max(0, x2 - x1)
            h = max(0, y2 - y1)
            cx = x1 + (w / 2.0)
            cy = y1 + (h / 2.0)

            box_area = float(w * h)
            area_ratio = box_area / total_frame_area
            label = class_names.get(cls_id, f"obj_{cls_id}")
            zone = self.determine_zone(cx, frame_width)
            pwm = self.calculate_pwm(area_ratio)

            det = Detection(
                label=label,
                confidence=float(score),
                box=(int(x1), int(y1), int(x2), int(y2)),
                center_x=cx,
                center_y=cy,
                width=w,
                height=h,
                area_ratio=area_ratio,
                zone=zone,
                pwm_intensity=pwm,
            )
            detections.append(det)

            # Spatial routing to left / right wristbands
            if zone == "LEFT":
                max_left_pwm = max(max_left_pwm, pwm)
            elif zone == "RIGHT":
                max_right_pwm = max(max_right_pwm, pwm)
            elif zone == "CENTER":
                # Obstacle dead ahead triggers both wristbands for immediate warning
                max_left_pwm = max(max_left_pwm, pwm)
                max_right_pwm = max(max_right_pwm, pwm)

            if area_ratio > max_threat_area and pwm > 0.0:
                max_threat_area = area_ratio
                highest_threat_label = f"{label} ({zone})"

        state = HapticFeedbackState(
            left_pwm=max_left_pwm,
            right_pwm=max_right_pwm,
            active_threat=highest_threat_label,
            closest_distance_ratio=max_threat_area,
        )
        return detections, state


class ContextSceneTracker:
    """Maintains scene awareness, wake-up recognition, and location context."""

    def __init__(self):
        self.bed_seen_frames = 0
        self.morning_greeting_active = False
        self.last_greeting_time = 0.0
        self.greeting_cooldown_sec = 60.0  # Announce once per minute max
        self.assumed_location = "University of Sri Jayewardenepura (Faculty of Applied Sciences)"

    def update(self, detections: List[Detection]) -> Optional[str]:
        """Analyzes detected objects to infer context and scene status."""
        labels = [d.label.lower() for d in detections]
        current_time = time.time()

        # Check for bed in view (wake-up context)
        has_bed = any(lbl == "bed" for lbl in labels)
        if has_bed:
            self.bed_seen_frames += 1
            if self.bed_seen_frames > 10 and (current_time - self.last_greeting_time > self.greeting_cooldown_sec):
                self.morning_greeting_active = True
                self.last_greeting_time = current_time
                return "Good morning! You are in your bed right now."
        else:
            self.bed_seen_frames = max(0, self.bed_seen_frames - 1)
            if self.bed_seen_frames == 0:
                self.morning_greeting_active = False

        return None

    def query_location(self, detections: List[Detection]) -> str:
        """Handles conversational 'Where am I?' query."""
        labels = list({d.label for d in detections})
        detected_summary = ", ".join(labels) if labels else "no immediate objects"
        return f"Location: {self.assumed_location} | In view: {detected_summary}"


def get_camera_name(idx: int) -> str:
    """Returns human-friendly camera name on macOS."""
    if idx == 1:
        return "iPhone (Continuity Camera / Ultra-Wide)"
    elif idx == 0:
        return "Mac FaceTime HD Camera"
    elif idx < 0:
        return "Synthetic Mock Stream"
    return f"Camera #{idx}"


def probe_available_cameras(max_probe: int = 4) -> List[int]:
    """Scans and returns all available camera indices."""
    available = []
    for idx in range(max_probe):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                available.append(idx)
            cap.release()
    return available


def open_camera(preferred_idx: int) -> Tuple[Optional[cv2.VideoCapture], int]:
    """Attempts to open the preferred camera with automatic fallback."""
    print(f"[Camera] Attempting camera index {preferred_idx} ({get_camera_name(preferred_idx)})...")
    cap = cv2.VideoCapture(preferred_idx)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"[Camera] Successfully opened {get_camera_name(preferred_idx)}.")
            return cap, preferred_idx
        cap.release()

    # Fallback to alternate camera indices
    fallbacks = [1, 0, 2]
    if preferred_idx in fallbacks:
        fallbacks.remove(preferred_idx)

    for idx in fallbacks:
        print(f"[Camera] Trying alternate index {idx} ({get_camera_name(idx)})...")
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                print(f"[Camera] Successfully opened {get_camera_name(idx)}.")
                return cap, idx
            cap.release()

    return None, -1


def create_mock_frame(width: int = 640, height: int = 480, frame_count: int = 0) -> np.ndarray:
    """Generates synthetic frames for headless testing or when camera is unavailable."""
    frame = np.full((height, width, 3), 35, dtype=np.uint8)

    pts = np.array([[width * 0.3, height], [width * 0.45, height * 0.4], [width * 0.55, height * 0.4], [width * 0.7, height]], np.int32)
    cv2.fillPoly(frame, [pts], (65, 65, 65))

    cycle = (frame_count % 150) / 150.0
    x_pos = int(width * 0.15 + (width * 0.7 * cycle))
    y_pos = int(height * 0.5)
    box_size = int(60 + 50 * np.sin(cycle * np.pi))

    cv2.rectangle(frame, (x_pos - box_size // 2, y_pos - box_size // 2), (x_pos + box_size // 2, y_pos + box_size // 2), (0, 180, 255), -1)
    cv2.putText(frame, "Obstacle (Simulated)", (x_pos - box_size // 2, y_pos - box_size // 2 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    return frame


def render_hud(
    frame: np.ndarray,
    detections: List[Detection],
    haptics: HapticFeedbackState,
    context_msg: Optional[str],
    fps: float,
    camera_idx: int,
    location_msg: Optional[str] = None,
    toast_msg: Optional[str] = None,
) -> np.ndarray:
    """Renders a modern, high-contrast assistive vision HUD."""
    h, w, _ = frame.shape
    overlay = frame.copy()

    one_third = int(w / 3.0)
    two_thirds = int((w * 2.0) / 3.0)

    # 1. TOP STATUS BAR (Semi-transparent dark header)
    top_bar_h = 44
    cv2.rectangle(overlay, (0, 0), (w, top_bar_h), (18, 18, 22), -1)

    # Title & Brand
    cv2.putText(overlay, "PulsePath AI", (14, 27), cv2.FONT_HERSHEY_DUPLEX, 0.65, (0, 230, 255), 1, cv2.LINE_AA)

    # Camera Device Badge
    cam_name = get_camera_name(camera_idx)
    cam_badge_color = (0, 200, 100) if camera_idx == 1 else (180, 180, 180)
    cv2.putText(overlay, f"Cam: {cam_name}", (160, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.44, cam_badge_color, 1, cv2.LINE_AA)

    # FPS Indicator
    fps_color = (0, 255, 120) if fps >= 20 else ((0, 200, 255) if fps >= 10 else (0, 100, 255))
    cv2.putText(overlay, f"{fps:4.1f} FPS", (w - 85, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.48, fps_color, 1, cv2.LINE_AA)

    # 2. ZONE DIVIDERS & LABELS
    cv2.line(overlay, (one_third, top_bar_h), (one_third, h - 85), (80, 80, 95), 1)
    cv2.line(overlay, (two_thirds, top_bar_h), (two_thirds, h - 85), (80, 80, 95), 1)

    # Zone Header Badges
    left_active = haptics.left_pwm > 0 and haptics.left_pwm != haptics.right_pwm
    center_active = haptics.left_pwm > 0 and haptics.left_pwm == haptics.right_pwm
    right_active = haptics.right_pwm > 0 and haptics.left_pwm != haptics.right_pwm

    cv2.putText(overlay, "< LEFT ZONE", (18, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 180, 255) if left_active else (140, 140, 150), 1, cv2.LINE_AA)
    cv2.putText(overlay, "^ CENTER (AHEAD)", (one_third + 20, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 100, 255) if center_active else (140, 140, 150), 1, cv2.LINE_AA)
    cv2.putText(overlay, "RIGHT ZONE >", (two_thirds + 20, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 180, 255) if right_active else (140, 140, 150), 1, cv2.LINE_AA)

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

        # Label tag pill
        tag_text = f"{det.label} {det.confidence:.0%} | {det.pwm_intensity:.0f}% PWM"
        (tw, th), _ = cv2.getTextSize(tag_text, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
        tag_y = max(top_bar_h + 16, y1 - 6)
        cv2.rectangle(overlay, (x1, tag_y - th - 4), (x1 + tw + 8, tag_y + 2), box_color, -1)
        cv2.putText(overlay, tag_text, (x1 + 4, tag_y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)

    # 4. BOTTOM HUD BAR (Haptic Vibration Meters & Telemetry)
    hud_bar_h = 88
    cv2.rectangle(overlay, (0, h - hud_bar_h), (w, h), (18, 18, 22), -1)

    # Left Wristband PWM Meter
    meter_w = int(w * 0.32)
    left_fill = int(meter_w * (haptics.left_pwm / 100.0))
    cv2.putText(overlay, f"LEFT WRIST: {haptics.left_pwm:4.1f}% PWM", (16, h - 58), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (210, 210, 220), 1, cv2.LINE_AA)
    cv2.rectangle(overlay, (16, h - 48), (16 + meter_w, h - 30), (50, 50, 60), 1)
    if left_fill > 0:
        cv2.rectangle(overlay, (16, h - 48), (16 + left_fill, h - 30), (0, 180, 255) if haptics.left_pwm < 50 else (0, 70, 255), -1)

    # Right Wristband PWM Meter
    right_x = w - meter_w - 16
    right_fill = int(meter_w * (haptics.right_pwm / 100.0))
    cv2.putText(overlay, f"RIGHT WRIST: {haptics.right_pwm:4.1f}% PWM", (right_x, h - 58), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (210, 210, 220), 1, cv2.LINE_AA)
    cv2.rectangle(overlay, (right_x, h - 48), (right_x + meter_w, h - 30), (50, 50, 60), 1)
    if right_fill > 0:
        cv2.rectangle(overlay, (right_x, h - 48), (right_x + right_fill, h - 30), (0, 180, 255) if haptics.right_pwm < 50 else (0, 70, 255), -1)

    # Center Telemetry Status
    threat_text = haptics.active_threat or "Path Clear"
    threat_color = (0, 80, 255) if haptics.active_threat else (50, 220, 100)
    cv2.putText(overlay, threat_text, (int(w * 0.37), h - 55), cv2.FONT_HERSHEY_SIMPLEX, 0.46, threat_color, 1, cv2.LINE_AA)

    # Active objects summary
    labels_summary = ", ".join(list({d.label for d in detections})) if detections else "None in view"
    if len(labels_summary) > 28:
        labels_summary = labels_summary[:25] + "..."
    cv2.putText(overlay, f"Seen: {labels_summary}", (int(w * 0.37), h - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 160, 175), 1, cv2.LINE_AA)

    # Keyboard helper shortcuts line at the very bottom
    cv2.putText(overlay, "[C] Switch Camera   |   [W] Where Am I?   |   [Q] Exit", (16, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (120, 120, 135), 1, cv2.LINE_AA)

    # 5. TOAST & NOTIFICATION BANNERS
    if toast_msg:
        cv2.rectangle(overlay, (w // 8, 50), (7 * w // 8, 86), (20, 120, 220), -1)
        cv2.putText(overlay, toast_msg, (w // 8 + 14, 74), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)

    if context_msg:
        cv2.rectangle(overlay, (w // 8, 92), (7 * w // 8, 128), (40, 140, 40), -1)
        cv2.putText(overlay, context_msg, (w // 8 + 14, 116), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2, cv2.LINE_AA)

    if location_msg:
        cv2.rectangle(overlay, (40, 92), (w - 40, 128), (140, 60, 0), -1)
        cv2.putText(overlay, location_msg, (50, 116), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1, cv2.LINE_AA)

    return overlay


def run_pipeline(args: argparse.Namespace):
    """Main execution loop for YOLO11 assistive vision and spatial routing."""
    print(f"[Model] Loading YOLO11 model: {args.model}...")
    try:
        from ultralytics import YOLO
        model = YOLO(args.model)
        class_names = model.names if hasattr(model, "names") else {}
    except Exception as exc:
        print(f"[Model Error] Could not load YOLO model: {exc}")
        sys.exit(1)

    use_mock = args.mock
    cap = None
    current_cam_idx = args.camera

    if not use_mock:
        cap, current_cam_idx = open_camera(current_cam_idx)
        if cap is None:
            print("[Warning] No video camera opened. Falling back to synthetic mock stream.")
            use_mock = True
        else:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    router = SpatialRoutingEngine(min_area_ratio=0.015, max_area_ratio=0.35)
    context_tracker = ContextSceneTracker()

    print("\n" + "=" * 65)
    print(" Assistive Vision Prototype (PulsePath) Active")
    print(f" - Active Camera: {get_camera_name(current_cam_idx)}")
    print(" - Press 'c' to cycle cameras (iPhone Continuity <-> Mac FaceTime)")
    print(" - Press 'w' for 'Where am I?' query")
    print(" - Press 'q' to quit")
    print("=" * 65 + "\n")

    frame_count = 0
    prev_time = time.time()
    current_fps = 0.0
    location_banner = None
    location_banner_time = 0.0
    toast_banner = f"Connected: {get_camera_name(current_cam_idx)}"
    toast_time = time.time()

    try:
        while True:
            frame_count += 1
            if use_mock:
                frame = create_mock_frame(args.width, args.height, frame_count)
                time.sleep(0.03)
            else:
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.05)
                    continue

            fh, fw, _ = frame.shape

            # Run YOLO11 inference across all 80 classes
            results = model(frame, conf=args.conf, verbose=False)
            boxes: List[Tuple[int, int, int, int]] = []
            scores: List[float] = []
            class_ids: List[int] = []

            if len(results) > 0 and results[0].boxes is not None:
                for b in results[0].boxes:
                    xyxy = b.xyxy[0].cpu().numpy().astype(int)
                    boxes.append((xyxy[0], xyxy[1], xyxy[2], xyxy[3]))
                    scores.append(float(b.conf[0].cpu().numpy()))
                    class_ids.append(int(b.cls[0].cpu().numpy()))

            # Spatial routing & haptics
            detections, haptic_state = router.process_detections(
                boxes=boxes,
                scores=scores,
                class_ids=class_ids,
                class_names=class_names,
                frame_width=fw,
                frame_height=fh,
            )

            # Context update (bed detection, morning routine)
            context_msg = context_tracker.update(detections)

            # Telemetry printing every 30 frames
            if frame_count % 30 == 0:
                threat_info = f"Threat: {haptic_state.active_threat}" if haptic_state.active_threat else "Clear"
                print(
                    f"[Telemetry] Frame {frame_count:04d} | "
                    f"Left PWM: {haptic_state.left_pwm:4.1f}% | "
                    f"Right PWM: {haptic_state.right_pwm:4.1f}% | "
                    f"{threat_info}"
                )

            # Timed banners
            now = time.time()
            if location_banner and (now - location_banner_time > 5.0):
                location_banner = None
            if toast_banner and (now - toast_time > 4.0):
                toast_banner = None

            # Calculate FPS
            dt = now - prev_time
            prev_time = now
            if dt > 0:
                current_fps = (current_fps * 0.9) + ((1.0 / dt) * 0.1)

            # Render Modern HUD
            annotated = render_hud(
                frame=frame,
                detections=detections,
                haptics=haptic_state,
                context_msg=context_msg,
                fps=current_fps,
                camera_idx=current_cam_idx if not use_mock else -1,
                location_msg=location_banner,
                toast_msg=toast_banner,
            )

            if not args.headless:
                cv2.imshow("PulsePath - Assistive Vision Prototype", annotated)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("[Pipeline] Exiting on user request.")
                    break
                elif key == ord("w"):
                    location_banner = context_tracker.query_location(detections)
                    location_banner_time = time.time()
                    print(f"[Location Query Response] {location_banner}")
                elif key == ord("c") and not use_mock:
                    # Switch Camera (0 <-> 1)
                    new_idx = 0 if current_cam_idx == 1 else 1
                    print(f"\n[Camera] User requested switch to index {new_idx} ({get_camera_name(new_idx)})...")
                    if cap is not None:
                        cap.release()
                    new_cap, actual_new = open_camera(new_idx)
                    if new_cap is not None:
                        cap = new_cap
                        current_cam_idx = actual_new
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
                        toast_banner = f"Switched: {get_camera_name(current_cam_idx)}"
                        toast_time = time.time()
                    else:
                        print(f"[Camera Error] Could not switch to index {new_idx}.")
                        toast_banner = f"Error opening camera #{new_idx}"
                        toast_time = time.time()
            else:
                if args.max_frames and frame_count >= args.max_frames:
                    break

    finally:
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PulsePath Assistive Vision Prototype")
    # Default camera set to 1 (iPhone Continuity Camera)
    parser.add_argument("--camera", type=int, default=1, help="Camera index (default: 1 for iPhone Continuity Camera)")
    parser.add_argument("--conf", type=float, default=0.35, help="YOLO confidence threshold (default: 0.35)")
    parser.add_argument("--model", type=str, default="yolo11n.pt", help="YOLO model path or weight name")
    parser.add_argument("--width", type=int, default=640, help="Frame width (default: 640)")
    parser.add_argument("--height", type=int, default=480, help="Frame height (default: 480)")
    parser.add_argument("--mock", action="store_true", help="Run with synthetic test stream")
    parser.add_argument("--headless", action="store_true", help="Run without opening graphical window (for tests)")
    parser.add_argument("--max-frames", type=int, default=0, help="Exit after N frames (useful for test runs)")
    return parser.parse_args()


if __name__ == "__main__":
    run_pipeline(parse_arguments())
