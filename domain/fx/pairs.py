from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MAJOR_PAIRS = {"EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "USD/CAD", "AUD/USD", "NZD/USD"}
MINOR_PAIRS = {"EUR/GBP", "EUR/JPY", "GBP/JPY", "EUR/CHF", "EUR/AUD", "GBP/CHF"}
EXOTIC_PAIRS = {"USD/TRY", "USD/ZAR", "USD/MXN", "EUR/TRY", "USD/IRR", "EUR/IRR"}


@dataclass
class CurrencyPairInfo:
    symbol: str = ""
    base_currency: str = ""
    quote_currency: str = ""
    category: str = "exotic"
    pip_size: int = 4
    lot_size: int = 100000
    min_trade_size: float = 0.01
    max_leverage: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
