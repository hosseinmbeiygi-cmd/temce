#!/usr/bin/env python
from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta

from core.logging import get_logger
from services.quote_service import QuoteService

logger = get_logger(__name__)


async def backfill(symbol: str, days: int = 365) -> None:
    service = QuoteService()
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    logger.info("Backfilling %s from %s to %s", symbol, start_date, end_date)
    result = await service.get_history(symbol, start_date.isoformat(), end_date.isoformat())
    if result.success:
        logger.info("Backfill complete: %d records", len(result.value) if isinstance(result.value, list) else 0)
    else:
        logger.error("Backfill failed: %s", result.error)


async def main() -> None:
    symbols = sys.argv[1:] if len(sys.argv) > 1 else ["فولاد", "فملی", "وبانک", "کگل", "خودرو"]
    for symbol in symbols:
        await backfill(symbol)


if __name__ == "__main__":
    asyncio.run(main())
