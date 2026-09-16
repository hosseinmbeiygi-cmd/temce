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
import contextlib

from core.logging import get_logger

logger = get_logger(__name__)


async def rebuild() -> int:
    logger.info("Rebuilding feature store...")
    from ml.feature_store import FeatureStore

    store = FeatureStore()

    features = [
        ("close", "price", "float64"),
        ("open", "price", "float64"),
        ("high", "price", "float64"),
        ("low", "price", "float64"),
        ("volume", "volume", "int64"),
        ("value", "volume", "float64"),
        ("trade_count", "volume", "int32"),
        ("price_change", "price", "float64"),
        ("price_change_pct", "price", "float64"),
        ("sma_20", "technical", "float64"),
        ("sma_50", "technical", "float64"),
        ("ema_20", "technical", "float64"),
        ("rsi_14", "technical", "float64"),
        ("macd", "technical", "float64"),
        ("bb_upper", "technical", "float64"),
        ("bb_lower", "technical", "float64"),
        ("eps", "fundamental", "float64"),
        ("pe_ratio", "fundamental", "float64"),
        ("volume_ma_20", "volume", "float64"),
    ]

    count = 0
    for name, group, dtype in features:
        with contextlib.suppress(ValueError):
            store.register_feature(name, group, dtype)
            count += 1

    logger.info("Feature store rebuilt with %d features", count)
    return count


async def main() -> None:
    count = await rebuild()
    logger.info("Done. %d features registered.", count)


if __name__ == "__main__":
    asyncio.run(main())
