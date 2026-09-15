"""Codal Adapter — ترکیب پرتفوی ماهانه، تغییر مدیر، اطلاعیه‌ها.

طبق spec صندوق‌یار:
- فرکانس: روزانه/رویدادمحور
- TTL: ۱۲ ساعت + رویدادمحور
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import AdapterError, AdapterParseError, BaseAdapter, SourceData

logger = logging.getLogger(__name__)

CODAL_PORTFOLIO_URL = "https://codal.ir/api/v1/Reports/Portfolio"
CODAL_MANAGER_CHANGE_URL = "https://codal.ir/api/v1/Reports/FundManagerHistory"


class CodalAdapter(BaseAdapter):
    name = "codal"
    cache_ttl_seconds = 12 * 3600
    stale_threshold_hours = 36

    def __init__(self, http_client: Any | None = None, **kwargs: Any):
        super().__init__(**kwargs)
        self._http = http_client

    async def fetch(self, symbol: str) -> SourceData:
        """برای Codal، fetch پیش‌فرض ترکیب پرتفوی است."""
        return await self.fetch_portfolio(symbol)

    async def fetch_portfolio(self, symbol: str) -> SourceData:
        if self._http is None:
            return SourceData(
                source=self.name,
                symbol=symbol,
                data={"holdings": [], "_dev_mode": True},
                confidence=0.0,
            )

        try:
            resp = await asyncio.wait_for(
                self._http.get(
                    CODAL_PORTFOLIO_URL,
                    params={"symbol": symbol},
                ),
                timeout=15.0,
            )
        except TimeoutError as exc:
            raise AdapterError(f"Codal timeout: {exc}") from exc

        try:
            payload = resp.json() if hasattr(resp, "json") else {}
        except Exception as exc:
            raise AdapterParseError(f"Codal parse: {exc}") from exc

        holdings = payload.get("holdings", [])
        normalized_holdings = [
            {
                "ticker": h.get("ticker"),
                "name": h.get("name"),
                "weight": h.get("weight"),
                "shares": h.get("shares"),
                "value": h.get("value"),
            }
            for h in holdings
        ]
        return SourceData(
            source=self.name,
            symbol=symbol,
            data={
                "holdings": normalized_holdings,
                "report_date": payload.get("reportDate"),
            },
        )

    async def fetch_manager_history(self, symbol: str) -> list[dict[str, Any]]:
        if self._http is None:
            return []
        try:
            resp = await asyncio.wait_for(
                self._http.get(
                    CODAL_MANAGER_CHANGE_URL,
                    params={"symbol": symbol},
                ),
                timeout=15.0,
            )
        except TimeoutError as exc:
            raise AdapterError(f"Codal manager history: {exc}") from exc

        try:
            data = resp.json() if hasattr(resp, "json") else []
        except Exception:
            return []

        return [
            {
                "manager": item.get("manager"),
                "started_at": item.get("startDate"),
                "ended_at": item.get("endDate"),
            }
            for item in data
        ]
