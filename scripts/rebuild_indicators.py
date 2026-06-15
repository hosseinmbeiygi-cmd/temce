#!/usr/bin/env python
from __future__ import annotations

import asyncio

from core.logging import get_logger

logger = get_logger(__name__)


async def rebuild_indicators(symbols: list[str] | None = None) -> int:
    from services.market_service import MarketService

    service = MarketService()

    if symbols is None:
        symbols = ["فولاد", "فملی", "وبانک", "کگل", "خودرو"]

    indicator_types = ["sma", "ema", "rsi", "macd", "bbands"]
    count = 0

    for symbol in symbols:
        for ind_type in indicator_types:
            params = {"period": 14}
            if ind_type == "macd":
                params = {"fast": 12, "slow": 26, "signal": 9}
            elif ind_type == "bbands":
                params = {"period": 20, "num_std": 2}

            result = await service.calculate_indicator(symbol, ind_type, params)
            if result.success:
                count += 1
                logger.debug("Rebuilt %s for %s", ind_type, symbol)
            else:
                logger.warning("Failed to rebuild %s for %s: %s", ind_type, symbol, result.error)

    logger.info("Rebuilt %d indicators", count)
    return count


async def main() -> None:
    import sys

    symbols = sys.argv[1:] if len(sys.argv) > 1 else None
    count = await rebuild_indicators(symbols)
    logger.info("Done. %d indicators rebuilt.", count)


if __name__ == "__main__":
    asyncio.run(main())
