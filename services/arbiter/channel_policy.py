"""L2 Rule Arbiter — Channel Policy (Ears-Free dispatch: Haptic vs Speech)."""

from __future__ import annotations

from enum import Enum
from typing import Tuple

from contracts.safety_alert import SafetyAlert, Tier


class DispatchChannel(str, Enum):
    HAPTIC_ONLY = "HAPTIC_ONLY"
    SPEECH_ONLY = "SPEECH_ONLY"
    BOTH = "BOTH"
    SILENCE = "SILENCE"


class ChannelPolicy:
    """Enforces the Ears-Free design philosophy across output channels.

    - CRITICAL alerts: Dispatch to BOTH haptics and speech (interrupting).
    - ADVISORY navigation: Dispatch to HAPTIC_ONLY (zero ear flooding).
    - SOCIAL/INFORMATIONAL: Dispatch to SPEECH_ONLY or SILENCE.
    """

    @staticmethod
    def select_channels(alert: SafetyAlert, is_user_speaking: bool = False) -> DispatchChannel:
        if alert.tier == Tier.CRITICAL:
            # Critical alerts override everything, even ongoing user speech
            return DispatchChannel.BOTH
        elif alert.tier == Tier.ADVISORY:
            # Haptic vibration provides continuous spatial guidance without blocking hearing
            return DispatchChannel.HAPTIC_ONLY
        elif alert.tier == Tier.SOCIAL:
            # Social alerts wait if the user is currently speaking
            if is_user_speaking:
                return DispatchChannel.SILENCE
            return DispatchChannel.SPEECH_ONLY
        return DispatchChannel.SILENCE
