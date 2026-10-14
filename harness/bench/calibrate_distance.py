#!/usr/bin/env python3
"""Distance Calibration Harness — Empirically measures bounding box area ratios at 1m, 2m, 3m.

Replaces starting-point guesses in config/thresholds.yaml with measured real-world data.
Supports both interactive camera capture and automated synthetic/recorded frame benchmarks.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import yaml

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.camera.factory import CameraFactory
from services.safety.yolo_ensemble import YoloEnsembleDetector


def collect_samples_for_distance(
    camera,
    detector: YoloEnsembleDetector,
    target_class: str,
    distance_label: str,
    num_samples: int = 30,
    conf: float = 0.35,
    interactive: bool = True,
) -> Tuple[List[float], List[float]]:
    """Captures N frames with an object at a known distance and extracts box height & area ratios."""
    if interactive:
        print(f"\n[Calibration] Position a '{target_class}' at {distance_label} from the camera.")
        input(" -> Press [ENTER] when ready to start sampling...")

    height_ratios: List[float] = []
    area_ratios: List[float] = []
    collected = 0
    attempts = 0
    max_attempts = num_samples * 5

    print(f"[Calibration] Sampling {num_samples} frames for {distance_label}...")

    while collected < num_samples and attempts < max_attempts:
        attempts += 1
        ret, frame, _ = camera.read()
        if not ret or frame is None:
            time.sleep(0.01)
            continue

        fh, fw = frame.shape[:2]
        boxes, scores, labels = detector.detect(frame, conf=conf)

        matched_boxes = [
            b for b, l in zip(boxes, labels)
            if target_class.lower() in l.lower() or l.lower() in target_class.lower()
        ]

        if not matched_boxes and target_class != "any":
            time.sleep(0.02)
            continue

        target_box = matched_boxes[0] if matched_boxes else (boxes[0] if boxes else None)
        if target_box is None:
            time.sleep(0.02)
            continue

        x1, y1, x2, y2 = target_box
        bw = max(0, x2 - x1)
        bh = max(0, y2 - y1)

        h_ratio = float(bh) / float(fh)
        a_ratio = float(bw * bh) / float(fw * fh)

        height_ratios.append(h_ratio)
        area_ratios.append(a_ratio)
        collected += 1
        time.sleep(0.03)

    if not area_ratios:
        print(f"[Calibration] Warning: No '{target_class}' detected for {distance_label}.")
        return [], []

    return height_ratios, area_ratios


def run_calibration(
    camera_profile: str = "synthetic_mock",
    camera_url: str = "",
    target_class: str = "person",
    num_samples: int = 30,
    conf: float = 0.35,
    interactive: bool = False,
    apply_config: bool = False,
) -> Dict[str, float]:
    """Runs distance calibration across 1m, 2m, and 3m intervals."""
    print("\n" + "=" * 65)
    print(" Nethra Distance & Bounding-Box Ratio Calibration Harness")
    print("=" * 65)
    print(f" - Target Object Class: {target_class}")
    print(f" - Camera Profile:       {camera_profile}")
    print(f" - Samples per distance: {num_samples}")
    print("=" * 65)

    cli_overrides = {"stream_url": camera_url} if camera_url else None
    camera = CameraFactory.create(profile_name=camera_profile, cli_overrides=cli_overrides)
    if not camera.start():
        print(f"[Calibration] Error: Could not start camera {camera.name}")
        sys.exit(1)

    detector = YoloEnsembleDetector()

    distances = [
        ("1.0m (Immediate / Critical Threshold)", "1.0m"),
        ("2.0m (Near / Advisory Threshold)", "2.0m"),
        ("3.0m (Mid / Social Threshold)", "3.0m"),
    ]

    measured_ratios: Dict[str, float] = {}

    try:
        for full_label, short_dist in distances:
            h_ratios, a_ratios = collect_samples_for_distance(
                camera=camera,
                detector=detector,
                target_class=target_class,
                distance_label=full_label,
                num_samples=num_samples,
                conf=conf,
                interactive=interactive,
            )

            if a_ratios:
                median_area = float(np.median(a_ratios))
                median_height = float(np.median(h_ratios))
                measured_ratios[short_dist] = median_area
                print(
                    f" -> {short_dist}: Median Area Ratio = {median_area:.4f} "
                    f"({median_area * 100:.1f}% frame area), Height Ratio = {median_height:.4f}"
                )
            else:
                # Fallback to realistic perspective geometric scaling if unmeasured
                defaults = {"1.0m": 0.45, "2.0m": 0.22, "3.0m": 0.08}
                measured_ratios[short_dist] = defaults[short_dist]
                print(f" -> {short_dist}: Fallback default = {defaults[short_dist]:.4f}")

    finally:
        camera.release()

    imm_ratio = round(measured_ratios.get("1.0m", 0.45), 3)
    near_ratio = round(measured_ratios.get("2.0m", 0.22), 3)
    mid_ratio = round(measured_ratios.get("3.0m", 0.08), 3)

    print("\n" + "=" * 65)
    print(" Recommended Calibrated Thresholds for config/thresholds.yaml:")
    print("=" * 65)
    print(f"  immediate_ratio: {imm_ratio:<6} # ~1.0m boundary")
    print(f"  near_ratio:      {near_ratio:<6} # ~2.0m boundary")
    print(f"  mid_ratio:       {mid_ratio:<6} # ~3.0m boundary")
    print("=" * 65 + "\n")

    if apply_config:
        update_thresholds_yaml(imm_ratio, near_ratio, mid_ratio)

    return {
        "immediate_ratio": imm_ratio,
        "near_ratio": near_ratio,
        "mid_ratio": mid_ratio,
    }


def update_thresholds_yaml(imm: float, near: float, mid: float, path: str = "config/thresholds.yaml") -> None:
    """Updates config/thresholds.yaml with calibrated values."""
    yaml_path = Path(path)
    if not yaml_path.exists():
        print(f"[Calibration] Warning: {path} not found.")
        return

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

        if "safety" in cfg and "buckets" in cfg["safety"]:
            cfg["safety"]["buckets"]["immediate_ratio"] = imm
            cfg["safety"]["buckets"]["near_ratio"] = near
            cfg["safety"]["buckets"]["mid_ratio"] = mid

            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
            print(f"[Calibration] Successfully updated {path} with calibrated values! ✅")
    except Exception as exc:
        print(f"[Calibration] Could not update {path}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Nethra Distance Calibration Harness")
    parser.add_argument("--camera-profile", type=str, default="synthetic_mock", help="Camera profile")
    parser.add_argument("--camera-url", type=str, default="", help="Camera stream URL")
    parser.add_argument("--target-class", type=str, default="person", help="Target object class (default: person)")
    parser.add_argument("--samples", type=int, default=20, help="Number of frames per distance (default: 20)")
    parser.add_argument("--interactive", action="store_true", help="Prompt user between distance positions")
    parser.add_argument("--apply", action="store_true", help="Apply calibrated values directly to config/thresholds.yaml")
    args = parser.parse_args()

    run_calibration(
        camera_profile=args.camera_profile,
        camera_url=args.camera_url,
        target_class=args.target_class,
        num_samples=args.samples,
        interactive=args.interactive,
        apply_config=args.apply,
    )


if __name__ == "__main__":
    main()
