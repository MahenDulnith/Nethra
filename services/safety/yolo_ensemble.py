"""L2 Offline Safety Detector — Dual-Model YOLO11 Nano Ensemble & IoU Deduplication."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch

Box = Tuple[int, int, int, int]
Candidate = Tuple[Box, float, str]

# Classes from the fine-tuned indoor/doors model that we allow into the ensemble.
# Excluding 'table', 'chair', 'sofa', 'lamp', etc. prevents the small synthetic model
# from overriding COCO-80's real-world furniture detections or mislabeling beds as tables/chairs.
DOORS_MODEL_ALLOWED_CLASSES = {"door", "wardrobe", "window", "bed"}

# Furniture classes that YOLO frequently confuses with extra beds in a multi-bed room
BED_CONFUSABLE_FURNITURE = {"chair", "dining table", "table", "couch", "sofa", "bench"}


def detect_best_device() -> str:
    """Detects available hardware accelerator across Windows (CUDA), macOS (MPS), and CPU."""
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        print(f"[Hardware Acceleration] NVIDIA CUDA GPU ({gpu_name}): ACTIVE ✅")
        return "0"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        print("[Hardware Acceleration] Apple Silicon MPS (Metal Performance Shaders): ACTIVE ✅")
        return "mps"
    print("[Hardware Acceleration] CPU mode (No dedicated GPU detected).")
    return "cpu"


def compute_iou(boxA: Box, boxB: Box) -> float:
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
    candidates: List[Candidate],
    iou_thresh: float = 0.45,
) -> List[Candidate]:
    """Merges detections from multiple models and eliminates duplicate overlapping boxes.
    
    Prioritizes 'bed' over confusable furniture labels ('table', 'dining table', 'chair', 'couch')
    when two candidate boxes overlap on the same physical piece of furniture.
    """
    if not candidates:
        return []

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
    """Recovers 2nd/3rd beds in a room that YOLO misclassifies as 'table', 'dining table', or 'chair'."""
    frame_area = float(max(1, frame_width * frame_height))
    has_confirmed_bed = (
        bedroom_context_active
        or any(c[2].lower() == "bed" for c in strong_candidates)
        or len(weak_bed_boxes) > 0
    )

    resolved: List[Candidate] = []
    for box, score, label in strong_candidates:
        lbl_low = label.lower()
        if lbl_low in BED_CONFUSABLE_FURNITURE:
            if any(compute_iou(box, bed_box) >= 0.25 for bed_box in weak_bed_boxes):
                resolved.append((box, score, "bed"))
                has_confirmed_bed = True
                continue

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


def resolve_model_path(model_path: str) -> Path:
    """Resolves a model weight file from either the given path, `models/`, or root fallback."""
    direct = Path(model_path)
    if direct.exists():
        return direct
    in_models = Path("models") / direct.name
    if in_models.exists():
        return in_models
    if "doors" in direct.name:
        for alt in [
            Path("models/nethra_doors_yolo11n.pt"),
            Path("nethra_doors_yolo11n.pt"),
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
        device: Optional[str] = None,
    ) -> None:
        from ultralytics import YOLO

        self.device = device or detect_best_device()
        self.iou_thresh = iou_thresh
        self.model_coco = None
        self.model_doors = None
        self.coco_names: Dict[int, str] = {}
        self.door_names: Dict[int, str] = {}
        self._recent_bed_frames: int = 0

        resolved_coco = resolve_model_path(coco_model_path)
        print(f"[Model 1] Loading Base YOLO11 Nano (COCO 80 classes): {resolved_coco} on device={self.device}...")
        try:
            self.model_coco = YOLO(str(resolved_coco))
            self.coco_names = getattr(self.model_coco, "names", {})
        except Exception as exc:
            print(f"[Warning] Could not load COCO model: {exc}")

        resolved_doors = resolve_model_path(doors_model_path)
        if resolved_doors.exists():
            print(f"[Model 2] Loading Fine-Tuned Doors/Assistive Model: {resolved_doors} on device={self.device}...")
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
    ) -> Tuple[List[Box], List[float], List[str]]:
        """Runs inference across active models and returns deduplicated (boxes, scores, labels)."""
        fh, fw = frame.shape[:2]
        raw_conf = min(0.12, conf * 0.4)
        strong_candidates: List[Candidate] = []
        weak_bed_boxes: List[Box] = []

        if self.model_coco is not None:
            results_coco = self.model_coco(frame, conf=raw_conf, device=self.device, verbose=False)
            if len(results_coco) > 0 and results_coco[0].boxes is not None:
                for b in results_coco[0].boxes:
                    xyxy = b.xyxy[0].cpu().numpy().astype(int)
                    box_tuple: Box = (int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3]))
                    conf_val = float(b.conf[0].cpu().numpy())
                    cls_idx = int(b.cls[0].cpu().numpy())
                    lbl = self.coco_names.get(cls_idx, f"obj_{cls_idx}")
                    if lbl.lower() == "bed":
                        weak_bed_boxes.append(box_tuple)
                    if conf_val >= conf:
                        strong_candidates.append((box_tuple, conf_val, lbl))

        if self.model_doors is not None:
            results_doors = self.model_doors(frame, conf=raw_conf, device=self.device, verbose=False)
            if len(results_doors) > 0 and results_doors[0].boxes is not None:
                for b in results_doors[0].boxes:
                    xyxy = b.xyxy[0].cpu().numpy().astype(int)
                    box_tuple = (int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3]))
                    conf_val = float(b.conf[0].cpu().numpy())
                    cls_idx = int(b.cls[0].cpu().numpy())
                    lbl = self.door_names.get(cls_idx, f"indoor_{cls_idx}")
                    if lbl.lower() == "bed":
                        weak_bed_boxes.append(box_tuple)
                    if conf_val >= conf and lbl.lower() in DOORS_MODEL_ALLOWED_CLASSES:
                        strong_candidates.append((box_tuple, conf_val, lbl))

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
        merged = merge_candidate_detections(disambiguated, iou_thresh=self.iou_thresh)
        boxes = [c[0] for c in merged]
        scores = [c[1] for c in merged]
        labels = [c[2] for c in merged]
        return boxes, scores, labels
