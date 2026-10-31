from __future__ import annotations

from enum import StrEnum
from zoneinfo import ZoneInfo

# Iranian market sessions are evaluated in Tehran local time (BT-013 / MKT-001).
# Kept here (not in engine.clock) so market/strategy modules can use it without
# importing the engine package (AUD-ARCH-01).
TEHRAN_TZ = ZoneInfo("Asia/Tehran")


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
