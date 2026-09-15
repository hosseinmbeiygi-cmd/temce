from __future__ import annotations

from enum import StrEnum


class ExecutionType(StrEnum):
    BAR = "bar"
    TICK = "tick"
    EVENT = "event"


class SlippageMode(StrEnum):
    FIXED = "fixed"
    PERCENT = "percent"
    VOLUME_BASED = "volume_based"
    NONE = "none"


class CommissionMode(StrEnum):
    FIXED = "fixed"
    PERCENT = "percent"
    PER_SHARE = "per_share"
    TIERED = "tiered"
