"""Quick test: mimic the hourly orchestrator cron's run-now — full pipeline with ML."""
from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import core.database
from core.database import init_database
from services.quant_signal_orchestrator import QuantSignalOrchestrator


async def main() -> int:
    print("=" * 60)
    print("ORCHESTRATOR CRON — Run-Now Simulation")
    print(f"Time: {datetime.now(UTC).isoformat()}")
    print("=" * 60)

    # Init DB
    print("\n[1] Initializing database...")
    try:
        await init_database()
        if core.database.async_session_factory is not None:
            print("  [OK] Database connected")
        else:
            print("  [SKIP] No DB — running in memory mode")
    except Exception as e:
        print(f"  [SKIP] DB init failed: {e}")

    # Run orchestrator
    print("\n[2] Running orchestrator.generate() — full pipeline (ML + voting + confidence)...")
    orchestrator = QuantSignalOrchestrator()
    report = await orchestrator.generate(
        market_filter="all",
        timeframe_filter="all",
        min_confidence=0.35,
        limit=100,
        use_ml=True,
        use_voting=True,
        use_confidence_calibration=True,
    )

    d = report.to_dict()

    # Results
    signals = d.get("signals", [])
    accuracy = d.get("accuracy", {})
    retrain = d.get("retrain", [])
    cross_market = d.get("cross_market", [])
    reports = d.get("reports", [])

    print("\n[3] Results:")
    print(f"  Signals generated:     {len(signals)}")
    print(f"  Markets covered:       {sorted({s.get('market', '?') for s in signals})}")
    print(f"  Overall accuracy:      {accuracy.get('overall', 'N/A')}%")

    # Direction distribution
    from collections import Counter

    dirs = Counter(s.get("direction", "?") for s in signals)
    print(f"  Direction distribution: {dict(dirs)}")

    # ML coverage
    ml_signals = [s for s in signals if s.get("ml_score", 0) > 0]
    print(f"  ML score > 0:          {len(ml_signals)}/{len(signals)}")

    # Confidence stats
    if signals:
        confs = [s.get("confidence", 0) for s in signals]
        print(f"  Avg confidence:        {sum(confs)/len(confs):.3f}")

    # Calibration levels
    levels = Counter(s.get("calibration_level", "?") for s in signals)
    print(f"  Calibration levels:    {dict(levels)}")

    # Vote strategies
    votes = Counter(s.get("vote_strategy", "?") for s in signals)
    print(f"  Vote strategies:       {dict(votes)}")

    # Cross-market
    print(f"  Cross-market signals:  {len(cross_market)}")
    for cs in cross_market:
        if cs.get("name") != "Market-Biases":
            print(f"    [{cs.get('signal', '?')}] {cs.get('name', '?')}")

    # Per-market report
    print(f"\n[4] Generation reports ({len(reports)} markets):")
    for r in reports:
        status = "OK" if r.get("success") else "ERR"
        err = f" — {r.get('error', '')[:80]}" if not r.get("success") else ""
        print(f"  [{status}] {r.get('market', '?')}: {r.get('signal_count', 0)} signals{err}")

    # Retrain
    print(f"\n[5] Retrain: {len(retrain)} markets")
    for rr in retrain:
        print(
            f"  [RETRAIN] {rr.get('market', '?')}: {rr.get('trigger', '?')} "
            f"({rr.get('old_accuracy_pct', 0):.1f}% -> {rr.get('new_accuracy_pct', 0):.1f}%)"
        )

    # Save to cron state (simulate)
    print("\n[6] Cron state update (simulated):")
    print(f"  last_run:           {datetime.now(UTC).isoformat()}")
    print(f"  last_signal_count:  {len(signals)}")
    print(f"  last_accuracy:      {accuracy}")
    print(f"  last_retrain_count: {len(retrain)}")
    print("  last_error:         None")
    print("  run_count:          would increment by 1")

    print("\n" + "=" * 60)
    if signals:
        print("CRON RUN SUCCESSFUL — Signals generated, cron would persist to DB")
    else:
        print("CRON RUN COMPLETE — No signals (may need data in DB tables)")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
