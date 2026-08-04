"""Dual-table ML training with resume support.

Runs ML on BOTH daily (quotes) and intraday (intraday_trades) data.
Saves results to ml_symbol_results table.
Supports resume: skips symbols already trained successfully.

Usage:
    python scripts/run_ml_dual.py                      # both tables
    python scripts/run_ml_dual.py --data-type daily     # daily only
    python scripts/run_ml_dual.py --data-type intraday  # intraday only
    python scripts/run_ml_dual.py --resume              # skip completed symbols
    python scripts/run_ml_dual.py --force               # retrain all
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings
from repositories.instrument_repository import InstrumentRepository
from repositories.quote_repository import QuoteRepository
from services.training_service import TrainingService, _to_numpy

# ═══════════════════════════════════════════════════════════════
# INTRADAY DATA: ticks → OHLCV bars
# ═══════════════════════════════════════════════════════════════

async def fetch_intraday_ohlcv(
    session: AsyncSession, symbol: str, bar_minutes: int = 5
) -> pd.DataFrame:
    """Aggregate intraday ticks into OHLCV bars."""
    result = await session.execute(text("""
        SELECT s.symbol, it.trade_date, it.time, it.price, it.volume, it.is_canceled
        FROM intraday_trades it
        JOIN symbols s ON it.symbol_id = s.id
        WHERE s.symbol = :symbol AND it.is_canceled = false
        ORDER BY it.trade_date, it.time
    """), {"symbol": symbol})
    rows = result.fetchall()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["symbol", "trade_date", "time", "price", "volume", "is_canceled"])
    df["datetime"] = pd.to_datetime(df["trade_date"].astype(str) + " " + df["time"].astype(str))
    df["price"] = df["price"].astype(float)
    df["volume"] = df["volume"].astype(int)

    # Create bar groups
    df["bar_group"] = df["datetime"].dt.floor(f"{bar_minutes}min")

    # Aggregate to OHLCV
    bars = df.groupby("bar_group").agg(
        open=("price", "first"),
        high=("price", "max"),
        low=("price", "min"),
        close=("price", "last"),
        volume=("volume", "sum"),
    ).reset_index()

    bars = bars.rename(columns={"bar_group": "date"})
    bars = bars.sort_values("date").reset_index(drop=True)

    # Remove zero-volume bars
    bars = bars[bars["volume"] > 0].reset_index(drop=True)

    return bars


# ═══════════════════════════════════════════════════════════════
# DB OPERATIONS
# ═══════════════════════════════════════════════════════════════

async def get_completed_symbols(session: AsyncSession, data_type: str) -> set[str]:
    """Get symbols already trained for this data_type."""
    result = await session.execute(text("""
        SELECT symbol FROM ml_symbol_results
        WHERE data_type = :data_type AND status = 'completed'
    """), {"data_type": data_type})
    return {row[0] for row in result.fetchall()}


async def save_result(session_factory, result: dict, data_type: str) -> None:
    """Save training result to ml_symbol_results (upsert) using its own session."""
    try:
        async with session_factory() as session:
            symbol = result.get("symbol", "")
            model_type = result.get("best_model") or result.get("model_type", "")
            run_id = result.get("id", uuid.uuid4().hex[:12])

            await session.execute(text("""
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
            """), {
                "id": run_id, "symbol": symbol, "data_type": data_type,
                "model_type": model_type,
                "metrics": json.dumps(result.get("metrics", {}), default=str),
                "fold_metrics": json.dumps(result.get("fold_metrics", []), default=str),
                "feature_importance": json.dumps(result.get("importance", {}), default=str),
                "train_samples": result.get("train_samples", 0),
                "val_samples": result.get("val_samples", 0),
                "feature_count": len(result.get("feature_names", [])),
                "feature_groups": json.dumps(result.get("feature_groups", [])),
                "start_date": result.get("start_date", ""),
                "end_date": result.get("end_date", ""),
                "artifact_path": result.get("artifact_path", ""),
                "duration_seconds": result.get("duration_seconds", 0),
            })
            await session.commit()
    except Exception as e:
        print(f"  DB save failed for {result.get('symbol', '?')}: {e}")


async def save_failure(session_factory, symbol: str, data_type: str,
                       model_type: str, error: str, elapsed: float) -> None:
    """Save failed training attempt using its own session."""
    try:
        async with session_factory() as session:
            run_id = uuid.uuid4().hex[:12]
            await session.execute(text("""
                INSERT INTO ml_symbol_results
                    (id, symbol, data_type, model_type, status, error, duration_seconds, trained_at)
                VALUES (:id, :symbol, :data_type, :model_type, 'failed', :error, :elapsed, NOW())
                ON CONFLICT (symbol, data_type, model_type) DO UPDATE SET
                    status = 'failed', error = EXCLUDED.error,
                    duration_seconds = EXCLUDED.duration_seconds, trained_at = NOW(), updated_at = NOW()
            """), {"id": run_id, "symbol": symbol, "data_type": data_type,
                   "model_type": model_type, "error": error[:500], "elapsed": elapsed})
            await session.commit()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

async def train_daily(
    session_factory, trainer: TrainingService,
    symbols: list[str], resume: bool, sem: asyncio.Semaphore,
) -> list[dict]:
    """Train ML on daily data (quotes table)."""
    async with session_factory() as session:
        completed = await get_completed_symbols(session, "daily") if resume else set()
    to_train = [s for s in symbols if s not in completed]

    print(f"\n  Daily: {len(symbols)} total, {len(completed)} completed, {len(to_train)} remaining\n")

    results = []
    count = 0

    async def _train_one(sym: str) -> dict:
        nonlocal count
        async with sem:
            t0 = time.time()
            try:
                result = await trainer.train_with_best_model(
                    symbol=sym, start_date="1403-01-01", end_date="1405-07-01",
                    feature_groups=["price", "technical"], data_type="daily",
                )
                elapsed = time.time() - t0
                count += 1

                if result.success and result.value:
                    run = result.value
                    run["duration_seconds"] = round(elapsed, 2)
                    m = run.get("metrics", {})
                    bm = run.get("best_model", "?")
                    print(f"  [{count}/{len(to_train)}] {sym:12s}  {bm:18s}  R2={m.get('mean_r2', 0):+.4f}  ({elapsed:.1f}s)")
                    await save_result(session_factory, run, "daily")
                    return {"symbol": sym, "success": True, "metrics": m, "best_model": bm}
                else:
                    print(f"  [{count}/{len(to_train)}] {sym:12s}  FAIL: {result.error[:50]}  ({elapsed:.1f}s)")
                    await save_failure(session_factory, sym, "daily", "", result.error or "failed", elapsed)
                    return {"symbol": sym, "success": False, "error": result.error}
            except Exception as e:
                elapsed = time.time() - t0
                count += 1
                print(f"  [{count}/{len(to_train)}] {sym:12s}  ERR: {str(e)[:50]}  ({elapsed:.1f}s)")
                await save_failure(session_factory, sym, "daily", "", str(e), elapsed)
                return {"symbol": sym, "success": False, "error": str(e)}

    tasks = [_train_one(sym) for sym in to_train]
    results = await asyncio.gather(*tasks)
    return results


async def train_intraday(
    session_factory, trainer: TrainingService,
    symbols: list[str], resume: bool, sem: asyncio.Semaphore,
) -> list[dict]:
    """Train ML on intraday data (intraday_trades → 5min OHLCV bars)."""
    async with session_factory() as session:
        completed = await get_completed_symbols(session, "intraday") if resume else set()
    to_train = [s for s in symbols if s not in completed]

    print(f"\n  Intraday: {len(symbols)} total, {len(completed)} completed, {len(to_train)} remaining\n")

    results = []
    count = 0

    async def _train_one(sym: str) -> dict:
        nonlocal count
        async with sem:
            t0 = time.time()
            try:
                # Fetch and aggregate intraday ticks to 5-min bars (own session)
                async with session_factory() as sess:
                    df = await fetch_intraday_ohlcv(sess, sym, bar_minutes=5)
                if df.empty or len(df) < 30:
                    elapsed = time.time() - t0
                    count += 1
                    print(f"  [{count}/{len(to_train)}] {sym:12s}  SKIP: not enough intraday data ({len(df)} bars)  ({elapsed:.1f}s)")
                    return {"symbol": sym, "success": False, "error": f"Not enough data: {len(df)} bars"}

                # Build features from bars directly (shared index, no alignment issues)
                from ml.types import FeatureMatrix, TargetVector

                feats = pd.DataFrame(index=df.index)
                for w in [5, 10, 20]:
                    feats[f"ret_{w}"] = df["close"].pct_change(w)
                    feats[f"ma_{w}"] = df["close"].rolling(w).mean() / df["close"] - 1
                    feats[f"vol_{w}"] = df["close"].pct_change().rolling(w).std()
                    feats[f"high_low_{w}"] = (df["high"].rolling(w).max() - df["low"].rolling(w).min()) / df["close"]
                feats["volume_ratio"] = df["volume"] / df["volume"].rolling(20).mean()
                feats["range"] = (df["high"] - df["low"]) / df["close"]
                feats["gap"] = (df["open"] - df["close"].shift(1)) / df["close"].shift(1)

                # Target
                target = df["close"].pct_change().shift(-1)

                # Align and clean
                combined = pd.concat([feats, target.rename("target")], axis=1)
                combined = combined.replace([np.inf, -np.inf], np.nan)
                combined = combined.dropna(subset=["target"])
                combined = combined.fillna(method="ffill").fillna(0)

                feature_cols = [c for c in combined.columns if c != "target"]
                target = combined.pop("target")

                if len(combined) < 30:
                    elapsed = time.time() - t0
                    count += 1
                    print(f"  [{count}/{len(to_train)}] {sym:12s}  SKIP: {len(combined)} valid rows  ({elapsed:.1f}s)")
                    return {"symbol": sym, "success": False, "error": f"Only {len(combined)} valid rows"}

                # Run best model selection using a mini TrainingService
                X = FeatureMatrix(data=combined[feature_cols], feature_names=feature_cols)
                y = TargetVector(data=target.values, name="next_return", task_type="regression")

                # Quick model comparison
                models_to_try = ["lightgbm", "xgboost", "catboost", "extra_trees", "random_forest"]
                best_r2 = -999.0
                best_model_type = ""
                all_model_results = []

                from sklearn.model_selection import TimeSeriesSplit
                tscv = TimeSeriesSplit(n_splits=3)

                for model_type in models_to_try:
                    try:
                        wrapper = trainer._get_model(model_type, "regression")
                        sklearn_model = wrapper._model

                        X_np = _to_numpy(X)
                        y_np = _to_numpy(y)

                        from sklearn.model_selection import cross_val_score
                        scores = cross_val_score(sklearn_model, X_np, y_np, cv=tscv, scoring="r2")
                        mean_r2 = float(scores.mean())
                        all_model_results.append({"model_type": model_type, "r2": mean_r2})

                        if mean_r2 > best_r2:
                            best_r2 = mean_r2
                            best_model_type = model_type
                            sklearn_model.fit(X_np, y_np)
                    except Exception:
                        continue

                elapsed = time.time() - t0
                count += 1

                if not all_model_results:
                    print(f"  [{count}/{len(to_train)}] {sym:12s}  FAIL: all models failed  ({elapsed:.1f}s)")
                    await save_failure(session_factory, sym, "intraday", "", "all models failed", elapsed)
                    return {"symbol": sym, "success": False, "error": "all models failed"}

                # Save result
                run_id = uuid.uuid4().hex[:12]
                run = {
                    "id": run_id, "symbol": sym, "best_model": best_model_type,
                    "model_type": best_model_type,
                    "metrics": {"mean_r2": best_r2, "mean_rmse": 0, "mean_directional_accuracy": 0},
                    "fold_metrics": [], "importance": {},
                    "train_samples": len(combined), "val_samples": 0,
                    "feature_names": feature_cols, "feature_groups": ["price", "technical"],
                    "start_date": "intraday", "end_date": "intraday",
                    "duration_seconds": round(elapsed, 2),
                }
                await save_result(session_factory, run, "intraday")

                print(f"  [{count}/{len(to_train)}] {sym:12s}  {best_model_type:18s}  R2={best_r2:+.4f}  ({elapsed:.1f}s)")
                return {"symbol": sym, "success": True, "metrics": run["metrics"], "best_model": best_model_type}

            except Exception as e:
                elapsed = time.time() - t0
                count += 1
                print(f"  [{count}/{len(to_train)}] {sym:12s}  ERR: {str(e)[:50]}  ({elapsed:.1f}s)")
                await save_failure(session_factory, sym, "intraday", "", str(e), elapsed)
                return {"symbol": sym, "success": False, "error": str(e)}

    tasks = [_train_one(sym) for sym in to_train]
    results = await asyncio.gather(*tasks)
    return results


async def main() -> None:
    args = sys.argv[1:]
    data_type = "both"
    resume = True  # Default: resume mode ON

    for i, arg in enumerate(args):
        if arg == "--data-type" and i + 1 < len(args):
            data_type = args[i + 1]
        elif arg == "--resume":
            resume = True
        elif arg == "--force":
            resume = False

    engine = create_async_engine(
        settings.database_url_async,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Get daily symbols
    async with session_factory() as session:
        repo = InstrumentRepository(session=session)
        result = await repo.list(page=1, page_size=10000)
        daily_symbols = [
            inst.symbol for inst in result.value.items
            if inst.symbol and inst.status.value == "active"
        ] if result.success and result.value else []

    # Get intraday symbols
    async with session_factory() as session:
        r = await session.execute(text("""
            SELECT s.symbol, COUNT(*) as cnt
            FROM intraday_trades it
            JOIN symbols s ON it.symbol_id = s.id
            WHERE it.is_canceled = false
            GROUP BY s.symbol
            HAVING COUNT(*) >= 1000
            ORDER BY cnt DESC
        """))
        intraday_symbols = [row[0] for row in r.fetchall()]

    print(f"{'=' * 70}")
    print("  DUAL-TABLE ML TRAINING")
    print(f"  Daily symbols:  {len(daily_symbols)}")
    print(f"  Intraday symbols: {len(intraday_symbols)}")
    print(f"  Resume mode: {'ON (skip completed)' if resume else 'OFF (retrain all)'}")
    print(f"  Data type: {data_type}")
    print(f"{'=' * 70}")

    overall_start = time.time()
    sem = asyncio.Semaphore(5)

    all_daily = []
    all_intraday = []

    async with session_factory() as session:
        trainer = TrainingService(quote_repo=QuoteRepository(session=session))

    if data_type in ("daily", "both"):
        print(f"\n{'─' * 70}")
        print("  PHASE 1: DAILY DATA (quotes)")
        print(f"{'─' * 70}")
        all_daily = await train_daily(session_factory, trainer, daily_symbols, resume, sem)

    if data_type in ("intraday", "both"):
        print(f"\n{'─' * 70}")
        print("  PHASE 2: INTRADAY DATA (intraday_trades → 5min bars)")
        print(f"{'─' * 70}")
        all_intraday = await train_intraday(session_factory, trainer, intraday_symbols, resume, sem)

    # ── Final Summary ──
    total_time = time.time() - overall_start

    print(f"\n{'=' * 70}")
    print("  FINAL SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Total time: {total_time:.1f}s ({total_time/60:.1f} min)")

    for label, results in [("DAILY", all_daily), ("INTRADAY", all_intraday)]:
        if not results:
            continue
        ok = [r for r in results if r.get("success")]
        fail = [r for r in results if not r.get("success")]
        print(f"\n  {label}:")
        print(f"    Successful: {len(ok)}")
        print(f"    Failed:     {len(fail)}")
        if ok:
            r2_vals = [r["metrics"].get("mean_r2", 0) for r in ok]
            print(f"    Avg R2:     {sum(r2_vals)/len(r2_vals):+.4f}")
            best = max(ok, key=lambda x: x["metrics"].get("mean_r2", 0))
            print(f"    Best:       {best['symbol']} ({best['best_model']}) R2={best['metrics'].get('mean_r2', 0):+.4f}")

    print("\n  Results saved to: ml_symbol_results table")
    print(f"{'=' * 70}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
