"""L2 Rule Arbiter — Cooldown Registry (Prevents alert chatter)."""

from __future__ import annotations

import time
from typing import Dict, Tuple

from contracts.safety_alert import Tier


class CooldownRegistry:
    """Maintains cooldown timers per tier and per object class to prevent fatigue."""

    def __init__(
        self,
        critical_ms: int = 1500,
        advisory_ms: int = 6000,
        social_ms: int = 20000,
    ) -> None:
        self.cooldowns_sec = {
            Tier.CRITICAL: critical_ms / 1000.0,
            Tier.ADVISORY: advisory_ms / 1000.0,
            Tier.SOCIAL: social_ms / 1000.0,
        }
        self.last_fired: Dict[Tuple[Tier, str], float] = {}

    def is_in_cooldown(self, tier: Tier, object_class: str) -> bool:
        """Returns True if the alert is currently suppressed by a cooldown timer."""
        key = (tier, object_class)
        if key not in self.last_fired:
            return False
        elapsed = time.time() - self.last_fired[key]
        cooldown = self.cooldowns_sec.get(tier, 5.0)
        return elapsed < cooldown

    def mark_fired(self, tier: Tier, object_class: str) -> None:
        """Records the timestamp when an alert was dispatched."""
        self.last_fired[(tier, object_class)] = time.time()

    def reset(self) -> None:
        self.last_fired.clear()
