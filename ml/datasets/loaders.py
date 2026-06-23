from __future__ import annotations

from typing import Any

import pandas as pd
import yfinance as yf
import requests
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
from bs4 import BeautifulSoup
import json

from core.logging import get_logger
from core.result import Result
import aiohttp
from datetime import datetime
import time

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

    async def _get_tsetmc_stock_info(self, symbol: str) -> dict | None:
        """Get stock info from TSE API"""
        url = "https://cdn.tsetmc.com/api/Instrument/GetInstrumentSearch"
        params = {'text': symbol}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    data = await response.json()
                    if data and data['instrumentSearch']:
                        return data['instrumentSearch'][0]
        except Exception as e:
            logger.warning(f"Failed to get stock info for {symbol}: {str(e)}")
        return None

    async def _get_tsetmc_history(self, ins_code: str, start: str, end: str) -> list[dict] | None:
        """Get historical data from TSE API"""
        start_dt = datetime.strptime(start, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end, "%Y-%m-%d").date()
        
        url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceHistory/{ins_code}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as response:
                    data = await response.json()
                    if not data or 'closingPriceHistory' not in data:
                        return None
                    
                    # Filter by date range
                    filtered = [
                        item for item in data['closingPriceHistory']
                        if start_dt <= datetime.strptime(str(item['dEven']), "%Y%m%d").date() <= end_dt
                    ]
                    return filtered
        except Exception as e:
            logger.warning(f"Failed to get history for {ins_code}: {str(e)}")
        return None

    async def get_realtime_data(self, symbol: str) -> Result[dict]:
        """Get realtime market data for a symbol"""
        try:
            search_url = "https://search.tsetmc.com/api/Stock/GetStockSearch"
            params = {'text': symbol, 'page': 1, 'pageSize': 1}
            response = requests.get(search_url, params=params, headers=DEFAULT_HEADERS)
            if response.status_code != 200 or not response.json().get('data'):
                return Result.fail("Symbol not found")
            
            ins_code = response.json()['data'][0]['insCode']
            realtime_url = f"http://cdn.tsetmc.com/api/Stock/GetStockDetail/{ins_code}"
            response = requests.get(realtime_url, headers=DEFAULT_HEADERS)
            
            if response.status_code != 200:
                return Result.fail("Failed to get realtime data")
                
            return Result.ok(response.json())
        except Exception as e:
            return Result.fail(f"Realtime data error: {str(e)}")

    async def load_market_data(
        self,
        instrument_ids: list[str],
        start: str,
        end: str,
        source: str = "yahoo"
    ) -> Result[pd.DataFrame]:
        """Load market data with improved error handling and retry mechanism"""
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
                dfs = []
                for symbol in instrument_ids:
                    # First get instrument code
                    stock_info = await self._get_tsetmc_stock_info(symbol)
                    if not stock_info:
                        continue
                    
                    # Get historical data
                    history = await self._get_tsetmc_history(
                        stock_info['ins_code'],
                        start,
                        end
                    )
                    if history is not None:
                        df = pd.DataFrame(history)
                        df['Symbol'] = symbol
                        dfs.append(df)
                
                if not dfs:
                    return Result.fail("No valid data received from TSE")
                
                return Result.ok(pd.concat(dfs))
            except Exception as e:
                logger.exception("TSE data download failed")
                return Result.fail(f"TSE data error: {str(e)}")
            try:
                # Get instrument info from new API
                dfs = []
                for symbol in instrument_ids:
                    # Search for symbol
                    search_url = "https://search.tsetmc.com/api/Stock/GetStockSearch"
                    params = {
                        'text': symbol,
                        'page': 1,
                        'pageSize': 1
                    }
                    response = requests.get(search_url, params=params, headers=DEFAULT_HEADERS)
                    response.encoding = 'utf-8'  # Ensure UTF-8 encoding
                    try:
                        json_data = response.json()
                        if response.status_code != 200 or not json_data.get('data'):
                            continue
                        
                        inst_data = json_data['data'][0]
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode JSON: {e}")
                        continue
                    ins_code = inst_data['insCode']
                    
                    # Get historical data
                    hist_url = f"http://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/{ins_code}/0"
                    response = requests.get(hist_url, headers=DEFAULT_HEADERS)
                    if response.status_code != 200:
                        continue
                    
                    # Parse and process data
                    raw_data = response.json()['closingPriceDaily']
                    df = pd.DataFrame(raw_data)
                    df['Symbol'] = symbol
                    df['Date'] = pd.to_datetime(df['dEven'], format='%Y%m%d')
                    df = df.set_index('Date')
                    dfs.append(df)
                
                if not dfs:
                    logger.error("No data frames were created - check symbol names and API response")
                    return Result.fail("No historical data found on TSE")
                
                combined_df = pd.concat(dfs)
                logger.info(f"Successfully loaded data for {len(dfs)} symbols")
                return Result.ok(combined_df)
                
            except Exception as e:
                return Result.fail(f"TSE data download failed: {str(e)}")
        
        else:
            return Result.fail(f"Unsupported data source: {source}")
