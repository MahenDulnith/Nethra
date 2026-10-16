"""Object detection: dual-model ensemble, IoU merging and spatial haptic routing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

Box = Tuple[int, int, int, int]  # x1, y1, x2, y2
Candidate = Tuple[Box, float, str]  # box, confidence, label

# Classes from the fine-tuned indoor/doors model that we allow into the ensemble.
# Excluding 'table', 'chair', 'sofa', 'lamp', etc. prevents the small synthetic model
# from overriding COCO-80's real-world furniture detections or mislabeling beds as tables/chairs.
DOORS_MODEL_ALLOWED_CLASSES = {"door", "wardrobe", "window", "bed"}

# Furniture classes that YOLO frequently confuses with extra beds in a multi-bed room
BED_CONFUSABLE_FURNITURE = {"chair", "dining table", "table", "couch", "sofa", "bench"}


@dataclass
class Detection:
    """Represents a single detected object."""
    label: str
    confidence: float
    box: Box
    center_x: float
    center_y: float
    width: float
    height: float
    area_ratio: float
    zone: str  # "LEFT", "CENTER", "RIGHT"
    pwm_intensity: float  # 0.0 to 100.0%


@dataclass
class HapticFeedbackState:
    """Obstacle-avoidance wristband levels computed from detections."""
    left_pwm: float = 0.0   # 0.0 to 100.0%
    right_pwm: float = 0.0  # 0.0 to 100.0%
    active_threat: Optional[str] = None
    closest_distance_ratio: float = 0.0


def compute_iou(box_a: Box, box_b: Box) -> float:
    """Calculates Intersection over Union (IoU) between two bounding boxes."""
    inter_w = max(0, min(box_a[2], box_b[2]) - max(box_a[0], box_b[0]))
    inter_h = max(0, min(box_a[3], box_b[3]) - max(box_a[1], box_b[1]))
    inter_area = float(inter_w * inter_h)

    area_a = float(max(0, box_a[2] - box_a[0]) * max(0, box_a[3] - box_a[1]))
    area_b = float(max(0, box_b[2] - box_b[0]) * max(0, box_b[3] - box_b[1]))
    union_area = area_a + area_b - inter_area
    if union_area <= 0.0:
        return 0.0
    return inter_area / union_area


def box_contains_point(box: Box, point: Tuple[float, float]) -> bool:
    """Returns True if the point lies inside the box."""
    x, y = point
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def merge_candidate_detections(candidates: List[Candidate], iou_thresh: float = 0.45) -> List[Candidate]:
    """Merges detections from multiple models and eliminates duplicate boxes.
    
    Prioritizes 'bed' over confusable furniture labels ('table', 'dining table', 'chair', 'couch')
    when two candidate boxes overlap on the same physical piece of furniture.
    """
    # Sort primarily so 'bed' wins ties against confusable furniture when boxes overlap, then by confidence
    kept: List[Candidate] = []
    for cand in sorted(candidates, key=lambda c: (1 if c[2].lower() == "bed" else 0, c[1]), reverse=True):
        if all(compute_iou(cand[0], k[0]) <= iou_thresh for k in kept):
            kept.append(cand)
    return kept


def disambiguate_multi_bed_candidates(
    strong_candidates: List[Candidate],
    weak_bed_boxes: Sequence[Box],
    frame_width: int,
    frame_height: int,
    bedroom_context_active: bool = False,
) -> List[Candidate]:
    """Recovers 2nd/3rd beds in a room that YOLO misclassifies as 'table', 'dining table', or 'chair'.

    1. If a furniture candidate ('table', 'dining table', 'chair', 'couch', 'bench') overlaps (IoU >= 0.25)
       with any raw 'bed' hypothesis (even lower-confidence ones down to 0.18), relabel it as 'bed'.
    2. If at least one 'bed' is present in the room (or recent frames confirm a bedroom) and another
       furniture candidate ('dining table', 'table', 'couch', 'sofa', 'bench', or a wide/large 'chair')
       has bed-like proportions, relabel it as 'bed'.
    """
    frame_area = float(max(1, frame_width * frame_height))
    has_confirmed_bed = bedroom_context_active or any(c[2].lower() == "bed" for c in strong_candidates) or len(weak_bed_boxes) > 0

    resolved: List[Candidate] = []
    for box, score, label in strong_candidates:
        lbl_low = label.lower()
        if lbl_low in BED_CONFUSABLE_FURNITURE:
            # Check 1: Does this table/chair box overlap with a weak or strong 'bed' hypothesis?
            if any(compute_iou(box, bed_box) >= 0.25 for bed_box in weak_bed_boxes):
                resolved.append((box, score, "bed"))
                has_confirmed_bed = True
                continue

            # Check 2: In a room that already has a bed, check if this 'table'/'chair' has bed geometry
            if has_confirmed_bed:
                w = max(1, box[2] - box[0])
                h = max(1, box[3] - box[1])
                area_ratio = (w * h) / frame_area
                aspect = w / float(h)
                if lbl_low in ("dining table", "table", "couch", "sofa", "bench") and area_ratio >= 0.025:
                    resolved.append((box, score, "bed"))
                    continue
                if lbl_low == "chair" and area_ratio >= 0.030 and aspect >= 0.65:
                    resolved.append((box, score, "bed"))
                    continue

        resolved.append((box, score, label))
    return resolved


class SpatialRoutingEngine:
    """Divides the field of view into spatial zones and calculates haptic intensity."""

    def __init__(self, min_area_ratio: float = 0.02, max_area_ratio: float = 0.35):
        self.min_area_ratio = min_area_ratio
        self.max_area_ratio = max_area_ratio

    def calculate_pwm(self, area_ratio: float) -> float:
        """Maps bounding box area ratio to motor PWM duty cycle (0.0% - 100.0%)."""
        if area_ratio <= self.min_area_ratio:
            return 0.0
        if area_ratio >= self.max_area_ratio:
            return 100.0
        intensity = (area_ratio - self.min_area_ratio) / (self.max_area_ratio - self.min_area_ratio) * 100.0
        return round(float(np.clip(intensity, 0.0, 100.0)), 1)

    def determine_zone(self, center_x: float, frame_width: int) -> str:
        """Determines the horizontal zone for a given x-coordinate."""
        if center_x < frame_width / 3.0:
            return "LEFT"
        if center_x > frame_width * 2.0 / 3.0:
            return "RIGHT"
        return "CENTER"

    def build_detections(
        self,
        boxes: Sequence[Box],
        scores: Sequence[float],
        labels: Sequence[str],
        frame_width: int,
        frame_height: int,
    ) -> List[Detection]:
        """Converts raw boxes into Detection objects with zone and PWM intensity."""
        total_area = float(max(1, frame_width * frame_height))
        detections: List[Detection] = []
        for box, score, label in zip(boxes, scores, labels):
            x1, y1, x2, y2 = (int(v) for v in box)
            w = max(0, x2 - x1)
            h = max(0, y2 - y1)
            cx = x1 + w / 2.0
            area_ratio = (w * h) / total_area
            detections.append(Detection(
                label=str(label),
                confidence=float(score),
                box=(x1, y1, x2, y2),
                center_x=cx,
                center_y=y1 + h / 2.0,
                width=w,
                height=h,
                area_ratio=area_ratio,
                zone=self.determine_zone(cx, frame_width),
                pwm_intensity=self.calculate_pwm(area_ratio),
            ))
        return detections

    @staticmethod
    def compute_state(detections: Sequence[Detection]) -> HapticFeedbackState:
        """Computes obstacle-avoidance wristband levels from a list of detections."""
        left = right = 0.0
        threat_label = None
        max_area = 0.0
        for det in detections:
            if det.zone in ("LEFT", "CENTER"):
                left = max(left, det.pwm_intensity)
            if det.zone in ("RIGHT", "CENTER"):
                # An obstacle dead ahead vibrates both wristbands
                right = max(right, det.pwm_intensity)
            if det.area_ratio > max_area and det.pwm_intensity > 0.0:
                max_area = det.area_ratio
                threat_label = f"{det.label} ({det.zone})"
        return HapticFeedbackState(left, right, threat_label, max_area)

    def process_detections(
        self,
        boxes: Sequence[Box],
        scores: Sequence[float],
        labels: Optional[Sequence[str]] = None,
        frame_width: int = 640,
        frame_height: int = 480,
        class_ids: Optional[Sequence[int]] = None,
        class_names: Optional[Dict[int, str]] = None,
    ) -> Tuple[List[Detection], HapticFeedbackState]:
        """Processes raw model detections into spatial cues and dual wristband signals."""
        if labels is None:
            if class_ids is not None and class_names is not None:
                labels = [class_names.get(cid, f"obj_{cid}") for cid in class_ids]
            else:
                labels = [f"obj_{i}" for i in range(len(boxes))]
        detections = self.build_detections(boxes, scores, labels, frame_width, frame_height)
        return detections, self.compute_state(detections)


class EnsembleDetector:
    """Runs the COCO-80 model and the fine-tuned indoor/doors model and merges their output."""

    def __init__(self, coco_model: str, doors_model: str, conf: float = 0.35):
        from ultralytics import YOLO

        self.conf = conf
        self.models: List[Tuple[str, object, Dict[int, str]]] = []
        names_loaded = []
        for label, path in (("COCO-80", coco_model), ("Doors", doors_model)):
            if label == "Doors" and not Path(path).exists():
                print(f"[Model] Doors model '{path}' not found, skipping.")
                continue
            try:
                print(f"[Model] Loading {label}: {path}...")
                model = YOLO(path)
                self.models.append((label, model, dict(model.names)))
                names_loaded.append(label)
            except Exception as exc:  # noqa: BLE001 - keep running with whatever loads
                print(f"[Model Warning] Could not load {path}: {exc}")
        if not self.models:
            raise RuntimeError("No YOLO model could be loaded.")
        self.mode_label = " + ".join(names_loaded)
        self._recent_bed_frames: int = 0

    def detect(self, frame: np.ndarray) -> List[Candidate]:
        """Returns merged candidates (box, confidence, label) for a frame."""
        fh, fw = frame.shape[:2]
        raw_conf = min(0.12, self.conf * 0.4)
        strong_candidates: List[Candidate] = []
        weak_bed_boxes: List[Box] = []

        for model_tag, model, names in self.models:
            results = model(frame, conf=raw_conf, verbose=False)
            if not results or results[0].boxes is None:
                continue
            for b in results[0].boxes:
                xyxy = b.xyxy[0].cpu().numpy().astype(int)
                cls_idx = int(b.cls[0].cpu().numpy())
                score = float(b.conf[0].cpu().numpy())
                lbl = names.get(cls_idx, f"obj_{cls_idx}")
                box: Box = (int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3]))

                # Record any low-confidence 'bed' hypothesis (down to raw_conf) to rescue 2nd/3rd beds
                if lbl.lower() == "bed":
                    weak_bed_boxes.append(box)

                if score < self.conf:
                    continue

                # Filter noisy duplicate furniture classes from the synthetic Doors model
                if model_tag == "Doors" and lbl.lower() not in DOORS_MODEL_ALLOWED_CLASSES:
                    continue

                strong_candidates.append((box, score, lbl))

        # Track whether we are currently in a bedroom scene across recent frames
        if any(c[2].lower() == "bed" for c in strong_candidates):
            self._recent_bed_frames = 25
        elif self._recent_bed_frames > 0:
            self._recent_bed_frames -= 1

        disambiguated = disambiguate_multi_bed_candidates(
            strong_candidates=strong_candidates,
            weak_bed_boxes=weak_bed_boxes,
            frame_width=fw,
            frame_height=fh,
            bedroom_context_active=(self._recent_bed_frames > 0),
        )
        return merge_candidate_detections(disambiguated, iou_thresh=0.45)
