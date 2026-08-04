"""Run ML training on ALL active symbols — finds the best model for each symbol.

Usage:
    python scripts/run_ml_all_symbols.py
    python scripts/run_ml_all_symbols.py --data-type intraday
    python scripts/run_ml_all_symbols.py --data-type daily --model-type lightgbm
    python scripts/run_ml_all_symbols.py --best-model  # try all models, pick best
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings
from repositories.instrument_repository import InstrumentRepository
from repositories.quote_repository import QuoteRepository
from services.training_service import TrainingService


async def get_all_symbols(session: AsyncSession) -> list[str]:
    repo = InstrumentRepository(session=session)
    result = await repo.list(page=1, page_size=10000)
    if result.success and result.value:
        return [
            inst.symbol
            for inst in result.value.items
            if inst.symbol and inst.status.value == "active"
        ]
    return []


async def save_result_to_db(session: AsyncSession, result: dict, data_type: str) -> None:
    """Save training result to ml_symbol_results table."""
    try:
        symbol = result.get("symbol", "")
        model_type = result.get("best_model") or result.get("model_type", "")
        run_id = result.get("id", uuid.uuid4().hex[:12])

        metrics = result.get("metrics", {})
        fold_metrics = result.get("fold_metrics", [])
        importance = result.get("importance", {})

        await session.execute(
            text("""
                INSERT INTO ml_symbol_results
                    (id, symbol, data_type, model_type, status, metrics, fold_metrics,
                     feature_importance, train_samples, val_samples, feature_count,
                     feature_groups, start_date, end_date, artifact_path, duration_seconds, trained_at)
                VALUES
                    (:id, :symbol, :data_type, :model_type, 'completed', :metrics, :fold_metrics,
                     :feature_importance, :train_samples, :val_samples, :feature_count,
                     :feature_groups, :start_date, :end_date, :artifact_path, :duration_seconds, NOW())
                ON CONFLICT (symbol, data_type, model_type) DO UPDATE SET
                    status = 'completed',
                    metrics = EXCLUDED.metrics,
                    fold_metrics = EXCLUDED.fold_metrics,
                    feature_importance = EXCLUDED.feature_importance,
                    train_samples = EXCLUDED.train_samples,
                    val_samples = EXCLUDED.val_samples,
                    feature_count = EXCLUDED.feature_count,
                    artifact_path = EXCLUDED.artifact_path,
                    duration_seconds = EXCLUDED.duration_seconds,
                    trained_at = NOW(),
                    updated_at = NOW()
            """),
            {
                "id": run_id,
                "symbol": symbol,
                "data_type": data_type,
                "model_type": model_type,
                "metrics": json.dumps(metrics, default=str),
                "fold_metrics": json.dumps(fold_metrics, default=str),
                "feature_importance": json.dumps(importance, default=str),
                "train_samples": result.get("train_samples", 0),
                "val_samples": result.get("val_samples", 0),
                "feature_count": len(result.get("feature_names", [])),
                "feature_groups": json.dumps(result.get("feature_groups", [])),
                "start_date": result.get("start_date", ""),
                "end_date": result.get("end_date", ""),
                "artifact_path": result.get("artifact_path", ""),
                "duration_seconds": result.get("duration_seconds", 0),
            },
        )
        await session.commit()
    except Exception as e:
        print(f"  DB save failed for {result.get('symbol', '?')}: {e}")
        await session.rollback()


async def main() -> None:
    # ── Parse CLI args ──
    args = sys.argv[1:]
    data_type = "daily"
    model_type = "lightgbm"
    best_model_mode = False
    start_date = ""
    end_date = ""

    for i, arg in enumerate(args):
        if arg == "--data-type" and i + 1 < len(args):
            data_type = args[i + 1]
        elif arg == "--model-type" and i + 1 < len(args):
            model_type = args[i + 1]
        elif arg == "--best-model":
            best_model_mode = True
        elif arg == "--start-date" and i + 1 < len(args):
            start_date = args[i + 1]
        elif arg == "--end-date" and i + 1 < len(args):
            end_date = args[i + 1]

    if not start_date:
        start_date = "1403-01-01"
    if not end_date:
        end_date = "1405-07-01"

    engine = create_async_engine(
        settings.database_url_async,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        symbols = await get_all_symbols(session)

    print(f"{'=' * 70}")
    print(f"  ML Training — All Symbols ({data_type.upper()} data)")
    if best_model_mode:
        print("  Mode: BEST MODEL (trying all 9 models)")
    else:
        print(f"  Model: {model_type}")
    print(f"  Dates: {start_date} to {end_date}")
    print(f"  Symbols: {len(symbols)}")
    print(f"{'=' * 70}\n")

    if not symbols:
        print("ERROR: No symbols found in database.")
        await engine.dispose()
        return

    # ── Train on each symbol ──
    sem = asyncio.Semaphore(5)
    results: list[dict] = []
    completed_count = 0
    total = len(symbols)
    overall_start = time.time()

    async with session_factory() as session:
        trainer = TrainingService(quote_repo=QuoteRepository(session=session))

        async def _train_one(sym: str) -> dict:
            nonlocal completed_count
            async with sem:
                t0 = time.time()
                try:
                    if best_model_mode:
                        result = await trainer.train_with_best_model(
                            symbol=sym,
                            start_date=start_date,
                            end_date=end_date,
                            feature_groups=["price", "technical"],
                            data_type=data_type,
                        )
                    else:
                        result = await trainer.train_with_db_data(
                            symbol=sym,
                            model_type=model_type,
                            start_date=start_date,
                            end_date=end_date,
                            feature_groups=["price", "technical"],
                        )

                    elapsed = time.time() - t0
                    completed_count += 1

                    if result.success and result.value:
                        run = result.value
                        run["duration_seconds"] = round(elapsed, 2)
                        m = run.get("metrics", {})
                        best = run.get("best_model", model_type)
                        r2 = m.get("mean_r2", 0)
                        da = m.get("mean_directional_accuracy", 0)
                        print(f"  [{completed_count}/{total}] {sym:12s}  Best={best:18s}  R2={r2:+.4f}  DA={da:.1%}  ({elapsed:.1f}s)")

                        # Save to DB
                        await save_result_to_db(session, run, data_type)

                        return {
                            "symbol": sym,
                            "success": True,
                            "run_id": run.get("id", ""),
                            "best_model": best,
                            "metrics": m,
                            "model_comparison": run.get("model_comparison", []),
                            "train_samples": run.get("train_samples", 0),
                            "duration_seconds": round(elapsed, 2),
                        }
                    else:
                        print(f"  [{completed_count}/{total}] {sym:12s}  FAIL: {result.error or 'failed'}  ({elapsed:.1f}s)")
                        # Save failure to DB
                        await save_result_to_db(session, {
                            "symbol": sym, "id": uuid.uuid4().hex[:12],
                            "model_type": model_type, "status": "failed",
                            "error": result.error, "metrics": {},
                            "fold_metrics": [], "importance": {},
                            "train_samples": 0, "val_samples": 0,
                            "feature_groups": [], "start_date": start_date,
                            "end_date": end_date, "duration_seconds": elapsed,
                        }, data_type)

                        return {
                            "symbol": sym,
                            "success": False,
                            "error": result.error or "Training failed",
                            "duration_seconds": round(elapsed, 2),
                        }
                except Exception as e:
                    elapsed = time.time() - t0
                    completed_count += 1
                    print(f"  [{completed_count}/{total}] {sym:12s}  ERROR: {e}  ({elapsed:.1f}s)")
                    return {
                        "symbol": sym,
                        "success": False,
                        "error": str(e),
                        "duration_seconds": round(elapsed, 2),
                    }

        tasks = [_train_one(sym) for sym in symbols]
        results = await asyncio.gather(*tasks)

    # ── Summary ──
    total_time = time.time() - overall_start
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    print(f"\n{'=' * 70}")
    print(f"  RESULTS SUMMARY ({data_type.upper()} data)")
    print(f"{'=' * 70}")
    print(f"  Total symbols:     {total}")
    print(f"  Successful:        {len(successful)}")
    print(f"  Failed:            {len(failed)}")
    print(f"  Total time:        {total_time:.1f}s ({total_time/60:.1f} min)")

    if successful:
        r2_values = [r["metrics"].get("mean_r2", 0) for r in successful]
        avg_r2 = sum(r2_values) / len(r2_values)
        best = max(successful, key=lambda x: x["metrics"].get("mean_r2", 0))
        worst = min(successful, key=lambda x: x["metrics"].get("mean_r2", 0))
        print(f"\n  Average R2:        {avg_r2:+.4f}")
        print(f"  Best:              {best['symbol']}  R2={best['metrics'].get('mean_r2', 0):+.4f}")
        print(f"  Worst:             {worst['symbol']}  R2={worst['metrics'].get('mean_r2', 0):+.4f}")

        # Model distribution
        if best_model_mode:
            model_counts: dict[str, int] = {}
            for r in successful:
                m = r.get("best_model", "unknown")
                model_counts[m] = model_counts.get(m, 0) + 1
            print("\n  Best Model Distribution:")
            for m, c in sorted(model_counts.items(), key=lambda x: -x[1]):
                print(f"    {m:25s}: {c:3d} symbols ({c/len(successful)*100:.1f}%)")

        # R2 distribution
        excellent = sum(1 for r in r2_values if r > 0.5)
        good = sum(1 for r in r2_values if 0.2 < r <= 0.5)
        fair = sum(1 for r in r2_values if 0 < r <= 0.2)
        poor = sum(1 for r in r2_values if r <= 0)
        print("\n  R2 Distribution:")
        print(f"    Excellent (>0.5):   {excellent}")
        print(f"    Good (0.2-0.5):     {good}")
        print(f"    Fair (0-0.2):       {fair}")
        print(f"    Poor (<=0):         {poor}")

        # Top 10 models
        sorted_r = sorted(successful, key=lambda x: x["metrics"].get("mean_r2", 0), reverse=True)
        print("\n  Top 10 Models:")
        for i, r in enumerate(sorted_r[:10], 1):
            m = r["metrics"]
            bm = r.get("best_model", "?")
            print(f"    {i:2d}. {r['symbol']:12s}  {bm:18s}  R2={m.get('mean_r2', 0):+.4f}  RMSE={m.get('mean_rmse', 0):.4f}  DA={m.get('mean_directional_accuracy', 0):.1%}")

    if failed:
        print(f"\n  Failed Symbols ({len(failed)}):")
        for r in failed[:20]:
            print(f"    {r['symbol']:12s}  {r.get('error', 'unknown')[:60]}")

    print(f"\n{'=' * 70}")
    print("  Results saved to database (ml_symbol_results table)")
    print(f"{'=' * 70}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
