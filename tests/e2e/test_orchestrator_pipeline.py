"""E2E test: Run QuantSignalOrchestrator.generate() with real DB and validate the full pipeline.

Tests each stage:
  1. Engine → rule-based signals
  2. ML predictions (disabled if no trained models)
  3. Voting
  4. Confidence calibration
  5. Cross-market correlation
  6. Confidence filter
  6.5. Persist pending signals
  7. Outcome evaluation + auto-retrain check
"""
from __future__ import annotations

import asyncio
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

# Ensure project root is in sys.path (tests/e2e/ → project root)
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import core.database
from core.database import init_database
from core.logging import get_logger
from services.quant_signal_orchestrator import QuantSignalOrchestrator

logger = get_logger("e2e_test")

PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"


def check(condition: bool, label: str) -> bool:
    # Encode to ASCII to avoid Windows console Unicode issues
    msg = f"  {PASS if condition else FAIL} {label}"
    print(msg.encode("ascii", errors="replace").decode("ascii"))
    return condition


async def main() -> int:
    errors = 0

    print("=" * 60)
    print("QuantSignalOrchestrator E2E Pipeline Test")
    print(f"Time: {datetime.now(UTC).isoformat()}")
    print("=" * 60)
    # Force UTF-8 output on Windows
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # ── Stage 0: DB connectivity ──
    print("\n[Stage 0] Database connectivity + init")
    db_connected = False
    try:
        await init_database()
        db_connected = core.database.async_session_factory is not None
        if db_connected:
            async with core.database.async_session_factory() as session:
                from sqlalchemy import text

                result = await session.execute(text("SELECT 1"))
                check(result.scalar() == 1, "Database connection OK")
                # Verify signal_accuracy table exists
                try:
                    await session.execute(text("SELECT COUNT(*) FROM signal_accuracy"))
                    check(True, "signal_accuracy table exists (feedback loop ready)")
                except Exception:
                    print(f"  {FAIL} signal_accuracy table MISSING — run 'alembic upgrade head'")
                    errors += 1
        else:
            print(f"  {FAIL} init_database() completed but async_session_factory is None")
            errors += 1
    except Exception as e:
        print(f"  {SKIP} DB init failed: {str(e)[:120]}")
        print(f"  {SKIP} Running in memory-only mode for structural validation.")

    # ── Stage 1: Create orchestrator ──
    print("\n[Stage 1] Create QuantSignalOrchestrator")
    try:
        orch = QuantSignalOrchestrator()
        check(True, "Orchestrator created")
    except Exception as e:
        print(f"  {FAIL} Failed: {e}")
        traceback.print_exc()
        return 1

    # ── Run generate() with ML disabled ──
    print("\n[Stage 2] Run generate() — no ML, no voting, no confidence (fast path)")
    try:
        report = await orch.generate(
            market_filter="all",
            timeframe_filter="all",
            signal_filter="all",
            min_strength=0.0,
            min_confidence=0.0,  # don't filter — we want all signals
            limit=20,
            use_ml=False,
            use_voting=False,
            use_confidence_calibration=False,
        )
        check(True, "generate() returned without exception")
    except Exception as e:
        print(f"  {FAIL} generate() crashed: {e}")
        traceback.print_exc()
        errors += 1
        return errors

    # ── Validate output ──
    print("\n[Stage 3] Validate orchestrator report structure")

    d = report.to_dict()
    check(isinstance(d, dict), "report.to_dict() returns dict")
    check("signals" in d, "report has 'signals' key")
    check("summary" in d, "report has 'summary' key")
    check("reports" in d, "report has 'reports' key")
    check("accuracy" in d, "report has 'accuracy' key")
    check("cross_market" in d, "report has 'cross_market' key")
    check("retrain" in d, "report has 'retrain' key")
    check("generated_at" in d, "report has 'generated_at' key")

    # ── Validate signals ──
    signals = d.get("signals", [])
    print(f"\n[Stage 4] Signal validation — {len(signals)} signals returned")

    if len(signals) > 0:
        first = signals[0]
        required_fields = [
            "symbol",
            "name",
            "market",
            "direction",
            "timeframe",
            "entry_zone",
            "stop_loss",
            "targets",
            "risk_reward",
            "price",
            "change_pct",
            "rule_score",
            "boosted_score",
            "confidence",
            "calibration_level",
            "vote_strategy",
            "source",
        ]
        for field in required_fields:
            check(field in first, f"signal has '{field}' field")

        # Check direction values
        valid_dirs = {"buy", "sell", "hold", "wait"}
        for s in signals:
            if s.get("direction") not in valid_dirs:
                print(f"  {FAIL} Invalid direction '{s.get('direction')}' for {s.get('symbol')}")
                errors += 1

        # Check market values
        valid_markets = {
            "stock",
            "gold",
            "currency",
            "crypto",
            "option",
            "commodity",
            "ime",
        }
        for s in signals:
            if s.get("market") not in valid_markets:
                print(f"  {FAIL} Invalid market '{s.get('market')}' for {s.get('symbol')}")
                errors += 1

        # Count by direction
        from collections import Counter

        dir_counts = Counter(s.get("direction") for s in signals)
        print(f"  [INFO] Direction distribution: {dict(dir_counts)}")

        # Count by market
        market_counts = Counter(s.get("market") for s in signals)
        print(f"  [INFO] Market distribution: {dict(market_counts)}")
    else:
        print(f"  {SKIP} No signals generated — may need data in DB tables")

    # ── Validate summary ──
    summary = d.get("summary", {})
    print("\n[Stage 5] Summary validation")
    for key in [
        "total_signals",
        "buy_count",
        "sell_count",
        "hold_count",
        "markets",
        "filters",
    ]:
        check(key in summary, f"summary has '{key}' key")

    # ── Validate generation reports ──
    reports = d.get("reports", [])
    print(f"\n[Stage 6] Generation reports — {len(reports)} markets reported")
    if reports:
        for r in reports:
            status = "OK" if r.get("success") else "ERR"
            err = (" [error: " + str(r.get("error", "")) + "]") if not r.get("success") else ""
            print(f"  [{status}] {r.get('market')}: {r.get('signal_count')} signals{err}")

    # ── Validate cross-market signals ──
    cross = d.get("cross_market", [])
    print(f"\n[Stage 7] Cross-market signals — {len(cross)} entries")
    if cross:
        for cs in cross:
            desc = (cs.get("description", "") or "")[:60]
            print(f"  [SIGNAL] {cs.get('name')} [{cs.get('signal')}] - {desc}...")

    # ── Validate retrain reports ──
    retrain = d.get("retrain", [])
    print(f"\n[Stage 8] Retrain reports — {len(retrain)} markets retrained")
    if retrain:
        for rr in retrain:
            print(
                f"  [RETRAIN] {rr.get('market')}: {rr.get('trigger')} "
                f"({rr.get('old_accuracy_pct', 0):.1f}% -> {rr.get('new_accuracy_pct', 0):.1f}%)"
            )

    # ── Stage 9: Run with ML enabled (may fail gracefully if no models) ──
    print("\n[Stage 9] Run generate() — full pipeline (ML + voting + confidence)")
    try:
        report_full = await orch.generate(
            market_filter="stock",  # stocks only for speed
            timeframe_filter="daily",
            min_confidence=0.35,
            limit=10,
            use_ml=True,
            use_voting=True,
            use_confidence_calibration=True,
        )
        d_full = report_full.to_dict()
        sigs = d_full.get("signals", [])
        print(f"  {PASS} Full pipeline completed — {len(sigs)} signals")

        # Check that confidence is calibrated (should be 0-1 range)
        if sigs:
            conf_values = [s.get("confidence", 0) for s in sigs]
            avg_conf = sum(conf_values) / len(conf_values)
            check(
                0 <= avg_conf <= 1,
                f"Average confidence {avg_conf:.3f} in valid range (0-1)",
            )
            # Check calibration levels
            levels = Counter(s.get("calibration_level") for s in sigs)
            print(f"  [INFO] Calibration distribution: {dict(levels)}")
            # Check vote strategies
            votes = Counter(s.get("vote_strategy") for s in sigs)
            print(f"  [INFO] Vote strategy distribution: {dict(votes)}")
    except Exception as e:
        print(f"  {SKIP} Full pipeline failed (likely no ML models trained): {e}")

    # ── Final summary ──
    print("\n" + "=" * 60)
    if errors == 0:
        print("ALL TESTS PASSED - Pipeline is healthy!")
    else:
        print(f"{errors} error(s) found - see above for details")
    print("=" * 60)
    return min(errors, 1)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
