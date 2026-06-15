from __future__ import annotations

from enum import StrEnum


class BoardType(StrEnum):
    MAIN = "main"
    SECONDARY = "secondary"
    GROWTH = "growth"
    EMERGING = "emerging"
    FUTURES = "futures"
    OPTION = "option"


class InstrumentGroupType(StrEnum):
    SECTOR = "sector"
    INDUSTRY = "industry"
    SUB_INDUSTRY = "sub_industry"
    BOARD = "board"
    MARKET = "market"


class TradingStatus(StrEnum):
    ALLOWED = "allowed"
    RESTRICTED = "restricted"
    FORBIDDEN = "forbidden"


class PriceLimit(StrEnum):
    NONE = "none"
    FIVE_PCT = "5%"
    TEN_PCT = "10%"
    FIFTEEN_PCT = "15%"
    TWENTY_PCT = "20%"
    FIFTY_PCT = "50%"
