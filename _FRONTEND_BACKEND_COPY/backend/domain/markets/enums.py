from __future__ import annotations

from enum import StrEnum


class MarketStatus(StrEnum):
    PRE_OPEN = "pre_open"
    OPEN = "open"
    LUNCH_BREAK = "lunch_break"
    CLOSED = "closed"
    HALTED = "halted"


class SessionType(StrEnum):
    REGULAR = "regular"
    AUCTION = "auction"
    EXTENDED = "extended"
    PRE_MARKET = "pre_market"
    AFTER_HOURS = "after_hours"


class SettlementCycle(StrEnum):
    T0 = "T+0"
    T1 = "T+1"
    T2 = "T+2"
    T3 = "T+3"
