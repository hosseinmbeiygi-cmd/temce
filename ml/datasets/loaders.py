from __future__ import annotations

from typing import Any

import pandas as pd

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class DataLoader:
    async def load_from_csv(self, path: str) -> Result[pd.DataFrame]:
        try:
            df = pd.read_csv(path)
            return Result.ok(df)
        except Exception as e:
            return Result.fail(str(e))

    async def load_from_dict(self, data: list[dict[str, Any]]) -> pd.DataFrame:
        return pd.DataFrame(data)

    async def load_market_data(self, instrument_ids: list[str], start: str, end: str) -> Result[pd.DataFrame]:
        logger.info("Loading market data for %d instruments", len(instrument_ids))
        return Result.ok(pd.DataFrame())
