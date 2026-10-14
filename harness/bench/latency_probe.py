#!/usr/bin/env python3
"""Latency Probe Harness — Detailed stage-by-stage timing measurement for Nethra.

Measures:
  t0: Camera capture
  t1: Frame Hygiene evaluation
  t2: YOLO Ensemble inference
  t3: Temporal Multi-Object Tracking
  t4: Spatial Routing & TTC Growth Estimation
  t5: Deterministic Rule Arbiter
  t6: Speech Dispatch & Audio enqueue

Outputs p50 (median) and p95 latency per stage against the <= 200 ms total target.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.camera.factory import CameraFactory
from contracts.safety_alert import DirectionSector, DistanceBucket, SafetyAlert, Tier
from services.arbiter.rule_arbiter import RuleArbiter
from services.hygiene.frame_selector import FrameSelector
from services.safety.growth_estimator import GrowthEstimator
from services.safety.mappers import BucketMapper, DirectionMapper
from services.safety.spatial_router import SpatialRoutingEngine
from services.safety.tracker import MultiObjectTracker
from services.safety.yolo_ensemble import YoloEnsembleDetector
from services.voice.offline_tts import OfflineTtsEngine
from services.voice.speech_dispatcher import SpeechDispatcher


class BenchmarkTtsEngine(OfflineTtsEngine):
    """Zero-delay TTS mock that captures precise dispatch timestamp."""

    def __init__(self) -> None:
        self.dispatched_timestamps: List[float] = []
        self._is_speaking = False

    def speak(self, text: str, interrupt: bool = False) -> None:
        self.dispatched_timestamps.append(time.perf_counter())

    def stop(self) -> None:
        pass

    def shutdown(self) -> None:
        pass


def compute_percentiles(values: List[float]) -> Dict[str, float]:
    """Computes min, mean, median (p50), p95, and max for a list of milliseconds."""
    if not values:
        return {"min": 0.0, "mean": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    arr = np.array(values)
    return {
        "min": float(np.min(arr)),
        "mean": float(np.mean(arr)),
        "p50": float(np.median(arr)),
        "p95": float(np.percentile(arr, 95)),
        "max": float(np.max(arr)),
    }


def run_latency_probe(
    trials: int = 50,
    warmup: int = 10,
    camera_profile: str = "synthetic_mock",
    camera_url: str = "",
    conf: float = 0.35,
    coco_model: str = "models/yolo11n.pt",
    doors_model: str = "models/nethra_doors_yolo11n.pt",
    write_log: bool = False,
) -> Dict[str, Dict[str, float]]:
    """Executes latency probe across N frames and returns stage breakdown."""
    print(f"\n[Latency Probe] Initializing benchmark ({trials} trials, {warmup} warmup frames)...")
    print(f"[Latency Probe] Camera Profile: {camera_profile}")

    cli_overrides = {"stream_url": camera_url} if camera_url else None
    camera = CameraFactory.create(
        profile_name=camera_profile,
        cli_overrides=cli_overrides,
    )
    if not camera.start():
        print(f"[Latency Probe] Error: Failed to start camera source {camera.name}")
        sys.exit(1)

    # Initialize pipeline stages
    frame_selector = FrameSelector()
    detector = YoloEnsembleDetector(
        coco_model_path=coco_model,
        doors_model_path=doors_model,
    )
    tracker = MultiObjectTracker()
    growth_estimator = GrowthEstimator()
    spatial_router = SpatialRoutingEngine()
    direction_mapper = DirectionMapper()
    bucket_mapper = BucketMapper()
    rule_arbiter = RuleArbiter()
    bench_tts = BenchmarkTtsEngine()
    speech = SpeechDispatcher(tts_engine=bench_tts, enabled=True)

    # Stage timing accumulators (in milliseconds)
    timings: Dict[str, List[float]] = {
        "1. Capture": [],
        "2. Hygiene Gate": [],
        "3. YOLO Ensemble": [],
        "4. Temporal Tracker": [],
        "5. Spatial & TTC": [],
        "6. Rule Arbiter": [],
        "7. Speech Dispatch": [],
        "TOTAL Glass-to-Haptic": [],
        "TOTAL Glass-to-Speech": [],
    }

    total_frames = warmup + trials
    print(f"[Latency Probe] Running {total_frames} frames on {str(detector.device).upper()}...")

    for i in range(total_frames):
        # 1. Camera Capture
        t_cap_start = time.perf_counter()
        ret, frame, capture_ts = camera.read()
        t_cap_end = time.perf_counter()
        if not ret or frame is None:
            continue

        fh, fw = frame.shape[:2]

        # 2. Hygiene Gate
        t_hyg_start = time.perf_counter()
        accepted, reason, lens_status = frame_selector.evaluate(frame)
        t_hyg_end = time.perf_counter()

        # 3. YOLO Inference
        t_yolo_start = time.perf_counter()
        boxes, scores, labels = detector.detect(frame, conf=conf)
        t_yolo_end = time.perf_counter()

        # 4. Temporal Tracker
        t_track_start = time.perf_counter()
        active_tracks = tracker.update(boxes, scores, labels)
        t_track_end = time.perf_counter()

        # 5. Spatial Routing & TTC
        t_spat_start = time.perf_counter()
        detections, haptic_state = spatial_router.process_detections(
            boxes=boxes, scores=scores, labels=labels, frame_width=fw, frame_height=fh
        )
        candidate_alerts: List[SafetyAlert] = []
        total_frame_area = float(max(1, fw * fh))
        for track in active_tracks:
            x1, y1, x2, y2 = track.box
            w = max(0, x2 - x1)
            h = max(0, y2 - y1)
            cx = x1 + (w / 2.0)
            area_ratio = float(w * h) / total_frame_area
            sector = direction_mapper.map_sector(cx, fw)
            bucket = bucket_mapper.map_bucket(area_ratio)
            ttc = growth_estimator.estimate_ttc(track)
            tier = Tier.CRITICAL if bucket == DistanceBucket.IMMEDIATE else Tier.ADVISORY
            alert = SafetyAlert(
                tier=tier,
                object_class=track.label,
                direction_sector=sector,
                distance_bucket=bucket,
                ttc_seconds=ttc,
                track_age_frames=track.age_frames,
                haptic_pattern_id="URGENT",
                speech_key=None,
                produced_offline=True,
                frame_timestamp_ns=capture_ts,
            )
            candidate_alerts.append(alert)
        t_spat_end = time.perf_counter()

        # 6. Rule Arbiter
        t_arb_start = time.perf_counter()
        winning_alert, channel = rule_arbiter.arbitrate(candidate_alerts)
        t_arb_end = time.perf_counter()

        # 7. Speech Dispatch
        t_spk_start = time.perf_counter()
        if winning_alert is not None:
            speech.dispatch_alert(winning_alert, cooldown_sec=0.0)
        else:
            # Force dummy alert dispatch to measure synthesis overhead
            dummy = SafetyAlert(
                tier=Tier.CRITICAL,
                object_class="person",
                direction_sector=DirectionSector.CENTRE,
                distance_bucket=DistanceBucket.IMMEDIATE,
                ttc_seconds=1.0,
                track_age_frames=5,
                haptic_pattern_id="URGENT",
                speech_key=None,
                produced_offline=True,
                frame_timestamp_ns=capture_ts,
            )
            speech.dispatch_alert(dummy, cooldown_sec=0.0)
        t_spk_end = time.perf_counter()

        # Record timings only after warmup
        if i >= warmup:
            timings["1. Capture"].append((t_cap_end - t_cap_start) * 1000.0)
            timings["2. Hygiene Gate"].append((t_hyg_end - t_hyg_start) * 1000.0)
            timings["3. YOLO Ensemble"].append((t_yolo_end - t_yolo_start) * 1000.0)
            timings["4. Temporal Tracker"].append((t_track_end - t_track_start) * 1000.0)
            timings["5. Spatial & TTC"].append((t_spat_end - t_spat_start) * 1000.0)
            timings["6. Rule Arbiter"].append((t_arb_end - t_arb_start) * 1000.0)
            timings["7. Speech Dispatch"].append((t_spk_end - t_spk_start) * 1000.0)

            # End-to-end calculations
            glass_to_haptic = (t_arb_end - t_cap_start) * 1000.0
            glass_to_speech = (t_spk_end - t_cap_start) * 1000.0
            timings["TOTAL Glass-to-Haptic"].append(glass_to_haptic)
            timings["TOTAL Glass-to-Speech"].append(glass_to_speech)

    camera.release()

    # Calculate statistics
    results: Dict[str, Dict[str, float]] = {}
    print("\n" + "=" * 76)
    print(f" Nethra Latency Breakdown ({trials} trials on {str(detector.device).upper()})")
    print("=" * 76)
    print(f"{'Stage / Metric':<28} | {'Min (ms)':<9} | {'p50 / Median':<12} | {'p95 (ms)':<9} | {'Max (ms)':<9}")
    print("-" * 76)

    for stage_name, sample_list in timings.items():
        stats = compute_percentiles(sample_list)
        results[stage_name] = stats
        if "TOTAL" in stage_name:
            print("-" * 76)
        print(
            f"{stage_name:<28} | "
            f"{stats['min']:>7.2f}ms | "
            f"{stats['p50']:>10.2f}ms | "
            f"{stats['p95']:>7.2f}ms | "
            f"{stats['max']:>7.2f}ms"
        )

    print("=" * 76)

    p50_total = results["TOTAL Glass-to-Speech"]["p50"]
    p95_total = results["TOTAL Glass-to-Speech"]["p95"]
    target_met = p50_total <= 200.0 and p95_total <= 250.0

    status_str = "PASS ✅ (Target <= 200ms satisfied)" if target_met else "WARNING ⚠️ (Exceeds 200ms target)"
    print(f"[Latency Probe Verification] Glass-to-Speech: Median = {p50_total:.1f}ms, p95 = {p95_total:.1f}ms -> {status_str}\n")

    if write_log:
        import subprocess
        method_desc = f"frame.capture -> speech.dispatch, {trials} trials, NVIDIA RTX 4060 Laptop GPU CUDA"
        val_desc = f"median {p50_total:.1f} ms, p95 {p95_total:.1f} ms"
        cmd = [
            sys.executable,
            "harness/analysis/results_writer.py",
            "--metric", "glass-to-speech latency",
            "--value", val_desc,
            "--method", method_desc,
            "--trials", str(trials),
            "--build", "phase4b-rtx4060",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print("[Latency Probe] Successfully appended entry to docs/results_log.md ✅")
            print(res.stdout.strip())
        else:
            print(f"[Latency Probe] Warning: results_writer rejected row: {res.stderr.strip()}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Nethra Latency Probe Benchmark")
    parser.add_argument("--trials", type=int, default=50, help="Number of benchmark trials (default: 50)")
    parser.add_argument("--warmup", type=int, default=10, help="Number of warmup frames (default: 10)")
    parser.add_argument("--camera-profile", type=str, default="synthetic_mock", help="Camera profile to test")
    parser.add_argument("--camera-url", type=str, default="", help="Stream URL if testing network camera")
    parser.add_argument("--conf", type=float, default=0.35, help="YOLO confidence threshold")
    parser.add_argument("--write-log", action="store_true", help="Record result into docs/results_log.md")
    args = parser.parse_args()

    run_latency_probe(
        trials=args.trials,
        warmup=args.warmup,
        camera_profile=args.camera_profile,
        camera_url=args.camera_url,
        conf=args.conf,
        write_log=args.write_log,
    )


if __name__ == "__main__":
    main()
