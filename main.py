#!/usr/bin/env python3
"""Assistive Vision Prototype (PulsePath)

Main orchestrator for real-time edge computer vision, guided search mode,
spatial haptic steering (left/right wristbands), and contextual scene intelligence.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

import cv2

from pulsepath.audio import AudioFeedback
from pulsepath.camera import create_mock_frame, get_camera_name, open_camera
from pulsepath.commands import FIND_KEYS
from pulsepath.context import ContextSceneTracker
from pulsepath.detection import EnsembleDetector, SpatialRoutingEngine
from pulsepath.guidance import GuidanceConfig, GuidanceStateMachine
from pulsepath.hand_tracker import HandTracker
from pulsepath.haptics import HapticPatternEngine
from pulsepath.hud import render_hud


def run_pipeline(args: argparse.Namespace):
    """Main execution loop for PulsePath Assistive Vision."""
    # 1. Initialize Audio Engine (Non-blocking TTS and system chimes)
    audio = AudioFeedback(enabled=not args.no_audio)

    # 2. Initialize Detectors (Dual-Model Ensemble)
    try:
        detector = EnsembleDetector(
            coco_model=args.coco_model,
            doors_model=args.doors_model,
            conf=args.conf,
        )
    except Exception as exc:
        print(f"[Fatal] Failed to load detection models: {exc}")
        sys.exit(1)

    # 3. Initialize Hand Tracking
    hand_tracker = HandTracker(min_confidence=0.5)

    # 4. Initialize Engines
    spatial_engine = SpatialRoutingEngine(min_area_ratio=0.015, max_area_ratio=0.35)
    guidance = GuidanceStateMachine(GuidanceConfig())
    haptic_engine = HapticPatternEngine(override_threshold=80.0)
    context_tracker = ContextSceneTracker()

    # If starting with an initial target (e.g. --target door)
    if args.target:
        initial_out = guidance.start(args.target, time.time())
        if initial_out.speech:
            audio.speak(initial_out.speech)

    # 5. Video Capture Setup
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

    print("\n" + "=" * 68)
    print(" PulsePath AI - Assistive Vision & Guided Search Active")
    print(f" - Vision Models: {detector.mode_label}")
    print(f" - Active Camera: {get_camera_name(current_cam_idx)}")
    print(f" - Hand Tracking: {hand_tracker.backend}")
    print(" Controls:")
    print("   [F] Find Door        | [B] Find Bottle    | [X] Cancel Guidance")
    print("   [C] Switch Camera    | [W] Where Am I?    | [M] Mute/Unmute Audio")
    print("   [Q] Quit")
    print("=" * 68 + "\n")

    frame_count = 0
    prev_time = time.time()
    current_fps = 0.0
    location_banner: Optional[str] = None
    location_banner_time = 0.0
    toast_banner: Optional[str] = f"Connected: {get_camera_name(current_cam_idx)}"
    toast_time = time.time()

    try:
        while True:
            frame_count += 1
            now = time.time()

            # Acquire Frame
            if use_mock:
                frame = create_mock_frame(args.width, args.height, frame_count)
                time.sleep(0.03)
            else:
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.05)
                    continue

            fh, fw = frame.shape[:2]

            # 1. Run Object Detections (Dual Ensemble)
            candidates = detector.detect(frame)
            boxes = [c[0] for c in candidates]
            scores = [c[1] for c in candidates]
            labels = [c[2] for c in candidates]

            detections = spatial_engine.build_detections(boxes, scores, labels, fw, fh)
            obstacle_state = spatial_engine.compute_state(detections)

            # 2. Hand Tracking (Index Fingertip)
            hand_point = None
            if guidance.needs_hand_tracking:
                hand_point = hand_tracker.detect(frame)

            # 3. Guided Search State Machine Update
            g_out = guidance.update(
                detections=detections,
                hand_point=hand_point,
                frame_width=fw,
                frame_height=fh,
                now=now,
            )

            # 4. Audio Feedback (Speech & Chimes)
            if g_out.chime:
                audio.chime(g_out.chime)
            if g_out.speech:
                audio.speak(g_out.speech, now=now)

            # Context Scene Update (e.g. morning in bed)
            context_msg = context_tracker.update(detections)
            if context_msg:
                audio.speak(context_msg, now=now)

            # 5. Haptic Pattern Engine (Guidance + Obstacle Safety Override)
            haptic_out = haptic_engine.compute(
                command=g_out.command,
                magnitude=g_out.magnitude,
                now=now,
                obstacle=obstacle_state,
                guidance_active=guidance.active,
            )

            # 6. Telemetry Logging (Every 30 frames)
            if frame_count % 30 == 0:
                h_source = f"[{haptic_out.source.upper()}]"
                g_str = f"Mode: {guidance.state.value}"
                if guidance.active and guidance.target_name:
                    g_str += f" ({guidance.target_name})"
                print(
                    f"[Telemetry] Frame {frame_count:04d} | "
                    f"Left: {haptic_out.left_pwm:4.1f}% | "
                    f"Right: {haptic_out.right_pwm:4.1f}% | "
                    f"{h_source} {haptic_out.label} | {g_str}"
                )

            # Clear temporary banners
            if location_banner and (now - location_banner_time > 5.0):
                location_banner = None
            if toast_banner and (now - toast_time > 4.0):
                toast_banner = None

            # Calculate FPS
            dt = now - prev_time
            prev_time = now
            if dt > 0:
                current_fps = (current_fps * 0.9) + ((1.0 / dt) * 0.1)

            # 7. Render Visual HUD
            annotated = render_hud(
                frame=frame,
                detections=detections,
                haptics=haptic_out,
                guidance=g_out,
                fps=current_fps,
                camera_name=get_camera_name(current_cam_idx if not use_mock else -1),
                speech_subtitle=audio.last_message if (now - audio.last_message_time < 5.0) else None,
                toast_msg=toast_banner,
                location_msg=location_banner,
            )

            # 8. Interactive Keyboard & Window Handling
            if not args.headless:
                cv2.imshow("PulsePath - Assistive Vision Prototype", annotated)
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    print("[Pipeline] Exiting on user request.")
                    break

                elif key in FIND_KEYS:
                    target_name = FIND_KEYS[key]
                    out = guidance.start(target_name, now=now)
                    toast_banner = f"Search started: {target_name.upper()}"
                    toast_time = now
                    if out.speech:
                        audio.speak(out.speech, now=now)

                elif key == ord("x"):
                    out = guidance.cancel(now=now, speech="Guidance stopped.")
                    toast_banner = "Guidance Cancelled"
                    toast_time = now
                    if out.speech:
                        audio.speak(out.speech, now=now)

                elif key == ord("w"):
                    location_banner = context_tracker.query_location(detections)
                    location_banner_time = now
                    audio.speak(location_banner, now=now)

                elif key == ord("m"):
                    is_muted = audio.toggle_mute()
                    toast_banner = "Audio Muted" if is_muted else "Audio Unmuted"
                    toast_time = now
                    print(f"[Audio] {'Muted' if is_muted else 'Unmuted'}")

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
                    print(f"[Pipeline] Reached max frames ({args.max_frames}). Completed successfully.")
                    break

    finally:
        audio.shutdown()
        hand_tracker.close()
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PulsePath Assistive Vision Prototype")
    parser.add_argument("--coco-model", type=str, default="yolo11n.pt", help="Base COCO-80 model path (default: yolo11n.pt)")
    parser.add_argument("--doors-model", type=str, default="pulsepath_doors_yolo11n.pt", help="Fine-tuned doors model (default: pulsepath_doors_yolo11n.pt)")
    parser.add_argument("--target", type=str, default=None, help="Start directly searching for target object (e.g. door, bottle)")
    parser.add_argument("--camera", type=int, default=1, help="Camera index (default: 1 for iPhone Continuity Camera)")
    parser.add_argument("--conf", type=float, default=0.35, help="YOLO confidence threshold (default: 0.35)")
    parser.add_argument("--width", type=int, default=640, help="Frame width (default: 640)")
    parser.add_argument("--height", type=int, default=480, help="Frame height (default: 480)")
    parser.add_argument("--mock", action="store_true", help="Run with synthetic test stream")
    parser.add_argument("--headless", action="store_true", help="Run without opening graphical window (for tests)")
    parser.add_argument("--no-audio", action="store_true", help="Disable audio speech and chimes")
    parser.add_argument("--max-frames", type=int, default=0, help="Exit after N frames (useful for test runs)")
    return parser.parse_args()


if __name__ == "__main__":
    run_pipeline(parse_arguments())
