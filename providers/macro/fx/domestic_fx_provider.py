"""Iranian domestic FX rates (USD/IRR, AED/IRR) from TGJU.org.

Replaces the api.example.com placeholder with the real call3.tgju.org feed.
Prices are in Tomans (1 Toman = 10 Rials; TGJU _rl slugs are converted).
"""

from __future__ import annotations

from typing import Any

import httpx

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.macro_sources.tgju import TGJUClient

logger = get_logger(__name__)

IRANIAN_CURRENCY_PAIRS = ["USD_IRR", "EUR_IRR", "GBP_IRR", "TRY_IRR", "AED_IRR", "CNY_IRR"]

_FX_SLUGS = ["price_dollar_rl", "price_aed"]


class DomesticFXProvider(BaseProvider):
    """Live Iranian FX rates via TGJU JSON feed.

    Returns USD and AED rates in Tomans.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(name="domestic_fx")
        self._tgju = TGJUClient(client=client)

    async def fetch(self, pair: str | None = None, **kwargs: Any) -> Result[Any]:
        slugs = _FX_SLUGS
        if pair:
            pair_to_slug = {
                "USD_IRR": "price_dollar_rl",
                "AED_IRR": "price_aed",
            }
            slug = pair_to_slug.get(pair.upper())
            if slug:
                slugs = [slug]
            else:
                return Result.fail(f"Unknown FX pair: {pair!r} (supported: USD_IRR, AED_IRR)")

        quotes = await self._tgju.fetch(slugs)
        if not quotes:
            return Result.fail("TGJU returned no FX rates")

        data = [
            {
                "symbol": q.symbol,
                "slug": q.slug,
                "price_toman": q.price,
                "unit": q.unit,
                "fetched_at": q.fetched_at.isoformat(),
            }
            for q in quotes
        ]
        return Result.ok(data)

    async def health(self) -> dict[str, Any]:
        quotes = await self._tgju.fetch(["price_dollar_rl"])
        if quotes and quotes[0].price > 0:
            return {"healthy": True, "message": f"USD={quotes[0].price:.0f} Toman"}
        return {"healthy": False, "message": "TGJU FX rate unavailable"}
