#!/usr/bin/env python
from __future__ import annotations

import asyncio

from core.ids import new_id
from core.logging import get_logger

logger = get_logger(__name__)


async def seed() -> int:
    from domain.common.enum_types import AssetClass, MarketType
    from domain.instruments.instrument import Instrument
    from repositories.instrument_repository import InstrumentRepository

    repo = InstrumentRepository()
    symbols_data = [
        {"symbol": "شستا", "name": "سرمایه گذاری تامین اجتماعی", "isin": "IRO1SHST0001", "group_code": "04"},
        {"symbol": "حافظ", "name": "حافظ", "isin": "IRO1HAFZ0001", "group_code": "03"},
        {"symbol": "آریا", "name": "آریا", "isin": "IRO1ARYA0001", "group_code": "01"},
        {"symbol": "دماوند", "name": "دماوند", "isin": "IRO1DMAV0001", "group_code": "02"},
        {"symbol": "سینا", "name": "سینا", "isin": "IRO1SINA0001", "group_code": "05"},
        {"symbol": "شپنا", "name": "پالایش نفت اصفهان", "isin": "IRO1SHPN0001", "group_code": "06"},
        {"symbol": "شتران", "name": "پالایش نفت تهران", "isin": "IRO1SHTR0001", "group_code": "06"},
        {"symbol": "پارسان", "name": "پارسیان", "isin": "IRO1PARS0001", "group_code": "04"},
        {"symbol": "وبصادر", "name": "بانک صادرات", "isin": "IRO1BSDR0001", "group_code": "02"},
        {"symbol": "وتجارت", "name": "بانک تجارت", "isin": "IRO1BTJR0001", "group_code": "02"},
    ]

    count = 0
    for sd in symbols_data:
        instrument = Instrument(
            id=new_id("inst"),
            symbol=sd["symbol"],
            name=sd["name"],
            isin=sd["isin"],
            market_type=MarketType.BOURS,
            asset_class=AssetClass.EQUITY,
            group_code=sd["group_code"],
        )
        result = await repo.save(instrument)
        if result.success:
            count += 1

    logger.info("Seeded %d reference instruments", count)
    return count


async def main() -> None:
    count = await seed()
    logger.info("Done. %d instruments seeded.", count)


if __name__ == "__main__":
    asyncio.run(main())
