"""L2 Spatial Haptic Routing Engine — Maps bounding boxes to Left/Right wristband PWM."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from contracts.detection import Detection
from contracts.haptic_command import HapticFeedbackState


class SpatialRoutingEngine:
    """Divides the field of view into spatial zones and calculates haptic intensity."""

    def __init__(
        self,
        min_area_ratio: float = 0.02,
        max_area_ratio: float = 0.35,
        fov_area_scale: float = 1.0,
    ) -> None:
        self.min_area_ratio = min_area_ratio
        self.max_area_ratio = max_area_ratio
        self.fov_area_scale = fov_area_scale

    def calculate_pwm(self, area_ratio: float) -> float:
        """Maps bounding box area ratio to motor PWM duty cycle (0.0% - 100.0%)."""
        scaled_ratio = area_ratio * self.fov_area_scale
        if scaled_ratio <= self.min_area_ratio:
            return 0.0
        if scaled_ratio >= self.max_area_ratio:
            return 100.0
        intensity = (
            (scaled_ratio - self.min_area_ratio)
            / (self.max_area_ratio - self.min_area_ratio)
        ) * 100.0
        return round(float(np.clip(intensity, 0.0, 100.0)), 1)

    def determine_zone(self, center_x: float, frame_width: int) -> str:
        """Determines the horizontal zone (LEFT, CENTER, RIGHT) for a given x-coordinate."""
        one_third = frame_width / 3.0
        two_thirds = (frame_width * 2.0) / 3.0

        if center_x < one_third:
            return "LEFT"
        elif center_x > two_thirds:
            return "RIGHT"
        else:
            return "CENTER"

    def process_detections(
        self,
        boxes: List[Tuple[int, int, int, int]],
        scores: List[float],
        labels: Optional[List[str]] = None,
        class_ids: Optional[List[int]] = None,
        class_names: Optional[Dict[int, str]] = None,
        frame_width: int = 640,
        frame_height: int = 480,
    ) -> Tuple[List[Detection], HapticFeedbackState]:
        """Processes raw model detections into spatial cues and dual wristband PWM signals.

        Also supports the legacy positional signature `(boxes, scores, class_ids, class_names, frame_width, frame_height)`.
        """
        # Handle legacy positional call where `labels` receives `class_ids` (List[int])
        # and `class_ids` receives `class_names` (Dict[int, str])
        if (
            labels is not None
            and len(labels) > 0
            and isinstance(labels[0], int)
            and isinstance(class_ids, dict)
        ):
            actual_class_ids: List[int] = labels  # type: ignore[assignment]
            actual_class_names: Dict[int, str] = class_ids  # type: ignore[assignment]
            if isinstance(class_names, int):
                frame_height = frame_width
                frame_width = class_names
            resolved_labels = [
                actual_class_names.get(cid, f"obj_{cid}") for cid in actual_class_ids
            ]
        elif labels is not None:
            resolved_labels = [str(lbl) for lbl in labels]
        elif class_ids is not None and class_names is not None:
            resolved_labels = [class_names.get(cid, f"obj_{cid}") for cid in class_ids]
        else:
            resolved_labels = [f"obj_{i}" for i in range(len(boxes))]

        total_frame_area = float(max(1, frame_width * frame_height))
        detections: List[Detection] = []

        max_left_pwm = 0.0
        max_right_pwm = 0.0
        highest_threat_label = None
        max_threat_area = 0.0

        for box, score, label in zip(boxes, scores, resolved_labels):
            x1, y1, x2, y2 = box
            w = max(0, x2 - x1)
            h = max(0, y2 - y1)
            cx = x1 + (w / 2.0)
            cy = y1 + (h / 2.0)

            box_area = float(w * h)
            area_ratio = box_area / total_frame_area
            zone = self.determine_zone(cx, frame_width)
            pwm = self.calculate_pwm(area_ratio)

            det = Detection(
                label=label,
                confidence=float(score),
                box=(int(x1), int(y1), int(x2), int(y2)),
                center_x=cx,
                center_y=cy,
                width=w,
                height=h,
                area_ratio=area_ratio,
                zone=zone,
                pwm_intensity=pwm,
            )
            detections.append(det)

            if zone == "LEFT":
                max_left_pwm = max(max_left_pwm, pwm)
            elif zone == "RIGHT":
                max_right_pwm = max(max_right_pwm, pwm)
            elif zone == "CENTER":
                max_left_pwm = max(max_left_pwm, pwm)
                max_right_pwm = max(max_right_pwm, pwm)

            if area_ratio > max_threat_area and pwm > 0.0:
                max_threat_area = area_ratio
                highest_threat_label = f"{label} ({zone})"

        state = HapticFeedbackState(
            left_pwm=max_left_pwm,
            right_pwm=max_right_pwm,
            active_threat=highest_threat_label,
            closest_distance_ratio=max_threat_area,
        )
        return detections, state
