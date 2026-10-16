"""L2 Hand tracking with MediaPipe: returns the index-fingertip position in pixel coordinates.

Supports both the legacy `mp.solutions.hands` API and the newer Tasks `HandLandmarker` API
(which needs the `hand_landmarker.task` model file, downloaded once into ./models).
"""

from __future__ import annotations

import time
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

Point = Tuple[float, float]

INDEX_FINGER_TIP = 8
MIDDLE_FINGER_MCP = 9  # palm centre fallback
TASK_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)
TASK_MODEL_PATH = Path("models/hand_landmarker.task")


class HandTracker:
    def __init__(self, min_confidence: float = 0.5) -> None:
        self.backend = "none"
        self._hands = None
        self._landmarker = None
        self._mp = None
        try:
            import mediapipe as mp

            self._mp = mp
        except Exception as exc:  # noqa: BLE001
            print(f"[Hand] MediaPipe unavailable ({exc}); hand guidance disabled, head guidance only.")
            return

        solutions = getattr(self._mp, "solutions", None)
        if solutions is not None and hasattr(solutions, "hands"):
            self._hands = solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=min_confidence,
                min_tracking_confidence=min_confidence,
            )
            self.backend = "mediapipe-solutions"
        else:
            self._init_tasks(min_confidence)
        print(f"[Hand] Hand tracker backend: {self.backend}")

    def _init_tasks(self, min_confidence: float) -> None:
        try:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision

            if not TASK_MODEL_PATH.exists():
                TASK_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
                print(f"[Hand] Downloading hand model to {TASK_MODEL_PATH}...")
                req = urllib.request.Request(TASK_MODEL_URL, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req) as resp, open(TASK_MODEL_PATH, "wb") as f:
                    f.write(resp.read())
            options = vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(TASK_MODEL_PATH)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=min_confidence,
                min_tracking_confidence=min_confidence,
            )
            self._landmarker = vision.HandLandmarker.create_from_options(options)
            self._t0 = time.monotonic()
            self._last_ts = -1
            self.backend = "mediapipe-tasks"
        except Exception as exc:  # noqa: BLE001
            print(f"[Hand] Could not initialise MediaPipe Tasks hand landmarker: {exc}")

    @property
    def available(self) -> bool:
        return self.backend != "none"

    def detect(self, frame_bgr: np.ndarray) -> Optional[Point]:
        """Returns the index fingertip (x, y) in pixels, or None if no hand is visible."""
        if not self.available:
            return None
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        landmarks = None
        if self._hands is not None:
            result = self._hands.process(rgb)
            if result.multi_hand_landmarks:
                landmarks = result.multi_hand_landmarks[0].landmark
        elif self._landmarker is not None:
            ts = int((time.monotonic() - self._t0) * 1000)
            ts = max(ts, self._last_ts + 1)  # VIDEO mode needs strictly increasing timestamps
            self._last_ts = ts
            image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
            result = self._landmarker.detect_for_video(image, ts)
            if result.hand_landmarks:
                landmarks = result.hand_landmarks[0]

        if not landmarks:
            return None
        tip = landmarks[INDEX_FINGER_TIP]
        if not (0.0 <= tip.x <= 1.0 and 0.0 <= tip.y <= 1.0):
            tip = landmarks[MIDDLE_FINGER_MCP]
        return (float(tip.x * w), float(tip.y * h))

    def close(self) -> None:
        if self._hands is not None:
            self._hands.close()
        if self._landmarker is not None:
            self._landmarker.close()
