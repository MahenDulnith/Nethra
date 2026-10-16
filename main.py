#!/usr/bin/env python3
"""Nethra: Edge-AI Assistive Vision & Spatial Haptic Navigation Prototype.

Real-time Edge-AI spatial obstacle detection, dual-wristband haptic routing,
guided hand-to-object micro-navigation, and contextual scene awareness for
visually impaired users.
Supports Dual-Model Ensemble: COCO-80 (people, vehicles, indoor items) +
Custom Fine-Tuned Model (doors, wardrobes, windows, beds).
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Optional, Union

import cv2

from adapters.audio.mic_listener import PushToTalkListener
from adapters.camera.base import CameraSource, get_camera_name, open_camera
from adapters.camera.factory import CameraFactory
from adapters.camera.mock_camera import create_mock_frame
from adapters.haptic.pattern_engine import HapticPatternEngine
from contracts.detection import Detection
from contracts.frame import LensStatus, SourceId
from contracts.haptic_command import GuidanceState, HapticFeedbackState
from features.context_routines.context_tracker import ContextSceneTracker
from features.lookaround.commands import FIND_KEYS, parse_intent
from features.lookaround.guidance import GuidanceStateMachine
from services.agent.voice_agent import VoiceAgent
from services.arbiter.channel_policy import DispatchChannel
from services.arbiter.rule_arbiter import RuleArbiter
from services.safety.hand_tracker import HandTracker
from services.safety.safety_engine import SafetyEngine
from services.safety.spatial_router import SpatialRoutingEngine
from services.safety.yolo_ensemble import (
    YoloEnsembleDetector,
    compute_iou,
    disambiguate_multi_bed_candidates,
    merge_candidate_detections,
)
from services.voice.speech_dispatcher import SpeechDispatcher
from shell.hud.opencv_hud import render_hud

__all__ = [
    "Detection",
    "HapticFeedbackState",
    "SpatialRoutingEngine",
    "ContextSceneTracker",
    "compute_iou",
    "disambiguate_multi_bed_candidates",
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
    context_tracker = ContextSceneTracker(location=getattr(args, "location", None))
    speech = SpeechDispatcher(
        enabled=not (args.mute or getattr(args, "no_audio", False)),
        use_clock_face=not args.relative_directions,
    )

    # Initialize L4/L2/L1 Guided Search Engine & L1/L3 Voice Agent
    guidance_sm = GuidanceStateMachine()
    hand_tracker = HandTracker()
    haptic_pattern = HapticPatternEngine()
    mic_listener = PushToTalkListener()
    voice_agent = VoiceAgent()

    initial_target = getattr(args, "target", None)
    if initial_target:
        intent = parse_intent(f"find {initial_target}")
        if intent and intent.target:
            out = guidance_sm.start(intent.target, now=time.time())
            if out.speech:
                speech.say(out.speech)

    print("\n" + "=" * 68)
    print(" Nethra Assistive Vision Prototype Active")
    print(f" - Vision Engine: {mode_label}")
    print(f" - Active Camera: {camera.name} (FOV Scale: {camera.fov_area_scale}x)")
    print(f" - Voice Engine:  {'Muted' if not speech.enabled else 'Active (Offline TTS)'} | Mic STT: {mic_listener.backend}")
    print(f" - Directions:    {'Relative (Left/Right)' if args.relative_directions else 'Clock-Face (10-2 o\'clock)'}")
    print(f" - Ears-Free:     {'Advisory Haptic-Only' if not args.voice_advisory else 'All Speech Enabled'}")
    print(" - Keys: [V / Space] Talk to Voice Agent ('find door', 'what do you see', 'where am i')")
    print("         [D] Describe Scene | [F] Find Door | [B] Find Bottle | [X] Cancel")
    print("         [C] Cycle Camera   | [W] Where Am I? | [M] Mute      | [Q] Quit")
    print("=" * 68 + "\n")

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

            h, w, _ = frame.shape
            now = time.time()

            # 1. Run Offline Safety Engine
            detections, haptic_state, candidate_alerts, lens_status = safety_engine.process(
                frame=frame,
                timestamp_ns=capture_ts,
                conf=args.conf,
            )

            # Lens hygiene warning feedback
            if lens_status != LensStatus.OK and lens_status != LensStatus.BLURRED:
                toast_banner = f"Camera Alert: Lens {lens_status.value}"
                toast_time = now

            # 1B. Poll Non-Blocking Push-to-Talk Voice Agent Result
            transcript, mic_err = mic_listener.pop_result()
            if transcript:
                print(f'[VoiceAgent] Heard: "{transcript}"')
                agent_res = voice_agent.handle_transcript(
                    transcript=transcript,
                    detections=detections,
                    guidance_sm=guidance_sm,
                    context_tracker=context_tracker,
                    speech=speech,
                    now=now,
                )
                toast_banner = agent_res.hud_toast
                toast_time = now
                if agent_res.location_banner:
                    location_banner = agent_res.location_banner
                    location_banner_time = now
            elif mic_err:
                print(f"[VoiceAgent] {mic_err}")
                toast_banner = f"Mic: {mic_err}"
                toast_time = now
                speech.say("Sorry, I did not catch that.")

            # 2. Run Guided Search State Machine (if active)
            hand_pt = None
            if guidance_sm.needs_hand_tracking:
                hand_pt = hand_tracker.detect(frame)

            guidance_out = guidance_sm.update(
                detections=detections,
                hand_point=hand_pt,
                frame_width=w,
                frame_height=h,
                now=now,
            )
            if guidance_out.chime:
                speech.chime(guidance_out.chime)
            if guidance_out.speech:
                speech.say(guidance_out.speech)
                toast_banner = guidance_out.speech
                toast_time = now

            # Merge obstacle PWM with Guided Search pulse patterns
            if guidance_out.active:
                haptic_out = haptic_pattern.compute(
                    command=guidance_out.command,
                    magnitude=guidance_out.magnitude,
                    now=now,
                    obstacle=haptic_state,
                    guidance_active=guidance_out.active,
                )
                active_threat = (
                    f"GUIDANCE: {haptic_out.label}"
                    if haptic_out.source == "guidance"
                    else haptic_state.active_threat
                )
                haptic_state = HapticFeedbackState(
                    left_pwm=haptic_out.left_pwm,
                    right_pwm=haptic_out.right_pwm,
                    active_threat=active_threat,
                )

            # 3. Run Deterministic Rule Arbiter
            winning_alert, dispatch_channel = rule_arbiter.arbitrate(candidate_alerts)
            if winning_alert is not None and not guidance_out.active and not mic_listener.is_listening:
                dir_label = (
                    winning_alert.direction_sector.value
                    if args.relative_directions
                    else winning_alert.direction_sector.clock_face
                )
                toast_banner = f"[{winning_alert.tier.value}] {winning_alert.object_class.upper()} {dir_label}"
                toast_time = now

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

            # 4. Context Routine Update (bed detection, morning routine)
            context_msg = context_tracker.update(detections)
            if context_msg and not mic_listener.is_listening:
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
                guidance=guidance_out,
                voice_listening=mic_listener.is_listening,
            )

            if not args.headless:
                cv2.imshow("Nethra - Assistive Vision Prototype", annotated)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("[Pipeline] Exiting on user request.")
                    break
                elif key in (ord("v"), ord(" ")):
                    if not mic_listener.is_listening:
                        speech.stop()
                        speech.chime("found")
                        if mic_listener.start_listening():
                            print("[VoiceAgent] Listening for 3.2s... Speak your command now!")
                            toast_banner = "Listening... Speak now ('find door', 'what do you see')"
                            toast_time = time.time()
                elif key == ord("d"):
                    spoken_scene, hud_scene = voice_agent.summarize_scene(detections)
                    location_banner = hud_scene
                    location_banner_time = time.time()
                    print(f"[Scene Description] {spoken_scene}")
                    speech.say(spoken_scene, interrupt=True)
                elif key == ord("w"):
                    spoken_loc, hud_loc = context_tracker.query_location_details(detections)
                    location_banner = hud_loc
                    location_banner_time = time.time()
                    print(f"[Location Query Response] {spoken_loc}")
                    speech.say(spoken_loc)
                elif key == ord("m"):
                    muted = speech.toggle_mute()
                    toast_banner = "Audio Muted" if muted else "Audio Active"
                    toast_time = time.time()
                elif key == ord("x"):
                    out_cancel = guidance_sm.cancel(now=time.time())
                    if out_cancel.speech:
                        speech.say(out_cancel.speech)
                        toast_banner = out_cancel.speech
                        toast_time = time.time()
                elif key in FIND_KEYS:
                    target = FIND_KEYS[key]
                    out_start = guidance_sm.start(target, now=time.time())
                    if out_start.speech:
                        speech.say(out_start.speech)
                    toast_banner = f"Finding {target}..."
                    toast_time = time.time()
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
        hand_tracker.close()
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
        "--no-audio",
        action="store_true",
        help="Alias for --mute: disable spoken TTS audio feedback",
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
    parser.add_argument(
        "--target",
        type=str,
        default=None,
        help="Start immediately in Guided Search mode for target (e.g., door, bottle)",
    )
    parser.add_argument(
        "--location",
        type=str,
        default=None,
        help="Override active location key from config/locations.json (e.g., home, cisco_lab, usj_campus)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_pipeline(parse_arguments())
