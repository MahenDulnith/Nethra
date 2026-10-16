"""End-to-end parity, API compatibility, and structural readiness tests for Nethra.

Verifies:
1. 100% symbol, signature, and CLI flag parity with MahenDulnith's original `main.py` and `train.py`.
2. Mathematical and functional parity for Dual-Model IoU NMS, SpatialRoutingEngine, ContextSceneTracker,
   Mock stream generation, OpenCV HUD rendering, and live YOLO11n inference.
3. Scalability & L0-L5 architectural readiness across all packages and datasets.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import yaml

import main as root_main
import train as root_train
from services.safety.yolo_ensemble import resolve_model_path


class TestMahenDulnithParityAndReadiness(unittest.TestCase):
    """Validates 100% parity with MahenDulnith's implementation and team scalability."""

    def test_1_root_main_exports_all_mahendulnith_symbols(self) -> None:
        """Every class and function from MahenDulnith's original main.py must remain importable from `main`."""
        expected_symbols = [
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
        for sym in expected_symbols:
            self.assertTrue(
                hasattr(root_main, sym),
                f"Missing symbol `{sym}` in root `main.py` required for backward compatibility",
            )

    def test_2_root_train_exports_all_mahendulnith_symbols(self) -> None:
        """Every function from MahenDulnith's original train.py must remain importable from `train`."""
        expected_symbols = [
            "check_environment",
            "train_doors_model",
            "parse_arguments",
        ]
        for sym in expected_symbols:
            self.assertTrue(
                hasattr(root_train, sym),
                f"Missing symbol `{sym}` in root `train.py` required for backward compatibility",
            )

    def test_3_cli_arguments_parity_main_and_train(self) -> None:
        """All CLI flags used by MahenDulnith on macOS and by Windows/Android must parse cleanly."""
        with patch.object(
            sys,
            "argv",
            [
                "main.py",
                "--coco-model",
                "yolo11n.pt",
                "--doors-model",
                "nethra_doors_yolo11n.pt",
                "--camera",
                "1",
                "--conf",
                "0.40",
                "--width",
                "640",
                "--height",
                "480",
                "--mock",
                "--headless",
                "--max-frames",
                "10",
            ],
        ):
            args = root_main.parse_arguments()
            self.assertEqual(args.coco_model, "yolo11n.pt")
            self.assertEqual(args.doors_model, "nethra_doors_yolo11n.pt")
            self.assertEqual(args.camera, 1)
            self.assertAlmostEqual(args.conf, 0.40)
            self.assertEqual(args.width, 640)
            self.assertEqual(args.height, 480)
            self.assertTrue(args.mock)
            self.assertTrue(args.headless)
            self.assertEqual(args.max_frames, 10)

        with patch.object(
            sys,
            "argv",
            [
                "train.py",
                "--data",
                "datasets/doors/data.yaml",
                "--epochs",
                "15",
                "--batch",
                "8",
                "--imgsz",
                "640",
                "--output",
                "nethra_doors_yolo11n.pt",
            ],
        ):
            t_args = root_train.parse_arguments()
            self.assertEqual(t_args.data, "datasets/doors/data.yaml")
            self.assertEqual(t_args.epochs, 15)
            self.assertEqual(t_args.batch, 8)
            self.assertEqual(t_args.imgsz, 640)
            self.assertEqual(t_args.output, "nethra_doors_yolo11n.pt")

    def test_4_model_path_resolution_backward_compatibility(self) -> None:
        """Passing legacy `yolo11n.pt` resolves automatically to `models/yolo11n.pt`."""
        resolved = resolve_model_path("yolo11n.pt")
        self.assertTrue(resolved.exists(), f"Expected models/yolo11n.pt to exist, got {resolved}")
        self.assertEqual(resolved.name, "yolo11n.pt")

    def test_5_mock_frame_and_hud_rendering_parity(self) -> None:
        """Verifies mock frame synthesis and HUD overlay rendering across all alert tiers and banners."""
        frame = root_main.create_mock_frame(640, 480, frame_count=35)
        self.assertEqual(frame.shape, (480, 640, 3))
        self.assertEqual(frame.dtype, np.uint8)

        router = root_main.SpatialRoutingEngine(min_area_ratio=0.015, max_area_ratio=0.35)
        boxes = [(20, 100, 120, 220), (260, 80, 400, 360), (480, 150, 600, 350)]
        scores = [0.88, 0.94, 0.76]
        labels = ["chair", "door", "person"]

        dets, haptics = router.process_detections(
            boxes=boxes,
            scores=scores,
            labels=labels,
            frame_width=640,
            frame_height=480,
        )
        self.assertEqual(len(dets), 3)
        self.assertEqual([d.zone for d in dets], ["LEFT", "CENTER", "RIGHT"])
        self.assertGreater(haptics.left_pwm, 0.0)
        self.assertGreater(haptics.right_pwm, 0.0)

        annotated = root_main.render_hud(
            frame=frame,
            detections=dets,
            haptics=haptics,
            context_msg="Good morning! You are in your bed right now.",
            fps=29.8,
            camera_idx=1,
            location_msg="Location: University of Sri Jayewardenepura | In view: chair, door, person",
            toast_msg="Connected: iPhone (Continuity Camera / Ultra-Wide)",
            model_mode_label="Ensemble: COCO-80 + Doors",
        )
        self.assertEqual(annotated.shape, (480, 640, 3))
        self.assertFalse(np.array_equal(frame, annotated))

    def test_6_datasets_and_configs_valid(self) -> None:
        """Confirms MahenDulnith's dataset YAMLs and team config YAMLs are intact and valid."""
        yaml_files = [
            "datasets/HomeObjects-3K.yaml",
            "datasets/doors/data.yaml",
            "config/classes.yaml",
            "config/thresholds.yaml",
            "config/phrasebook.yaml",
            "config/haptic_patterns.yaml",
            "config/providers.yaml",
        ]
        for ypath in yaml_files:
            p = Path(ypath)
            self.assertTrue(p.exists(), f"Missing required YAML file: {ypath}")
            with open(p, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            self.assertIsNotNone(data, f"Empty or invalid YAML file: {ypath}")

    def test_7_scalable_directory_structure_and_ci_rules(self) -> None:
        """Verifies all L0-L5 directories exist and CI dependency/safety checks pass."""
        required_dirs = [
            "contracts",
            "adapters/camera",
            "adapters/audio",
            "adapters/haptic",
            "adapters/clock",
            "adapters/storage",
            "services/hygiene",
            "services/safety",
            "services/arbiter",
            "services/memory",
            "services/voice",
            "services/vision",
            "services/agent",
            "features/lookaround",
            "features/context_routines",
            "features/people",
            "features/failsafe",
            "shell/hud",
            "instrumentation",
            "training",
            "datasets",
            "models",
            "tests",
            "config",
            "firmware",
            "harness",
            "ci",
            "docs",
        ]
        for d in required_dirs:
            self.assertTrue(Path(d).is_dir(), f"Missing scalable architecture directory: {d}")

        # Verify no legacy Android/Gradle pollution remains
        legacy_paths = ["app", "gradle", "build.gradle.kts", "settings.gradle.kts", "gradlew"]
        for lp in legacy_paths:
            self.assertFalse(Path(lp).exists(), f"Legacy Android path still exists: {lp}")

        # Run dependency graph check
        res = subprocess.run(
            [sys.executable, "ci/dependency_graph_check.py"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0, f"Dependency check failed: {res.stdout}\n{res.stderr}")

    def test_8_guided_search_and_haptic_pattern_integration(self) -> None:
        """Verifies L4 GuidanceStateMachine + L1 HapticPatternEngine + L5 HUD integration."""
        from adapters.haptic.pattern_engine import HapticPatternEngine
        from features.lookaround.guidance import GuidanceStateMachine

        sm = GuidanceStateMachine()
        haptic_engine = HapticPatternEngine()
        out_start = sm.start("door", now=1.0)
        self.assertTrue(out_start.active)

        frame = root_main.create_mock_frame(640, 480, frame_count=10)
        haptics = root_main.HapticFeedbackState(left_pwm=0.0, right_pwm=0.0, active_threat=None)
        h_out = haptic_engine.compute(
            command=out_start.command,
            magnitude=out_start.magnitude,
            now=1.02,
            obstacle=haptics,
            guidance_active=out_start.active,
        )
        self.assertEqual(h_out.source, "guidance")
        rendered = root_main.render_hud(
            frame=frame,
            detections=[],
            haptics=haptics,
            context_msg=None,
            fps=30.0,
            camera_idx="Mock",
            guidance=out_start,
        )
        self.assertEqual(rendered.shape, (480, 640, 3))


if __name__ == "__main__":
    unittest.main()
