"""STEP 7D-4 — fund market prices come from the per-symbol snapshot provider.

``_read_brsapi_prices`` used to ask BrsApi for ``get_fund_prices()``, which no
provider implements; the ``hasattr`` guard meant fund prices were silently never
collected, so ``gold_fund_nav.market_price`` fell through to its column default
``0.0`` and the feature layer reported ``gold_fund_pnav_pct = 0.0``.

``BrsApiQueryService.get_symbol_snapshot`` already returns ``price_last`` for
exactly those symbols, so the fix reads the price from the existing provider
rather than inventing a source.
"""

from __future__ import annotations

import core.database as database
from src.gold_desk import snapshot_service
from src.gold_desk.constants import FUND_SYMBOLS

#: symbol -> (price_last, price_close) as the provider would return them.
_FIXTURE = {
    "طلا": (1_828_599.0, 1_803_049.0),
    "عیار": (716_570.0, 706_393.0),
    "زر": (1_095_026.0, 1_082_677.0),
    "کهربا": (253_000.0, 251_000.0),
    "زرفام": (0.0, 192_974.0),  # no last price: must fall back, never store 0
    "گوهر": (None, None),  # no quote at all: the fund stays absent
}


class _FakeSession:
    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeQueryService:
    """Only the methods the snapshot path actually calls — no get_fund_prices."""

    def __init__(self, *, session: object = None) -> None:
        self.session = session
        self.snapshot_calls: list[str] = []

    async def get_gold_coin_prices(self) -> list[dict[str, object]]:
        return [{"symbol": "IR_COIN_EMAMI", "price": 80_000_000.0}]

    async def get_currency_prices(self) -> list[dict[str, object]]:
        return [{"symbol": "USD", "price": 90_000.0}]

    async def get_commodity_prices(self, category: str | None = None) -> list[dict[str, object]]:
        return [{"symbol": "XAUUSD", "price": 4_000.0}]

    async def get_symbol_snapshot(self, symbol: str) -> dict[str, object] | None:
        self.snapshot_calls.append(symbol)
        if symbol not in _FIXTURE:
            return None
        price_last, price_close = _FIXTURE[symbol]
        return {"symbol": symbol, "price_last": price_last, "price_close": price_close}


def _patch_provider(monkeypatch) -> _FakeQueryService:
    service = _FakeQueryService()
    monkeypatch.setattr(database, "async_session_factory", lambda: _FakeSession(), raising=False)
    monkeypatch.setattr(
        "brsapi.services.query_service.BrsApiQueryService",
        lambda *, session=None: service,
        raising=False,
    )
    return service


async def test_fund_prices_are_read_from_the_existing_provider(monkeypatch) -> None:
    service = _patch_provider(monkeypatch)

    prices = await snapshot_service._read_brsapi_prices()

    assert prices["طلا"] == 1_828_599.0
    assert prices["عیار"] == 716_570.0
    assert prices["زر"] == 1_095_026.0
    # every configured fund is asked for, by symbol
    assert set(service.snapshot_calls) >= set(FUND_SYMBOLS)


async def test_missing_last_price_falls_back_to_the_close(monkeypatch) -> None:
    _patch_provider(monkeypatch)

    prices = await snapshot_service._read_brsapi_prices()

    assert prices["زرفام"] == 192_974.0  # price_last was 0.0 -> use price_close


async def test_a_fund_without_any_quote_is_absent_not_zero(monkeypatch) -> None:
    """This is the regression that produced ``market_price = 0.0`` rows."""
    _patch_provider(monkeypatch)

    prices = await snapshot_service._read_brsapi_prices()

    assert "گوهر" not in prices
    assert all(value > 0 for value in prices.values())


async def test_non_fund_prices_are_unchanged(monkeypatch) -> None:
    _patch_provider(monkeypatch)

    prices = await snapshot_service._read_brsapi_prices()

    assert prices["IR_COIN_EMAMI"] == 80_000_000.0
    assert prices["USD"] == 90_000.0
    assert prices["XAUUSD"] == 4_000.0
