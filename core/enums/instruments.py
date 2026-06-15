from __future__ import annotations

from enum import StrEnum


class InstrumentGroup(StrEnum):
    EQUITY = "equity"
    BOND = "bond"
    FUND = "fund"
    FUTURES = "futures"
    OPTION = "option"
    ETF = "etf"
    COMMODITY = "commodity"
    CURRENCY = "currency"
    INDEX = "index"


class Board(StrEnum):
    MAIN = "main"
    SECONDARY = "secondary"
    GROWTH = "growth"
    EMERGING = "emerging"
    OPTION = "option"
    FUTURES = "futures"
    ETF = "etf"
    BOND = "bond"


class InstrumentFlow(StrEnum):
    ORDER_DRIVEN = "order_driven"
    QUOTE_DRIVEN = "quote_driven"
    HYBRID = "hybrid"
