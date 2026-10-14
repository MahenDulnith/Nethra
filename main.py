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
from typing import Optional, Union

import cv2

from adapters.camera.base import CameraSource, get_camera_name, open_camera
from adapters.camera.factory import CameraFactory
from adapters.camera.mock_camera import create_mock_frame
from contracts.detection import Detection
from contracts.frame import LensStatus, SourceId
from contracts.haptic_command import HapticFeedbackState
from features.context_routines.context_tracker import ContextSceneTracker
from services.arbiter.channel_policy import DispatchChannel
from services.arbiter.rule_arbiter import RuleArbiter
from services.safety.safety_engine import SafetyEngine
from services.safety.spatial_router import SpatialRoutingEngine
from services.voice.speech_dispatcher import SpeechDispatcher
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


def resolve_camera_source(args: argparse.Namespace) -> CameraSource:
    """Instantiates the appropriate CameraSource via CameraFactory or explicit CLI flags."""
    if args.mock:
        return CameraFactory.create("synthetic_mock")

    cli_overrides = {
        "width": args.width,
        "height": args.height,
    }

    if args.camera_url:
        cli_overrides["stream_url"] = args.camera_url
        return CameraFactory.create("android_usb", cli_overrides=cli_overrides)

    if args.camera_profile:
        return CameraFactory.create(args.camera_profile, cli_overrides=cli_overrides)

    if args.camera != 1:
        cli_overrides["device_index"] = args.camera
        return CameraFactory.create("uvc_webcam", cli_overrides=cli_overrides)

    return CameraFactory.create("auto", cli_overrides=cli_overrides)


def run_pipeline(args: argparse.Namespace) -> None:
    """Main execution loop for Nethra YOLO11 assistive vision, safety engine, and spatial routing."""
    detector = YoloEnsembleDetector(
        coco_model_path=args.coco_model,
        doors_model_path=args.doors_model,
        iou_thresh=0.45,
    )
    if not detector.is_ready:
        print("[Fatal Error] No YOLO model could be loaded.")
        sys.exit(1)

    mode_label = detector.mode_label

    camera = resolve_camera_source(args)
    if not camera.start():
        print(f"[Warning] Failed to start preferred camera ({camera.name}). Falling back to synthetic mock stream.")
        camera.release()
        camera = CameraFactory.create("synthetic_mock")
        camera.start()

    # Initialize L2 Safety Engine (Hygiene, Detector, Tracker, Growth Estimator, Spatial Router)
    router = SpatialRoutingEngine(
        min_area_ratio=0.015,
        max_area_ratio=0.35,
        fov_area_scale=camera.fov_area_scale,
    )
    safety_engine = SafetyEngine(
        detector=detector,
        spatial_router=router,
    )
    rule_arbiter = RuleArbiter()
    context_tracker = ContextSceneTracker()
    speech = SpeechDispatcher(
        enabled=not args.mute,
        use_clock_face=not args.relative_directions,
    )

    print("\n" + "=" * 65)
    print(" Nethra Assistive Vision Prototype Active")
    print(f" - Vision Engine: {mode_label}")
    print(f" - Active Camera: {camera.name} (FOV Scale: {camera.fov_area_scale}x)")
    print(f" - Voice Engine:  {'Muted' if args.mute else 'Active (Offline TTS)'}")
    print(f" - Directions:    {'Relative (Left/Right)' if args.relative_directions else 'Clock-Face (10-2 o\'clock)'}")
    print(f" - Ears-Free:     {'Advisory Haptic-Only' if not args.voice_advisory else 'All Speech Enabled'}")
    print(" - Press 'c' to cycle cameras (Phone Camera <-> Laptop Webcam)")
    print(" - Press 'w' for 'Where am I?' query")
    print(" - Press 'q' to quit")
    print("=" * 65 + "\n")

    frame_count = 0
    prev_time = time.time()
    current_fps = 0.0
    location_banner = None
    location_banner_time = 0.0
    toast_banner = f"Connected: {camera.name}"
    toast_time = time.time()

    try:
        while True:
            frame_count += 1
            ret, frame, capture_ts = camera.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            # 1. Run Offline Safety Engine
            detections, haptic_state, candidate_alerts, lens_status = safety_engine.process(
                frame=frame,
                timestamp_ns=capture_ts,
                conf=args.conf,
            )

            # Lens hygiene warning feedback
            if lens_status != LensStatus.OK and lens_status != LensStatus.BLURRED:
                toast_banner = f"Camera Alert: Lens {lens_status.value}"
                toast_time = time.time()

            # 2. Run Deterministic Rule Arbiter
            winning_alert, dispatch_channel = rule_arbiter.arbitrate(candidate_alerts)
            if winning_alert is not None:
                dir_label = (
                    winning_alert.direction_sector.value
                    if args.relative_directions
                    else winning_alert.direction_sector.clock_face
                )
                toast_banner = f"[{winning_alert.tier.value}] {winning_alert.object_class.upper()} {dir_label}"
                toast_time = time.time()

                # Ears-Free Policy:
                # - CRITICAL alerts dispatch to BOTH haptic and speech (interrupting).
                # - ADVISORY alerts dispatch to HAPTIC_ONLY unless user explicitly flags --voice-advisory.
                # - SOCIAL alerts dispatch to SPEECH_ONLY.
                should_speak = (
                    dispatch_channel in (DispatchChannel.BOTH, DispatchChannel.SPEECH_ONLY)
                    or (dispatch_channel == DispatchChannel.HAPTIC_ONLY and args.voice_advisory)
                )
                if should_speak:
                    speech.dispatch_alert(winning_alert)

            # 3. Context Routine Update (bed detection, morning routine)
            context_msg = context_tracker.update(detections)
            if context_msg:
                speech.say(context_msg)

            # Telemetry printing every 30 frames
            if frame_count % 30 == 0:
                threat_info = (
                    f"Threat: {haptic_state.active_threat}"
                    if haptic_state.active_threat
                    else "Clear"
                )
                arbiter_info = f" | Alert: {winning_alert.tier.value}" if winning_alert else ""
                print(
                    f"[Telemetry] Frame {frame_count:04d} | "
                    f"Left PWM: {haptic_state.left_pwm:4.1f}% | "
                    f"Right PWM: {haptic_state.right_pwm:4.1f}% | "
                    f"{threat_info}{arbiter_info}"
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
                camera_idx=camera.name,
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
                    speech.say(location_banner)
                elif key == ord("c"):
                    print("\n[Camera] User requested camera cycle...")
                    camera.release()
                    if camera.source_id.value in ("IPHONE", "ANDROID_USB", "ANDROID_IP"):
                        camera = CameraFactory.create("uvc_webcam", cli_overrides={"width": args.width, "height": args.height})
                    else:
                        camera = CameraFactory.create("auto", cli_overrides={"width": args.width, "height": args.height})

                    if not camera.start():
                        print("[Camera Error] Could not open alternate camera. Falling back to mock.")
                        camera = CameraFactory.create("synthetic_mock")
                        camera.start()

                    safety_engine.spatial_router.fov_area_scale = camera.fov_area_scale
                    toast_banner = f"Switched: {camera.name}"
                    toast_time = time.time()
                    speech.say(f"Switched to {camera.name}")
            else:
                if args.max_frames and frame_count >= args.max_frames:
                    break

    finally:
        speech.shutdown()
        camera.release()
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
        "--model",
        dest="doors_model",
        type=str,
        default="models/nethra_doors_yolo11n.pt",
        help="Fine-tuned doors/assistive model path (default: models/nethra_doors_yolo11n.pt)",
    )
    parser.add_argument(
        "--camera-profile",
        type=str,
        default="",
        choices=["", "auto", "iphone_continuity", "android_usb", "android_ip", "uvc_webcam", "synthetic_mock", "file_replay"],
        help="Named camera profile from config/camera.yaml (default: auto)",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=1,
        help="Camera device index (default: 1 for Phone Camera / Continuity Camera, 0 for Laptop Webcam)",
    )
    parser.add_argument(
        "--camera-url",
        type=str,
        default="",
        help="Stream URL for Android IP Webcam / ADB stream (e.g. http://127.0.0.1:8080/video)",
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
    parser.add_argument(
        "--mute",
        action="store_true",
        help="Disable spoken TTS audio feedback",
    )
    parser.add_argument(
        "--voice-advisory",
        action="store_true",
        help="Speak advisory obstacle alerts in addition to haptics (default: False, ears-free mode)",
    )
    parser.add_argument(
        "--relative-directions",
        action="store_true",
        help="Use relative directions (left/right) instead of standard clock-face directions (10-2 o'clock)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_pipeline(parse_arguments())
