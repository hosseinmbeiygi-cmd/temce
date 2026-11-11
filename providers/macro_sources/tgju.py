"""TGJU.org JSON price feed — single-request Iranian market data.

Endpoint: ``https://call3.tgju.org/ajax.json``
No API key required; accessible from Iranian IP without VPN.

Provides:
  - 18K and 24K gold gram prices
  - Coin prices: Emami (sekee), Bahar Azadi (sekeb), half (nim), quarter (rob)
  - USD/IRR and AED/IRR exchange rates
  - International gold oz price (USD) as a cross-check

Units (as of 2026-11): ALL prices in the ``current`` section are in RIALS.
Multiply every value by 0.1 to get Tomans.

API change log:
  2026-11: response key changed ``market`` → ``current``;
           coin slugs renamed coin-emami→sekee, coin-bahar→sekeb,
           coin-half→nim, coin-quarter→rob;
           gold gram prices changed from Tomans to Rials.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TGJU_AJAX_URL = "https://call3.tgju.org/ajax.json"
DEFAULT_TIMEOUT_SECONDS: float = 8.0

# Persian/Arabic → ASCII digit translation table
_PERSIAN_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# IRR → Toman conversion: TGJU '_rl' slugs are quoted in Rials
_RIAL_TO_TOMAN: float = 0.1


def _to_float(raw: str | int | float | None) -> float | None:
    """Parse a price string (possibly with Persian digits and commas) → float."""
    if raw is None:
        return None
    try:
        cleaned = str(raw).translate(_PERSIAN_MAP).replace(",", "").replace("٬", "").replace("%", "")
        cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
        if not cleaned or cleaned in (".", "-", "-."):
            return None
        return float(cleaned)
    except (ValueError, TypeError):
        return None


@dataclass(frozen=True)
class TGJUQuote:
    """One price observation from tgju.org."""

    symbol: str           # canonical symbol (e.g. IR_GOLD_18K_GRAM)
    slug: str             # tgju market key (e.g. geram18)
    price: float          # price in unit
    unit: str             # "toman" | "usd"
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# Maps tgju ``current`` key → (canonical symbol, unit, rial_to_toman factor)
# As of 2026-11 ALL prices in the current section are in Rials → factor=0.1.
# ``ons`` (international gold oz) is in USD → factor=1.0.
TGJU_PRICE_MAP: dict[str, tuple[str, str, float]] = {
    "geram18":          ("IR_GOLD_18K_GRAM",  "toman", _RIAL_TO_TOMAN),
    "geram24":          ("IR_GOLD_24K_GRAM",  "toman", _RIAL_TO_TOMAN),
    "sekee":            ("IR_COIN_EMAMI",      "toman", _RIAL_TO_TOMAN),  # renamed from coin-emami
    "sekeb":            ("IR_COIN_BAHAR",      "toman", _RIAL_TO_TOMAN),  # renamed from coin-bahar
    "nim":              ("IR_COIN_HALF",       "toman", _RIAL_TO_TOMAN),  # renamed from coin-half
    "rob":              ("IR_COIN_QUARTER",    "toman", _RIAL_TO_TOMAN),  # renamed from coin-quarter
    "price_dollar_rl":  ("USD",               "toman", _RIAL_TO_TOMAN),
    "price_aed":        ("AED",               "toman", _RIAL_TO_TOMAN),
    "ons":              ("XAUUSD",            "usd",   1.0),
}


class TGJUClient:
    """Fetch all Iranian market prices from tgju.org's JSON feed.

    Inject ``client`` in tests to avoid real network calls.
    """

    def __init__(
        self,
        *,
        url: str = TGJU_AJAX_URL,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._url = url
        self._client = client
        self._timeout_seconds = timeout_seconds

    async def fetch(
        self,
        slugs: list[str] | None = None,
    ) -> list[TGJUQuote]:
        """Fetch prices from tgju.org for the given slugs (all if None).

        Returns only slugs that appear in TGJU_PRICE_MAP and have a valid price.
        """
        targets = slugs if slugs is not None else list(TGJU_PRICE_MAP.keys())
        close_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=True,
        )
        try:
            resp = await client.get(
                self._url,
                headers={"User-Agent": "Mozilla/5.0 (Temce GoldDesk)"},
            )
            resp.raise_for_status()
            payload: dict[str, Any] = resp.json()
        except Exception as exc:
            logger.warning("TGJU fetch failed: %s", exc)
            return []
        finally:
            if close_client:
                await client.aclose()

        # 2026-11: TGJU renamed the top-level key from "market" to "current"
        market: dict[str, Any] = payload.get("current") or payload.get("market") or {}
        quotes: list[TGJUQuote] = []
        for slug in targets:
            if slug not in TGJU_PRICE_MAP:
                continue
            entry = market.get(slug) or {}
            raw_price = entry.get("p")
            price = _to_float(raw_price)
            if price is None or price <= 0:
                logger.debug("TGJU: no valid price for slug=%s raw=%r", slug, raw_price)
                continue
            canonical, unit, factor = TGJU_PRICE_MAP[slug]
            quotes.append(TGJUQuote(
                symbol=canonical,
                slug=slug,
                price=round(price * factor, 2),
                unit=unit,
            ))
        return quotes

    async def fetch_as_dict(
        self,
        slugs: list[str] | None = None,
    ) -> dict[str, float]:
        """Return {canonical_symbol: price} for convenience."""
        quotes = await self.fetch(slugs)
        return {q.symbol: q.price for q in quotes}


# ── Convenience top-level function (matches secondary_source.py interface) ──

async def fetch_tgju_json(
    slugs: list[str] | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[TGJUQuote]:
    """Convenience wrapper — single call, no instance required."""
    return await TGJUClient(client=client).fetch(slugs)
