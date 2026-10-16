"""L2 Deterministic Rule Arbiter — The single entry point for alert arbitration."""

from __future__ import annotations

from typing import List, Optional, Tuple

from contracts.safety_alert import SafetyAlert, Tier
from services.arbiter.channel_policy import ChannelPolicy, DispatchChannel
from services.arbiter.cooldown_registry import CooldownRegistry
from services.arbiter.duplicate_suppressor import DuplicateSuppressor
from services.arbiter.priority_matrix import PriorityMatrix


class RuleArbiter:
    """Evaluates candidate alerts against deterministic rules, cooldowns, and channels.

    Rule R4 Enforced: Contains NO MACHINE LEARNING MODELS and NO NETWORK CALLS.
    Deterministic: identical inputs and configuration produce identical decisions every time.
    """

    def __init__(
        self,
        cooldown_registry: Optional[CooldownRegistry] = None,
        duplicate_suppressor: Optional[DuplicateSuppressor] = None,
    ) -> None:
        self.cooldown_registry = cooldown_registry or CooldownRegistry()
        self.duplicate_suppressor = duplicate_suppressor or DuplicateSuppressor()
        self.channel_policy = ChannelPolicy()

    def arbitrate(
        self,
        candidates: List[SafetyAlert],
        is_user_speaking: bool = False,
    ) -> Tuple[Optional[SafetyAlert], DispatchChannel]:
        """Filters and selects the single winning alert for this frame interval."""
        if not candidates:
            return None, DispatchChannel.SILENCE

        # 1. Rank candidates by severity and TTC
        ranked = PriorityMatrix.rank_candidates(candidates)

        for alert in ranked:
            if alert.tier == Tier.IGNORE:
                continue

            # 2. Duplicate suppression
            if self.duplicate_suppressor.is_duplicate(
                alert.object_class, alert.direction_sector, alert.tier
            ):
                continue

            # 3. Cooldown check
            if self.cooldown_registry.is_in_cooldown(alert.tier, alert.object_class):
                continue

            # 4. Winning alert found! Determine channel policy
            channel = self.channel_policy.select_channels(
                alert, is_user_speaking=is_user_speaking
            )
            if channel != DispatchChannel.SILENCE:
                self.cooldown_registry.mark_fired(alert.tier, alert.object_class)
                return alert, channel

        return None, DispatchChannel.SILENCE
