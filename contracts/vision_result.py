"""L0 Vision Result Contract (Depends on nothing)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CannotSeeReason(str, Enum):
    OK = "OK"
    TOO_DARK = "TOO_DARK"
    BLURRED = "BLURRED"
    OCCLUDED = "OCCLUDED"
    OUT_OF_FRAME = "OUT_OF_FRAME"
    NOT_PRESENT = "NOT_PRESENT"


@dataclass
class VisionResult:
    """Standardized result shape for high-level visual inspection or scene tool outputs."""
    can_see: bool
    reason: Optional[CannotSeeReason] = None
    description: Optional[str] = None
    detected_items: List[str] = field(default_factory=list)
    text_content: Optional[str] = None
    confidence: float = 1.0
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
