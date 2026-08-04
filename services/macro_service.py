from __future__ import annotations

from datetime import date
from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)

# Macro economic indicators that require government/central bank data
# These are updated periodically from official sources
MACRO_INDICATORS: dict[str, dict[str, Any]] = {
    "inflation": {"name": "نرخ تورم", "value": 31.2, "unit": "%", "date": "1403-06", "change": -0.8, "source": "مرکز آمار ایران"},
    "gdp": {"name": "تولید ناخالص داخلی", "value": 4250, "unit": "هزار میلیارد ریال", "date": "1402", "change": 4.2, "source": "بانک مرکزی"},
    "unemployment": {"name": "نرخ بیکاری", "value": 8.9, "unit": "%", "date": "1403-03", "change": -0.3, "source": "مرکز آمار ایران"},
    "interest_rate": {"name": "نرخ بهره بانکی", "value": 23.0, "unit": "%", "date": "1403-06", "change": 0, "source": "بانک مرکزی"},
}


class MacroService:
    def __init__(self, brsapi_query_service: Any | None = None, brsapi_client: Any = None) -> None:
        self._brsapi = brsapi_query_service
        self._client = brsapi_client

    async def list_indicators(self) -> Result[list[str]]:
        keys = list(MACRO_INDICATORS.keys())
        # Add live indicators if BrsApi is available
        if self._brsapi:
            keys.extend(["dollar", "eur", "gold_ounce", "oil_price"])
        return Result.ok(keys)

    async def get_indicator(self, indicator: str) -> Result[dict[str, Any]]:
        # Try live data first for tradeable indicators
        if self._brsapi and indicator in ("dollar", "eur", "gold_ounce", "oil_price"):
            live = await self._get_live_indicator(indicator)
            if live:
                return Result.ok(live)

        # Fallback to macro indicators
        if indicator in MACRO_INDICATORS:
            return Result.ok(MACRO_INDICATORS[indicator])
        return Result.fail(f"Indicator {indicator} not found")

    async def _get_live_indicator(self, indicator: str) -> dict[str, Any] | None:
        """Fetch real-time indicator value from BrsApi database."""
        try:
            if indicator == "dollar":
                currencies = await self._brsapi.get_currency_prices()
                for c in currencies:
                    if c.get("symbol", "").lower() in ("usd", "usdrial", "دلار"):
                        return {
                            "name": "نرخ دلار",
                            "value": c.get("price_close", c.get("price_last", 0)),
                            "unit": "ریال",
                            "date": date.today().isoformat(),
                            "change": c.get("close_change", 0),
                            "source": "BrsApi (لحظه‌ای)",
                        }
                # Try 24h data
                currencies_24h = await self._brsapi.get_currency_24h()
                for c in currencies_24h:
                    if c.get("symbol", "").lower() in ("usd", "usdrial", "دلار"):
                        return {
                            "name": "نرخ دلار",
                            "value": c.get("price_close", c.get("price_last", 0)),
                            "unit": "ریال",
                            "date": date.today().isoformat(),
                            "change": c.get("close_change", 0),
                            "source": "BrsApi (۲۴ ساعته)",
                        }

            elif indicator == "eur":
                currencies = await self._brsapi.get_currency_prices()
                for c in currencies:
                    if c.get("symbol", "").lower() in ("eur", "eurrial", "یورو"):
                        return {
                            "name": "نرخ یورو",
                            "value": c.get("price_close", c.get("price_last", 0)),
                            "unit": "ریال",
                            "date": date.today().isoformat(),
                            "change": c.get("close_change", 0),
                            "source": "BrsApi (لحظه‌ای)",
                        }
                currencies_24h = await self._brsapi.get_currency_24h()
                for c in currencies_24h:
                    if c.get("symbol", "").lower() in ("eur", "eurrial", "یورو"):
                        return {
                            "name": "نرخ یورو",
                            "value": c.get("price_close", c.get("price_last", 0)),
                            "unit": "ریال",
                            "date": date.today().isoformat(),
                            "change": c.get("close_change", 0),
                            "source": "BrsApi (۲۴ ساعته)",
                        }

            elif indicator == "gold_ounce":
                gold = await self._brsapi.get_gold_24h()
                for g in gold:
                    if g.get("symbol", "").lower() in ("اونس", "gold_ounce", "xauusd"):
                        return {
                            "name": "قیمت طلا (اونس)",
                            "value": g.get("price_close", g.get("price_last", 0)),
                            "unit": "دلار",
                            "date": date.today().isoformat(),
                            "change": g.get("close_change", 0),
                            "source": "BrsApi (۲۴ ساعته)",
                        }
                gold_coins = await self._brsapi.get_gold_coin_prices()
                for g in gold_coins:
                    if "18" in str(g.get("symbol", "")):
                        return {
                            "name": "قیمت طلا (اونس)",
                            "value": g.get("price_close", g.get("price_last", 0)),
                            "unit": "دلار",
                            "date": date.today().isoformat(),
                            "change": g.get("close_change", 0),
                            "source": "BrsApi (سکه)",
                        }

            elif indicator == "oil_price":
                commodities = await self._brsapi.get_commodity_prices(category="oil")
                for c in commodities:
                    if "برنت" in str(c.get("symbol", "")) or "brent" in str(c.get("symbol", "")).lower():
                        return {
                            "name": "قیمت نفت برنت",
                            "value": c.get("price_close", c.get("price_last", 0)),
                            "unit": "دلار",
                            "date": date.today().isoformat(),
                            "change": c.get("close_change", 0),
                            "source": "BrsApi (کامودیتی)",
                        }
                # Try any oil-related commodity
                commodities = await self._brsapi.get_commodity_prices()
                for c in commodities:
                    sym = str(c.get("symbol", "")).lower()
                    cat = str(c.get("category", "")).lower()
                    if "oil" in sym or "نفت" in sym or "oil" in cat:
                        return {
                            "name": "قیمت نفت",
                            "value": c.get("price_close", c.get("price_last", 0)),
                            "unit": "دلار",
                            "date": date.today().isoformat(),
                            "change": c.get("close_change", 0),
                            "source": "BrsApi (کامودیتی)",
                        }
        except Exception as e:
            logger.warning("Failed to fetch live indicator %s: %s", indicator, e)
        return None

    async def get_history(self, indicator: str, limit: int = 100) -> Result[list[dict[str, Any]]]:
        # For live indicators, try to get history from BrsApi
        if self._brsapi and indicator in ("dollar", "eur", "gold"):
            try:
                if indicator == "gold":
                    data = await self._brsapi.get_gold_coin_prices()
                else:
                    data = await self._brsapi.get_currency_prices()
                if data:
                    return Result.ok(data[:limit])
            except Exception:
                logger.exception("Failed to fetch macro history")

        # Live fallback: fetch from BrsApi API
        if self._client and indicator in ("dollar", "eur", "gold"):
            try:
                data = await self._fetch_live_history(indicator)
                if data:
                    return Result.ok(data[:limit])
            except Exception:
                logger.exception("Live fetch for macro history failed")
        return Result.ok([])

    async def _fetch_live_history(self, indicator: str) -> list[dict[str, Any]]:
        """Fetch macro history directly from BrsApi API using the combined Gold_Currency endpoint.

        The old /Market/Coin.php and /Market/Currency.php endpoints are deprecated (HTTP 404).
        Uses /Market/Gold_Currency.php which returns gold, currency & crypto in one call.
        """
        from brsapi.config import BrsApiEndpoints
        from brsapi.parsers import GoldCurrencyParser

        result = await self._client.fetch(BrsApiEndpoints.GOLD_CURRENCY)
        if not (result.success and result.value and result.value.data):
            return []

        data = result.value.data
        parsed = GoldCurrencyParser.parse_gold(data) if indicator == "gold" else GoldCurrencyParser.parse_currency(data)

        if isinstance(parsed, list):
            return parsed
        return []

    async def save(self, data: dict[str, Any]) -> Result[dict[str, Any]]:
        return Result.ok(data)
