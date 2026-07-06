from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)

MOCK_INDICATORS: dict[str, dict[str, Any]] = {
    "inflation": {"name": "نرخ تورم", "value": 31.2, "unit": "%", "date": "1403-06", "change": -0.8},
    "gdp": {"name": "تولید ناخالص داخلی", "value": 4250, "unit": "هزار میلیارد ریال", "date": "1402", "change": 4.2},
    "unemployment": {"name": "نرخ بیکاری", "value": 8.9, "unit": "%", "date": "1403-03", "change": -0.3},
    "oil_price": {"name": "قیمت نفت برنت", "value": 82.5, "unit": "دلار", "date": "1403-06-30", "change": 1.2},
    "gold_ounce": {"name": "قیمت طلا (اونس)", "value": 2340, "unit": "دلار", "date": "1403-06-30", "change": 15.0},
    "dollar": {"name": "نرخ دلار", "value": 58500, "unit": "ریال", "date": "1403-06-30", "change": -200},
    "eur": {"name": "نرخ یورو", "value": 63500, "unit": "ریال", "date": "1403-06-30", "change": -150},
    "interest_rate": {"name": "نرخ بهره بانکی", "value": 23.0, "unit": "%", "date": "1403-06", "change": 0},
}


class MacroService:
    def __init__(self, brsapi_query_service: Any | None = None, brsapi_client: Any = None) -> None:
        self._brsapi = brsapi_query_service
        self._client = brsapi_client

    async def list_indicators(self) -> Result[list[str]]:
        return Result.ok(list(MOCK_INDICATORS.keys()))

    async def get_indicator(self, indicator: str) -> Result[dict[str, Any]]:
        if indicator in MOCK_INDICATORS:
            return Result.ok(MOCK_INDICATORS[indicator])
        return Result.fail(f"Indicator {indicator} not found")

    async def get_history(self, indicator: str, limit: int = 100) -> Result[list[dict[str, Any]]]:
        if self._brsapi and indicator in ("dollar", "eur", "gold"):
            try:
                if indicator == "gold":
                    data = await self._brsapi.get_gold_coin_prices()
                else:
                    data = await self._brsapi.get_currency_prices()
                if data:
                    return Result.ok(data[:limit])
            except Exception as e:
                logger.exception("Failed to fetch macro history")
        # Live fallback: fetch gold/currency from BrsApi API
        if self._client and indicator in ("dollar", "eur", "gold"):
            try:
                data = await self._fetch_live_history(indicator)
                if data:
                    return Result.ok(data[:limit])
            except Exception:
                logger.exception("Live fetch for macro history failed")
        return Result.ok([])

    async def _fetch_live_history(self, indicator: str) -> list[dict[str, Any]]:
        """Fetch macro history directly from BrsApi API."""
        from brsapi.config import BrsApiEndpoints
        from brsapi.parsers import GoldCoinParser, CurrencyParser

        if indicator == "gold":
            result = await self._client.fetch(BrsApiEndpoints.GOLD_COIN)
            if result.success and result.value and result.value.data:
                parsed = GoldCoinParser.parse(result.value.data)
                if isinstance(parsed, list):
                    return parsed
        else:
            result = await self._client.fetch(BrsApiEndpoints.CURRENCY)
            if result.success and result.value and result.value.data:
                parsed = CurrencyParser.parse(result.value.data)
                if isinstance(parsed, list):
                    return parsed
        return []

    async def save(self, data: dict[str, Any]) -> Result[dict[str, Any]]:
        return Result.ok(data)
