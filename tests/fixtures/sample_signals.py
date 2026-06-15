from __future__ import annotations

from core.ids import new_id
from domain.analytics.signal import Signal
from domain.common.enum_types import SignalType


def sample_signal(
    id: str | None = None,
    symbol: str = "فولاد",
    signal_type: str = "bullish",
) -> Signal:
    return Signal(
        id=id or new_id("sig"),
        instrument_id="inst_test_001",
        symbol=symbol,
        signal_type=SignalType(signal_type),
        score=0.75,
        confidence=0.8,
        source="technical_analysis",
        description="قوی بودن سیگنال خرید بر اساس اندیکاتورهای تکنیکال",
        timeframe="1d",
        extra={
            "direction": "up",
            "indicators": {"rsi": 65.0, "macd": 120.0, "sma_20": 14900, "sma_50": 14700},
            "data_source": "system",
        },
    )


def sample_signal_list(count: int = 5) -> list[Signal]:
    types = ["bullish", "bearish", "neutral", "strong_buy", "strong_sell"]
    symbols = ["فولاد", "فملی", "وبانک", "کگل", "خودرو"]
    return [
        sample_signal(
            symbol=symbols[i % len(symbols)],
            signal_type=types[i % len(types)],
        )
        for i in range(count)
    ]
