"""TDD tests for TGJUClient — call3.tgju.org JSON price feed.

RED: TGJUClient not yet implemented.
GREEN: TGJUClient fetches from call3.tgju.org/ajax.json and parses prices.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_response(market: dict) -> MagicMock:
    """Return a mock client whose response uses the 2026-11 ``current`` key."""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"current": market}
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    client.aclose = AsyncMock()
    return client


# 2026-11 slugs: coin-emami→sekee, coin-bahar→sekeb, coin-half→nim, coin-quarter→rob
# All gold/coin prices now in Rials (factor 0.1 → Tomans)
_SAMPLE_MARKET = {
    "geram18":         {"p": "255,000,000", "d": "1403/09/01"},  # Rials → 25,500,000 Toman
    "geram24":         {"p": "340,000,000", "d": "1403/09/01"},  # Rials → 34,000,000 Toman
    "sekee":           {"p": "2,570,000,000", "d": "1403/09/01"},  # Rials → 257,000,000 Toman
    "sekeb":           {"p": "2,500,000,000", "d": "1403/09/01"},  # Rials → 250,000,000 Toman
    "nim":             {"p": "1,350,000,000", "d": "1403/09/01"},  # Rials → 135,000,000 Toman
    "rob":             {"p": "722,000,000",   "d": "1403/09/01"},  # Rials → 72,200,000 Toman
    "price_dollar_rl": {"p": "2,640,000",     "d": "1403/09/01"},  # Rials → 264,000 Toman
    "price_aed":       {"p": "719,000",       "d": "1403/09/01"},  # Rials → 71,900 Toman
    "ons":             {"p": "4123.5",        "d": "1403/09/01"},  # USD (no conversion)
}


# ── 1. Import ─────────────────────────────────────────────────────────────────

def test_tgju_client_importable():
    from providers.macro_sources.tgju import (  # noqa: F401
        TGJU_AJAX_URL,
        TGJU_PRICE_MAP,
        TGJUClient,
        TGJUQuote,
        fetch_tgju_json,
    )


# ── 2. TGJU_PRICE_MAP completeness ───────────────────────────────────────────

def test_price_map_contains_expected_slugs():
    from providers.macro_sources.tgju import TGJU_PRICE_MAP

    # 2026-11: coin slugs renamed
    expected = {
        "geram18", "geram24",
        "sekee", "sekeb", "nim", "rob",
        "price_dollar_rl", "price_aed", "ons",
    }
    missing = expected - set(TGJU_PRICE_MAP.keys())
    assert not missing, f"Missing slugs: {missing}"


def test_price_map_all_rial_slugs_have_correct_factor():
    """All gold/coin and FX Rial-quoted slugs must carry a 0.1 factor (2026-11)."""
    from providers.macro_sources.tgju import TGJU_PRICE_MAP

    for slug in ("geram18", "geram24", "sekee", "sekeb", "nim", "rob",
                 "price_dollar_rl", "price_aed"):
        _, _, factor = TGJU_PRICE_MAP[slug]
        assert factor == pytest.approx(0.1), f"slug={slug} should have factor 0.1"


def test_price_map_ons_has_usd_factor_one():
    """International oz price (ons) is in USD — no Rial conversion."""
    from providers.macro_sources.tgju import TGJU_PRICE_MAP

    _, unit, factor = TGJU_PRICE_MAP["ons"]
    assert unit == "usd"
    assert factor == pytest.approx(1.0)


# ── 3. TGJUClient.fetch() — happy path ───────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_returns_quotes_for_all_slugs():
    from providers.macro_sources.tgju import TGJUClient

    client = _mock_response(_SAMPLE_MARKET)
    quotes = await TGJUClient(client=client).fetch()

    symbols = {q.symbol for q in quotes}
    assert "IR_GOLD_18K_GRAM" in symbols
    assert "IR_COIN_EMAMI"    in symbols
    assert "USD"              in symbols
    assert "XAUUSD"           in symbols


@pytest.mark.asyncio
async def test_fetch_parses_comma_separated_prices():
    """Comma-separated Rial string is parsed and converted to Tomans (* 0.1)."""
    from providers.macro_sources.tgju import TGJUClient

    client = _mock_response({"geram18": {"p": "175,000,000"}})  # Rials
    quotes = await TGJUClient(client=client).fetch(["geram18"])

    assert len(quotes) == 1
    assert quotes[0].price == pytest.approx(17_500_000.0)  # Tomans


@pytest.mark.asyncio
async def test_fetch_converts_rial_to_toman_for_dollar():
    """price_dollar_rl is in Rials (580,000) → converted to Tomans (58,000)."""
    from providers.macro_sources.tgju import TGJUClient

    client = _mock_response({"price_dollar_rl": {"p": "580,000"}})
    quotes = await TGJUClient(client=client).fetch(["price_dollar_rl"])

    assert len(quotes) == 1
    assert quotes[0].symbol == "USD"
    assert quotes[0].price == pytest.approx(58_000.0)


@pytest.mark.asyncio
async def test_fetch_uses_correct_canonical_symbols():
    from providers.macro_sources.tgju import TGJUClient

    client = _mock_response(_SAMPLE_MARKET)
    quotes = await TGJUClient(client=client).fetch()

    by_slug = {q.slug: q for q in quotes}
    assert by_slug["geram18"].symbol == "IR_GOLD_18K_GRAM"
    assert by_slug["sekee"].symbol == "IR_COIN_EMAMI"   # renamed from coin-emami (2026-11)
    assert by_slug["ons"].symbol == "XAUUSD"
    assert by_slug["ons"].unit == "usd"


@pytest.mark.asyncio
async def test_fetch_as_dict_returns_symbol_to_price_map():
    """fetch_as_dict returns canonical symbols → Toman values (Rial * 0.1)."""
    from providers.macro_sources.tgju import TGJUClient

    # Prices in Rials; expect Tomans after * 0.1
    client = _mock_response({"geram18": {"p": "175000000"}, "sekee": {"p": "750000000"}})
    result = await TGJUClient(client=client).fetch_as_dict()

    assert result["IR_GOLD_18K_GRAM"] == pytest.approx(17_500_000.0)
    assert result["IR_COIN_EMAMI"]    == pytest.approx(75_000_000.0)


# ── 4. Persian digit support ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_handles_persian_digits():
    """Persian-digit string is correctly parsed to float, then Rial→Toman factor applied."""
    from providers.macro_sources.tgju import TGJUClient

    # "۱۷٬۵۰۰٬۰۰۰" = 17,500,000 Rials → 1,750,000 Toman after factor 0.1
    client = _mock_response({"geram18": {"p": "۱۷٬۵۰۰٬۰۰۰"}})
    quotes = await TGJUClient(client=client).fetch(["geram18"])

    assert len(quotes) == 1
    assert quotes[0].price == pytest.approx(1_750_000.0)


# ── 5. Error handling ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_returns_empty_on_network_error():
    from providers.macro_sources.tgju import TGJUClient

    bad_client = MagicMock()
    bad_client.get = AsyncMock(side_effect=Exception("connection refused"))
    bad_client.aclose = AsyncMock()

    quotes = await TGJUClient(client=bad_client).fetch()
    assert quotes == []


@pytest.mark.asyncio
async def test_fetch_skips_slugs_with_zero_price():
    from providers.macro_sources.tgju import TGJUClient

    client = _mock_response({"geram18": {"p": "0"}, "sekee": {"p": "750000000"}})
    quotes = await TGJUClient(client=client).fetch()

    symbols = {q.symbol for q in quotes}
    assert "IR_GOLD_18K_GRAM" not in symbols
    assert "IR_COIN_EMAMI"    in symbols


@pytest.mark.asyncio
async def test_fetch_skips_missing_slugs_in_response():
    from providers.macro_sources.tgju import TGJUClient

    client = _mock_response({})  # empty market
    quotes = await TGJUClient(client=client).fetch()
    assert quotes == []


@pytest.mark.asyncio
async def test_fetch_ignores_unknown_slugs():
    """Slugs not in TGJU_PRICE_MAP are ignored gracefully."""
    from providers.macro_sources.tgju import TGJUClient

    client = _mock_response({"unknown_slug": {"p": "12345"}})
    quotes = await TGJUClient(client=client).fetch(["unknown_slug"])
    assert quotes == []


# ── 6. Subset fetch ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_subset_of_slugs():
    """Only the requested slugs are returned."""
    from providers.macro_sources.tgju import TGJUClient

    client = _mock_response(_SAMPLE_MARKET)
    quotes = await TGJUClient(client=client).fetch(["geram18", "sekee"])  # new slug names

    assert len(quotes) == 2
    symbols = {q.symbol for q in quotes}
    assert symbols == {"IR_GOLD_18K_GRAM", "IR_COIN_EMAMI"}


# ── 7. fetch_tgju_json convenience function ───────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_tgju_json_convenience():
    """Convenience wrapper returns correctly converted Toman prices."""
    from providers.macro_sources.tgju import fetch_tgju_json

    # 17,500,000 Rials → 1,750,000 Toman after factor 0.1
    mock_client = _mock_response({"geram18": {"p": "17500000"}})
    quotes = await fetch_tgju_json(["geram18"], client=mock_client)

    assert len(quotes) == 1
    assert quotes[0].price == pytest.approx(1_750_000.0)
