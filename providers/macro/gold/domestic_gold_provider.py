"""Iranian domestic gold and coin prices from TGJU.org.

Replaces the api.example.com placeholder with the real call3.tgju.org feed.
Covers 18K/24K gold gram prices and all coin types in Tomans.
"""

from __future__ import annotations

from typing import Any

import httpx

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.macro_sources.tgju import TGJU_PRICE_MAP, TGJUClient

logger = get_logger(__name__)

IRANIAN_GOLD_TYPES = ["bahar_azadi", "nim_azadi", "rob_azadi", "gerami", "gold_coin", "gold_ingot"]

_GOLD_SLUGS = [
    "geram18",
    "geram24",
    "sekee",    # Emami full coin (renamed from coin-emami 2026-11)
    "sekeb",    # Bahar Azadi full coin (renamed from coin-bahar 2026-11)
    "nim",      # half coin (renamed from coin-half 2026-11)
    "rob",      # quarter coin (renamed from coin-quarter 2026-11)
]


class DomesticGoldProvider(BaseProvider):
    """Live Iranian gold/coin prices via TGJU JSON feed.

    Args:
        client: injectable httpx.AsyncClient for testing.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(name="domestic_gold")
        self._tgju = TGJUClient(client=client)

    async def fetch(self, gold_type: str | None = None, **kwargs: Any) -> Result[Any]:
        slugs = _GOLD_SLUGS
        if gold_type:
            # Map friendly gold_type strings to tgju slugs when possible
            type_map = {
                "bahar_azadi": "sekeb",
                "nim_azadi": "nim",
                "rob_azadi": "rob",
                "gerami": "sekee",
                "gold_coin": "sekee",
                "geram18": "geram18",
                "geram24": "geram24",
            }
            slug = type_map.get(gold_type)
            if slug:
                slugs = [slug]
            else:
                return Result.fail(f"Unknown gold_type: {gold_type!r}")

        quotes = await self._tgju.fetch(slugs)
        if not quotes:
            return Result.fail("TGJU returned no gold prices")

        data = [
            {
                "symbol": q.symbol,
                "slug": q.slug,
                "price": q.price,
                "unit": q.unit,
                "fetched_at": q.fetched_at.isoformat(),
            }
            for q in quotes
        ]
        return Result.ok(data)

    async def health(self) -> dict[str, Any]:
        quotes = await self._tgju.fetch(["geram18"])
        if quotes and quotes[0].price > 0:
            return {"healthy": True, "message": f"geram18={quotes[0].price:,.0f} Toman"}
        return {"healthy": False, "message": "TGJU gold price unavailable"}
