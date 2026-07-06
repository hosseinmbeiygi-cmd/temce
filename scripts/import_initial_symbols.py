#!/usr/bin/env python
from __future__ import annotations

# --- auto PYTHONPATH ---
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import asyncio

from core.ids import new_id
from core.logging import get_logger
from domain.common.enum_types import AssetClass, MarketType
from domain.instruments.instrument import Instrument

logger = get_logger(__name__)


INITIAL_SYMBOLS = [
    {
        "symbol": "فولاد",
        "name": "فولاد مبارکه اصفهان",
        "isin": "IRO1FOLD0001",
        "market_type": "bours",
        "group_code": "01",
    },
    {
        "symbol": "فملی",
        "name": "ملی صنایع مس ایران",
        "isin": "IRO1FMLI0001",
        "market_type": "bours",
        "group_code": "01",
    },
    {"symbol": "وبانک", "name": "بانک ملت", "isin": "IRO1BANK0001", "market_type": "bours", "group_code": "02"},
    {"symbol": "کگل", "name": "گل گهر", "isin": "IRO1KEGL0001", "market_type": "bours", "group_code": "01"},
    {"symbol": "خودرو", "name": "ایران خودرو", "isin": "IRO1IKCO0001", "market_type": "bours", "group_code": "03"},
]


async def import_symbols() -> int:
    from repositories.instrument_repository import InstrumentRepository

    repo = InstrumentRepository()
    count = 0
    for sym in INITIAL_SYMBOLS:
        instrument = Instrument(
            id=new_id("inst"),
            symbol=sym["symbol"],
            name=sym["name"],
            isin=sym["isin"],
            market_type=MarketType(sym["market_type"]),
            asset_class=AssetClass.EQUITY,
            group_code=sym["group_code"],
        )
        result = await repo.save(instrument)
        if result.success:
            count += 1
            logger.info("Imported: %s", sym["symbol"])
        else:
            logger.error("Failed to import %s: %s", sym["symbol"], result.error)
    return count


async def main() -> None:
    logger.info("Importing initial symbols...")
    count = await import_symbols()
    logger.info("Imported %d symbols", count)


if __name__ == "__main__":
    asyncio.run(main())
