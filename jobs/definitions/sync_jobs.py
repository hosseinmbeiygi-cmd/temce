from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


async def sync_instruments(source: str = "tsetmc") -> dict[str, Any]:
    logger.info("Syncing instruments from %s", source)
    return {"status": "completed", "source": source, "count": 0}


async def sync_quotes(source: str = "tsetmc") -> dict[str, Any]:
    logger.info("Syncing quotes from %s", source)
    return {"status": "completed", "source": source, "count": 0}


async def sync_codal(source: str = "codal") -> dict[str, Any]:
    logger.info("Syncing codal data from %s", source)
    return {"status": "completed", "source": source, "count": 0}


async def sync_news(source: str = "rss") -> dict[str, Any]:
    logger.info("Syncing news from %s", source)
    return {"status": "completed", "source": source, "count": 0}
