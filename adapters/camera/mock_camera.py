"""L1 Synthetic Mock Camera Generator for hardware-free testing."""

from __future__ import annotations

import cv2
import numpy as np


def create_mock_frame(width: int = 640, height: int = 480, frame_count: int = 0) -> np.ndarray:
    """Generates synthetic corridor frames with an oscillating obstacle for headless/mock testing."""
    frame = np.full((height, width, 3), 35, dtype=np.uint8)

    pts = np.array(
        [
            [width * 0.3, height],
            [width * 0.45, height * 0.4],
            [width * 0.55, height * 0.4],
            [width * 0.7, height],
        ],
        np.int32,
    )
    cv2.fillPoly(frame, [pts], (65, 65, 65))

    cycle = (frame_count % 150) / 150.0
    x_pos = int(width * 0.15 + (width * 0.7 * cycle))
    y_pos = int(height * 0.5)
    box_size = int(60 + 50 * np.sin(cycle * np.pi))

    cv2.rectangle(
        frame,
        (x_pos - box_size // 2, y_pos - box_size // 2),
        (x_pos + box_size // 2, y_pos + box_size // 2),
        (0, 180, 255),
        -1,
    )
    cv2.putText(
        frame,
        "Obstacle (Simulated)",
        (x_pos - box_size // 2, y_pos - box_size // 2 - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
    )

    return frame
