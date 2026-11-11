"""Tokenized-gold (PAXG / XAUT) source provider.

The BrsApi crypto feed already carries the tokenized-gold assets — it labels
them with ``category = "goldCrypto"`` in the raw payload — so no extra market
data subscription is needed.  The spot price comes from the stored gold
snapshots (``gold_snapshots.xau_usd``), which keeps this feed free of any
extra network call and consistent with the stored-data macro posture.

Providers are injectable so tests never touch the network or a real database.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import select

from core.logging import get_logger

logger = get_logger(__name__)

#: Category tag the BrsApi crypto feed puts on tokenized-gold rows.
TOKENIZED_GOLD_CATEGORY = "goldCrypto"

#: Feed display name -> ticker. The crypto feed labels the tokenized-gold
#: assets by name, not by ticker, so the mapping is explicit.
TOKENIZED_GOLD_TICKERS: dict[str, str] = {
    "PAX Gold": "PAXG",
    "Tether Gold": "XAUT",
}

#: Indicator name used to store a token's premium against spot.
PREMIUM_INDICATOR_SUFFIX = "_PREMIUM_VS_SPOT"


class TokenizedGoldProvider(ABC):
    """A source of tokenized-gold quotes (one entry per token)."""

    name: str

    @abstractmethod
    async def fetch(self) -> list[dict[str, Any]]:
        """Return one dict per token::

            {
                "ticker": "PAXG",       # canonical ticker
                "symbol": "PAX Gold",   # feed display name
                "price_usd": 4143.0,    # token price per ounce
                "as_of": "2026-10-18",  # ISO date, when the feed provides one
            }
        """


class GoldSpotPriceProvider(ABC):
    """A source of the USD-per-troy-ounce gold spot price."""

    name: str

    @abstractmethod
    async def fetch(self) -> float | None:
        """Return the spot price, or ``None`` when it is unavailable."""


def _derive_ticker(symbol: str) -> str:
    """Derive a ticker from a feed display name (``Matrixdock Gold`` → ``MATRIXDOCK_GOLD``)."""
    cleaned = re.sub(r"[^0-9A-Za-z]+", "_", symbol).strip("_").upper()
    return cleaned


def _as_of_iso(row: Any) -> str | None:
    """Read the feed's fetch timestamp as an ISO date, when it has one."""
    raw = getattr(row, "fetched_at", None)
    if not raw:
        return None
    text = str(raw)[:10]
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return text
    return None


def parse_tokenized_gold_row(
    row: Any,
    *,
    tickers: dict[str, str] | None = None,
    category: str = TOKENIZED_GOLD_CATEGORY,
) -> dict[str, Any] | None:
    """Map one feed row to a tokenized-gold quote.

    Returns ``None`` when the row is not a tokenized-gold asset or carries no
    usable price.
    """
    mapping = TOKENIZED_GOLD_TICKERS if tickers is None else tickers

    raw = getattr(row, "raw_json", None)
    payload: dict[str, Any] = {}
    if raw:
        try:
            loaded = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            loaded = None
        if isinstance(loaded, dict):
            payload = loaded

    if payload.get("category") != category:
        return None

    price = getattr(row, "price_usd", None)
    if price is None:
        return None
    try:
        price_value = float(price)
    except (TypeError, ValueError):
        return None

    symbol = str(getattr(row, "symbol", "") or payload.get("name_en") or "").strip()
    ticker = mapping.get(symbol) or _derive_ticker(symbol)
    if not ticker:
        return None

    return {
        "ticker": ticker,
        "symbol": symbol,
        "price_usd": price_value,
        "as_of": _as_of_iso(row),
    }


class BrsApiTokenizedGoldProvider(TokenizedGoldProvider):
    """Read tokenized-gold quotes from the already-synced BrsApi crypto table.

    The BrsApi sync job keeps the crypto feed in ``brsapi_crypto_prices``;
    reading it here avoids a second market-data call.
    """

    name = "BrsApi"

    def __init__(
        self,
        session: Any,
        *,
        tickers: dict[str, str] | None = None,
        category: str = TOKENIZED_GOLD_CATEGORY,
    ) -> None:
        self._session = session
        self._tickers = dict(tickers if tickers is not None else TOKENIZED_GOLD_TICKERS)
        self._category = category

    async def fetch(self) -> list[dict[str, Any]]:
        from brsapi.models.crypto import CryptoPriceModel

        statement = (
            select(CryptoPriceModel)
            .where(CryptoPriceModel.raw_json.ilike(f"%{self._category}%"))
            .order_by(CryptoPriceModel.price_usd.desc())
        )
        result = await self._session.execute(statement)
        quotes: list[dict[str, Any]] = []
        for row in result.scalars().all():
            quote = parse_tokenized_gold_row(
                row, tickers=self._tickers, category=self._category
            )
            if quote is not None:
                quotes.append(quote)
        return quotes


class StoredGoldSpotProvider(GoldSpotPriceProvider):
    """Latest stored XAU/USD spot from the gold snapshot table."""

    name = "gold_snapshots"

    def __init__(self, session: Any) -> None:
        self._session = session

    async def fetch(self) -> float | None:
        try:
            from src.gold_desk.models import GoldSnapshotModel
        except Exception:  # pragma: no cover - optional surface
            logger.warning("Gold snapshot model unavailable", exc_info=True)
            return None

        statement = (
            select(GoldSnapshotModel)
            .where(GoldSnapshotModel.xau_usd.isnot(None))
            .order_by(GoldSnapshotModel.snapshot_at.desc())
            .limit(1)
        )
        result = await self._session.execute(statement)
        row = result.scalars().first()
        if row is None:
            return None
        try:
            return float(row.xau_usd)
        except (TypeError, ValueError):
            return None


def compute_tokenized_gold_premium(
    token_price_usd: float, spot_price_usd: float | None
) -> float | None:
    """Premium of the token over spot, in percent (negative = discount)."""
    if spot_price_usd is None or spot_price_usd <= 0:
        return None
    return round((token_price_usd / spot_price_usd - 1.0) * 100.0, 6)


__all__ = [
    "PREMIUM_INDICATOR_SUFFIX",
    "TOKENIZED_GOLD_CATEGORY",
    "TOKENIZED_GOLD_TICKERS",
    "BrsApiTokenizedGoldProvider",
    "GoldSpotPriceProvider",
    "StoredGoldSpotProvider",
    "TokenizedGoldProvider",
    "compute_tokenized_gold_premium",
    "parse_tokenized_gold_row",
]
