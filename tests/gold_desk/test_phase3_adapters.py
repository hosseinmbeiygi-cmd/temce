"""Phase 3 source-layer adapters — offline, fixture-driven, no network.

Covers Assistant 4 source-layer obligations (phase 3):
* silver feed (domestic primary, international fallback, no invented FX)
* read-only derivative (price / settlement / expiry / distance-from-spot,
  divide-by-zero guarded, no order entry)
* news regime normalizer (fixed label set only, non-price note)
* freshness / staleness marker for Assistant 1's `data_stale` gate
* universal rules: value/unit/asOf/source/quality; SAMPLE never → LIVE;
  secrets stripped; missing source → UNAVAILABLE
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from services.data.adapters import (
    BaseAdapter,
    BrsApiAdapter,
    DerivativeAdapter,
    FreshnessAdapter,
    NewsAdapter,
    SilverAdapter,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
IR_TZ = timezone(timedelta(hours=3, minutes=30))
NOW = datetime(2026, 10, 26, 10, 0, tzinfo=IR_TZ)


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


REQUIRED = ("value", "unit", "asOf", "source", "quality")


def record_dict(raw, adapter, now=NOW) -> dict:
    if not isinstance(adapter, BaseAdapter):
        adapter = adapter()
    return adapter.normalize(raw, now=now).to_dict()


# ------------------------------------------------------------------ brsapi


def test_brsapi_live_fresh_carries_contract_fields():
    raw = {
        "symbol": "XAU18",
        "value": 26_396_987.8,
        "unit": "toman",
        "asOf": "2026-10-26T09:59:00+03:30",
        "source": "brsapi",
        "quality": "LIVE",
    }
    out = record_dict(raw, BrsApiAdapter())
    for key in REQUIRED:
        assert key in out, f"missing {key}"
    assert out["source"] == "brsapi"
    assert out["quality"] == "LIVE"
    assert "+03:30" in str(out["asOf"])
    assert out["metadata"]["freshness"] == "fresh"
    assert out["metadata"]["staleFlag"] is False


def test_brsapi_stale_downgraded():
    raw = load("phase3-stale.json")
    out = record_dict(raw, BrsApiAdapter())
    assert out["quality"] == "DELAYED"
    assert out["metadata"]["staleFlag"] is True
    assert out["metadata"]["ageSeconds"] is not None
    assert out["metadata"]["ageSeconds"] > BrsApiAdapter.ttl_seconds


def test_sample_never_promoted_to_live():
    raw = {
        "symbol": "XAU18",
        "value": 25_500_000,
        "unit": "toman",
        "asOf": "2026-10-26T09:59:00+03:30",
        "source": "brsapi",
        "quality": "SAMPLE",
    }
    out = record_dict(raw, BrsApiAdapter())
    assert out["quality"] == "SAMPLE"


def test_missing_source_is_unavailable():
    out = record_dict({}, BrsApiAdapter())
    assert out["quality"] == "UNAVAILABLE"
    assert out["source"] == "unknown"
    assert out["asOf"] is None
    assert out["value"] is None


def test_secrets_never_leak():
    raw = load("phase3-secret.json")
    out = record_dict(raw, BrsApiAdapter())
    for secret in ("token", "cookie", "authorization"):
        assert secret not in out
    assert out["quality"] == "LIVE"


# ------------------------------------------------------------------ silver


def test_silver_domestic_is_preferred():
    raw = load("phase3-silver.json")
    adapter = SilverAdapter()
    adapter.ttl_seconds = 86_400  # same-day fixture must read fresh
    out = record_dict(raw, adapter)
    assert out["value"] == 1_050_000
    assert out["unit"] == "toman/gram"
    assert out["source"] == "brsapi"
    assert out["metadata"]["freshness"] == "fresh"


def test_silver_international_conversion_uses_explicit_fx_only():
    raw = {
        "international": {
            "symbol": "XAG_USD",
            "value": 32.5,
            "unit": "USD/oz",
            "asOf": "2026-10-26T09:59:00+03:30",
            "source": "London_Bullion_Market",
            "quality": "DELAYED",
        },
        "usd_irr": 950_000,
    }
    adapter = SilverAdapter()
    adapter.ttl_seconds = 86_400
    out = record_dict(raw, adapter)
    expected = 32.5 * 950_000 / 31.1035
    assert out["value"] == pytest.approx(expected, rel=1e-6)
    assert out["unit"] == "toman/gram"
    assert out["source"] == "London_Bullion_Market"


def test_silver_no_source_is_null_not_invented():
    out = record_dict({}, SilverAdapter())
    assert out["value"] is None
    assert out["quality"] == "UNAVAILABLE"


# ------------------------------------------------------------------ derivative


def test_derivative_readonly_fields():
    raw = load("phase3-derivative.json")
    out = record_dict(raw, DerivativeAdapter())
    assert out["value"] == 4100.0
    assert out["metadata"]["settlement"] == 4080.0
    assert out["metadata"]["expiry"] == "2026-11-26"
    assert out["metadata"]["distance_from_spot_pct"] == pytest.approx(2.5)
    assert out["metadata"]["risks_simple"] == ["liquidity-low", "assignment-risk"]
    for forbidden in ("place_order", "cancel", "position", "order"):
        assert forbidden not in str(out)


def test_derivative_without_spot_distance_null():
    raw = {
        "symbol": "XAU_OPT_1M",
        "price": 4100.0,
        "unit": "USD/oz",
        "asOf": "2026-10-26T09:59:00+03:30",
        "source": "motor_option",
        "quality": "LIVE",
    }
    out = record_dict(raw, DerivativeAdapter())
    assert out["metadata"]["distance_from_spot_pct"] is None


# ------------------------------------------------------------------ news


def test_news_labels_drawn_from_fixed_set_only():
    raw = load("phase3-news.json")
    out = record_dict(raw, NewsAdapter())
    fixed = {"dollar", "geopolitical", "monetary_policy", "coin_supply", "other"}
    assert set(out["metadata"]["labels"]).issubset(fixed)
    assert "monetary_policy" in out["metadata"]["labels"]
    note = out["metadata"]["note"]
    for banned in ("هدف قیمت", "خرید", "فروش", "target price", "buy", "sell"):
        assert banned not in note


# ------------------------------------------------------------------ freshness marker


def test_freshness_mark_stale_sets_gate_flag():
    raw = load("phase3-stale.json")
    record = BrsApiAdapter().normalize(raw, now=NOW)
    mark = FreshnessAdapter().mark(record, now=NOW)
    assert set(mark) == {"ageSeconds", "freshness", "staleFlag"}
    assert mark["staleFlag"] is True
    assert mark["ageSeconds"] > 900


def test_freshness_mark_fresh_no_flag():
    raw = {
        "symbol": "XAU18",
        "value": 25_500_000,
        "unit": "toman",
        "asOf": "2026-10-26T09:59:00+03:30",
        "source": "brsapi",
        "quality": "LIVE",
    }
    record = BrsApiAdapter().normalize(raw, now=NOW)
    mark = FreshnessAdapter().mark(record, now=NOW)
    assert mark["staleFlag"] is False
    assert mark["freshness"] == "fresh"


def test_missing_asof_unknown_freshness():
    raw = {
        "symbol": "XAU18",
        "value": 25_500_000,
        "unit": "toman",
        "source": "brsapi",
        "quality": "LIVE",
    }
    record = BrsApiAdapter().normalize(raw, now=NOW)
    assert record.as_of is None
    assert FreshnessAdapter().mark(record, now=NOW)["freshness"] == "unknown"
