#!/usr/bin/env python3
"""Nethra: Edge-AI Assistive Vision & Spatial Haptic Navigation Prototype.

Real-time Edge-AI spatial obstacle detection, dual-wristband haptic routing,
and contextual scene awareness for visually impaired users.
Supports Dual-Model Ensemble: COCO-80 (people, vehicles, indoor items) +
Custom Fine-Tuned Model (doors, handles, stairs, indoor hazards).
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Union

import cv2

from adapters.camera.base import get_camera_name, open_camera
from adapters.camera.mock_camera import create_mock_frame
from contracts.detection import Detection
from contracts.haptic_command import HapticFeedbackState
from features.context_routines.context_tracker import ContextSceneTracker
from services.safety.spatial_router import SpatialRoutingEngine
from services.safety.yolo_ensemble import (
    YoloEnsembleDetector,
    compute_iou,
    merge_candidate_detections,
)
from shell.hud.opencv_hud import render_hud

__all__ = [
    "Detection",
    "HapticFeedbackState",
    "SpatialRoutingEngine",
    "ContextSceneTracker",
    "compute_iou",
    "merge_candidate_detections",
    "get_camera_name",
    "open_camera",
    "create_mock_frame",
    "render_hud",
    "run_pipeline",
    "parse_arguments",
]


def run_pipeline(args: argparse.Namespace) -> None:
    """Main execution loop for Nethra YOLO11 assistive vision and spatial routing."""
    detector = YoloEnsembleDetector(
        coco_model_path=args.coco_model,
        doors_model_path=args.doors_model,
        iou_thresh=0.45,
    )
    if not detector.is_ready:
        print("[Fatal Error] No YOLO model could be loaded.")
        sys.exit(1)

    mode_label = detector.mode_label
    use_mock = args.mock
    cap = None

    # Allow numeric camera index or string URL (e.g. Android IP Webcam / ADB USB stream)
    current_cam_idx: Union[int, str]
    if args.camera_url:
        current_cam_idx = args.camera_url
    else:
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
    print(" Nethra Assistive Vision Prototype Active")
    print(f" - Vision Engine: {mode_label}")
    print(f" - Active Camera: {get_camera_name(current_cam_idx if not use_mock else -1)}")
    print(" - Press 'c' to cycle cameras (Phone Camera <-> Laptop Webcam)")
    print(" - Press 'w' for 'Where am I?' query")
    print(" - Press 'q' to quit")
    print("=" * 65 + "\n")

    frame_count = 0
    prev_time = time.time()
    current_fps = 0.0
    location_banner = None
    location_banner_time = 0.0
    toast_banner = f"Connected: {get_camera_name(current_cam_idx if not use_mock else -1)}"
    toast_time = time.time()

    try:
        while True:
            frame_count += 1
            if use_mock:
                frame = create_mock_frame(args.width, args.height, frame_count)
                time.sleep(0.03)
            else:
                assert cap is not None
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.05)
                    continue

            fh, fw, _ = frame.shape
            boxes, scores, labels = detector.detect(frame, conf=args.conf)

            # Spatial routing & dual-wristband PWM haptics
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
                threat_info = (
                    f"Threat: {haptic_state.active_threat}"
                    if haptic_state.active_threat
                    else "Clear"
                )
                print(
                    f"[Telemetry] Frame {frame_count:04d} | "
                    f"Left PWM: {haptic_state.left_pwm:4.1f}% | "
                    f"Right PWM: {haptic_state.right_pwm:4.1f}% | "
                    f"{threat_info}"
                )

            now = time.time()
            if location_banner and (now - location_banner_time > 5.0):
                location_banner = None
            if toast_banner and (now - toast_time > 4.0):
                toast_banner = None

            dt = now - prev_time
            prev_time = now
            if dt > 0:
                current_fps = (current_fps * 0.9) + ((1.0 / dt) * 0.1)

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
                cv2.imshow("Nethra - Assistive Vision Prototype", annotated)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("[Pipeline] Exiting on user request.")
                    break
                elif key == ord("w"):
                    location_banner = context_tracker.query_location(detections)
                    location_banner_time = time.time()
                    print(f"[Location Query Response] {location_banner}")
                elif key == ord("c") and not use_mock and isinstance(current_cam_idx, int):
                    new_idx = 0 if current_cam_idx == 1 else 1
                    print(
                        f"\n[Camera] User requested switch to index {new_idx} ({get_camera_name(new_idx)})..."
                    )
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
    parser = argparse.ArgumentParser(description="Nethra Assistive Vision Prototype")
    parser.add_argument(
        "--coco-model",
        type=str,
        default="models/yolo11n.pt",
        help="Base COCO-80 model path (default: models/yolo11n.pt)",
    )
    parser.add_argument(
        "--doors-model",
        type=str,
        default="models/nethra_doors_yolo11n.pt",
        help="Fine-tuned doors/assistive model path (default: models/nethra_doors_yolo11n.pt)",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=1,
        help="Camera index (default: 1 for Phone Camera / Continuity Camera, 0 for Laptop Webcam)",
    )
    parser.add_argument(
        "--camera-url",
        type=str,
        default="",
        help="Optional stream URL for Android IP Webcam / ADB USB stream (e.g. http://127.0.0.1:8080/video)",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.35,
        help="YOLO confidence threshold (default: 0.35)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=640,
        help="Frame width (default: 640)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=480,
        help="Frame height (default: 480)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run with synthetic test stream",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without opening graphical window (for tests)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Exit after N frames (useful for test runs)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_pipeline(parse_arguments())
