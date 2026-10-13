"""L2 Rule Arbiter — Priority Matrix (Pure config-driven ranking, NO ML models)."""

from __future__ import annotations

from typing import List

from contracts.safety_alert import SafetyAlert, Tier


class PriorityMatrix:
    """Ranks safety alert candidates strictly by safety severity tier."""

    TIER_RANK = {
        Tier.CRITICAL: 0,
        Tier.ADVISORY: 1,
        Tier.SOCIAL: 2,
        Tier.IGNORE: 3,
    }

    @classmethod
    def rank_candidates(cls, candidates: List[SafetyAlert]) -> List[SafetyAlert]:
        """Sorts candidates so highest priority alerts are first."""
        # Sort by: (Tier rank, lowest TTC, closest distance)
        return sorted(
            candidates,
            key=lambda a: (
                cls.TIER_RANK.get(a.tier, 99),
                a.ttc_seconds if a.ttc_seconds is not None else 999.0,
            ),
        )
