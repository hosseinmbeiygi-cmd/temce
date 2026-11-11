"""Unit tests for the tokenized-gold (PAXG / XAUT) premium feed.

The BrsApi crypto feed already carries the two tokenized-gold assets, tagged
``category = "goldCrypto"``; the spot price comes from the stored gold
snapshots.  No network and no real database — the session is mocked.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from providers.macro_sources.tokenized_gold import (
    TOKENIZED_GOLD_CATEGORY,
    TOKENIZED_GOLD_TICKERS,
    BrsApiTokenizedGoldProvider,
    StoredGoldSpotProvider,
    compute_tokenized_gold_premium,
    parse_tokenized_gold_row,
)
from services.gold.macro_sync import MacroSyncService


def _feed_row(
    symbol: str = "PAX Gold",
    price_usd: float | None = 4143.0,
    category: str = "goldCrypto",
    fetched_at: str = "2026-10-18T20:41:09.612Z",
    name_en: str | None = None,
):
    """A BrsApi crypto row as the feed delivers it."""
    row = MagicMock()
    row.symbol = symbol
    row.price_usd = price_usd
    row.fetched_at = fetched_at
    row.raw_json = json.dumps(
        {
            "name_en": name_en or symbol,
            "category": category,
            "price": price_usd,
        }
    )
    return row


def _make_session(rows=None, spot=None):
    session = MagicMock()
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = list(rows or [])
    scalars.first.return_value = spot
    result.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


# ── Pure parsing ──────────────────────────────────────────────────────────


def test_parse_tokenized_gold_row_maps_ticker() -> None:
    quote = parse_tokenized_gold_row(
        _feed_row(), tickers=TOKENIZED_GOLD_TICKERS, category=TOKENIZED_GOLD_CATEGORY
    )

    assert quote is not None
    assert quote["ticker"] == "PAXG"
    assert quote["symbol"] == "PAX Gold"
    assert quote["price_usd"] == 4143.0
    assert quote["as_of"] == "2026-10-18"


def test_parse_tokenized_gold_row_rejects_other_category() -> None:
    quote = parse_tokenized_gold_row(
        _feed_row(category="defi"),
        tickers=TOKENIZED_GOLD_TICKERS,
        category=TOKENIZED_GOLD_CATEGORY,
    )

    assert quote is None


def test_parse_tokenized_gold_row_rejects_missing_price() -> None:
    quote = parse_tokenized_gold_row(
        _feed_row(price_usd=None),
        tickers=TOKENIZED_GOLD_TICKERS,
        category=TOKENIZED_GOLD_CATEGORY,
    )

    assert quote is None


def test_parse_tokenized_gold_row_rejects_unparsable_raw_json() -> None:
    row = _feed_row()
    row.raw_json = "not json"
    quote = parse_tokenized_gold_row(
        row, tickers=TOKENIZED_GOLD_TICKERS, category=TOKENIZED_GOLD_CATEGORY
    )

    assert quote is None


def test_parse_tokenized_gold_row_derives_ticker_for_unknown_token() -> None:
    """A new tokenized gold still lands in the feed under a derived ticker."""
    quote = parse_tokenized_gold_row(
        _feed_row(symbol="Matrixdock Gold"),
        tickers=TOKENIZED_GOLD_TICKERS,
        category=TOKENIZED_GOLD_CATEGORY,
    )

    assert quote is not None
    assert quote["ticker"] == "MATRIXDOCK_GOLD"


def test_ticker_mapping_covers_paxg_and_xaut() -> None:
    assert TOKENIZED_GOLD_TICKERS["PAX Gold"] == "PAXG"
    assert TOKENIZED_GOLD_TICKERS["Tether Gold"] == "XAUT"


# ── Premium maths ─────────────────────────────────────────────────────────


def test_premium_negative_when_token_trades_below_spot() -> None:
    assert compute_tokenized_gold_premium(4143.0, 4285.0) == pytest.approx(
        -3.313886, rel=1e-6
    )


def test_premium_zero_at_parity() -> None:
    assert compute_tokenized_gold_premium(4285.0, 4285.0) == pytest.approx(0.0)


def test_premium_positive_when_token_trades_above_spot() -> None:
    assert compute_tokenized_gold_premium(4385.0, 4285.0) == pytest.approx(
        2.333723454, rel=1e-6
    )


def test_premium_none_without_valid_spot() -> None:
    assert compute_tokenized_gold_premium(4143.0, 0.0) is None
    assert compute_tokenized_gold_premium(4143.0, None) is None


# ── Providers ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_provider_returns_gold_tokens_only() -> None:
    session = _make_session(
        rows=[
            _feed_row(symbol="PAX Gold", price_usd=4143.0),
            _feed_row(symbol="Tether Gold", price_usd=4144.0),
            _feed_row(symbol="Bitcoin", price_usd=95000.0, category="main"),
        ]
    )
    provider = BrsApiTokenizedGoldProvider(session)

    quotes = await provider.fetch()

    assert [q["ticker"] for q in quotes] == ["PAXG", "XAUT"]
    assert [q["price_usd"] for q in quotes] == [4143.0, 4144.0]


@pytest.mark.asyncio
async def test_provider_empty_when_feed_has_no_tokenized_gold() -> None:
    session = _make_session(rows=[_feed_row(symbol="Bitcoin", category="main")])
    provider = BrsApiTokenizedGoldProvider(session)

    assert await provider.fetch() == []


@pytest.mark.asyncio
async def test_stored_spot_provider_returns_latest_snapshot_price() -> None:
    snapshot = MagicMock()
    snapshot.xau_usd = 4285.0
    session = _make_session(spot=snapshot)

    provider = StoredGoldSpotProvider(session)

    assert await provider.fetch() == 4285.0


@pytest.mark.asyncio
async def test_stored_spot_provider_none_without_snapshot() -> None:
    session = _make_session(spot=None)
    provider = StoredGoldSpotProvider(session)

    assert await provider.fetch() is None


# ── Sync ──────────────────────────────────────────────────────────────────


def _token_provider(quotes):
    provider = MagicMock()
    provider.fetch = AsyncMock(return_value=quotes)
    return provider


def _spot_provider(price):
    provider = MagicMock()
    provider.fetch = AsyncMock(return_value=price)
    return provider


@pytest.mark.asyncio
async def test_sync_upserts_premium_for_each_token() -> None:
    session = _make_session()
    service = MacroSyncService(
        session,
        tokenized_gold_provider=_token_provider(
            [
                {"ticker": "PAXG", "symbol": "PAX Gold", "price_usd": 4143.0, "as_of": "2026-10-18"},
                {"ticker": "XAUT", "symbol": "Tether Gold", "price_usd": 4144.0, "as_of": "2026-10-18"},
            ]
        ),
        gold_spot_provider=_spot_provider(4285.0),
    )

    result = await service.sync_tokenized_gold_premium()

    assert result.ok
    assert result.upserted == 2
    assert result.job_type == "tokenized_gold_premium"
    assert session.add.call_count == 2
    session.commit.assert_awaited()

    indicators = {call.args[0].indicator for call in session.add.call_args_list}
    assert indicators == {"PAXG_PREMIUM_VS_SPOT", "XAUT_PREMIUM_VS_SPOT"}
    paxg_row = next(
        call.args[0] for call in session.add.call_args_list
        if call.args[0].indicator == "PAXG_PREMIUM_VS_SPOT"
    )
    assert paxg_row.value == pytest.approx(-3.313886, rel=1e-6)
    assert paxg_row.unit == "percent"
    assert paxg_row.source == "BrsApi"
    assert paxg_row.provenance


@pytest.mark.asyncio
async def test_sync_is_idempotent() -> None:
    session = _make_session()
    existing = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(
                    first=MagicMock(return_value=existing),
                    all=MagicMock(return_value=[]),
                )
            )
        )
    )
    service = MacroSyncService(
        session,
        tokenized_gold_provider=_token_provider(
            [{"ticker": "PAXG", "symbol": "PAX Gold", "price_usd": 4143.0, "as_of": "2026-10-18"}]
        ),
        gold_spot_provider=_spot_provider(4285.0),
    )

    result = await service.sync_tokenized_gold_premium()

    assert result.skipped == 1
    assert result.upserted == 0
    assert session.add.call_count == 0


@pytest.mark.asyncio
async def test_sync_skips_when_spot_unavailable() -> None:
    session = _make_session()
    service = MacroSyncService(
        session,
        tokenized_gold_provider=_token_provider(
            [{"ticker": "PAXG", "symbol": "PAX Gold", "price_usd": 4143.0, "as_of": "2026-10-18"}]
        ),
        gold_spot_provider=_spot_provider(None),
    )

    result = await service.sync_tokenized_gold_premium()

    assert result.upserted == 0
    assert session.add.call_count == 0
    assert result.errors


@pytest.mark.asyncio
async def test_sync_records_provider_error() -> None:
    session = _make_session()
    provider = MagicMock()
    provider.fetch = AsyncMock(side_effect=RuntimeError("feed down"))
    service = MacroSyncService(
        session,
        tokenized_gold_provider=provider,
        gold_spot_provider=_spot_provider(4285.0),
    )

    result = await service.sync_tokenized_gold_premium()

    assert not result.ok
    assert "feed down" in result.errors[0]
