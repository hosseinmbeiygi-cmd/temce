"""TSETMC Adapter — قیمت تابلو، حجم، سفارش‌ها.

طبق spec صندوق‌یار:
- فرکانس: لحظه‌ای/۱۵ دقیقه
- TTL: ۱۵ دقیقه
- Stale threshold: ۲ ساعت
- مرجع Source of Truth برای قیمت و حجم تابلو
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import AdapterError, AdapterParseError, BaseAdapter, SourceData

logger = logging.getLogger(__name__)

# URL دیده‌بان بازار TSETMC — طبق کد موجود در repo
TSETMC_MARKETWATCH_URL = "http://old.tsetmc.com/tsev2/data/MarketWatchPlus.aspx"
TSETMC_CLIENTTYPE_URL = "http://old.tsetmc.com/tsev2/data/clienttype.aspx"


class TSETMCAdapter(BaseAdapter):
    """Adapter برای TSETMC.

    در حالت واقعی از httpx.AsyncClient استفاده می‌کند.
    در این پیاده‌سازی، یک HTTP client تزریق‌پذیر گرفته می‌شود تا
    برای mock در تست ساده باشد.
    """

    name = "tsetmc"
    cache_ttl_seconds = 15 * 60
    stale_threshold_hours = 2

    def __init__(self, http_client: Any | None = None, **kwargs: Any):
        super().__init__(**kwargs)
        self._http = http_client  # expected to have async get(url, headers)

    async def fetch(self, symbol: str) -> SourceData:
        if self._http is None:
            # dev/test mode — برگرداندن داده خالی
            return SourceData(
                source=self.name,
                symbol=symbol,
                data={"price": None, "volume": None, "_dev_mode": True},
                confidence=0.0,
            )

        headers = {"User-Agent": "Temce/1.0 (+sandooghyar)"}
        try:
            resp = await asyncio.wait_for(
                self._http.get(TSETMC_MARKETWATCH_URL, headers=headers),
                timeout=10.0,
            )
        except TimeoutError as exc:
            raise AdapterError(f"TSETMC timeout: {exc}") from exc

        text = resp.text if hasattr(resp, "text") else str(resp)
        parsed = self._parse_market_watch(text, symbol)
        if parsed is None:
            raise AdapterParseError(f"Symbol {symbol} not found in TSETMC response")

        return SourceData(
            source=self.name,
            symbol=symbol,
            data=parsed,
        )

    async def fetch_client_type(self, ins_code: str) -> dict[str, Any]:
        """دریافت داده حقیقی/حقوقی برای یک نماد (ins_code)."""
        if self._http is None:
            return {"real_buy": 0, "real_sell": 0, "_dev_mode": True}
        url = f"{TSETMC_CLIENTTYPE_URL}?i={ins_code}"
        try:
            resp = await asyncio.wait_for(
                self._http.get(url, headers={"User-Agent": "Temce/1.0"}),
                timeout=10.0,
            )
        except TimeoutError as exc:
            raise AdapterError(f"TSETMC clienttype timeout: {exc}") from exc

        return self._parse_client_type(resp.text)

    def _parse_market_watch(self, text: str, symbol: str) -> dict[str, Any] | None:
        """پارس کردن پاسخ CSV-like TSETMC.

        فرمت: هر ردیف با ; جدا شده، فیلدها با ,
        field[3] = symbol, field[6] = last price, field[9] = volume
        """
        rows = text.split(";")
        for row in rows:
            fields = row.split(",")
            if len(fields) > 18 and fields[3] == symbol:
                try:
                    return {
                        "symbol": fields[3],
                        "name": fields[2],
                        "last_price": int(fields[6]) if fields[6].isdigit() else 0,
                        "close_price": int(fields[7]) if fields[7].isdigit() else 0,
                        "volume": int(fields[9]) if fields[9].isdigit() else 0,
                        "trade_value": int(fields[10]) if fields[10].isdigit() else 0,
                        "group_id": fields[18] if len(fields) > 18 else None,
                    }
                except (ValueError, IndexError) as exc:
                    raise AdapterParseError(f"TSETMC parse error: {exc}") from exc
        return None

    def _parse_client_type(self, text: str) -> dict[str, Any]:
        # ساختار نمونه: "buy_i_volume,sell_i_volume,buy_n_volume,sell_n_volume,..."
        try:
            parts = text.split(";")
            if len(parts) < 3:
                return {"real_buy": 0, "real_sell": 0, "legal_buy": 0, "legal_sell": 0}
            real = parts[0].split(",")
            legal = parts[1].split(",")
            return {
                "real_buy": int(real[0]) if real[0].isdigit() else 0,
                "real_sell": int(real[1]) if len(real) > 1 and real[1].isdigit() else 0,
                "legal_buy": int(legal[0]) if legal[0].isdigit() else 0,
                "legal_sell": int(legal[1]) if len(legal) > 1 and legal[1].isdigit() else 0,
            }
        except (ValueError, IndexError):
            return {"real_buy": 0, "real_sell": 0, "legal_buy": 0, "legal_sell": 0}
