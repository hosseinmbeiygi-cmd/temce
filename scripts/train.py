#!/usr/bin/env python
"""
Unified training launcher — pick your mode:

  --mode quick  3 fast models (xgboost, lightgbm, random_forest), sequential, JSON
  --mode full   All models, multiprocessing, saves to PostgreSQL (DEFAULT)
  --mode legacy All models, sequential, JSON

Usage:
  python scripts/train.py --mode quick --symbols فولاد,فملی
  python scripts/train.py --mode full --workers 4 --test 10
  python scripts/train.py --mode legacy --test 3
  python scripts/train.py --mode full --symbols خودرو --models xgboost,lightgbm
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import ml.models.shallow.advanced_models  # noqa: F401
import ml.models.shallow.boosting_models  # noqa: F401

# Ensure all model classes are registered
import ml.models.shallow.linear_models  # noqa: F401
import ml.models.shallow.tree_models  # noqa: F401
from core.config import settings
from ml.models.registry import model_registry

# ── Constants ──────────────────────────────────────────────────────────────

QUICK_MODELS = ["xgboost", "lightgbm", "random_forest"]
MIN_ROWS = 60
MIN_SAMPLES = 30
FETCH_SQL = sql_text("""
    SELECT price_first AS open, price_last AS close,
           price_max AS high, price_min AS low, trade_volume AS volume
    FROM brsapi_historical_daily
    WHERE symbol = :symbol
    ORDER BY date ASC
""")


# ── CLI ────────────────────────────────────────────────────────────────────

def parse_cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Unified ML training launcher — quick / full / legacy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--mode", choices=["quick", "full", "legacy"], default="full",
        help="Training mode (default: full)",
    )
    p.add_argument(
        "--symbols", type=str, default="",
        help="Comma-separated symbols to train (default: auto-discover all)",
    )
    p.add_argument(
        "--models", type=str, default="",
        help="Comma-separated model types (default: all registered for full/legacy, 3 for quick)",
    )
    p.add_argument(
        "--test", type=int, default=0,
        help="Limit to first N symbols (for testing)",
    )
    p.add_argument(
        "--workers", type=int, default=0,
        help="Number of parallel workers (full mode only, default: min(CPU cores, 8))",
    )
    p.add_argument(
        "--output", type=str, default="",
        help="JSON output path (quick/legacy modes, default: train_results_<mode>.json)",
    )
    return p.parse_args()


# ── Data ───────────────────────────────────────────────────────────────────

async def fetch_ohlcv(session, symbol: str) -> pd.DataFrame:
    result = await session.execute(FETCH_SQL, {"symbol": symbol})
    rows = result.fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["open", "close", "high", "low", "volume"])
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close"])
    df = df[df["close"] > 0]
    return df


async def discover_symbols(engine, symbols_filter: list[str] | None) -> list[tuple[str, int]]:
    """Return (symbol, row_count) sorted by count desc."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        if symbols_filter:
            placeholders = ", ".join(f"'{s}'" for s in symbols_filter)
            r = await session.execute(sql_text(f"""
                SELECT symbol, COUNT(*) as cnt
                FROM brsapi_historical_daily
                WHERE symbol IN ({placeholders})
                  AND symbol IS NOT NULL AND symbol != ''
                GROUP BY symbol
                ORDER BY cnt DESC
            """))
        else:
            r = await session.execute(sql_text("""
                SELECT symbol, COUNT(*) as cnt
                FROM brsapi_historical_daily
                WHERE symbol IS NOT NULL AND symbol != ''
                GROUP BY symbol
                ORDER BY cnt DESC
            """))
        return [(row[0], row[1]) for row in r]


async def fetch_all_data(engine, symbols: list[str]) -> dict[str, pd.DataFrame]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    results: dict[str, pd.DataFrame] = {}

    async def fetch_one(sym: str):
        async with factory() as session:
            rows = (await session.execute(FETCH_SQL, {"symbol": sym})).fetchall()
            if not rows:
                return sym, pd.DataFrame()
            df = pd.DataFrame(rows, columns=["open", "close", "high", "low", "volume"])
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["close"])
            df = df[df["close"] > 0]
            return sym, df

    # Fetch in batches of 50
    for i in range(0, len(symbols), 50):
        batch = symbols[i:i + 50]
        tasks = [fetch_one(s) for s in batch]
        for coro in asyncio.as_completed(tasks):
            sym, df = await coro
            results[sym] = df
    return results


# ── Features ───────────────────────────────────────────────────────────────

def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    from ml.features.price_features import PriceFeatures
    from ml.features.technical_features import TechnicalFeatures

    pf = PriceFeatures(window_sizes=[5, 10, 20])
    tf = TechnicalFeatures()
    X_price = pf.compute(df)
    X_tech = tf.compute(df)

    if hasattr(X_price, "data"):
        X_price = X_price.data
    if hasattr(X_tech, "data"):
        X_tech = X_tech.data

    X = pd.concat([X_price, X_tech], axis=1).fillna(0)
    y = df["close"].pct_change().shift(-1).fillna(0)

    common = X.index.intersection(y.index)
    X = X.loc[common]
    y = y.loc[common]

    X = X.iloc[MIN_SAMPLES:]
    y = y.iloc[MIN_SAMPLES:]
    return X, y


# ── Single-model training (for ProcessPoolExecutor) ────────────────────────

def _train_job(args: tuple) -> dict:
    """Picklable top-level function for multiprocessing."""
    model_type, X_train_list, y_train_list, X_val_list, y_val_list, symbol = args

    import numpy as np
    import pandas as pd

    import ml.models.shallow.advanced_models  # noqa: F401
    import ml.models.shallow.boosting_models  # noqa: F401
    import ml.models.shallow.linear_models  # noqa: F401
    import ml.models.shallow.tree_models  # noqa: F401
    from ml.artifacts import ArtifactManager
    from ml.evaluation.metrics import MetricsCalculator
    from ml.types import ModelArtifactMeta

    X_train = pd.DataFrame(X_train_list)
    y_train = pd.Series(y_train_list)
    X_val = pd.DataFrame(X_val_list)
    y_val = pd.Series(y_val_list)

    t0 = time.time()
    try:
        model = model_registry.create(model_type)
        model.fit(X_train, y_train)

        train_pred = model.predict(X_train)
        val_pred = model.predict(X_val)

        if hasattr(train_pred, "predictions"):
            train_pred = np.asarray(train_pred.predictions)
        if hasattr(val_pred, "predictions"):
            val_pred = np.asarray(val_pred.predictions)

        mc = MetricsCalculator()
        train_m = mc.compute(y_train, train_pred)
        val_m = mc.compute(y_val, val_pred)

        am = ArtifactManager()
        meta = ModelArtifactMeta(
            model_id=f"{model_type}_{symbol}",
            version=f"v1-{uuid.uuid4().hex[:8]}",
            metrics={"train": train_m, "val": val_m},
            params={},
            feature_names=list(X_train.columns),
            stage="development",
        )
        artifact_path = am.save_model(model, meta)
        elapsed = time.time() - t0

        return {
            "symbol": symbol, "model": model_type, "ok": True,
            "r2": round(val_m.get("r2", 0), 4),
            "mae": round(val_m.get("mae", 0), 6),
            "mse": round(val_m.get("mse", 0), 8),
            "train_samples": len(X_train),
            "val_samples": len(X_val),
            "feature_count": len(X_train.columns),
            "train_metrics": train_m,
            "val_metrics": val_m,
            "artifact_path": str(artifact_path),
            "time": round(elapsed, 1),
        }
    except Exception as e:
        elapsed = time.time() - t0
        return {
            "symbol": symbol, "model": model_type, "ok": False,
            "error": str(e)[:500],
            "train_samples": len(X_train),
            "val_samples": len(X_val),
            "feature_count": len(X_train.columns),
            "time": round(elapsed, 1),
        }


# ── DB saver ───────────────────────────────────────────────────────────────

async def save_results_to_db(engine, results: list[dict]) -> int:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    inserted = 0
    async with factory() as session:
        for r in results:
            rid = f"train_{uuid.uuid4().hex[:12]}"
            if r["ok"]:
                await session.execute(sql_text("""
                    INSERT INTO ml_symbol_results
                        (id, symbol, data_type, model_type, status, metrics,
                         train_samples, val_samples, feature_count, artifact_path,
                         duration_seconds, trained_at)
                    VALUES (:id, :symbol, 'historical_daily', :model_type, 'completed', :metrics,
                            :train_samples, :val_samples, :feature_count, :artifact_path,
                            :duration_seconds, NOW())
                    ON CONFLICT (symbol, data_type, model_type) DO UPDATE SET
                        status = 'completed', metrics = EXCLUDED.metrics,
                        train_samples = EXCLUDED.train_samples, val_samples = EXCLUDED.val_samples,
                        feature_count = EXCLUDED.feature_count, artifact_path = EXCLUDED.artifact_path,
                        duration_seconds = EXCLUDED.duration_seconds, trained_at = NOW(), updated_at = NOW()
                """), {
                    "id": rid, "symbol": r["symbol"], "model_type": r["model"],
                    "metrics": json.dumps(r.get("val_metrics", {}), ensure_ascii=False),
                    "train_samples": r.get("train_samples", 0),
                    "val_samples": r.get("val_samples", 0),
                    "feature_count": r.get("feature_count", 0),
                    "artifact_path": r.get("artifact_path", ""),
                    "duration_seconds": r.get("time", 0),
                })
            else:
                await session.execute(sql_text("""
                    INSERT INTO ml_symbol_results
                        (id, symbol, data_type, model_type, status, error, duration_seconds, trained_at)
                    VALUES (:id, :symbol, 'historical_daily', :model_type, 'failed', :error, :duration_seconds, NOW())
                    ON CONFLICT (symbol, data_type, model_type) DO UPDATE SET
                        status = 'failed', error = EXCLUDED.error,
                        duration_seconds = EXCLUDED.duration_seconds, trained_at = NOW(), updated_at = NOW()
                """), {
                    "id": rid, "symbol": r["symbol"], "model_type": r["model"],
                    "error": r.get("error", "")[:500],
                    "duration_seconds": r.get("time", 0),
                })
            inserted += 1
        await session.commit()
    return inserted


# ── Modes ──────────────────────────────────────────────────────────────────

def _filter_models(model_types: list[str], model_filter: list[str] | None) -> list[str]:
    if not model_filter:
        return model_types
    valid = [m for m in model_filter if m in model_types]
    if not valid:
        print(f"WARNING: No requested models found. Available: {', '.join(model_types)}")
        print("Falling back to all models.")
        return model_types
    if len(valid) < len(model_filter):
        missing = set(model_filter) - set(valid)
        print(f"WARNING: Unknown models skipped: {', '.join(missing)}")
    return valid


async def run_quick_mode(args: argparse.Namespace, engine) -> None:
    """Sequential training with 3 fast models, JSON output."""
    model_types = _filter_models(QUICK_MODELS, _parse_model_filter(args.models))
    symbols_data = await discover_symbols(engine, _parse_symbol_filter(args.symbols))

    if args.test > 0:
        symbols_data = symbols_data[:args.test]

    trainable = [(s, c) for s, c in symbols_data if c >= MIN_ROWS]
    if not trainable:
        print("No symbols with enough data!")
        return

    print(f"\n{'='*60}")
    print(f"  QUICK MODE — {len(trainable)} symbols × {len(model_types)} models")
    print(f"  Models: {', '.join(model_types)}")
    print(f"{'='*60}")

    all_data = await fetch_all_data(engine, [s for s, _ in trainable])
    all_results = []
    total = 0
    t_start = time.time()

    for symbol, _row_count in trainable:
        df = all_data.get(symbol)
        if df is None or df.empty or len(df) < MIN_ROWS:
            continue
        X, y = build_features(df)
        if len(X) < MIN_SAMPLES:
            continue

        split = int(len(X) * 0.8)
        X_train, X_val = X.iloc[:split], X.iloc[split:]
        y_train, y_val = y.iloc[:split], y.iloc[split:]

        for mt in model_types:
            total += 1
            t0 = time.time()
            try:
                model = model_registry.create(mt)
                model.fit(X_train, y_train)

                train_pred = model.predict(X_train)
                val_pred = model.predict(X_val)

                if hasattr(train_pred, "predictions"):
                    train_pred = np.asarray(train_pred.predictions)
                if hasattr(val_pred, "predictions"):
                    val_pred = np.asarray(val_pred.predictions)

                from ml.evaluation.metrics import MetricsCalculator
                mc = MetricsCalculator()
                mc.compute(y_train, train_pred)
                val_m = mc.compute(y_val, val_pred)

                elapsed = time.time() - t0
                r2 = val_m.get("r2", 0)
                print(f"  [{total}] {symbol} + {mt}  R2={r2:.4f}  {elapsed:.1f}s")
                all_results.append({
                    "symbol": symbol, "model": mt, "ok": True,
                    "r2": round(r2, 4), "mae": round(val_m.get("mae", 0), 6),
                    "train_samples": len(X_train), "val_samples": len(X_val),
                    "time": round(elapsed, 1),
                })
            except Exception as e:
                elapsed = time.time() - t0
                print(f"  [{total}] {symbol} + {mt}  ERROR: {str(e)[:60]}  {elapsed:.1f}s")
                all_results.append({
                    "symbol": symbol, "model": mt, "ok": False,
                    "error": str(e)[:200], "time": round(elapsed, 1),
                })

    _save_json_output(args, all_results, "quick", t_start, total)
    # Also save to DB
    print("Saving to database...")
    saved = await save_results_to_db(engine, all_results)
    print(f"Saved {saved} rows to ml_symbol_results!")


async def run_legacy_mode(args: argparse.Namespace, engine) -> None:
    """Full sequential training with all models, JSON output."""
    model_types = _filter_models(model_registry.list_models(), _parse_model_filter(args.models))
    symbols_data = await discover_symbols(engine, _parse_symbol_filter(args.symbols))

    if args.test > 0:
        symbols_data = symbols_data[:args.test]

    trainable = [(s, c) for s, c in symbols_data if c >= MIN_ROWS]
    if not trainable:
        print("No symbols with enough data!")
        return

    print(f"\n{'='*60}")
    print(f"  LEGACY MODE — {len(trainable)} symbols × {len(model_types)} models")
    print(f"  Models: {', '.join(model_types)}")
    print(f"{'='*60}")

    all_data = await fetch_all_data(engine, [s for s, _ in trainable])
    all_results = []
    total = 0
    t_start = time.time()

    for symbol, _row_count in trainable:
        df = all_data.get(symbol)
        if df is None or df.empty or len(df) < MIN_ROWS:
            continue
        X, y = build_features(df)
        if len(X) < MIN_SAMPLES:
            continue

        split = int(len(X) * 0.8)
        X_train, X_val = X.iloc[:split], X.iloc[split:]
        y_train, y_val = y.iloc[:split], y.iloc[split:]

        for mt in model_types:
            total += 1
            t0 = time.time()
            try:
                model = model_registry.create(mt)
                model.fit(X_train, y_train)

                train_pred = model.predict(X_train)
                val_pred = model.predict(X_val)

                if hasattr(train_pred, "predictions"):
                    train_pred = np.asarray(train_pred.predictions)
                if hasattr(val_pred, "predictions"):
                    val_pred = np.asarray(val_pred.predictions)

                from ml.evaluation.metrics import MetricsCalculator
                mc = MetricsCalculator()
                train_m = mc.compute(y_train, train_pred)
                val_m = mc.compute(y_val, val_pred)

                from ml.artifacts import ArtifactManager
                from ml.types import ModelArtifactMeta
                am = ArtifactManager()
                meta = ModelArtifactMeta(
                    model_id=f"{mt}_{symbol}", version="v1",
                    metrics={"train": train_m, "val": val_m},
                    params={}, feature_names=list(X.columns), stage="development",
                )
                am.save_model(model, meta)

                elapsed = time.time() - t0
                r2 = val_m.get("r2", 0)
                print(f"  [{total}] {symbol} + {mt}  R2={r2:.4f}  MAE={val_m.get('mae', 0):.6f}  {elapsed:.1f}s")
                all_results.append({
                    "symbol": symbol, "model": mt, "ok": True,
                    "r2": round(r2, 4), "mae": round(val_m.get("mae", 0), 6),
                    "train_samples": len(X_train), "val_samples": len(X_val),
                    "time": round(elapsed, 1),
                })
            except Exception as e:
                elapsed = time.time() - t0
                print(f"  [{total}] {symbol} + {mt}  ERROR: {str(e)[:60]}  {elapsed:.1f}s")
                all_results.append({
                    "symbol": symbol, "model": mt, "ok": False,
                    "error": str(e)[:200], "time": round(elapsed, 1),
                })

    _save_json_output(args, all_results, "legacy", t_start, total)
    # Also save to DB
    print("Saving to database...")
    saved = await save_results_to_db(engine, all_results)
    print(f"Saved {saved} rows to ml_symbol_results!")


async def run_full_mode(args: argparse.Namespace, engine) -> None:
    """Multiprocessing training with all models, DB output."""
    model_types = _filter_models(model_registry.list_models(), _parse_model_filter(args.models))
    max_workers = args.workers or min(os.cpu_count() or 4, 8)

    symbols_data = await discover_symbols(engine, _parse_symbol_filter(args.symbols))
    print(f"\nTotal symbols in DB: {len(symbols_data)}")

    trainable = [(s, c) for s, c in symbols_data if c >= MIN_ROWS]
    [(s, c) for s, c in symbols_data if c < MIN_ROWS]
    print(f"Trainable (>= {MIN_ROWS} rows): {len(trainable)}")

    if args.test and args.test < len(trainable):
        trainable = trainable[:args.test]
        print(f"  *** TEST MODE: {args.test} symbols ***")

    if not trainable:
        print("No symbols with enough data!")
        return

    print(f"Models: {len(model_types)} | Workers: {max_workers}")
    print(f"Fetching data for {len(trainable)} symbols...")

    t_fetch = time.time()
    all_data = await fetch_all_data(engine, [s for s, _ in trainable])
    print(f"Data fetched in {time.time() - t_fetch:.1f}s")

    # Build features
    symbol_features: dict[str, tuple[pd.DataFrame, pd.Series]] = {}
    skipped = []
    for symbol, _ in trainable:
        df = all_data.get(symbol, pd.DataFrame())
        if df.empty or len(df) < MIN_ROWS:
            skipped.append(symbol)
            continue
        X, y = build_features(df)
        if len(X) < MIN_SAMPLES:
            skipped.append(symbol)
            continue
        symbol_features[symbol] = (X, y)

    print(f"Features built for {len(symbol_features)} symbols ({len(skipped)} skipped)")

    # Prepare jobs
    jobs = []
    for symbol, (X, y) in symbol_features.items():
        split = int(len(X) * 0.8)
        X_train, X_val = X.iloc[:split], X.iloc[split:]
        y_train, y_val = y.iloc[:split], y.iloc[split:]
        for mt in model_types:
            jobs.append((
                mt,
                X_train.to_dict(orient="list"),
                y_train.tolist(),
                X_val.to_dict(orient="list"),
                y_val.tolist(),
                symbol,
            ))

    total = len(jobs)
    print(f"Total jobs: {total} ({len(symbol_features)} symbols × {len(model_types)} models)")
    print(f"Running with {max_workers} parallel workers...\n")

    # Train
    all_results: list[dict] = []
    t_start = time.time()
    done = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_train_job, job): job for job in jobs}
        for future in as_completed(futures):
            done += 1
            result = future.result()
            sym, mod = result["symbol"], result["model"]
            if result["ok"]:
                print(f"  [{done}/{total}] {sym} + {mod}  R2={result['r2']}  {result['time']}s")
            else:
                print(f"  [{done}/{total}] {sym} + {mod}  FAIL: {result['error'][:40]}  {result['time']}s")
            all_results.append(result)

    total_time = time.time() - t_start

    # Save to DB
    print(f"\nSaving {len(all_results)} results to database...")
    saved = await save_results_to_db(engine, all_results)
    print(f"Saved {saved} rows to ml_symbol_results table!")

    # Summary
    success = sum(1 for r in all_results if r["ok"])
    failed = total - success
    print(f"\n{'='*60}")
    print("  FULL MODE COMPLETE")
    print(f"  Total: {total} | Success: {success} | Failed: {failed}")
    print(f"  Time: {total_time:.1f}s ({total_time/60:.1f}min)")
    print(f"  Speed: {total/total_time:.1f} jobs/sec")

    good = [r for r in all_results if r.get("ok")]
    if good:
        best = max(good, key=lambda r: r["r2"])
        print(f"  Best:  {best['symbol']} + {best['model']}  R2={best['r2']}")
        worst = min(good, key=lambda r: r["r2"])
        print(f"  Worst: {worst['symbol']} + {worst['model']}  R2={worst['r2']}")
    print(f"{'='*60}")


# ── Helpers ────────────────────────────────────────────────────────────────

def _parse_symbol_filter(raw: str) -> list[str] | None:
    """Return None (all symbols) or a list of requested symbols."""
    if not raw:
        return None
    return [s.strip() for s in raw.split(",") if s.strip()]


def _parse_model_filter(raw: str) -> list[str] | None:
    if not raw:
        return None
    return [s.strip() for s in raw.split(",") if s.strip()]


def _save_json_output(args: argparse.Namespace, results: list[dict], mode: str, t_start: float, total: int) -> None:
    success = sum(1 for r in results if r.get("ok"))
    failed = total - success
    total_time = time.time() - t_start

    output_path = args.output or f"train_results_{mode}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "mode": mode,
            "total": total,
            "success": success,
            "failed": failed,
            "time_seconds": round(total_time, 1),
            "results": results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"  {mode.upper()} MODE COMPLETE")
    print(f"  Total: {total} | Success: {success} | Failed: {failed}")
    print(f"  Time: {total_time:.1f}s ({total_time/60:.1f}min)")
    print(f"  Results saved to: {output_path}")
    print(f"{'='*60}")


# ── Main ───────────────────────────────────────────────────────────────────

async def main() -> None:
    args = parse_cli()
    engine = create_async_engine(settings.database_url_async, echo=False)

    try:
        if args.mode == "quick":
            await run_quick_mode(args, engine)
        elif args.mode == "legacy":
            await run_legacy_mode(args, engine)
        else:
            await run_full_mode(args, engine)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
