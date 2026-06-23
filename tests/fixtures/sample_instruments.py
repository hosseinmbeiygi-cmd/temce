from __future__ import annotations

from domain.common.enum_types import AssetClass, InstrumentStatus, MarketType
from domain.instruments.instrument import Instrument


def sample_instrument(id: str = "inst_test_001", symbol: str = "فولاد") -> Instrument:
    return Instrument(
        id=id,
        symbol=symbol,
        name="فولاد مبارکه اصفهان",
        isin="IRO1FOLD0001",
        market_type=MarketType.BOURS,
        asset_class=AssetClass.EQUITY,
        status=InstrumentStatus.ACTIVE,
        sector_code="metal",
        group_code="01",
        tick_size=1.0,
        lot_size=1000,
        par_value=1000,
        eps=1500,
        shares_count=10_000_000_000,
        base_volume=5_000_000,
        exchange_code="TSETMC",
        board_code="main",
        tags=["sharia", "blue_chip"],
    )


def sample_instrument_list(count: int = 5) -> list[Instrument]:
    symbols = ["فولاد", "فملی", "وبانک", "کگل", "خودرو"]
    return [sample_instrument(id=f"inst_{i:04d}", symbol=symbols[i % len(symbols)]) for i in range(count)]

