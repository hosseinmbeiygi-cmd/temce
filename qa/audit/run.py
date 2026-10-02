#!/usr/bin/env python3
"""Read-only synthetic QA, deliberately not a full-system qualification.

Exactly 75 accounting/analytics + 55 ML + 50 screener + 20 specialized cases.
Exit 0 = all contracts hold; 1 = observed contract failures/runtime errors;
2 = harness/infrastructure/immutability failure. All evidence stays in qa/.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import socket
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
AUDIT_REPORTS = {
    "reports/QA_AUDIT_2026-10-03.md",
    "reports/QA_PROPOSED_FIXES_2026-10-03.diff",
    "reports/QA_READINESS_2026-10-03.json",
}


def tracked_hashes():
    files = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files
            if p and not p.startswith("qa/") and p not in AUDIT_REPORTS and (ROOT / p).is_file()}


# Capture before any original application import, so import side effects are covered.
BASELINE = tracked_hashes()
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
os.environ.update({
    "ENV": "test", "PYTHONDONTWRITEBYTECODE": "1",
    "DATABASE_URL": "postgresql+asyncpg://qa:qa@127.0.0.1:1/qa_never_connect",
    "REDIS_URL": "redis://127.0.0.1:1/0",
    "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
})
WORK = ROOT / "qa/runtime/work"
WORK.mkdir(parents=True, exist_ok=True)
os.chdir(WORK)

# This suite needs no network, including loopback. Fail closed before app imports.
BLOCKED_NETWORK = []
_connect, _connect_ex = socket.socket.connect, socket.socket.connect_ex

def deny_connect(sock, address):
    if sock.family in (socket.AF_INET, socket.AF_INET6):
        BLOCKED_NETWORK.append(str(address))
        raise RuntimeError("QA blocked an IP network connection")
    return _connect(sock, address)

def deny_connect_ex(sock, address):
    if sock.family in (socket.AF_INET, socket.AF_INET6):
        BLOCKED_NETWORK.append(str(address))
        raise RuntimeError("QA blocked an IP network connection")
    return _connect_ex(sock, address)

socket.socket.connect = deny_connect
socket.socket.connect_ex = deny_connect_ex

import numpy as np
import pandas as pd
from backtesting.analytics.engine import AnalyticsEngine, AnalyticsResult
from backtesting.engine.portfolio import PortfolioManager
from backtesting.types import FillEvent
from domain.options.margin_engine import (
    DEFAULT_CONFIG, Direction, LegType, OptionLeg, UniversalMarginEngine,
)
from domain.options.pricing import black_scholes_price, implied_volatility
from ml.features.microstructure_features import MicrostructureFeatures
from ml.features.trade_features import TradeFeatures
from ml.models.shallow.linear_models import LinearRegressionModel, LogisticRegressionModel
from ml.models.shallow.tree_models import RandomForestModel
from ml.types import FeatureMatrix, TargetVector
from services.gold.calculator import (
    TROY_OUNCE_GRAM, calculate_coin_bubble, calculate_dollar_adjusted_return,
    calculate_nav_premium,
)
from services.screener_service import (
    ScreenedSymbol, ScreenerPipeline, ScreenerService, _get_filter_value,
    _get_sort_value,
)
from services.smart_screener_v2 import SmartScreenerV2

STAMP = datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)
SEED = 20261003
CASES = []
EVIDENCE = {}


def clean(value):
    """Strict JSON: preserve nonfinite evidence as strings, never JSON NaN."""
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def check(actual, expected, label, *, tolerance=1e-8):
    EVIDENCE[label] = {"actual": clean(actual), "expected": clean(expected)}
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        ok = isinstance(actual, (int, float, np.number)) and math.isfinite(actual)
        ok = ok and math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance)
    else:
        ok = actual == expected
    if not ok:
        raise AssertionError(f"{label}: expected {expected!r}, observed {actual!r}")


def case(category, family, number, function, parameters):
    CASES.append({"id": f"{category}-{family}-{number:02d}", "category": category,
                  "family": family, "parameters": parameters, "function": function})


def fill(side, quantity, price, commission=0.0, offset=0):
    return FillEvent(f"qa-{side}-{offset}", "QA-SYNTHETIC", side, quantity, price,
                     commission, STAMP + timedelta(seconds=offset))


def portfolio(capital):
    p = PortfolioManager()
    p.reset(capital)
    return p


def rejects(operation):
    try:
        operation()
    except (ValueError, TypeError):
        return True
    return False


def bt_roundtrip(i):
    q, buy, sell, fee = i + 1, 100.0 + i, 112.0 + i, 0.25 * (i + 1)
    p = portfolio(100_000.0)
    trades = [fill("buy", q, buy, fee), fill("sell", q, sell, fee, 1)]
    for f in trades:
        p.update_fill_sync(f)
    expected = (sell - buy) * q - 2 * fee
    check(p.get_nav(), 100_000 + expected, "cash_and_nav_after_roundtrip")
    ar = AnalyticsResult()
    AnalyticsEngine()._compute_trade_metrics(ar, trades)
    check(ar.avg_win, expected, "fifo_net_pnl_includes_both_fees")
    check(p.get_position("QA-SYNTHETIC"), 0, "flat_quantity")


def bt_drawdown(i):
    scale = i + 1
    navs = [100 * scale, 80 * scale, 1000 * scale, 950 * scale]
    ar = AnalyticsResult()
    AnalyticsEngine()._compute_drawdown(ar, navs)
    peak = navs[0]
    maximum = 0.0
    for nav in navs:
        peak = max(peak, nav)
        maximum = max(maximum, (peak - nav) / peak * 100)
    check(ar.max_drawdown_pct, maximum, "maximum_percentage_independent_of_absolute_dd")


def bt_budget(i):
    capital = 100.0 * (i + 1)
    p = portfolio(capital)
    accepted_error = rejects(lambda: p.update_fill_sync(fill("buy", i + 2, 100)))
    check(accepted_error or p.get_cash() >= 0, True, "long_only_fill_cannot_create_negative_cash")


def bt_invalid(i):
    q, price = [(-1, 100.0), (0, 100.0), (1, -10.0),
                (1, float("nan")), (1, float("inf"))][i % 5]
    p = portfolio(1000)
    rejected = rejects(lambda: p.update_fill_sync(fill("buy", q, price)))
    check(rejected, True, "reject_invalid_fill_domain")
    check(p.get_cash(), 1000, "rejection_keeps_cash_atomic")
    check(p.get_positions(), {}, "rejection_keeps_positions_atomic")


def bt_oversell(i):
    p = portfolio(10_000)
    p.update_fill_sync(fill("buy", i + 1, 100))
    requested = fill("sell", (i + 1) * 2, 120, 10)
    before = (requested.quantity, requested.commission)
    try:
        p.update_fill_sync(requested)
    except ValueError:
        pass
    check((requested.quantity, requested.commission), before, "caller_owned_fill_not_mutated")


def bt_precision(i):
    # Explicit boundary probe, not an assertion of reachable live account limits.
    capital = 10**16 + i * 100
    p = portfolio(capital)
    p.update_fill_sync(fill("buy", 1, 1.0))
    observed = int(p.get_cash())
    check(observed == capital - 1, True, "exact_single_rial_cash_debit")
    EVIDENCE["observed_integer_cash"] = observed


for family, count, fn in [("roundtrip", 15, bt_roundtrip), ("drawdown", 15, bt_drawdown),
                          ("budget", 15, bt_budget), ("invalid", 10, bt_invalid),
                          ("oversell", 10, bt_oversell), ("precision", 10, bt_precision)]:
    for i in range(count):
        case("BT", family, i, lambda i=i, fn=fn: fn(i), {"variant": i})


def micro_data(multiplier):
    n = 12
    return pd.DataFrame({
        "date": pd.date_range("2026-09-01", periods=n), "symbol": ["QA"] * n,
        "trade_count": [1] * n, "volume": [0] + [10] * (n - 1),
        "value": [0, 1000 * multiplier] + [1000] * (n - 2),
        "price_open": [100.] * n, "price_high": [110.] * n,
        "price_low": [90.] * n, "price_close": [100.] * n, "price_last": [100.] * n,
    })


def ml_prefix(i):
    original = MicrostructureFeatures().compute(micro_data(1)).data.iloc[0]["vwap"]
    changed = MicrostructureFeatures().compute(micro_data(i + 2)).data.iloc[0]["vwap"]
    check(changed, original, "future_row_must_not_change_first_row_vwap")


def ml_trade(i):
    n = 12 + i
    df = pd.DataFrame({"date": pd.date_range("2026-09-01", periods=n),
                       "symbol": ["QA"] * n})
    for actor in ("real", "legal"):
        for side in ("buy", "sell"):
            for metric, value in (("volume", 10), ("value", 1000), ("count", 1)):
                df[f"{actor}_{side}_{metric}"] = value + i
    result = TradeFeatures().compute(df)
    check(len(result.data), n, "trade_feature_builder_accepts_complete_schema")


def ml_linear(i):
    rng = np.random.default_rng(SEED + i)
    x = rng.normal(size=(80, 3))
    y = x @ np.array([2.0, -3.0, 0.5]) + 7
    model = LinearRegressionModel()
    model.fit(FeatureMatrix(x[:60]), TargetVector(y[:60]))
    predictions = model.predict(FeatureMatrix(x[60:])).predictions
    check(float(np.max(np.abs(predictions - y[60:]))), 0.0, "linear_holdout_error", tolerance=1e-7)


def ml_logistic(i):
    rng = np.random.default_rng(SEED + 100 + i)
    x = np.vstack([rng.normal(-3, .25, (60, 2)), rng.normal(3, .25, (60, 2))])
    y = np.array([0] * 60 + [1] * 60)
    train = np.r_[0:45, 60:105]
    test = np.r_[45:60, 105:120]
    model = LogisticRegressionModel(params={"random_state": SEED, "max_iter": 200})
    model.fit(FeatureMatrix(x[train]), TargetVector(y[train], task_type="classification"))
    result = model.predict(FeatureMatrix(x[test]))
    check(float(np.mean(result.predictions == y[test])), 1.0, "classification_holdout_accuracy")


def ml_forest(i):
    rng = np.random.default_rng(SEED + 200 + i)
    x = rng.normal(size=(80, 3))
    y = x[:, 0] - x[:, 1]
    predictions = []
    for _ in range(2):
        model = RandomForestModel(params={"random_state": SEED, "n_estimators": 12, "n_jobs": 1})
        model.fit(FeatureMatrix(x[:60]), TargetVector(y[:60]))
        predictions.append(model.predict(FeatureMatrix(x[60:])).predictions)
    check(bool(np.isfinite(predictions[0]).all()), True, "forest_finite_holdout")
    check(bool(np.array_equal(*predictions)), True, "forest_seeded_repeatability")


for family, count, fn in [("causal_prefix", 15, ml_prefix), ("trade_schema", 10, ml_trade),
                          ("linear", 15, ml_linear), ("logistic", 10, ml_logistic),
                          ("forest", 5, ml_forest)]:
    for i in range(count):
        case("ML", family, i, lambda i=i, fn=fn: fn(i), {"variant": i, "seed": SEED + i})


def screened(value=100.0, details=None):
    return ScreenedSymbol("QA", "Synthetic", "TSE", "test", value, 0., 10, 1000.,
                          details=details or {})


def sc_numeric(i):
    ops = ["gte", "lte", "gt", "lt", "eq", "between"]
    op, offset = ops[i % 6], [-2, 0, 2, 5][i // 6]
    value, threshold = 100.0 + offset, 100.0
    expected = {"gte": value >= threshold, "lte": value <= threshold,
                "gt": value > threshold, "lt": value < threshold,
                "eq": abs(value - threshold) < max(abs(threshold) * .01, .001),
                "between": 100 <= value <= 103}[op]
    filt = {"field": "last_price", "operator": op, "value": "100", "value_to": "103"}
    check(ScreenerService._apply_filter(screened(value), {}, [filt], "and"), expected,
          "filter_numeric_oracle")


def sc_logic(i):
    filters = [{"field": "market", "operator": "contains", "value": "ts"},
               {"field": "last_price", "operator": "gt", "value": 120}]
    logic = "or" if i % 2 else "and"
    check(ScreenerService._apply_filter(screened(100 + i), {}, filters, logic), logic == "or",
          "filter_and_or_and_strings")


def sc_closed(i):
    filt = ({"field": "missing_field", "operator": "gte", "value": 0} if i % 2 else
            {"field": "last_price", "operator": "unknown", "value": 0})
    check(ScreenerService._apply_filter(screened(), {}, [filt], "and"), False,
          "unknown_or_missing_filter_fails_closed")


def sc_sort(i):
    values = [0., -1., 10., 100., None, "1,234"]
    actual = _get_sort_value(screened(details={"pe_ratio": values[i]}), "pe_ratio")
    expected = [0., -1., 10., 100., 0., 1234.][i]
    check(actual, expected, "sort_numeric_oracle_including_formatted_value")


def quote_history(i):
    base = 100 + i
    history = []
    for d in range(160):
        p = base + d * .5 + math.sin(d) * 2
        history.append({"date": (STAMP - timedelta(days=160-d)).date().isoformat(),
                        "price_open": p - 1, "price_high": p + 2, "price_low": p - 2,
                        "price_close": p, "price_last": p, "volume": 10_000 + d,
                        "value": p * (10_000 + d), "trade_count": 100,
                        "real_buy_volume": 5000, "real_sell_volume": 4000,
                        "legal_buy_volume": 3000, "legal_sell_volume": 4000,
                        "real_buy_count": 20, "real_sell_count": 20,
                        "legal_buy_count": 5, "legal_sell_count": 5})
    quote = dict(history[-1], price_change_pct=1.)
    return quote, history


def sc_rsi(i):
    quote, history = quote_history(i)
    result = ScreenerPipeline().run("QA-RSI", "Synthetic", "TSE", "test", quote, history)
    actual = _get_filter_value(result, quote, "rsi")
    EVIDENCE["lookup"] = clean(actual)
    check(actual is not None and math.isfinite(float(actual)), True,
          "pipeline_populates_advertised_rsi_filter")


def sc_cache(i):
    service = SmartScreenerV2()
    quote, history = quote_history(i)
    first = service.analyze_symbol("QA-CACHE", "Synthetic", "TSE", "test", quote, history)
    new_quote = dict(quote, price_close=quote["price_close"] * 2)
    new_history = [dict(row) for row in history]
    new_history[-1]["price_close"] = new_quote["price_close"]
    second = service.analyze_symbol("QA-CACHE", "Synthetic", "TSE", "test", new_quote, new_history)
    EVIDENCE["previous_price"] = first.last_price
    check(second.last_price, new_quote["price_close"], "same_length_history_cache_is_content_aware")


for family, count, fn in [("numeric", 24, sc_numeric), ("logic", 6, sc_logic),
                          ("fail_closed", 6, sc_closed), ("sort", 6, sc_sort),
                          ("rsi", 4, sc_rsi), ("cache", 4, sc_cache)]:
    for i in range(count):
        case("SC", family, i, lambda i=i, fn=fn: fn(i), {"variant": i})


def sp_zero_sigma(i):
    kind, s, k, r = [("call", 100., 90., .05), ("put", 90., 100., .05),
                     ("call", 100., 110., .20), ("put", 90., 100., .20)][i]
    discounted = k * math.exp(-r)
    expected = max(0., s - discounted) if kind == "call" else max(0., discounted - s)
    check(black_scholes_price(s, k, 1., r, 0., kind).price, expected,
          "positive_maturity_zero_vol_discounted_forward_payoff")


def sp_margin(i):
    config = dict(DEFAULT_CONFIG, min_margin=0., portfolio_discount=0.)
    engine = UniversalMarginEngine(config)
    short = OptionLeg(LegType.CALL, Direction.SHORT, strike=100, premium=5,
                      underlying_price=100, quantity=10, days_to_expiry=30)
    long = OptionLeg(LegType.CALL, Direction.LONG, strike=110, premium=2,
                     underlying_price=100, quantity=1 + i % 2, days_to_expiry=30)
    if i < 2:
        actual = engine.calculate_margin([short, long]).total_initial_margin
        residual = engine._naked_short_margin(OptionLeg(
            LegType.CALL, Direction.SHORT, strike=100, premium=5,
            underlying_price=100, quantity=short.quantity - long.quantity, days_to_expiry=30))
        EVIDENCE["actual_and_residual_lower_bound"] = {"actual": actual, "lower_bound": residual}
        check(actual >= residual, True, "unequal_spread_residual_requires_naked_margin")
    elif i < 4:
        stock = OptionLeg(LegType.STOCK, Direction.LONG, quantity=10_000, contract_size=1)
        put = OptionLeg(LegType.PUT, Direction.SHORT, strike=100, premium=5,
                        underlying_price=100, quantity=1 + i % 2)
        actual = engine.calculate_margin([stock, short, put]).total_initial_margin
        check(actual >= engine._naked_short_margin(put), True,
              "covered_calls_do_not_remove_unrelated_naked_put_margin")
    else:
        engine = UniversalMarginEngine()
        actual = engine.calculate_margin([OptionLeg(LegType.CALL, Direction.SHORT,
            strike=100, premium=1, underlying_price=100)]).total_initial_margin
        check(actual >= DEFAULT_CONFIG["min_margin"], True, "single_naked_minimum_not_discounted")


def sp_nav(i):
    price, nav = [(100., float("nan")), (float("nan"), 100.),
                  (100., float("inf")), (float("inf"), 100.)][i]
    check(rejects(lambda: calculate_nav_premium(price, nav)), True,
          "nav_premium_rejects_nonfinite_input")


def sp_coin(i):
    weight, purity, oz, usd = 8.133, .900, 2000. + i * 100, 600_000.
    intrinsic = oz / TROY_OUNCE_GRAM * weight * purity * usd
    result = calculate_coin_bubble(intrinsic * 1.2, oz, usd, weight_g=weight, purity=purity)
    check(result.coin_intrinsic_irr, round(intrinsic, 2), "explicit_physical_gold_content_irr")
    check(result.bubble_pct, 20., "explicit_coin_bubble_pct", tolerance=1e-6)


def sp_usd(i):
    entry, current, efx, cfx = 1_000_000., 1_200_000. + i * 100_000, 500_000., 600_000.
    result = calculate_dollar_adjusted_return(entry, current, efx, cfx)
    expected = ((current / cfx) / (entry / efx) - 1) * 100
    check(result.dollar_roi_pct, round(expected, 2), "dollar_adjusted_return_oracle")


def sp_iv(i):
    option_type = "call" if i == 0 else "put"
    check(rejects(lambda: implied_volatility(1000., 100., 100., 1., .05, option_type)),
          True, "implied_volatility_rejects_impossible_option_premium")


for family, count, fn in [("zero_sigma", 4, sp_zero_sigma), ("margin", 5, sp_margin),
                          ("nav_finite", 4, sp_nav), ("coin", 2, sp_coin),
                          ("usd", 3, sp_usd), ("iv_bounds", 2, sp_iv)]:
    for i in range(count):
        case("SP", family, i, lambda i=i, fn=fn: fn(i), {"variant": i})


def run(output):
    assert len(CASES) == 200
    assert Counter(c["category"] for c in CASES) == {"BT": 75, "ML": 55, "SC": 50, "SP": 20}
    # The full per-file manifest is runtime-only; compact aggregate proof is versioned.
    baseline_path = ROOT / "qa/runtime/baseline_hashes.json"
    baseline_path.write_text(json.dumps(BASELINE, sort_keys=True) + "\n")
    baseline = BASELINE
    before = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() if (ROOT / p).is_file() else None
              for p in baseline}
    if before != baseline:
        raise RuntimeError("Original tracked file differs from captured baseline")
    rows = []
    started = time.perf_counter()
    for c in CASES:
        EVIDENCE.clear()
        t0 = time.perf_counter()
        status, error = "PASS", None
        try:
            c["function"]()
        except AssertionError as exc:
            status, error = "FAIL", {"type": type(exc).__name__, "message": str(exc)}
        except Exception as exc:
            status, error = "ERROR", {"type": type(exc).__name__, "message": str(exc),
                                       "traceback": traceback.format_exc(limit=5)}
        rows.append({**{k: v for k, v in c.items() if k != "function"},
                     "status": status, "error": error, "observations": dict(EVIDENCE),
                     "duration_ms": round((time.perf_counter() - t0) * 1000, 3),
                     "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
    after = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() if (ROOT / p).is_file() else None
             for p in baseline}
    changed = [p for p in baseline if baseline[p] != after[p]]
    # Only economic observations and outcomes enter the digest: no wall clock, RSS, UUIDs or stack paths.
    canonical = [{k: r[k] for k in ("id", "category", "family", "parameters", "status", "observations")}
                 | {"error": ({k: r["error"][k] for k in ("type", "message")} if r["error"] else None)}
                 for r in rows]
    digest = hashlib.sha256(json.dumps(clean(canonical), sort_keys=True, allow_nan=False).encode()).hexdigest()
    report = {
        "schema_version": 1, "suite": "compact-read-only-200-v1", "seed": SEED,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "historical_evidence_reused": False, "scope": "isolated original numerical modules; not full app/UI/API",
        "counts": dict(Counter(r["status"] for r in rows)),
        "by_category": {k: dict(Counter(r["status"] for r in rows if r["category"] == k)) for k in ("BT", "ML", "SC", "SP")},
        "duration_seconds": round(time.perf_counter() - started, 3),
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "economic_digest_sha256": digest,
        "isolation": {"network_policy": "all IP socket connects blocked", "blocked_attempts": BLOCKED_NETWORK,
                      "external_services_started": False, "persistent_test_state": "QA runtime workspace only"},
        "immutability": {"baseline_files": len(baseline), "changed_original_files": changed,
                         "baseline_manifest_sha256": hashlib.sha256(baseline_path.read_bytes()).hexdigest()},
        "cases": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(clean(report), indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: report[k] for k in ("counts", "by_category", "duration_seconds", "economic_digest_sha256", "immutability")}))
    if changed or BLOCKED_NETWORK:
        return 2
    return int(any(r["status"] != "PASS" for r in rows))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "qa/audit/results.json")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT / "qa"):
        parser.error("Evidence output must be inside qa/")
    try:
        sys.exit(run(output))
    except Exception:
        traceback.print_exc()
        sys.exit(2)
