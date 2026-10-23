"""Step 1 - real execution of the signal-backtest call path.

Part A: the exact call sequence of POST /signal-insights/backtest against the live DB.
Part B: the same engine run on an isolated SQLite copy (audit_out/_tmp/step1_copy.sqlite)
        with pinned signals -> deterministic, re-runnable acceptance check.

The ONLY deviation from production: ``SignalAccuracyTracker.record_outcome`` is replaced by
a capturing stub so the audit does not write to the live ``signal_accuracy`` table.
Nothing else is stubbed; the engine, tracker.evaluate_signal and SQL are the real code.

Writes only inside audit_out/. No credentials printed.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, os.getcwd())  # run from the repo root: audit_out/_tmp is not a package

TMP = Path("audit_out/_tmp")
COPY = TMP / "step1_copy.sqlite"
PINNED = TMP / "step1_pinned_signals.json"

OUT: dict = {"part_a": {}, "part_b": {}}


def check_env() -> None:
    """core.config reads .env itself (pydantic-settings); do not pollute os.environ."""
    if not Path(".env").exists():
        raise SystemExit("missing .env")


def install_write_guard() -> list:
    """Replace the DB write in the tracker with an in-memory capture."""
    from services.signal_accuracy_tracker import SignalAccuracyTracker

    captured: list = []

    async def _capture(self, outcome):  # noqa: ANN001
        captured.append({
            "signal_id": getattr(outcome, "signal_id", None),
            "symbol": getattr(outcome, "symbol", None),
            "actual_return_pct": getattr(outcome, "actual_return_pct", None),
            "direction_correct": getattr(outcome, "direction_correct", None),
        })
        return True

    SignalAccuracyTracker.record_outcome = _capture
    return captured


async def part_a() -> None:
    from core.database import init_database
    from services.multi_market_signal_engine import MultiMarketSignalEngine
    from services.signal_backtest_engine import SignalBacktestEngine

    await init_database()
    captured = install_write_guard()

    t0 = time.monotonic()
    gen = MultiMarketSignalEngine()
    signals, reports = await gen.generate_all(
        market_filter="stock", signal_filter="all", limit=30
    )
    gen_s = time.monotonic() - t0

    sample = [{
        "symbol": getattr(s, "symbol", None),
        "date": str(getattr(s, "date", None)),
        "market": getattr(s, "market", None),
        "direction": getattr(s, "direction", None),
        "source": getattr(s, "source", None),
        "price": getattr(s, "price", None),
    } for s in signals[:8]]

    OUT["part_a"] = {
        "call_path": [
            "POST /signal-insights/backtest",
            "apps/api/endpoints/signal_insights.py:89 backtest_signals",
            "services/multi_market_signal_engine.py:357 MultiMarketSignalEngine.generate_all",
            "services/signal_backtest_engine.py:138 SignalBacktestEngine.backtest_signals",
            "services/signal_backtest_engine.py:257 _fetch_future_prices (live SQL)",
        ],
        "parameters": {"market": "stock", "source": "all", "days_forward": 30, "limit": 30},
        "generate_all_seconds": round(gen_s, 2),
        "signals_generated": len(signals),
        "market_reports": [{"market": r.market, "ok": r.success, "n": r.signal_count,
                            "ms": round(r.duration_ms, 1), "error": r.error} for r in reports],
        "signal_sample": sample,
        "today": date.today().isoformat(),
    }

    # The endpoint does exactly this before calling the engine:
    #   signals=[s.to_dict() for s in signals]   (apps/api/endpoints/signal_insights.py:112)
    try:
        payload = [s.to_dict() for s in signals]
        OUT["part_a"]["endpoint_signal_serialization"] = {"ok": True, "n": len(payload)}
    except Exception as e:  # noqa: BLE001
        OUT["part_a"]["endpoint_signal_serialization"] = {
            "ok": False,
            "exception": f"{type(e).__name__}: {e}",
            "site": "apps/api/endpoints/signal_insights.py:112",
        }
        from dataclasses import asdict
        payload = [asdict(s) for s in signals]
        OUT["part_a"]["serialization_workaround"] = "dataclasses.asdict"

    t1 = time.monotonic()
    res = await SignalBacktestEngine().backtest_signals(
        signals=payload, days_forward=30, market=None, source=None
    )
    bt_s = time.monotonic() - t1
    OUT["part_a"]["backtest_seconds"] = round(bt_s, 2)
    if not res.success:
        OUT["part_a"]["backtest"] = {"success": False, "error": res.error}
    else:
        OUT["part_a"]["backtest"] = {
            "success": True,
            "raw": res.value.to_dict(),
            "trades_returned": len(res.value.trades),
        }
    OUT["part_a"]["outcomes_the_tracker_would_have_written"] = len(captured)
    OUT["part_a"]["write_guard_sample"] = captured[:5]


async def part_b(anchor_within_copy: bool = True) -> None:
    """Isolated copy: real engine + real tracker SQL, SQLite instead of PostgreSQL."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    import core.database as dbmod
    from services.signal_backtest_engine import SignalBacktestEngine

    if not COPY.exists():
        raise SystemExit(f"missing {COPY}; run step1_snapshot.py first")

    eng = create_async_engine(f"sqlite+aiosqlite:///{COPY.as_posix()}", future=True)
    dbmod.async_session_factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)

    pinned = json.loads(PINNED.read_text(encoding="utf-8"))
    bars = sqlite3.connect(COPY).execute(
        "SELECT symbol, min(gregorian_date), max(gregorian_date) FROM brsapi_historical_daily "
        "GROUP BY symbol ORDER BY symbol"
    ).fetchall()

    # signal dates: the copy's oldest gregorian_date (so the window is non-empty)
    oldest = min(b[1] for b in bars)
    for s in pinned:
        s["date"] = oldest
    shifted = [dict(s, date=max(b[2] for b in bars)) for s in pinned]  # newest sync date

    results = {}
    for label, sigs in (("anchor_oldest_gregorian", pinned), ("anchor_newest_gregorian", shifted)):
        res = await SignalBacktestEngine().backtest_signals(signals=sigs, days_forward=30)
        entry: dict = {
            "signal_dates": sorted({s["date"] for s in sigs}),
            "success": res.success,
            "raw": res.value.to_dict() if res.success else None,
            "error": None if res.success else res.error,
            "n_trades": len(res.value.trades) if res.success else 0,
        }
        if res.success:
            entry["trades"] = res.value.trades
            try:
                json.dumps(res.value.to_dict(), allow_nan=False)
                entry["strict_json_serializable"] = True
            except ValueError as e:
                entry["strict_json_serializable"] = False
                entry["strict_json_error"] = f"{type(e).__name__}: {e}"
                entry["non_finite_fields"] = [
                    k for k, v in res.value.to_dict().items()
                    if isinstance(v, float) and (v != v or v in (float("inf"), float("-inf")))
                ]
        results[label] = entry

    OUT["part_b"] = {
        "db": str(COPY),
        "table": "brsapi_historical_daily (copy of live rows, price_close > 0)",
        "symbol_ranges": [{"symbol": b[0], "min_gregorian": b[1], "max_gregorian": b[2]} for b in bars],
        "engine_transaction_costs": SignalBacktestEngine.DEFAULT_TRANSACTION_COSTS,
        "results": results,
    }
    await eng.dispose()
    dbmod.async_session_factory = None


async def main() -> None:
    check_env()
    if "--only-b" not in sys.argv:
        await part_a()
    await part_b()
    (TMP / "step1_run_raw.json").write_text(
        json.dumps(OUT, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(OUT, indent=2, ensure_ascii=False))


asyncio.run(main())
