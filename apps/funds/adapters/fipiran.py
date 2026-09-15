"""Fipiran Adapter — NAV رسمی، نوع صندوق، بازدهی دوره‌ای، آلفا/بتا.

طبق spec صندوق‌یار:
- فرکانس: روزانه
- TTL: ۲۴ ساعت
- Stale threshold: ۲۵ ساعت
- مرجع Source of Truth برای NAV رسمی
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import AdapterError, AdapterParseError, BaseAdapter, SourceData

logger = logging.getLogger(__name__)

FIPIRAN_FUND_LIST_URL = "https://fund.fipiran.ir/api/v1/funds"
FIPIRAN_FUND_DETAIL_URL = "https://fund.fipiran.ir/api/v1/funds/{symbol}"


class FipiranAdapter(BaseAdapter):
    """Adapter برای فیپیران.

    در حالت واقعی JSON API می‌زند. در dev/test یا بدون HTTP client
    داده خالی برمی‌گرداند تا سیستم قابل اجرا باشد.
    """

    name = "fipiran"
    cache_ttl_seconds = 24 * 3600
    stale_threshold_hours = 25

    def __init__(self, http_client: Any | None = None, **kwargs: Any):
        super().__init__(**kwargs)
        self._http = http_client

    async def fetch(self, symbol: str) -> SourceData:
        if self._http is None:
            return SourceData(
                source=self.name,
                symbol=symbol,
                data={
                    "nav_issue": None,
                    "nav_redeem": None,
                    "type_code": None,
                    "_dev_mode": True,
                },
                confidence=0.0,
            )

        url = FIPIRAN_FUND_DETAIL_URL.format(symbol=symbol)
        try:
            resp = await asyncio.wait_for(
                self._http.get(url, headers={"User-Agent": "Temce/1.0"}),
                timeout=10.0,
            )
        except TimeoutError as exc:
            raise AdapterError(f"Fipiran timeout: {exc}") from exc

        try:
            payload = resp.json() if hasattr(resp, "json") else {}
        except Exception as exc:
            raise AdapterParseError(f"Fipiran JSON parse error: {exc}") from exc

        return SourceData(
            source=self.name,
            symbol=symbol,
            data=self._normalize(payload),
        )

    async def fetch_fund_list(self) -> list[dict[str, Any]]:
        """دریافت لیست همه صندوق‌ها از فیپیران."""
        if self._http is None:
            return []
        try:
            resp = await asyncio.wait_for(
                self._http.get(FIPIRAN_FUND_LIST_URL),
                timeout=15.0,
            )
        except TimeoutError as exc:
            raise AdapterError(f"Fipiran list timeout: {exc}") from exc

        try:
            data = resp.json() if hasattr(resp, "json") else []
        except Exception as exc:
            raise AdapterParseError(f"Fipiran list parse: {exc}") from exc

        if not isinstance(data, list):
            return []
        return [self._normalize(item) for item in data]

    def _normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        """تبدیل schema فیپیران به schema داخلی صندوق‌یار."""
        return {
            "symbol": payload.get("symbol") or payload.get("shortName"),
            "name_fa": payload.get("name") or payload.get("fundName"),
            "type_code": payload.get("typeCode"),
            "nav_issue": payload.get("navIssue"),
            "nav_redeem": payload.get("navRedempt"),
            "aum_btoman": payload.get("netAsset") or payload.get("aum"),
            "daily_return": payload.get("dailyReturn"),
            "weekly_return": payload.get("weeklyReturn"),
            "monthly_return": payload.get("monthlyReturn"),
            "yearly_return": payload.get("yearlyReturn"),
            "inception_return": payload.get("inceptionReturn"),
            "alpha": payload.get("alpha"),
            "beta": payload.get("beta"),
            "sharpe": payload.get("sharpeRatio"),
            "inception_date": payload.get("inceptionDate"),
            "manager": payload.get("manager"),
        }
