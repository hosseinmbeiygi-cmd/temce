"""snapshot_service: فیلدهای پوشش score و ترتیب سری روزانه (بدون دیتابیس).

* ``raw_total`` / ``available_weight`` / ``data_coverage_pct`` مستقیم از موتور
  خوانده می‌شوند؛ نتیجه‌ای که این فیلدها را ندارد دیگر با مقدار جعلی پوشانده
  نمی‌شود (AttributeError).
* تغییر روزانهٔ USD/DXY از دو ردیف **جدیدتر** سری محاسبه می‌شود (H1).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.gold_desk.snapshot_service as svc

_COMPONENT_KEYS = ("bubble", "nav", "tsetmc", "technical", "parity", "fund_flow")


def _components() -> dict:
    return {key: SimpleNamespace(value=0.0, reason="") for key in _COMPONENT_KEYS}


def _externals(monkeypatch, score_result) -> None:
    async def _prices():
        return {}

    async def _refs(*_args, **_kwargs):
        return ({"xau_usd": 2000.0, "usd_irt": 60_000.0, "aed_irt": 16_400.0}, "brsapi")

    async def _funds(*_args, **_kwargs):
        return []

    async def _indicators(*_args, **_kwargs):
        return {}

    async def _daily(*_args, **_kwargs):
        return {"usd": None, "tse": None, "dxy": None}

    monkeypatch.setattr(svc, "_read_brsapi_prices", _prices)
    monkeypatch.setattr(svc, "_read_references", _refs)
    monkeypatch.setattr(svc.nav_checker, "get_all_funds_status", _funds)
    monkeypatch.setattr(svc.signal_engine, "get_xau_indicators", _indicators)
    monkeypatch.setattr(svc, "_calc_daily_changes", _daily)
    monkeypatch.setattr(
        svc.hard_stops,
        "check_hard_stops",
        lambda **_kwargs: SimpleNamespace(active=False, reason=None),
    )
    monkeypatch.setattr(svc.scorer, "compute_score", lambda **_kwargs: score_result)


async def test_score_coverage_fields_come_straight_from_the_engine(monkeypatch) -> None:
    score = SimpleNamespace(
        total=42,
        decision="GREEN",
        raw_total=48,
        available_weight=80,
        data_coverage_pct=80.0,
        hard_stop_active=False,
        hard_stop_reason=None,
        components=_components(),
    )
    _externals(monkeypatch, score)

    snap = await svc.build_snapshot(object())

    assert snap.score.total == 42
    assert snap.score.raw_total == 48
    assert snap.score.available_weight == 80
    assert snap.score.data_coverage_pct == 80.0


async def test_score_without_coverage_fields_is_not_silently_defaulted(monkeypatch) -> None:
    """قبلاً ``hasattr`` این خطای قرارداد را به raw_total=0/weight=100 تبدیل می‌کرد."""
    incomplete = SimpleNamespace(
        total=10,
        decision="NO_DATA",
        hard_stop_active=False,
        hard_stop_reason=None,
        components=_components(),
    )
    _externals(monkeypatch, incomplete)

    with pytest.raises(AttributeError):
        await svc.build_snapshot(object())


async def test_daily_changes_use_the_newest_two_closes(monkeypatch) -> None:
    series = {
        "USD": [90.0, 100.0, 110.0],
        "DXY": [60.0, 50.0, 45.0],
    }

    async def _fetch_closes(_session, symbol, _days):
        return series[symbol]

    monkeypatch.setattr(svc.signal_engine, "fetch_closes", _fetch_closes)

    class _Session:
        async def execute(self, _stmt):
            raise RuntimeError("TSE table is not part of this test")

    changes = await svc._calc_daily_changes(_Session(), {})

    # جدیدترین دو نقطه: 100 → 110 و 50 → 45.
    assert changes["usd"] == pytest.approx(10.0)
    assert changes["dxy"] == pytest.approx(-10.0)
    assert changes["tse"] is None
