from __future__ import annotations

from enum import StrEnum


class MarketSession(StrEnum):
    PRE_OPEN = "pre_open"
    OPEN = "open"
    CLOSE = "close"
    POST_CLOSE = "post_close"
    AUCTION = "auction"
    CONTINUOUS = "continuous"


class TradingState(StrEnum):
    ACTIVE = "active"
    HALTED = "halted"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    PRE_OPEN = "pre_open"


class MarketIndicator(StrEnum):
    TEDPIX = "tedpix"
    TEDIX = "tedix"
    TEFIX = "tefix"
    TEDIX30 = "tedix30"
    FARABOURSE_INDEX = "farabourse_index"
