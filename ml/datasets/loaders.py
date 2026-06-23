from __future__ import annotations

from typing import Any

import pandas as pd
import yfinance as yf

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

    async def load_market_data(
        self, 
        instrument_ids: list[str], 
        start: str, 
        end: str,
        source: str = "yahoo"
    ) -> Result[pd.DataFrame]:
        logger.info(
            "Loading market data for %d instruments from %s to %s (source: %s)",
            len(instrument_ids),
            start,
            end,
            source
        )
        
        if source.lower() == "yahoo":
            try:
                data = yf.download(
                    tickers=" ".join(instrument_ids),
                    start=start,
                    end=end,
                    group_by="ticker"
                )
                if data.empty:
                    return Result.fail("No data returned from Yahoo Finance")
                return Result.ok(data)
            except Exception as e:
                return Result.fail(f"Yahoo Finance download failed: {str(e)}")
        else:
            return Result.fail(f"Unsupported data source: {source}")
