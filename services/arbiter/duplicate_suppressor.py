"""L2 Rule Arbiter — Duplicate Suppressor (Suppresses repeated alerts for same track)."""

from __future__ import annotations

import time
from typing import Dict, Tuple

from contracts.safety_alert import DirectionSector, Tier


class DuplicateSuppressor:
    """Suppresses duplicate alert triggers for the same tracked physical object."""

    def __init__(self, repeat_window_sec: float = 3.0) -> None:
        self.repeat_window_sec = repeat_window_sec
        self.seen_alerts: Dict[Tuple[str, DirectionSector, Tier], float] = {}

    def is_duplicate(self, object_class: str, sector: DirectionSector, tier: Tier) -> bool:
        """Returns True if this exact hazard in this sector was already alerted recently."""
        key = (object_class, sector, tier)
        now = time.time()
        if key in self.seen_alerts:
            if (now - self.seen_alerts[key]) < self.repeat_window_sec:
                return True
        self.seen_alerts[key] = now
        return False

    def reset(self) -> None:
        self.seen_alerts.clear()
