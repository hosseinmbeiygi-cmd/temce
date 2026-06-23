from __future__ import annotations

from core.ids import new_id
from domain.common.enum_types import OrderSide
from domain.market_data.trade import Trade


def sample_trade(
    id: str | None = None,
    instrument_id: str = "inst_test_001",
    symbol: str = "فولاد",
) -> Trade:
    return Trade(
        id=id or new_id("tr"),
        instrument_id=instrument_id,
        symbol=symbol,
        price=15050,
        volume=1000,
        value=15_050_000,
        side=OrderSide.BUY,
        date="2024-01-15",
        time="12:30:05",
        data_source="tsetmc",
    )


def sample_trade_list(count: int = 10) -> list[Trade]:
    return [
        sample_trade(
            instrument_id=f"inst_{i % 5:04d}",
            symbol=["فولاد", "فملی", "وبانک", "کگل", "خودرو"][i % 5],
        )
        for i in range(count)
    ]

