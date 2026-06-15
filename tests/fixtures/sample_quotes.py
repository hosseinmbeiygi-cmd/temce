from __future__ import annotations

from domain.market_data.quote import Quote


def sample_quote(
    id: str = "q_test_001",
    instrument_id: str = "inst_test_001",
    symbol: str = "فولاد",
    date: str = "2024-01-15",
    time: str = "12:30:00",
) -> Quote:
    return Quote(
        id=id,
        instrument_id=instrument_id,
        symbol=symbol,
        price_close=15000,
        price_open=14900,
        price_high=15100,
        price_low=14850,
        price_last=15050,
        price_change=100,
        price_change_pct=0.67,
        volume=5_000_000,
        value=75_000_000_000,
        trade_count=1200,
        price_yesterday=14900,
        price_first=14900,
        price_max=15100,
        price_min=14850,
        ask_price=15060,
        ask_volume=10000,
        bid_price=15040,
        bid_volume=15000,
        time=time,
        date=date,
        timeframe="1d",
        data_source="tsetmc",
    )


def sample_quote_list(count: int = 10) -> list[Quote]:
    return [
        sample_quote(
            id=f"q_{i:04d}",
            instrument_id=f"inst_{i % 5:04d}",
            symbol=["فولاد", "فملی", "وبانک", "کگل", "خودرو"][i % 5],
            date=f"2024-01-{min(15 + i, 31):02d}",
        )
        for i in range(count)
    ]
