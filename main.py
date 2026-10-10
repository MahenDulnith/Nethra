#!/usr/bin/env python3
"""Assistive Vision Prototype (PulsePath)

Real-time Edge-AI spatial obstacle detection, haptic wristband routing,
and contextual scene awareness for the visually impaired.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
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
        return f"Location: {self.assumed_location}. In front of you: {detected_summary}."


def open_camera(camera_idx: int) -> Tuple[Optional[cv2.VideoCapture], int]:
    """Attempts to open the requested camera index with automatic fallback."""
    print(f"[Camera] Trying camera index {camera_idx} (e.g., iPhone Continuity Camera)...")
    cap = cv2.VideoCapture(camera_idx)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"[Camera] Successfully connected to camera index {camera_idx}.")
            return cap, camera_idx
        cap.release()

    # Try fallback indices
    fallbacks = [0, 1, 2]
    if camera_idx in fallbacks:
        fallbacks.remove(camera_idx)

    for idx in fallbacks:
        print(f"[Camera] Fallback: Trying camera index {idx}...")
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                print(f"[Camera] Connected to fallback camera index {idx}.")
                return cap, idx
            cap.release()

    return None, -1


def create_mock_frame(width: int = 640, height: int = 480, frame_count: int = 0) -> np.ndarray:
    """Generates synthetic frames for headless testing or when camera is unavailable."""
    frame = np.full((height, width, 3), 40, dtype=np.uint8)

    # Draw simulated walking corridor
    pts = np.array([[width * 0.3, height], [width * 0.45, height * 0.4], [width * 0.55, height * 0.4], [width * 0.7, height]], np.int32)
    cv2.fillPoly(frame, [pts], (70, 70, 70))

    # Move a simulated obstacle across zones
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
) -> np.ndarray:
    """Renders visual zone boundaries, bounding boxes, and simulated wristband PWM meters."""
    h, w, _ = frame.shape
    overlay = frame.copy()

    one_third = int(w / 3.0)
    two_thirds = int((w * 2.0) / 3.0)

    # 1. Zone Divider Lines (Dashed / Transparent)
    cv2.line(overlay, (one_third, 0), (one_third, h), (100, 100, 100), 1)
    cv2.line(overlay, (two_thirds, 0), (two_thirds, h), (100, 100, 100), 1)

    # Zone Labels at the top
    cv2.putText(overlay, "LEFT ZONE", (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
    cv2.putText(overlay, "CENTER (AHEAD)", (one_third + 20, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
    cv2.putText(overlay, "RIGHT ZONE", (two_thirds + 15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

    # 2. Draw Detections
    for det in detections:
        x1, y1, x2, y2 = det.box
        # Color coding: Green for minor, Orange for medium, Red for close threat
        if det.pwm_intensity > 60:
            box_color = (0, 0, 255)  # Red
        elif det.pwm_intensity > 25:
            box_color = (0, 165, 255)  # Orange
        else:
            box_color = (0, 255, 0)  # Green

        cv2.rectangle(overlay, (x1, y1), (x2, y2), box_color, 2)
        label_text = f"{det.label} {det.confidence:.2f} | PWM: {det.pwm_intensity:.0f}%"
        cv2.putText(overlay, label_text, (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

    # 3. Bottom HUD Bar for Simulated Dual-Wristband Haptics
    hud_bar_height = 80
    cv2.rectangle(overlay, (0, h - hud_bar_height), (w, h), (20, 20, 20), -1)

    # Left Wristband PWM Meter
    left_bar_w = int((w * 0.35) * (haptics.left_pwm / 100.0))
    cv2.putText(overlay, f"LEFT WRISTBAND: {haptics.left_pwm:.0f}% PWM", (15, h - 55), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)
    cv2.rectangle(overlay, (15, h - 45), (int(w * 0.35) + 15, h - 25), (60, 60, 60), 1)
    left_color = (0, int(255 - (haptics.left_pwm * 2.55)), int(haptics.left_pwm * 2.55))
    if left_bar_w > 0:
        cv2.rectangle(overlay, (15, h - 45), (15 + left_bar_w, h - 25), left_color, -1)

    # Right Wristband PWM Meter
    right_start_x = int(w * 0.6)
    right_bar_w = int((w * 0.35) * (haptics.right_pwm / 100.0))
    cv2.putText(overlay, f"RIGHT WRISTBAND: {haptics.right_pwm:.0f}% PWM", (right_start_x, h - 55), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)
    cv2.rectangle(overlay, (right_start_x, h - 45), (right_start_x + int(w * 0.35), h - 25), (60, 60, 60), 1)
    right_color = (0, int(255 - (haptics.right_pwm * 2.55)), int(haptics.right_pwm * 2.55))
    if right_bar_w > 0:
        cv2.rectangle(overlay, (right_start_x, h - 45), (right_start_x + right_bar_w, h - 25), right_color, -1)

    # Center Status Telemetry
    threat_text = haptics.active_threat or "Path Clear"
    cv2.putText(overlay, f"Threat: {threat_text}", (int(w * 0.37), h - 55), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)
    cv2.putText(overlay, f"Cam: #{camera_idx} | FPS: {fps:.1f}", (int(w * 0.37), h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

    # 4. Context Notification Banner (Top Center)
    if context_msg:
        cv2.rectangle(overlay, (w // 6, 40), (5 * w // 6, 75), (40, 120, 40), -1)
        cv2.putText(overlay, context_msg, (w // 6 + 10, 63), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

    if location_msg:
        cv2.rectangle(overlay, (50, 85), (w - 50, 115), (100, 50, 0), -1)
        cv2.putText(overlay, location_msg, (60, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)

    return overlay


def run_pipeline(args: argparse.Namespace):
    """Main execution loop for YOLO11 assistive vision and spatial routing."""
    # 1. Load YOLO11 Model
    print(f"[Model] Loading YOLO11 model: {args.model}...")
    try:
        from ultralytics import YOLO
        model = YOLO(args.model)
        # Ultralytics class dictionary
        class_names = model.names if hasattr(model, "names") else {}
    except Exception as exc:
        print(f"[Model Error] Could not load YOLO model: {exc}")
        print("[Model Error] Ensure ultralytics is installed via '.venv/bin/pip install ultralytics'")
        sys.exit(1)

    # 2. Video Capture
    use_mock = args.mock
    cap = None
    actual_cam_idx = -1
    if not use_mock:
        cap, actual_cam_idx = open_camera(args.camera)
        if cap is None:
            print("[Warning] No video camera could be opened. Falling back to synthetic mock stream.")
            use_mock = True
        else:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    router = SpatialRoutingEngine(min_area_ratio=0.015, max_area_ratio=0.35)
    context_tracker = ContextSceneTracker()

    print("\n" + "=" * 65)
    print(" Assistive Vision Prototype (PulsePath) Active")
    print(" - Detecting all 80 COCO classes")
    print(" - Dual-wristband spatial routing (Left/Center/Right + PWM %)")
    print(" - Context awareness (Bed detection, Location queries)")
    print(" Controls: Press 'q' to exit | 'w' for 'Where am I?' query | 'm' to mute")
    print("=" * 65 + "\n")

    frame_count = 0
    prev_time = time.time()
    current_fps = 0.0
    location_banner = None
    location_banner_time = 0.0

    try:
        while True:
            frame_count += 1
            if use_mock:
                frame = create_mock_frame(args.width, args.height, frame_count)
                time.sleep(0.03)  # Simulate ~30 FPS
            else:
                ret, frame = cap.read()
                if not ret or frame is None:
                    print("[Stream] Failed to read frame from camera.")
                    break

            fh, fw, _ = frame.shape

            # Run YOLO11 inference (all 80 classes)
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

            # Compute spatial routing and haptics
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
            if context_msg:
                print(f"[Context Announcement] {context_msg}")

            # Telemetry printing every 30 frames
            if frame_count % 30 == 0:
                threat_info = f"Threat: {haptic_state.active_threat}" if haptic_state.active_threat else "Clear"
                print(
                    f"[Telemetry] Frame {frame_count:04d} | "
                    f"Left PWM: {haptic_state.left_pwm:4.1f}% | "
                    f"Right PWM: {haptic_state.right_pwm:4.1f}% | "
                    f"{threat_info}"
                )

            # Clear temporary location query banner after 5 seconds
            if location_banner and (time.time() - location_banner_time > 5.0):
                location_banner = None

            # Calculate FPS
            now = time.time()
            dt = now - prev_time
            prev_time = now
            if dt > 0:
                current_fps = (current_fps * 0.9) + ((1.0 / dt) * 0.1)

            # Render Visual HUD
            annotated = render_hud(
                frame=frame,
                detections=detections,
                haptics=haptic_state,
                context_msg=context_msg,
                fps=current_fps,
                camera_idx=actual_cam_idx if not use_mock else -1,
                location_msg=location_banner,
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
            else:
                # In headless / test mode, run requested number of frames or break
                if args.max_frames and frame_count >= args.max_frames:
                    print(f"[Pipeline] Reached max frames ({args.max_frames}). Completed successfully.")
                    break

    finally:
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PulsePath Assistive Vision Prototype")
    parser.add_argument("--camera", type=int, default=1, help="Camera index (default: 1 for Continuity Camera)")
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
