from __future__ import annotations

from typing import Any

import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import json

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
        
        elif source.lower() == "tsetmc":
            try:
                # First get instrument IDs from symbols
                symbols_to_ids = {}
                for symbol in instrument_ids:
                    search_url = f"http://www.tsetmc.com/tsev2/data/search.aspx?skey={symbol}"
                    response = requests.get(search_url)
                    if response.status_code != 200:
                        continue
                    
                    data = json.loads(response.text)
                    if data and isinstance(data, list):
                        symbols_to_ids[symbol] = data[0]['n']  # Assuming first match is correct
                
                if not symbols_to_ids:
                    return Result.fail("No instruments found on TSE")
                
                # Now get historical data
                dfs = []
                for symbol, inst_id in symbols_to_ids.items():
                    hist_url = f"http://www.tsetmc.com/tsev2/data/Export-txt.aspx?t=i&a=1&b=0&i={inst_id}"
                    response = requests.get(hist_url)
                    if response.status_code != 200:
                        continue
                    
                    # Parse the CSV data
                    df = pd.read_csv(pd.compat.StringIO(response.text), sep=',')
                    df['Symbol'] = symbol
                    dfs.append(df)
                
                if not dfs:
                    return Result.fail("No historical data found on TSE")
                
                combined_df = pd.concat(dfs)
                return Result.ok(combined_df)
                
            except Exception as e:
                return Result.fail(f"TSE data download failed: {str(e)}")
        
        else:
            return Result.fail(f"Unsupported data source: {source}")
