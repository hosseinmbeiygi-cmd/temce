"""TGJU fallback unit conversion — فاز ۰.

The old code divided any non-XAU price above 2,000,000 by 10, assuming every
TGJU value was Rial while BrsApi was Toman. That destroyed gold/coin fallbacks
(an 18k gram of 25.9M Toman became 2.59M). TGJU's own slugs declare the unit:
``price_dollar_rl`` / ``price_aed`` are Rial, while gold/coin pages are Toman.
These tests pin the conversion per slug.
"""

from __future__ import annotations

import pytest

from src.gold_desk import secondary_source


@pytest.fixture
def parsed_price(monkeypatch):
    """Return a configurable (price, change) without network/HTML."""

    async def _page(_slug, _client):
        return "<html></html>"

    def _parser(_html):
        return (parsed_price.value, 1.25)

    monkeypatch.setattr(secondary_source, "fetch_tgju_page", _page)
    monkeypatch.setattr(secondary_source, "_parse_price", _parser)
    return parsed_price


@pytest.mark.asyncio
async def test_rial_slugs_are_converted_to_toman(parsed_price):
    parsed_price.value = 8_500_000.0  # TGJU dollar in Rial
    usd = await secondary_source._fetch_one("price_dollar_rl", None)
    assert usd is not None
    assert usd.symbol == "USD"
    assert usd.price_irt == pytest.approx(850_000.0)
    assert usd.unit == "toman"

    parsed_price.value = 2_450_000.0
    aed = await secondary_source._fetch_one("price_aed", None)
    assert aed is not None
    assert aed.price_irt == pytest.approx(245_000.0)


@pytest.mark.asyncio
async def test_gold_and_coin_slugs_stay_in_toman(parsed_price):
    """طلای ۱۸ عیار و سکه‌ها در TGJU تومان‌اند و نباید /۱۰ شوند."""
    parsed_price.value = 25_900_000.0
    gold = await secondary_source._fetch_one("geram18", None)
    assert gold is not None
    assert gold.symbol == "IR_GOLD_18K"
    assert gold.price_irt == pytest.approx(25_900_000.0)
    assert gold.unit == "toman"

    parsed_price.value = 264_190_000.0
    coin = await secondary_source._fetch_one("coin-emami", None)
    assert coin is not None
    assert coin.price_irt == pytest.approx(264_190_000.0)


@pytest.mark.asyncio
async def test_ounce_stays_in_usd(parsed_price):
    parsed_price.value = 4165.175
    ounce = await secondary_source._fetch_one("ons", None)
    assert ounce is not None
    assert ounce.symbol == "XAUUSD"
    assert ounce.price_irt == pytest.approx(4165.175)
    assert ounce.unit == "usd"


@pytest.mark.asyncio
async def test_unknown_slug_is_ignored(parsed_price):
    parsed_price.value = 1.0
    assert await secondary_source._fetch_one("not-a-slug", None) is None
