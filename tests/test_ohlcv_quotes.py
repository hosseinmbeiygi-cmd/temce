from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import func as sa_func
from sqlalchemy import select

from core.database import close_database, get_session, init_database
from models.instrument import InstrumentModel
from models.quote import QuoteModel
from repositories.instrument_repository import InstrumentRepository
from repositories.quote_repository import QuoteRepository
from services.market_service import MarketService

#!/usr/bin/env python
"""Test OHLCV data retrieval from the quotes table."""


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

OUTPUT_FILE = _PROJECT_ROOT / "test_ohlcv_result.txt"

TEST_SYMBOL = "\u0641\u0648\u0644\u0627\u062f"  # "فولاد"


async def main() -> None:
    lines = []

    def log(msg: str) -> None:
        lines.append(msg)
        # Avoid UnicodeEncodeError on Windows terminal
        safe_msg = msg.encode("ascii", "replace").decode("ascii")
        print(safe_msg, flush=True)

    await init_database()
    log("DB initialized")

    async for session in get_session():
        log("Session obtained")

        # 1. Check instrument lookup

        inst_repo = InstrumentRepository(session=session)
        inst_result = await inst_repo.get_by_symbol(TEST_SYMBOL)
        if inst_result.success and inst_result.value:
            log(f"OK: Found instrument id={inst_result.value.id}")
            inst_id = inst_result.value.id
        else:
            log(f"FAIL: Instrument not found: {inst_result.error}")
            # Check if any symbols exist at all

            cnt = await session.execute(sa_func.count(InstrumentModel.id))
            log(f"Total instruments in DB: {cnt.scalar()}")
            result = await session.execute(
                select(InstrumentModel.symbol).where(InstrumentModel.symbol.isnot(None)).limit(10)
            )
            all_symbols = [str(r[0]).encode("ascii", "replace").decode("ascii") for r in result.all()]
            log(f"Sample symbols: {', '.join(all_symbols)}")
            return

        # 2. Check quote range

        quote_repo = QuoteRepository(session=session)
        quotes_result = await quote_repo.get_range(
            inst_id,
            date(2025, 1, 1),
            date(2025, 12, 31),
            timeframe="1d",
        )
        if quotes_result.success and quotes_result.value:
            q_list = quotes_result.value
            log(f"OK: Got {len(q_list)} quotes from DB")
            log(f"First: date={q_list[0].date} close={q_list[0].price_close}")
            log(f"Last: date={q_list[-1].date} close={q_list[-1].price_close}")
        else:
            log(f"FAIL: No quotes found: {quotes_result.error}")
            # Check total count

            cnt = await session.execute(sa_func.count(QuoteModel.id))
            log(f"Total quotes in table: {cnt.scalar()}")

        # 3. Test MarketService.get_ohlcv

        svc = MarketService(session=session)
        ohlcv_result = (TEST_SYMBOL, "2025-01-01", "2025-12-31")
        if ohlcv_result.success and ohlcv_result.value:
            bars = ohlcv_result.value
            log(f"OK: MarketService returned {len(bars)} OHLCV bars")
            for bar in bars[:3]:
                log(
                    f"  date={bar.get('date')} o={bar.get('open')} h={bar.get('high')} l={bar.get('low')} c={bar.get('close')} v={bar.get('volume')}"
                )
        else:
            log(f"FAIL: MarketService returned no data: {ohlcv_result.error}")

        # 4. Test MarketService.get_historical_quotes
        hist_result = await svc.get_historical_quotes(TEST_SYMBOL, "2025-01-01", "2025-12-31")
        if hist_result.success and hist_result.value:
            recs = hist_result.value
            log(f"OK: get_historical_quotes returned {len(recs)} records")
            for rec in recs[:2]:
                log(
                    f"  date={rec.get('date')} last={rec.get('price_last')} close={rec.get('price_close')} vol={rec.get('trade_volume')}"
                )
        else:
            log(f"FAIL: get_historical_quotes returned no data: {hist_result.error}")

        break

    await close_database()
    log("Test complete")

    # Write to output file (UTF-8)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
