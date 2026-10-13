"""L2 Offline Safety Detector — Dual-Model YOLO11 Nano Ensemble & IoU Deduplication."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


def compute_iou(boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> float:
    """Calculates Intersection over Union (IoU) between two bounding boxes."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    inter_w = max(0, xB - xA)
    inter_h = max(0, yB - yA)
    inter_area = float(inter_w * inter_h)

    boxA_area = float(max(0, boxA[2] - boxA[0]) * max(0, boxA[3] - boxA[1]))
    boxB_area = float(max(0, boxB[2] - boxB[0]) * max(0, boxB[3] - boxB[1]))
    union_area = boxA_area + boxB_area - inter_area

    if union_area <= 0.0:
        return 0.0
    return inter_area / union_area


def merge_candidate_detections(
    candidates: List[Tuple[Tuple[int, int, int, int], float, str]],
    iou_thresh: float = 0.45,
) -> List[Tuple[Tuple[int, int, int, int], float, str]]:
    """Merges detections from multiple models and eliminates duplicate overlapping boxes."""
    if not candidates:
        return []

    candidates.sort(key=lambda x: x[1], reverse=True)
    kept: List[Tuple[Tuple[int, int, int, int], float, str]] = []

    for cand in candidates:
        box, score, label = cand
        overlap = False
        for k_box, k_score, k_label in kept:
            if compute_iou(box, k_box) > iou_thresh:
                overlap = True
                break
        if not overlap:
            kept.append(cand)

    return kept


def resolve_model_path(model_path: str) -> Path:
    """Resolves a model weight file from either the given path, `models/`, or root fallback."""
    direct = Path(model_path)
    if direct.exists():
        return direct
    in_models = Path("models") / direct.name
    if in_models.exists():
        return in_models
    # Legacy alias fallback (pulsepath_doors_yolo11n.pt <-> nethra_doors_yolo11n.pt)
    if "doors" in direct.name:
        for alt in [
            Path("models/nethra_doors_yolo11n.pt"),
            Path("models/pulsepath_doors_yolo11n.pt"),
            Path("nethra_doors_yolo11n.pt"),
            Path("pulsepath_doors_yolo11n.pt"),
        ]:
            if alt.exists():
                return alt
    return direct


class YoloEnsembleDetector:
    """Runs Base COCO-80 YOLO11n + Fine-Tuned Assistive Doors/Indoor YOLO11n with IoU NMS."""

    def __init__(
        self,
        coco_model_path: str = "models/yolo11n.pt",
        doors_model_path: str = "models/nethra_doors_yolo11n.pt",
        iou_thresh: float = 0.45,
    ) -> None:
        from ultralytics import YOLO

        self.iou_thresh = iou_thresh
        self.model_coco = None
        self.model_doors = None
        self.coco_names: Dict[int, str] = {}
        self.door_names: Dict[int, str] = {}

        resolved_coco = resolve_model_path(coco_model_path)
        print(f"[Model 1] Loading Base YOLO11 Nano (COCO 80 classes): {resolved_coco}...")
        try:
            self.model_coco = YOLO(str(resolved_coco))
            self.coco_names = getattr(self.model_coco, "names", {})
        except Exception as exc:
            print(f"[Warning] Could not load COCO model: {exc}")

        resolved_doors = resolve_model_path(doors_model_path)
        if resolved_doors.exists():
            print(f"[Model 2] Loading Fine-Tuned Doors/Assistive Model: {resolved_doors}...")
            try:
                self.model_doors = YOLO(str(resolved_doors))
                self.door_names = getattr(self.model_doors, "names", {})
            except Exception as exc:
                print(f"[Warning] Could not load doors model: {exc}")
        else:
            print(f"[Model 2] Doors model '{doors_model_path}' not found, running single COCO model.")

    @property
    def is_ready(self) -> bool:
        return self.model_coco is not None or self.model_doors is not None

    @property
    def mode_label(self) -> str:
        if self.model_coco is not None and self.model_doors is not None:
            return "Ensemble: COCO-80 + Doors"
        elif self.model_doors is not None:
            return "Model: Doors & Indoor"
        return "Model: COCO-80"

    def detect(
        self, frame: np.ndarray, conf: float = 0.35
    ) -> Tuple[List[Tuple[int, int, int, int]], List[float], List[str]]:
        """Runs inference across active models and returns deduplicated (boxes, scores, labels)."""
        raw_candidates: List[Tuple[Tuple[int, int, int, int], float, str]] = []

        if self.model_coco is not None:
            results_coco = self.model_coco(frame, conf=conf, verbose=False)
            if len(results_coco) > 0 and results_coco[0].boxes is not None:
                for b in results_coco[0].boxes:
                    xyxy = b.xyxy[0].cpu().numpy().astype(int)
                    box_tuple = (int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3]))
                    conf_val = float(b.conf[0].cpu().numpy())
                    cls_idx = int(b.cls[0].cpu().numpy())
                    lbl = self.coco_names.get(cls_idx, f"obj_{cls_idx}")
                    raw_candidates.append((box_tuple, conf_val, lbl))

        if self.model_doors is not None:
            results_doors = self.model_doors(frame, conf=conf, verbose=False)
            if len(results_doors) > 0 and results_doors[0].boxes is not None:
                for b in results_doors[0].boxes:
                    xyxy = b.xyxy[0].cpu().numpy().astype(int)
                    box_tuple = (int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3]))
                    conf_val = float(b.conf[0].cpu().numpy())
                    cls_idx = int(b.cls[0].cpu().numpy())
                    lbl = self.door_names.get(cls_idx, f"indoor_{cls_idx}")
                    raw_candidates.append((box_tuple, conf_val, lbl))

        merged = merge_candidate_detections(raw_candidates, iou_thresh=self.iou_thresh)
        boxes = [c[0] for c in merged]
        scores = [c[1] for c in merged]
        labels = [c[2] for c in merged]
        return boxes, scores, labels
