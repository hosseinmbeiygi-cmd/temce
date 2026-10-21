"""Unit tests — گزارش سلامت داده (freshness).

ریسک‌های پوشش‌داده‌شده:
  * آستانه‌های ok / stale / empty / missing
  * ستون‌های naive دیتابیس = زمان محلی تهران ⇒ سن نباید منفی شود
  * خطای خواندن جدول/ستون → ``missing`` (نه «تازه»)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.time import now_tehran, tehran_to_utc
from src.gold_desk import freshness as fr


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _Nested:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Session:
    def __init__(self, values=None, error: Exception | None = None) -> None:
        self._values = list(values or [])
        self._error = error

    def begin_nested(self):
        return _Nested()

    async def execute(self, *args, **kwargs):
        if self._error is not None:
            raise self._error
        return _Result(self._values.pop(0) if self._values else None)


def _source(max_age: int = 60) -> fr.FreshnessSource:
    return fr.FreshnessSource("t", "test", "t", "ts", max_age)


@pytest.mark.asyncio
async def test_status_ok_when_fresh() -> None:
    last = datetime.now(UTC) - timedelta(minutes=5)
    report = await fr.build_freshness_report(_Session([last, 12]), sources=[_source(60)])
    item = report["sources"][0]
    assert item["status"] == "ok"
    assert item["rows"] == 12
    assert item["age_minutes"] == pytest.approx(5, abs=1)
    assert report["overall"] == "ok"


@pytest.mark.asyncio
async def test_status_stale_when_older_than_threshold() -> None:
    last = datetime.now(UTC) - timedelta(days=3)
    report = await fr.build_freshness_report(_Session([last, 5]), sources=[_source(60)])
    assert report["sources"][0]["status"] == "stale"
    assert report["overall"] == "stale"


@pytest.mark.asyncio
async def test_status_empty_when_no_rows() -> None:
    report = await fr.build_freshness_report(_Session([None, 0]), sources=[_source(60)])
    assert report["sources"][0]["status"] == "empty"
    assert report["sources"][0]["age_minutes"] is None
    assert report["overall"] == "empty"


@pytest.mark.asyncio
async def test_status_missing_on_db_error() -> None:
    report = await fr.build_freshness_report(
        _Session(error=RuntimeError("relation does not exist")), sources=[_source(60)]
    )
    item = report["sources"][0]
    assert item["status"] == "missing"
    assert "does not exist" in item["detail"]
    assert report["overall"] == "missing"


@pytest.mark.asyncio
async def test_naive_timestamps_are_tehran_local_not_negative() -> None:
    """ستون naive دیتابیس زمان تهران را نگه می‌دارد ⇒ سن منفی نباید بسازد."""
    naive_now = now_tehran().replace(tzinfo=None)
    report = await fr.build_freshness_report(_Session([naive_now, 3]), sources=[_source(60)])
    age = report["sources"][0]["age_minutes"]
    assert age is not None and age >= 0
    assert report["sources"][0]["status"] == "ok"


@pytest.mark.asyncio
async def test_date_only_column_uses_tehran_midnight() -> None:
    today = now_tehran().date()
    report = await fr.build_freshness_report(
        _Session([today, 7]), sources=[_source(60)]
    )
    age = report["sources"][0]["age_minutes"]
    assert age is not None and age >= 0
    assert age < 24 * 60


def test_sources_cover_every_gold_table() -> None:
    keys = {s.key for s in fr.FRESHNESS_SOURCES}
    assert {
        "gold_snapshots",
        "gold_score_history",
        "gold_fund_nav",
        "gold_portfolio_values",
        "gold_alert_rules",
        "gold_alert_events",
    } <= keys
    assert all(s.max_age_minutes > 0 for s in fr.FRESHNESS_SOURCES)


def test_tehran_to_utc_roundtrip() -> None:
    stamp = datetime(2026, 10, 14, 12, 0)
    assert tehran_to_utc(stamp).hour == 8  # ۱۲:۰۰ تهران = ۰۸:۳۰ UTC
