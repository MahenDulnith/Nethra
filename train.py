#!/usr/bin/env python3
"""Root CLI entry point for Nethra YOLO11 Nano fine-tuning (`python train.py`)."""

from training.train_yolo import check_environment, main, parse_arguments, train_doors_model

__all__ = ["check_environment", "train_doors_model", "parse_arguments", "main"]

if __name__ == "__main__":
    main()
