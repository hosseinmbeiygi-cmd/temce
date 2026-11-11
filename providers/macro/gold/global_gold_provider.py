"""International gold and precious metal spot prices.

Priority chain for XAU/USD:
  1. goldapi.io  — if ``GOLDAPI_KEY`` env var is set (accurate spot price)
  2. OKX PAXG/USDT — free, no key, real-time (blocked on Binance from Iran)
  3. Yahoo Finance GC=F — free, no key, 15-min delayed futures

For XAG/USD (silver) and XPT/USD (platinum), goldapi.io is used if key is
configured; otherwise these symbols are unavailable.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from src.gold_desk.goldapi_client import (
    fetch_paxg_binance,
    fetch_xau_usd,
    get_goldapi_key,
)

logger = get_logger(__name__)

GLOBAL_GOLD_BENCHMARKS = ["XAU_USD", "XAG_USD", "XPT_USD"]

# Yahoo Finance GC=F chart endpoint (no key required)
_YF_GCF_URL = "https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF"
_YF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0",
    "Accept": "application/json",
}
_YF_TIMEOUT = 6.0


async def _fetch_gcf_yahoo(client: httpx.AsyncClient | None = None) -> float | None:
    """Latest GC=F (COMEX gold futures) price from Yahoo Finance."""
    close_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=_YF_TIMEOUT, follow_redirects=True)
    try:
        resp = await client.get(
            _YF_GCF_URL,
            params={"interval": "1m", "range": "1d"},
            headers=_YF_HEADERS,
        )
        resp.raise_for_status()
        payload = resp.json()
        result = payload["chart"]["result"][0]
        price = (result.get("meta") or {}).get("regularMarketPrice")
        if price and float(price) > 0:
            return float(price)
        return None
    except Exception as exc:
        logger.warning("Yahoo Finance GC=F failed: %s", exc)
        return None
    finally:
        if close_client:
            await client.aclose()


async def _fetch_xag_goldapi(key: str, client: httpx.AsyncClient | None = None) -> float | None:
    """Silver (XAG/USD) spot price from goldapi.io."""
    close_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=8.0)
    try:
        resp = await client.get(
            "https://www.goldapi.io/api/XAG/USD",
            headers={"x-access-token": key, "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        price = data.get("price")
        if price and float(price) > 0:
            return float(price)
        return None
    except Exception as exc:
        logger.warning("goldapi.io XAG/USD failed: %s", exc)
        return None
    finally:
        if close_client:
            await client.aclose()


async def _fetch_xpt_goldapi(key: str, client: httpx.AsyncClient | None = None) -> float | None:
    """Platinum (XPT/USD) spot price from goldapi.io."""
    close_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=8.0)
    try:
        resp = await client.get(
            "https://www.goldapi.io/api/XPT/USD",
            headers={"x-access-token": key, "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        price = data.get("price")
        if price and float(price) > 0:
            return float(price)
        return None
    except Exception as exc:
        logger.warning("goldapi.io XPT/USD failed: %s", exc)
        return None
    finally:
        if close_client:
            await client.aclose()


class GlobalGoldProvider(BaseProvider):
    """International spot prices for gold, silver and platinum.

    Inject ``http_client`` for testing; production uses real httpx.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        super().__init__(name="global_gold")
        self._http_client = http_client

    async def fetch(self, benchmark: str | None = None, **kwargs: Any) -> Result[Any]:
        key = get_goldapi_key()
        results: dict[str, float | None] = {}

        # XAU/USD — priority: goldapi.io → OKX PAXG → Yahoo Finance GC=F
        xau: float | None = None
        if key:
            xau = await fetch_xau_usd(key, client=self._http_client)
        if xau is None:
            xau = await fetch_paxg_binance(client=self._http_client)
        if xau is None:
            xau = await _fetch_gcf_yahoo(client=self._http_client)
        results["XAU_USD"] = xau

        if benchmark is None or benchmark.upper() in ("XAG_USD", "ALL"):
            results["XAG_USD"] = await _fetch_xag_goldapi(key, client=self._http_client) if key else None

        if benchmark is None or benchmark.upper() in ("XPT_USD", "ALL"):
            results["XPT_USD"] = await _fetch_xpt_goldapi(key, client=self._http_client) if key else None

        if benchmark and benchmark.upper() == "XAU_USD":
            results = {"XAU_USD": results["XAU_USD"]}

        if results.get("XAU_USD") is None:
            return Result.fail("All XAU/USD sources unavailable")

        data = [
            {"benchmark": k, "price_usd": v}
            for k, v in results.items()
            if v is not None
        ]
        return Result.ok(data)

    async def health(self) -> dict[str, Any]:
        key = get_goldapi_key()
        xau: float | None = None
        if key:
            xau = await fetch_xau_usd(key, client=self._http_client)
        if xau is None:
            xau = await fetch_paxg_binance(client=self._http_client)
        if xau:
            return {"healthy": True, "message": f"XAU/USD={xau:.2f}"}
        return {"healthy": False, "message": "No XAU/USD source available"}
