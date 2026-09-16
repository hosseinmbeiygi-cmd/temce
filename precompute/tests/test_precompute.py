"""Tests for the precompute scope: classifier, DRI, auditor, task pipeline.

No Redis/Celery needed: the event layer is faked by swapping
``redis_client.publish_event``/``save_result`` with recorders.
"""
from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from contracts.events import (
    PRECOMPUTATION_COMPLETED,
    PRECOMPUTATION_GROUP_COMPLETED,
    PRECOMPUTATION_PROGRESS,
    SYMBOL_RESULT_UPDATED,
)
from contracts.schemas import SymbolComputationResult, SymbolGroup

from precompute import redis_client
from precompute.classifier import (
    SymbolFeatures,
    classify_from_dicts,
    classify_symbols,
    compute_priority,
)
from precompute.dri_engine import DRISignals, compute_dri
from precompute.missing_data_auditor import MissingLevel, audit_batch, audit_row


def _row(symbol: str, price: float = 1000.0, value: float = 5e12, vol: float = 5e7, fresh: bool = True) -> dict:
    ts = datetime.now(UTC) if fresh else datetime.now(UTC) - timedelta(hours=2)
    return {
        "symbol": symbol,
        "price_last": price,
        "trade_volume": vol,
        "market": "TSE",
        "trade_value": value,
        "free_float_pct": 40,
        "price_lowest_allowed": price * 0.95,
        "price_highest_allowed": price * 1.05,
        "fetched_at": ts.isoformat(),
    }


# ── classifier ────────────────────────────────────────────────────────────
def test_priority_user_basket_boosts_score():
    base = SymbolFeatures(symbol="X", free_float_pct=40, trade_value=1e12, trade_volume=1e7)
    basket = SymbolFeatures(symbol="X", free_float_pct=40, trade_value=1e12, trade_volume=1e7, is_in_user_basket=True)
    assert compute_priority(basket) > compute_priority(base)


def test_classify_extremes_land_in_right_groups():
    rows = [_row(f"HIGH{i}", price=1000, value=9e13, vol=9e8) for i in range(6)]
    rows += [_row(f"LOW{i}", price=100, value=2e9, vol=2e3) for i in range(6)]
    groups = classify_from_dicts(rows)
    # High-liquidity names can never sink to C; low ones can never reach A.
    assert all(groups[f"HIGH{i}"] != SymbolGroup.C for i in range(6))
    assert all(groups[f"LOW{i}"] != SymbolGroup.A for i in range(6))
    assert groups["HIGH0"] == SymbolGroup.A and groups["LOW5"] == SymbolGroup.C


def test_classify_single_symbol_is_A():
    assert classify_symbols([SymbolFeatures(symbol="ONLY")]) == {"ONLY": SymbolGroup.A}


# ── DRI ───────────────────────────────────────────────────────────────────
def test_dri_full_signals_high_and_reliable():
    res = compute_dri(
        DRISignals(completeness=1.0, age_seconds=10, is_market_open=True, price_in_band=True,
                   volume_value_coherent=True, source_count=3, max_sources=3)
    )
    assert res.dri >= 90 and not res.is_unreliable


def test_dri_critical_missing_forces_unreliable():
    res = compute_dri(DRISignals(completeness=1.0, age_seconds=5, has_critical_missing=True))
    assert res.is_unreliable and "critical_missing" in res.red_flags


def test_dri_stale_during_market_forces_unreliable():
    res = compute_dri(
        DRISignals(completeness=0.9, age_seconds=7200, is_market_open=True, source_count=2, max_sources=3)
    )
    assert res.is_unreliable and "stale_during_market" in res.red_flags


def test_dri_bounds():
    res = compute_dri(DRISignals())
    assert 0.0 <= res.dri <= 100.0


# ── auditor ───────────────────────────────────────────────────────────────
def test_audit_flags_critical_and_reduces_completeness():
    res = audit_row({"symbol": "X", "market": "TSE"})
    assert res.has_critical
    assert "price_last" in res.missing[MissingLevel.CRITICAL]
    assert res.completeness < 1.0


def test_audit_applies_band_fallback_from_price():
    row = _row("FALL")
    del row["price_lowest_allowed"], row["price_highest_allowed"]
    res = audit_row(row)
    assert "price_lowest_allowed" in res.fallback_applied
    assert res.patched_row["price_lowest_allowed"] == round(row["price_last"] * 0.95)


def test_audit_batch_medians_fill_important_gaps():
    rows = [_row("A1"), _row("A2"), {"symbol": "A3", "price_last": 500, "trade_volume": 1e5, "market": "TSE"}]
    results, medians = audit_batch(rows)
    assert medians.get("trade_value"), "global median must be computed"
    assert "trade_value" in results[2].fallback_applied


# ── celery_tasks: computation + contract + events ────────────────────────
@pytest.fixture()
def captured(monkeypatch):
    events: list[tuple[str, dict]] = []
    stored: dict[str, dict] = {}

    async def fake_publish(event_type, payload, config=None):
        events.append((event_type, payload))

    async def fake_save(symbol, result, config=None):
        stored[symbol] = result

    monkeypatch.setattr(redis_client, "publish_event", fake_publish)
    monkeypatch.setattr(redis_client, "save_result", fake_save)
    # Deterministic: never touch a real broker even when Celery is installed.
    from precompute.workers import celery_tasks

    monkeypatch.setattr(celery_tasks, "_celery_app", None)
    monkeypatch.setattr(celery_tasks, "_get_celery_app", lambda: None)

    # _emit prefers the api ws_manager funnel when a loop is running.
    with contextlib.suppress(ImportError):
        import api.ws_manager as wsm

        class _FakeMgr:
            def broadcast_event(self, event_type, payload):
                events.append((event_type, payload))

        monkeypatch.setattr(wsm, "get_armor_ws_manager", lambda: _FakeMgr())
    return events, stored


def test_compute_single_symbol_matches_contract_schema():
    from precompute.workers.celery_tasks import compute_single_symbol

    result = compute_single_symbol(_row("VALID"), "A")
    parsed = SymbolComputationResult(**result)  # raises if shapes drift
    assert parsed.symbol == "VALID"
    assert 0 <= parsed.data_dri <= 100
    assert parsed.version == "v4.0"


def test_pipeline_emits_contract_events_in_order(captured):
    import asyncio

    from precompute.workers.celery_tasks import dispatch_armor_pipeline_async

    events, stored = captured
    groups = {
        "A": [_row("A_SYM"), _row("BAD", price=0.0, fresh=False)],
        "B": [_row("B_SYM")],
        "C": [],
    }
    payload = asyncio.run(dispatch_armor_pipeline_async(groups, job_id="test-job"))

    # Terminal contract payload validates and totals add up.
    PRECOMPUTATION_COMPLETED(**{k: payload[k] for k in PRECOMPUTATION_COMPLETED.model_fields})
    assert payload["total"] == 3
    assert set(stored) == {"A_SYM", "B_SYM", "BAD"}  # BAD still computed with fallbacks

    types = [t for t, _ in events]
    assert types.count("PRECOMPUTATION_GROUP_COMPLETED") == 3  # A, B, C
    assert types[-1] == "PRECOMPUTATION_COMPLETED"
    assert types.count("SYMBOL_RESULT_UPDATED") == payload["success"]
    # Every emitted payload validates against its contract model.
    for t, p in events:
        model = {"PRECOMPUTATION_PROGRESS": PRECOMPUTATION_PROGRESS,
                 "PRECOMPUTATION_GROUP_COMPLETED": PRECOMPUTATION_GROUP_COMPLETED,
                 "SYMBOL_RESULT_UPDATED": SYMBOL_RESULT_UPDATED,
                 "PRECOMPUTATION_COMPLETED": PRECOMPUTATION_COMPLETED}[t]
        model(**{k: p[k] for k in model.model_fields})


def test_sync_dispatch_refuses_running_loop(captured):
    """Regression: blocking the live loop used to raise 'loop is running'."""
    import asyncio

    from precompute.workers.celery_tasks import dispatch_armor_pipeline

    async def caller():
        with pytest.raises(RuntimeError, match="dispatch_armor_pipeline_async"):
            dispatch_armor_pipeline({"A": [_row("X")], "B": [], "C": []})

    asyncio.run(caller())


def test_result_json_roundtrip_hot_layer(captured):
    from precompute.workers.celery_tasks import compute_single_symbol

    result = compute_single_symbol(_row("RT"), "B")
    assert json.loads(json.dumps(result, ensure_ascii=False, default=str))["symbol"] == "RT"
