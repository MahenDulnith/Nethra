#!/usr/bin/env python3
"""Fine-tuning pipeline for PulsePath Assistive Vision (YOLO11 Nano).

Trains or fine-tunes YOLO11n on custom Doors, Obstacles, and Navigation
datasets using Apple Silicon M4 GPU acceleration (MPS).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

import torch
from ultralytics import YOLO


def check_environment() -> str:
    """Verifies GPU acceleration availability on Apple Silicon."""
    if torch.backends.mps.is_available():
        print("[Hardware] Apple Silicon MPS (Metal Performance Shaders) detected: ACTIVE ✅")
        return "mps"
    print("[Hardware] MPS not available, falling back to CPU.")
    return "cpu"


def train_doors_model(
    data_yaml: str,
    base_model: str = "yolo11n.pt",
    epochs: int = 30,
    imgsz: int = 640,
    batch_size: int = 16,
    output_name: str = "pulsepath_doors_yolo11n.pt",
):
    """Executes fine-tuning with transfer learning."""
    yaml_path = Path(data_yaml).resolve()
    if not yaml_path.exists():
        print(f"[Error] Dataset configuration not found at: {yaml_path}")
        print("\nPlease ensure your dataset folder has a data.yaml file.")
        print("Example: datasets/doors/data.yaml")
        sys.exit(1)

    device = check_environment()

    print("\n" + "=" * 65)
    print(" PulsePath Model Fine-Tuning")
    print(f" - Base Weights:  {base_model} (YOLO11 Nano)")
    print(f" - Dataset Config: {yaml_path}")
    print(f" - Epochs:        {epochs}")
    print(f" - Image Size:    {imgsz}")
    print(f" - Batch Size:    {batch_size}")
    print(f" - Compute Device:{device}")
    print("=" * 65 + "\n")

    # Load base YOLO11n model
    model = YOLO(base_model)

    # Train on dataset
    results = model.train(
        data=str(yaml_path),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch_size,
        device=device,
        project="runs/pulsepath",
        name="doors_nano",
        save=True,
        plots=True,
        verbose=True,
    )

    # Locate best trained weights
    best_weights = Path(results.save_dir) / "weights" / "best.pt"
    if best_weights.exists():
        dest_path = Path(output_name).resolve()
        shutil.copy(best_weights, dest_path)
        print("\n" + "=" * 65)
        print(" Fine-Tuning Completed Successfully! 🎉")
        print(f" - Trained Model Saved: {dest_path}")
        print(" - You can now run this model in PulsePath using:")
        print(f"   .venv/bin/python main.py --model {output_name}")
        print("=" * 65 + "\n")
    else:
        print(f"[Warning] Training completed, but best.pt was not found in: {results.save_dir}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune YOLO11 Nano on Door & Obstacle Datasets")
    parser.add_argument(
        "--data",
        type=str,
        default="datasets/doors/data.yaml",
        help="Path to dataset data.yaml file (default: datasets/doors/data.yaml)",
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
        default="pulsepath_doors_yolo11n.pt",
        help="Filename for the fine-tuned output weights (default: pulsepath_doors_yolo11n.pt)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    train_doors_model(
        data_yaml=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch_size=args.batch,
        output_name=args.output,
    )
