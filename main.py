#!/usr/bin/env python3
"""Assistive Vision Prototype (PulsePath)

Real-time Edge-AI spatial obstacle detection, haptic wristband routing,
and contextual scene awareness for the visually impaired.
Supports Dual-Model Ensemble: COCO-80 (people, bottles, laptops) +
Custom Fine-Tuned Model (doors, wardrobes, windows).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
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


def compute_iou(boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> float:
    """Calculates Intersection over Union (IoU) between two bounding boxes."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    inter_w = max(0, xB - xA)
    inter_h = max(0, yB - yA)
    inter_area = float(inter_w * inter_h)

    boxA_area = float(max(0, boxA[2] - boxA[0]) * max(0, boxA[3] - boxA[1]))
    boxB_area = float(max(0, boxB[2] - boxB[0]) * max(0, boxB[3] - boxB[1]))
    union_area = boxA_area + boxB_area - inter_area

    if union_area <= 0.0:
        return 0.0
    return inter_area / union_area


def merge_candidate_detections(
    candidates: List[Tuple[Tuple[int, int, int, int], float, str]],
    iou_thresh: float = 0.45,
) -> List[Tuple[Tuple[int, int, int, int], float, str]]:
    """Merges detections from multiple models and eliminates duplicate boxes."""
    if not candidates:
        return []

    # Sort descending by confidence score
    candidates.sort(key=lambda x: x[1], reverse=True)
    kept: List[Tuple[Tuple[int, int, int, int], float, str]] = []

    for cand in candidates:
        box, score, label = cand
        overlap = False
        for k_box, k_score, k_label in kept:
            if compute_iou(box, k_box) > iou_thresh:
                overlap = True
                break
        if not overlap:
            kept.append(cand)

    return kept


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
        labels: Optional[List[str]] = None,
        class_ids: Optional[List[int]] = None,
        class_names: Optional[Dict[int, str]] = None,
        frame_width: int = 640,
        frame_height: int = 480,
    ) -> Tuple[List[Detection], HapticFeedbackState]:
        """Processes raw model detections into spatial cues and dual wristband signals."""
        total_frame_area = float(max(1, frame_width * frame_height))
        detections: List[Detection] = []

        # Resolve labels from class_ids and class_names if labels not provided
        resolved_labels: List[str] = []
        if labels is not None:
            resolved_labels = labels
        elif class_ids is not None and class_names is not None:
            resolved_labels = [class_names.get(cid, f"obj_{cid}") for cid in class_ids]
        else:
            resolved_labels = [f"obj_{i}" for i in range(len(boxes))]

        max_left_pwm = 0.0
        max_right_pwm = 0.0
        highest_threat_label = None
        max_threat_area = 0.0

        for box, score, label in zip(boxes, scores, resolved_labels):
            x1, y1, x2, y2 = box
            w = max(0, x2 - x1)
            h = max(0, y2 - y1)
            cx = x1 + (w / 2.0)
            cy = y1 + (h / 2.0)

            box_area = float(w * h)
            area_ratio = box_area / total_frame_area
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
    model_mode_label: str = "Ensemble: COCO-80 + Doors",
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
    cv2.putText(overlay, "PulsePath AI", (14, 27), cv2.FONT_HERSHEY_DUPLEX, 0.62, (0, 230, 255), 1, cv2.LINE_AA)

    # Model Badge
    cv2.putText(overlay, f"[{model_mode_label}]", (150, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (200, 220, 255), 1, cv2.LINE_AA)

    # Camera Device Badge
    cam_name = get_camera_name(camera_idx)
    cam_badge_color = (0, 200, 100) if camera_idx == 1 else (180, 180, 180)
    cv2.putText(overlay, f"Cam: #{camera_idx}", (w - 180, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.42, cam_badge_color, 1, cv2.LINE_AA)

    # FPS Indicator
    fps_color = (0, 255, 120) if fps >= 20 else ((0, 200, 255) if fps >= 10 else (0, 100, 255))
    cv2.putText(overlay, f"{fps:4.1f} FPS", (w - 85, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.45, fps_color, 1, cv2.LINE_AA)

    # 2. ZONE DIVIDERS & LABELS
    cv2.line(overlay, (one_third, top_bar_h), (one_third, h - 88), (80, 80, 95), 1)
    cv2.line(overlay, (two_thirds, top_bar_h), (two_thirds, h - 88), (80, 80, 95), 1)

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
    cv2.putText(overlay, threat_text, (int(w * 0.36), h - 55), cv2.FONT_HERSHEY_SIMPLEX, 0.44, threat_color, 1, cv2.LINE_AA)

    # Active objects summary
    labels_summary = ", ".join(list({d.label for d in detections})) if detections else "None in view"
    if len(labels_summary) > 28:
        labels_summary = labels_summary[:25] + "..."
    cv2.putText(overlay, f"Seen: {labels_summary}", (int(w * 0.36), h - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 160, 175), 1, cv2.LINE_AA)

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
    from ultralytics import YOLO

    # 1. Initialize Models (Dual-Model Ensemble)
    model_coco = None
    model_doors = None

    print(f"[Model 1] Loading Base YOLO11 Nano (COCO 80 classes): {args.coco_model}...")
    try:
        model_coco = YOLO(args.coco_model)
        coco_names = model_coco.names if hasattr(model_coco, "names") else {}
    except Exception as exc:
        print(f"[Warning] Could not load COCO model: {exc}")

    doors_path = Path(args.doors_model)
    if doors_path.exists():
        print(f"[Model 2] Loading Fine-Tuned Doors Model: {args.doors_model}...")
        try:
            model_doors = YOLO(str(doors_path))
            door_names = model_doors.names if hasattr(model_doors, "names") else {}
        except Exception as exc:
            print(f"[Warning] Could not load doors model: {exc}")
    else:
        print(f"[Model 2] Doors model '{args.doors_model}' not found, running single COCO model.")

    if model_coco is None and model_doors is None:
        print("[Fatal Error] No YOLO model could be loaded.")
        sys.exit(1)

    # Determine mode label
    if model_coco is not None and model_doors is not None:
        mode_label = "Ensemble: COCO-80 + Doors"
    elif model_doors is not None:
        mode_label = "Model: Doors & Indoor"
    else:
        mode_label = "Model: COCO-80"

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
    print(f" - Vision Engine: {mode_label}")
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
            raw_candidates: List[Tuple[Tuple[int, int, int, int], float, str]] = []

            # 1. Run COCO-80 Model (people, bottles, cups, cell phones, etc.)
            if model_coco is not None:
                results_coco = model_coco(frame, conf=args.conf, verbose=False)
                if len(results_coco) > 0 and results_coco[0].boxes is not None:
                    for b in results_coco[0].boxes:
                        xyxy = b.xyxy[0].cpu().numpy().astype(int)
                        box_tuple = (xyxy[0], xyxy[1], xyxy[2], xyxy[3])
                        conf_val = float(b.conf[0].cpu().numpy())
                        cls_idx = int(b.cls[0].cpu().numpy())
                        lbl = coco_names.get(cls_idx, f"obj_{cls_idx}")
                        raw_candidates.append((box_tuple, conf_val, lbl))

            # 2. Run Fine-Tuned Doors Model (doors, wardrobes, windows, etc.)
            if model_doors is not None:
                results_doors = model_doors(frame, conf=args.conf, verbose=False)
                if len(results_doors) > 0 and results_doors[0].boxes is not None:
                    for b in results_doors[0].boxes:
                        xyxy = b.xyxy[0].cpu().numpy().astype(int)
                        box_tuple = (xyxy[0], xyxy[1], xyxy[2], xyxy[3])
                        conf_val = float(b.conf[0].cpu().numpy())
                        cls_idx = int(b.cls[0].cpu().numpy())
                        lbl = door_names.get(cls_idx, f"indoor_{cls_idx}")
                        raw_candidates.append((box_tuple, conf_val, lbl))

            # Merge and eliminate overlapping duplicate boxes
            merged_candidates = merge_candidate_detections(raw_candidates, iou_thresh=0.45)

            boxes = [c[0] for c in merged_candidates]
            scores = [c[1] for c in merged_candidates]
            labels = [c[2] for c in merged_candidates]

            # Spatial routing & haptics
            detections, haptic_state = router.process_detections(
                boxes=boxes,
                scores=scores,
                labels=labels,
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
                model_mode_label=mode_label,
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
    # Dual-model ensemble configuration
    parser.add_argument("--coco-model", type=str, default="yolo11n.pt", help="Base COCO-80 model path (default: yolo11n.pt)")
    parser.add_argument("--doors-model", type=str, default="pulsepath_doors_yolo11n.pt", help="Fine-tuned doors model path (default: pulsepath_doors_yolo11n.pt)")
    # Camera options
    parser.add_argument("--camera", type=int, default=1, help="Camera index (default: 1 for iPhone Continuity Camera)")
    parser.add_argument("--conf", type=float, default=0.35, help="YOLO confidence threshold (default: 0.35)")
    parser.add_argument("--width", type=int, default=640, help="Frame width (default: 640)")
    parser.add_argument("--height", type=int, default=480, help="Frame height (default: 480)")
    parser.add_argument("--mock", action="store_true", help="Run with synthetic test stream")
    parser.add_argument("--headless", action="store_true", help="Run without opening graphical window (for tests)")
    parser.add_argument("--max-frames", type=int, default=0, help="Exit after N frames (useful for test runs)")
    return parser.parse_args()


if __name__ == "__main__":
    run_pipeline(parse_arguments())
