#!/usr/bin/env python3
"""Fine-tuning pipeline for Nethra Assistive Vision (YOLO11 Nano).

Trains or fine-tunes YOLO11n on custom Doors, Obstacles, and Navigation
datasets using CUDA (Windows/Linux NVIDIA), MPS (Apple Silicon M1-M4), or CPU.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import torch
from ultralytics import YOLO

from services.safety.yolo_ensemble import resolve_model_path


def check_environment() -> str:
    """Verifies GPU acceleration availability across Windows (CUDA), macOS (MPS), and CPU."""
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        print(f"[Hardware] NVIDIA CUDA GPU detected ({gpu_name}): ACTIVE ✅")
        return "0"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        print("[Hardware] Apple Silicon MPS (Metal Performance Shaders) detected: ACTIVE ✅")
        return "mps"
    print("[Hardware] GPU not available, falling back to CPU.")
    return "cpu"


def train_doors_model(
    data_yaml: str,
    base_model: str = "models/yolo11n.pt",
    epochs: int = 30,
    imgsz: int = 640,
    batch_size: int = 16,
    output_name: str = "models/nethra_doors_yolo11n.pt",
) -> None:
    """Executes fine-tuning with transfer learning."""
    yaml_path = Path(data_yaml).resolve()
    if not yaml_path.exists():
        print(f"[Error] Dataset configuration not found at: {yaml_path}")
        print("\nPlease ensure your dataset folder has a data.yaml file.")
        print("Example: datasets/doors/data.yaml")
        sys.exit(1)

    device = check_environment()
    resolved_base = resolve_model_path(base_model)

    print("\n" + "=" * 65)
    print(" Nethra Model Fine-Tuning")
    print(f" - Base Weights:   {resolved_base} (YOLO11 Nano)")
    print(f" - Dataset Config: {yaml_path}")
    print(f" - Epochs:         {epochs}")
    print(f" - Image Size:     {imgsz}")
    print(f" - Batch Size:     {batch_size}")
    print(f" - Compute Device: {device}")
    print("=" * 65 + "\n")

    model = YOLO(str(resolved_base))

    results = model.train(
        data=str(yaml_path),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch_size,
        device=device,
        project="runs/nethra",
        name="doors_nano",
        save=True,
        plots=True,
        verbose=True,
    )

    best_weights = Path(results.save_dir) / "weights" / "best.pt"
    if best_weights.exists():
        dest_path = Path(output_name).resolve()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(best_weights, dest_path)
        print("\n" + "=" * 65)
        print(" Fine-Tuning Completed Successfully! 🎉")
        print(f" - Trained Model Saved: {dest_path}")
        print(" - You can now run this model in Nethra using:")
        print(f"   python main.py --doors-model {output_name}")
        print("=" * 65 + "\n")
    else:
        print(f"[Warning] Training completed, but best.pt was not found in: {results.save_dir}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune Nethra YOLO11 Nano on Door & Obstacle Datasets")
    parser.add_argument(
        "--data",
        type=str,
        default="datasets/doors/data.yaml",
        help="Path to dataset data.yaml file (default: datasets/doors/data.yaml)",
    )
    parser.add_argument(
        "--base-model",
        type=str,
        default="models/yolo11n.pt",
        help="Base YOLO11n model path (default: models/yolo11n.pt)",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=30,
        help="Number of training epochs (default: 30)",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=16,
        help="Batch size (default: 16)",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="Input image resolution (default: 640)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="models/nethra_doors_yolo11n.pt",
        help="Filename for the fine-tuned output weights (default: models/nethra_doors_yolo11n.pt)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    train_doors_model(
        data_yaml=args.data,
        base_model=args.base_model,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch_size=args.batch,
        output_name=args.output,
    )


if __name__ == "__main__":
    main()
