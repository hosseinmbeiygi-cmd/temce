"""Snapshot provenance & quality — فاز ۰.

Pins the trust contract against the real DB shape:

* BrsApi returns *all* fetches; only the newest row per symbol may win.
* ``asOf`` is the source ``fetched_at``, not the response build time.
* Stale data is ``DELAYED``; only proven-fresh BrsApi data is ``LIVE``.
* TGJU is always ``DELAYED`` (no source timestamp, known delay).
* A missing reference must not be filled from a different source
  (``source="mixed"`` is forbidden); the whole set comes from one source.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

import src.gold_desk.snapshot_service as svc
from src.gold_desk.schemas import AssetBlock, ReferenceBlock
from src.gold_desk.secondary_source import TGJUPrice

_COMPONENT_KEYS = ("bubble", "nav", "tsetmc", "technical", "parity", "fund_flow")
_NOW = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)


def _book(values: dict[str, float], stamps: dict[str, datetime]) -> svc.PriceBook:
    return svc.PriceBook(values, as_of_by_symbol=stamps)


def _components() -> dict:
    return {key: SimpleNamespace(value=0.0, reason="") for key in _COMPONENT_KEYS}


def _score() -> SimpleNamespace:
    return SimpleNamespace(
        total=0,
        decision="NO_DATA",
        raw_total=0,
        available_weight=0,
        data_coverage_pct=0.0,
        hard_stop_active=False,
        hard_stop_reason=None,
        components=_components(),
    )


def _patch_externals(monkeypatch) -> None:
    async def _funds(*_args, **_kwargs):
        return []

    async def _indicators(*_args, **_kwargs):
        return {}

    async def _daily(*_args, **_kwargs):
        return {"usd": None, "tse": None, "dxy": None}

    monkeypatch.setattr(svc.nav_checker, "get_all_funds_status", _funds)
    monkeypatch.setattr(svc.signal_engine, "get_xau_indicators", _indicators)
    monkeypatch.setattr(svc, "_calc_daily_changes", _daily)
    monkeypatch.setattr(
        svc.hard_stops,
        "check_hard_stops",
        lambda **_kwargs: SimpleNamespace(active=False, reason=None),
    )
    monkeypatch.setattr(svc.scorer, "compute_score", lambda **_kwargs: _score())


def _tgju(symbol: str, price: float, stamp: datetime) -> TGJUPrice:
    return TGJUPrice(symbol=symbol, price_irt=price, change_pct=None, fetched_at=stamp)


# ── row selection ────────────────────────────────────────────────


def test_latest_row_wins_by_source_timestamp():
    rows = [
        {"symbol": "IR_GOLD_18K", "price": 100.0, "fetched_at": "2026-10-18T20:00:00Z", "id": 1},
        {"symbol": "IR_GOLD_18K", "price": 200.0, "fetched_at": "2026-10-18T22:00:00Z", "id": 2},
        {"symbol": "IR_GOLD_18K", "price": 150.0, "fetched_at": "2026-10-18T21:00:00Z", "id": 3},
    ]

    latest = svc._latest_rows(rows)

    assert latest["IR_GOLD_18K"]["price"] == 200.0


def test_latest_row_falls_back_to_time_unix_then_id():
    rows = [
        {"symbol": "USD", "price": 100.0, "time_unix": 10, "id": 1},
        {"symbol": "USD", "price": 200.0, "time_unix": 30, "id": 2},
        {"symbol": "USD", "price": 150.0, "time_unix": 20, "id": 3},
    ]
    assert svc._latest_rows(rows)["USD"]["price"] == 200.0

    rows_without_time = [
        {"symbol": "AED", "price": 10.0, "id": 1},
        {"symbol": "AED", "price": 20.0, "id": 2},
    ]
    assert svc._latest_rows(rows_without_time)["AED"]["price"] == 20.0


def test_rows_with_non_positive_price_are_ignored():
    rows = [
        {"symbol": "USD", "price": 0, "fetched_at": "2026-10-26T09:00:00Z", "id": 9},
        {"symbol": "USD", "price": 262_800, "fetched_at": "2026-10-18T20:00:00Z", "id": 1},
    ]
    latest = svc._latest_rows(rows)
    assert latest["USD"]["price"] == 262_800


# ── source selection ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_complete_brsapi_is_used_as_one_source_with_oldest_timestamp():
    oldest = _NOW - timedelta(minutes=2)
    book = _book(
        {"XAUUSD": 4165.175, "USD": 262_800.0, "AED": 71_801.0},
        {"XAUUSD": _NOW, "USD": _NOW - timedelta(minutes=1), "AED": oldest},
    )

    refs, source, as_of, out = await svc._read_references(book)

    assert source == "brsapi"
    assert as_of == oldest
    assert out is book
    assert refs == {"xau_usd": 4165.175, "usd_irt": 262_800.0, "aed_irt": 71_801.0}


@pytest.mark.asyncio
async def test_dxy_timestamp_is_included_in_reference_freshness():
    """DXY هم قیمتِ نمایشی است؛ کهنگی‌اش نباید پشت برچسب LIVE پنهان شود."""
    old = _NOW - timedelta(hours=2)
    book = _book(
        {"XAUUSD": 4165.175, "USD": 262_800.0, "AED": 71_801.0, "DXY": 99.5},
        {"XAUUSD": _NOW, "USD": _NOW, "AED": _NOW, "DXY": old},
    )
    _, _, as_of, _ = await svc._read_references(book)
    assert as_of == old

    # DXY بدون timestamp اثبات‌پذیر نیست → کل مرجع DELAYED می‌شود.
    undated = _book(
        {"XAUUSD": 4165.175, "USD": 262_800.0, "AED": 71_801.0, "DXY": 99.5},
        {"XAUUSD": _NOW, "USD": _NOW, "AED": _NOW},
    )
    _, _, as_of, _ = await svc._read_references(undated)
    assert as_of is None


@pytest.mark.asyncio
async def test_incomplete_brsapi_uses_complete_tgju_and_never_mixes(monkeypatch):
    stamp = _NOW - timedelta(minutes=10)
    brsapi = _book(
        {"XAUUSD": 4165.175, "USD": 262_800.0},  # AED missing
        {"XAUUSD": _NOW, "USD": _NOW},
    )
    tgju_rows = [
        _tgju("XAUUSD", 4165.0, stamp),
        _tgju("USD", 850_000.0, stamp),
        _tgju("AED", 245_000.0, stamp),
        _tgju("IR_GOLD_18K", 25_900_000.0, stamp),
    ]

    async def _available():
        return True

    async def _fetch():
        return tgju_rows

    monkeypatch.setattr(svc, "tgju_available", _available)
    monkeypatch.setattr(svc, "fetch_tgju_prices", _fetch)

    refs, source, as_of, book = await svc._read_references(brsapi)

    assert source == "tgju"
    assert refs == {"xau_usd": 4165.0, "usd_irt": 850_000.0, "aed_irt": 245_000.0}
    assert as_of == stamp
    assert book["IR_GOLD_18K"] == 25_900_000.0
    # even the gold asset came from TGJU, not from the partial BrsApi book
    assert book["IR_GOLD_18K"] != 25_937_200.0


@pytest.mark.asyncio
async def test_partial_sources_raise_instead_of_mixed(monkeypatch):
    brsapi = _book(
        {"XAUUSD": 4165.175, "USD": 262_800.0},  # AED missing
        {"XAUUSD": _NOW, "USD": _NOW},
    )

    async def _available():
        return True

    async def _fetch():
        # XAUUSD missing too → neither source is complete
        return [_tgju("USD", 850_000.0, _NOW), _tgju("AED", 245_000.0, _NOW)]

    monkeypatch.setattr(svc, "tgju_available", _available)
    monkeypatch.setattr(svc, "fetch_tgju_prices", _fetch)

    with pytest.raises(RuntimeError, match="no complete price source"):
        await svc._read_references(brsapi)


# ── freshness / quality ──────────────────────────────────────────


def test_quality_is_fail_closed():
    assert svc._quality_for("brsapi", _NOW - timedelta(seconds=1), _NOW) == "LIVE"
    assert svc._quality_for("brsapi", _NOW - timedelta(seconds=301), _NOW) == "DELAYED"
    assert svc._quality_for("brsapi", _NOW + timedelta(seconds=5), _NOW) == "DELAYED"
    assert svc._quality_for("brsapi", None, _NOW) == "DELAYED"
    assert svc._quality_for("tgju", _NOW, _NOW) == "DELAYED"


@pytest.mark.asyncio
async def test_fresh_brsapi_snapshot_is_live_and_uses_source_time(monkeypatch):
    stamp = _NOW - timedelta(seconds=60)
    book = _book(
        {
            "XAUUSD": 4165.175,
            "USD": 262_800.0,
            "AED": 71_801.0,
            "IR_GOLD_18K": 25_937_200.0,
            "IR_COIN_EMAMI": 264_190_000.0,
        },
        dict.fromkeys(("XAUUSD", "USD", "AED", "IR_GOLD_18K", "IR_COIN_EMAMI"), stamp),
    )

    async def _prices():
        return book

    monkeypatch.setattr(svc, "_read_brsapi_prices", _prices)
    _patch_externals(monkeypatch)

    # The service builds its own clock; freeze it to the test instant.
    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return _NOW

    monkeypatch.setattr(svc, "datetime", _FrozenDatetime)

    snap = await svc.build_snapshot(object())

    assert snap.references.source == "brsapi"
    assert snap.references.quality == "LIVE"
    assert snap.references.asOf == stamp
    assert snap.references.age_seconds == pytest.approx(60.0)
    assert snap.references.unit == "toman"

    gold = snap.gold["gold_18k"]
    assert gold.source == "brsapi"
    assert gold.quality == "LIVE"
    assert gold.asOf == stamp
    assert gold.unit == "toman"
    # Rial-precision rounding: 0.1 Toman == 1 Rial.
    assert gold.value == pytest.approx(round(gold.value, 1))
    assert gold.fair_value == gold.value
    assert gold.market_price == 25_937_200.0

    coin = snap.coins["coin_emami"]
    assert coin.quality == "LIVE"
    assert coin.unit == "toman"


@pytest.mark.asyncio
async def test_stale_brsapi_snapshot_is_delayed(monkeypatch):
    stamp = _NOW - timedelta(days=8)
    book = _book(
        {
            "XAUUSD": 4165.175,
            "USD": 262_800.0,
            "AED": 71_801.0,
            "IR_GOLD_18K": 25_937_200.0,
        },
        {"XAUUSD": stamp, "USD": stamp, "AED": stamp, "IR_GOLD_18K": stamp},
    )

    async def _prices():
        return book

    monkeypatch.setattr(svc, "_read_brsapi_prices", _prices)
    _patch_externals(monkeypatch)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return _NOW

    monkeypatch.setattr(svc, "datetime", _FrozenDatetime)

    snap = await svc.build_snapshot(object())

    assert snap.references.quality == "DELAYED"
    assert snap.references.age_seconds == pytest.approx(8 * 86400, abs=1.0)
    assert snap.gold["gold_18k"].quality == "DELAYED"
    assert snap.gold["gold_18k"].asOf == stamp


@pytest.mark.asyncio
async def test_tgju_snapshot_is_always_delayed_even_if_fetched_now(monkeypatch):
    stamp = _NOW  # fetched this second, but TGJU is a delayed source
    partial = _book({"XAUUSD": 4165.175}, {"XAUUSD": stamp})
    tgju_rows = [
        _tgju("XAUUSD", 4165.0, stamp),
        _tgju("USD", 850_000.0, stamp),
        _tgju("AED", 245_000.0, stamp),
        _tgju("IR_GOLD_18K", 25_900_000.0, stamp),
    ]

    async def _prices():
        return partial

    async def _available():
        return True

    async def _fetch():
        return tgju_rows

    monkeypatch.setattr(svc, "_read_brsapi_prices", _prices)
    monkeypatch.setattr(svc, "tgju_available", _available)
    monkeypatch.setattr(svc, "fetch_tgju_prices", _fetch)
    _patch_externals(monkeypatch)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return _NOW

    monkeypatch.setattr(svc, "datetime", _FrozenDatetime)

    snap = await svc.build_snapshot(object())

    assert snap.references.source == "tgju"
    assert snap.references.quality == "DELAYED"
    assert snap.references.asOf == stamp
    assert snap.gold["gold_18k"].source == "tgju"
    assert snap.gold["gold_18k"].quality == "DELAYED"
    assert snap.gold["gold_18k"].market_price == 25_900_000.0


@pytest.mark.asyncio
async def test_asset_without_its_own_timestamp_is_delayed(monkeypatch):
    stamp = _NOW - timedelta(seconds=10)
    book = _book(
        {
            "XAUUSD": 4165.175,
            "USD": 262_800.0,
            "AED": 71_801.0,
            "IR_GOLD_18K": 25_937_200.0,
        },
        dict.fromkeys(("XAUUSD", "USD", "AED"), stamp),  # no gold stamp
    )

    async def _prices():
        return book

    monkeypatch.setattr(svc, "_read_brsapi_prices", _prices)
    _patch_externals(monkeypatch)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return _NOW

    monkeypatch.setattr(svc, "datetime", _FrozenDatetime)

    snap = await svc.build_snapshot(object())

    assert snap.references.quality == "LIVE"
    assert snap.gold["gold_18k"].quality == "DELAYED"
    assert snap.gold["gold_18k"].asOf == stamp  # display falls back to ref time


# ── schema guard ─────────────────────────────────────────────────


def test_schema_rejects_legacy_quality_and_source():
    base = {
        "xau_usd": 4165.0,
        "usd_irt": 262_800.0,
        "aed_irt": 71_801.0,
        "aed_parity_usd": 3.66,
        "aed_gap_pct": 0.1,
    }
    assert ReferenceBlock(**base, quality="LIVE", source="brsapi").quality == "LIVE"

    with pytest.raises(ValueError):
        ReferenceBlock(**base, quality="fallback")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ReferenceBlock(**base, source="mixed")  # type: ignore[arg-type]


def test_asset_block_requires_the_five_contract_fields():
    with pytest.raises(ValueError):
        AssetBlock(  # type: ignore[call-arg]
            symbol="IR_GOLD_18K",
            display_name="طلای ۱۸ عیار",
            asset_type="gold",
            market_price=1.0,
            fair_value=1.0,
            bubble_abs=0.0,
            bubble_pct=0.0,
            implied_usd=None,
        )
