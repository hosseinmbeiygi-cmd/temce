"""BrsApi History Fetch Service — fetches historical data from Gold_Currency_Pro.php.

Uses requests (sync) in thread executor — mirrors the tested Python scripts exactly.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

import requests
import urllib3

from brsapi.config import get_brsapi_settings
from core.logging import get_logger

logger = get_logger(__name__)

_brsapi_settings = get_brsapi_settings()
API_KEY = _brsapi_settings.api_key
BASE_URL = "https://api.brsapi.ir/Market/Gold_Currency_Pro.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

# TLS verification is enabled by default (secure). Only suppress the
# InsecureRequestWarning when the operator explicitly disabled verification
# via BRSAPI_VERIFY_SSL=false.
_VERIFY_SSL = _brsapi_settings.verify_ssl
if not _VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_executor = ThreadPoolExecutor(max_workers=2)

# Gold/coin symbols for table routing
GOLD_SYMBOLS = {
    "IR_GOLD_18K", "IR_GOLD_24K", "IR_GOLD_MELTED",
    "IR_COIN_1G", "IR_COIN_BAHAR", "IR_COIN_EMAMI",
    "IR_COIN_HALF", "IR_COIN_QUARTER",
}
GOLD_SYMBOLS.update({f"IR_PCOIN_{s}" for s in [
    "1-1G", "1-2G", "1-3G", "1-4G", "1-5G",
    "100MG", "1G", "200MG", "300MG", "400MG",
    "500MG", "600MG", "700MG", "800MG", "900MG",
]})


@dataclass
class FetchReport:
    symbol: str
    section: str
    record_count: int = 0
    success: bool = True
    error: str | None = None
    duration_ms: float = 0.0


def _fetch_symbol_list_sync(section: str) -> list[str]:
    """Fetch symbol list (sync, called in thread)."""
    params = {"key": API_KEY, "section": section}
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, verify=_VERIFY_SSL, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    symbols: list[str] = []
    if "gold" in data:
        for sub in ["ounce", "type", "coin", "coin_parsian"]:
            for item in data["gold"].get(sub, []):
                if "symbol" in item:
                    symbols.append(item["symbol"])
    if "currency" in data:
        for sub in ["free", "sana", "nima"]:
            for item in data["currency"].get(sub, []):
                if "symbol" in item:
                    symbols.append(item["symbol"])
    return sorted(set(symbols))


def _fetch_crypto_symbols_sync() -> list[str]:
    """Fetch crypto symbol list (sync, called in thread)."""
    params = {"key": API_KEY, "section": "cryptocurrency"}
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, verify=_VERIFY_SSL, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    symbols: list[str] = []
    if "cryptocurrency" in data:
        for item in data["cryptocurrency"]:
            if "symbol" in item:
                symbols.append(item["symbol"])
    return sorted(set(symbols))


def _fetch_history_sync(
    symbol: str,
    date_start: str = "1300-01-01",
    date_end: str = "1405-05-01",
) -> list[dict[str, Any]] | None:
    """Fetch history for one symbol (sync, called in thread)."""
    params = {
        "key": API_KEY,
        "history": 2,
        "symbol": symbol,
        "date_start": date_start,
        "date_end": date_end,
    }
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, verify=_VERIFY_SSL, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    records = data.get("history_daily") or data.get("result")
    if isinstance(records, list):
        return records
    return None


def _num(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("٬", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


class HistoryFetchService:
    """Fetches historical daily data from BrsApi.ir Gold_Currency_Pro endpoint."""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    async def fetch_symbol_list(self, section: str = "gold,currency") -> list[str]:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _fetch_symbol_list_sync, section)

    async def fetch_crypto_symbols(self) -> list[str]:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _fetch_crypto_symbols_sync)

    async def fetch_history(
        self, symbol: str,
        date_start: str = "1300-01-01",
        date_end: str = "1405-05-01",
    ) -> list[dict[str, Any]] | None:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, _fetch_history_sync, symbol, date_start, date_end,
        )

    async def sync_crypto_history(
        self,
        symbols: list[str] | None = None,
        limit: int = 0,
    ) -> list[FetchReport]:
        from sqlalchemy import text as sql_text

        if symbols is None:
            symbols = await self.fetch_crypto_symbols()
        if limit > 0:
            symbols = symbols[:limit]

        reports: list[FetchReport] = []
        for i, sym in enumerate(symbols):
            t0 = time.monotonic()
            try:
                records = await self.fetch_history(sym, "1390-01-01", "1405-05-01")
                dur = (time.monotonic() - t0) * 1000

                if not records:
                    reports.append(FetchReport(symbol=sym, section="crypto", duration_ms=dur))
                    continue

                inserted = 0
                if self._session:
                    for r in records:
                        date = str(r.get("date", "")).replace("/", "-")
                        o = _num(r.get("open"))
                        h = _num(r.get("high"))
                        low = _num(r.get("low"))
                        c = _num(r.get("close"))
                        v = _num(r.get("volume"))
                        if c is None or c <= 0:
                            continue
                        try:
                            await self._session.execute(sql_text("""
                                INSERT INTO brsapi_crypto_daily_history
                                    (symbol, date, price_open, price_high, price_low, price_close, volume)
                                VALUES (:sym, :date, :o, :h, :low, :c, :v)
                                ON CONFLICT (symbol, date) DO UPDATE SET
                                    price_open = EXCLUDED.price_open,
                                    price_high = EXCLUDED.price_high,
                                    price_low = EXCLUDED.price_low,
                                    price_close = EXCLUDED.price_close,
                                    volume = EXCLUDED.volume
                            """), {"sym": sym, "date": date, "o": o, "h": h, "low": low, "c": c, "v": v})
                            inserted += 1
                        except Exception:
                            pass
                    await self._session.commit()

                reports.append(FetchReport(
                    symbol=sym, section="crypto",
                    record_count=inserted, duration_ms=dur,
                ))
                logger.info("Crypto %s: %d rows (%.0fms)", sym, inserted, dur)

            except Exception as e:
                dur = (time.monotonic() - t0) * 1000
                reports.append(FetchReport(
                    symbol=sym, section="crypto",
                    success=False, error=str(e), duration_ms=dur,
                ))

            if i < len(symbols) - 1:
                import asyncio
                await asyncio.sleep(0.5)

        return reports

    async def sync_gold_currency_history(
        self,
        symbols: list[str] | None = None,
        limit: int = 0,
    ) -> list[FetchReport]:
        from sqlalchemy import text as sql_text

        if symbols is None:
            symbols = await self.fetch_symbol_list("gold,currency")
        if limit > 0:
            symbols = symbols[:limit]

        reports: list[FetchReport] = []
        for i, sym in enumerate(symbols):
            t0 = time.monotonic()
            try:
                records = await self.fetch_history(sym, "1300-01-01", "1405-05-01")
                dur = (time.monotonic() - t0) * 1000

                if not records:
                    reports.append(FetchReport(symbol=sym, section="gold_currency", duration_ms=dur))
                    continue

                table = "brsapi_gold_coin_history" if sym in GOLD_SYMBOLS else "brsapi_gold_currency_pro_daily_history"
                inserted = 0
                if self._session:
                    for r in records:
                        date = str(r.get("date", "")).replace("/", "-")
                        o = _num(r.get("open"))
                        h = _num(r.get("high"))
                        low = _num(r.get("low"))
                        c = _num(r.get("close"))
                        if c is None or c <= 0:
                            continue
                        try:
                            await self._session.execute(sql_text(f"""
                                INSERT INTO {table}
                                    (symbol, date, price_open, price_high, price_low, price_close)
                                VALUES (:sym, :date, :o, :h, :low, :c)
                                ON CONFLICT (symbol, date) DO UPDATE SET
                                    price_open = EXCLUDED.price_open,
                                    price_high = EXCLUDED.price_high,
                                    price_low = EXCLUDED.price_low,
                                    price_close = EXCLUDED.price_close
                            """), {"sym": sym, "date": date, "o": o, "h": h, "low": low, "c": c})
                            inserted += 1
                        except Exception:
                            pass
                    await self._session.commit()

                reports.append(FetchReport(
                    symbol=sym, section="gold_currency",
                    record_count=inserted, duration_ms=dur,
                ))
                logger.info("Gold/Currency %s → %s: %d rows (%.0fms)", sym, table, inserted, dur)

            except Exception as e:
                dur = (time.monotonic() - t0) * 1000
                reports.append(FetchReport(
                    symbol=sym, section="gold_currency",
                    success=False, error=str(e), duration_ms=dur,
                ))

            if i < len(symbols) - 1:
                import asyncio
                await asyncio.sleep(0.5)

        return reports
