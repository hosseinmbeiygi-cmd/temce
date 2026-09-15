from __future__ import annotations

from typing import Any

import httpx

from core.config import settings
from core.result import Result


class TsetmcClient:
    """
    Async client for TSETMC CDN API (cdn.tsetmc.com/api).

    All endpoints return raw JSON responses wrapped in Result.
    """

    BASE_URL = "https://cdn.tsetmc.com/api"

    def __init__(self, timeout: float | None = None) -> None:
        self._timeout = timeout or float(settings.provider_default_timeout)

    # ── Internal helpers ──────────────────────────────

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Result[dict[str, Any] | list[Any]]:
        url = f"{self.BASE_URL}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)
            if response.status_code != 200:
                return Result.fail(f"TSETMC error {response.status_code}: {response.text[:200]}")
            data = response.json()
            if data is None:
                return Result.fail("Empty response from TSETMC")
            return Result.ok(data)
        except httpx.TimeoutException:
            return Result.fail("TSETMC request timeout")
        except httpx.HTTPError as exc:
            return Result.fail(f"TSETMC HTTP error: {exc}")
        except Exception as exc:
            return Result.fail(f"TSETMC unexpected error: {exc}")

    # ── Instrument endpoints ──────────────────────────

    async def get_instrument_list(self) -> Result[list[dict[str, Any]]]:
        """لیست تمام نمادهای بورس"""
        result = await self._get("/Instrument/GetInstrumentList")
        if result.is_ok:
            data = result.value
            instruments = data if isinstance(data, list) else data.get("instrument", data.get("instruments", []))
            return Result.ok(instruments)
        return result  # type: ignore[return-value]

    async def get_instrument_info(self, ins_code: str) -> Result[dict[str, Any]]:
        """اطلاعات پایه یک نماد"""
        return await self._get(f"/Instrument/GetInstrumentInfo/{ins_code}")

    async def get_instrument_identity(self, ins_code: str) -> Result[dict[str, Any]]:
        """شناسایی کامل یک نماد"""
        return await self._get(f"/Instrument/GetInstrumentIdentity/{ins_code}")

    # ── Closing Price endpoints ───────────────────────

    async def get_closing_price_info(self, ins_code: str) -> Result[dict[str, Any]]:
        """آخرین اطلاعات قیمت پایانی یک نماد (همان GetClosingPriceInfo)"""
        return await self._get(f"/ClosingPrice/GetClosingPriceInfo/{ins_code}")

    async def get_closing_price_history(self, ins_code: str) -> Result[dict[str, Any]]:
        """تاریخچه کامل قیمت‌های پایانی یک نماد"""
        return await self._get(f"/ClosingPrice/GetClosingPriceHistory/{ins_code}")

    async def get_closing_price_daily(self, ins_code: str, date: str) -> Result[dict[str, Any]]:
        """قیمت پایانی یک روز خاص (date: 8-digit YYYYMMDD)"""
        return await self._get(f"/ClosingPrice/GetClosingPriceDaily/{ins_code}/{date}")

    async def get_closing_price_daily_list(self, ins_code: str, top: int = 10) -> Result[dict[str, Any]]:
        """لیست آخرین قیمت‌های روزانه"""
        return await self._get(f"/ClosingPrice/GetClosingPriceDailyList/{ins_code}/{top}")

    # ── Market Data endpoints ─────────────────────────

    async def get_market_data(self) -> Result[dict[str, Any]]:
        """داده‌های لحظه‌ای بازار (شاخص کل، حجم، ارزش)"""
        return await self._get("/MarketData/MarketData")

    async def get_market_watch(self) -> Result[dict[str, Any]]:
        """نمای کلی بازار (MarketWatch)"""
        return await self._get("/ClosingPrice/GetMarketWatch")

    async def get_market_map(self) -> Result[dict[str, Any]]:
        """نقشه بازار (Market Map) با پارامترهای پیش‌فرض"""
        return await self._get(
            "/ClosingPrice/GetMarketMap", params={"market": 0, "size": 1920, "sector": 0, "typeSelected": 0, "hEven": 0}
        )

    async def get_instrument_statistic(self, ins_code: str) -> Result[dict[str, Any]]:
        """آمار یک نماد"""
        return await self._get(f"/MarketData/GetInstrumentStatistic/{ins_code}")

    # ── Order Book (Best Limits) ──────────────────────

    async def get_order_book(self, ins_code: str) -> Result[dict[str, Any]]:
        """مظنه خرید و فروش (بهترین حدود قیمت)"""
        return await self._get(f"/BestLimits/{ins_code}/0")

    # ── Trade endpoints ───────────────────────────────

    async def get_trades(self, ins_code: str) -> Result[dict[str, Any]]:
        """معاملات امروز یک نماد"""
        return await self._get(f"/Trade/GetTrade/{ins_code}")

    async def get_trades_intraday(self, ins_code: str) -> Result[dict[str, Any]]:
        """معاملات درون‌روز (intraday) یک نماد"""
        return await self._get(f"/Trade/GetTradeIntraDay/{ins_code}")

    async def get_trade_history(self, ins_code: str, date: str, grouped: bool = False) -> Result[dict[str, Any]]:
        """تاریخچه معاملات یک روز مشخص"""
        return await self._get(f"/Trade/GetTradeHistory/{ins_code}/{date}/{str(grouped).lower()}")

    # ── Client Type (حقیقی/حقوقی) ─────────────────────

    async def get_client_type(self, ins_code: str) -> Result[dict[str, Any]]:
        """خرید/فروش حقیقی و حقوقی امروز"""
        return await self._get(f"/ClientType/GetClientType/{ins_code}/true/0")

    async def get_client_type_history(self, ins_code: str) -> Result[dict[str, Any]]:
        """تاریخچه خرید/فروش حقیقی و حقوقی"""
        return await self._get(f"/ClientType/GetClientTypeHistory/{ins_code}")

    # ── Shareholder endpoints ─────────────────────────

    async def get_shareholders(self, ins_code: str) -> Result[dict[str, Any]]:
        """آخرین اطلاعات سهامداران"""
        return await self._get(f"/Shareholder/GetInstrumentShareHolderLast/{ins_code}")

    # ── Calendar / Schedule ───────────────────────────

    async def get_instrument_calendar(self, ins_code: str) -> Result[dict[str, Any]]:
        """تقویم معاملاتی نماد"""
        return await self._get(f"/ClosingPrice/GetInstrumentCalendar/{ins_code}")
