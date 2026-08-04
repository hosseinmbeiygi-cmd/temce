#!/usr/bin/env python
"""
Train ALL models on ALL symbols and save results to PostgreSQL.
Uses multiprocessing for CPU-bound model training.Usage:
  python scripts/train_all_symbols.py                           # train ALL symbols
  python scripts/train_all_symbols.py --test 2                  # train only 2 symbols
  python scripts/train_all_symbols.py --workers 8                # use 8 parallel workers
  python scripts/train_all_symbols.py --symbols فولاد,فملی,خودرو  # train specific symbols"""
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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings
from ml.models.registry import model_registry

MIN_ROWS = 60
MIN_SAMPLES = 30
FETCH_SQL = text("""
    SELECT price_first AS open, price_last AS close,
           price_max AS high, price_min AS low, trade_volume AS volume
    FROM brsapi_historical_daily
    WHERE symbol = :symbol
    ORDER BY date ASC
""")


def parse_args():
    test_limit = 0
    workers = min(os.cpu_count() or 4, 8)
    symbols_filter = None
    if "--test" in sys.argv:
        idx = sys.argv.index("--test")
        if idx + 1 < len(sys.argv):
            test_limit = int(sys.argv[idx + 1])
    if "--workers" in sys.argv:
        idx = sys.argv.index("--workers")
        if idx + 1 < len(sys.argv):
            workers = int(sys.argv[idx + 1])
    if "--symbols" in sys.argv:
        idx = sys.argv.index("--symbols")
        if idx + 1 < len(sys.argv):
            raw = sys.argv[idx + 1]
            symbols_filter = [s.strip() for s in raw.split(",") if s.strip()]
    return test_limit, workers, symbols_filter


def train_single_model(args):
    """Train one model on one symbol's data. Runs in a separate process."""
    model_type, X_train_list, y_train_list, X_val_list, y_val_list, symbol = args

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

        # Save artifact with unique path per symbol+model
        am = ArtifactManager()
        model_id = f"{model_type}_{symbol}"
        version = f"v1-{uuid.uuid4().hex[:8]}"
        meta = ModelArtifactMeta(
            model_id=model_id,
            version=version,
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


async def get_all_symbols(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        r = await session.execute(text("""
            SELECT symbol, COUNT(*) as cnt
            FROM brsapi_historical_daily
            WHERE symbol IS NOT NULL AND symbol != ''
            GROUP BY symbol
            ORDER BY cnt DESC
        """))
        return [(row[0], row[1]) for row in r]


async def fetch_all_data(engine, symbols):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    results = {}

    async def fetch_one(sym):
        async with factory() as session:
            r = await session.execute(FETCH_SQL, {"symbol": sym})
            rows = r.fetchall()
            if not rows:
                return sym, pd.DataFrame()
            df = pd.DataFrame(rows, columns=["open", "close", "high", "low", "volume"])
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["close"])
            df = df[df["close"] > 0]
            return sym, df

    batch_size = 50
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        tasks = [fetch_one(s) for s in batch]
        for coro in asyncio.as_completed(tasks):
            sym, df = await coro
            results[sym] = df

    return results


def build_features(df):
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
    common_idx = X.index.intersection(y.index)
    X = X.loc[common_idx]
    y = y.loc[common_idx]
    X = X.iloc[MIN_SAMPLES:]
    y = y.iloc[MIN_SAMPLES:]
    return X, y


async def save_results_to_db(engine, results, skipped, insufficient):
    """Save all training results to ml_symbol_results table (upsert)."""
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        for r in results:
            result_id = f"train_{uuid.uuid4().hex[:12]}"
            if r["ok"]:
                await session.execute(text("""
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
                    "id": result_id,
                    "symbol": r["symbol"],
                    "model_type": r["model"],
                    "metrics": json.dumps(r.get("val_metrics", {}), ensure_ascii=False),
                    "train_samples": r.get("train_samples", 0),
                    "val_samples": r.get("val_samples", 0),
                    "feature_count": r.get("feature_count", 0),
                    "artifact_path": r.get("artifact_path", ""),
                    "duration_seconds": r.get("time", 0),
                })
            else:
                await session.execute(text("""
                    INSERT INTO ml_symbol_results
                        (id, symbol, data_type, model_type, status, error, duration_seconds, trained_at)
                    VALUES (:id, :symbol, 'historical_daily', :model_type, 'failed', :error, :duration_seconds, NOW())
                    ON CONFLICT (symbol, data_type, model_type) DO UPDATE SET
                        status = 'failed', error = EXCLUDED.error,
                        duration_seconds = EXCLUDED.duration_seconds, trained_at = NOW(), updated_at = NOW()
                """), {
                    "id": result_id,
                    "symbol": r["symbol"],
                    "model_type": r["model"],
                    "error": r.get("error", "")[:500],
                    "duration_seconds": r.get("time", 0),
                })

        await session.commit()


async def main():
    test_limit, max_workers, symbols_filter = parse_args()
    model_types = model_registry.list_models()
    print(f"CPU cores: {os.cpu_count()}  |  Workers: {max_workers}")
    print(f"Models: {len(model_types)}  |  {', '.join(model_types)}")

    engine = create_async_engine(settings.database_url_async, echo=False)

    # 1. Get all symbols
    all_symbols = await get_all_symbols(engine)
    print(f"\nTotal symbols in DB: {len(all_symbols)}")

    # Filter by --symbols if provided
    if symbols_filter:
        filtered = []
        not_found = []
        for sym in symbols_filter:
            matched = [(s, c) for s, c in all_symbols if s == sym]
            if matched:
                filtered.extend(matched)
            else:
                not_found.append(sym)
        if not_found:
            print(f"  Symbols NOT found in DB: {', '.join(not_found)}")
        all_symbols = filtered
        if not all_symbols:
            print("ERROR: None of the requested --symbols were found in the database.")
            await engine.dispose()
            return

    trainable = [(s, c) for s, c in all_symbols if c >= MIN_ROWS]
    insufficient = [(s, c) for s, c in all_symbols if c < MIN_ROWS]
    print(f"Trainable (>= {MIN_ROWS} rows): {len(trainable)}")
    print(f"Insufficient (< {MIN_ROWS} rows): {len(insufficient)}")

    if symbols_filter and len(trainable) < len(symbols_filter):
        insufficient_names = [s for s, _ in insufficient]
        if insufficient_names:
            print(f"  Some symbols have < {MIN_ROWS} rows (insufficient data): {', '.join(insufficient_names)}")

    if test_limit > 0:
        trainable = trainable[:test_limit]
        print(f"\n  *** TEST MODE: {test_limit} symbols ***")

    # 2. Fetch all data
    print(f"\nFetching data for {len(trainable)} symbols...")
    t_fetch = time.time()
    all_data = await fetch_all_data(engine, [s for s, _ in trainable])
    print(f"Data fetched in {time.time() - t_fetch:.1f}s")

    # 3. Build features
    print("\nBuilding features...")
    t_feat = time.time()
    symbol_features = {}
    skipped = []
    for symbol, _ in trainable:
        df = all_data.get(symbol, pd.DataFrame())
        if df.empty or len(df) < MIN_ROWS:
            skipped.append({"symbol": symbol, "reason": f"only {len(df)} rows"})
            continue
        X, y = build_features(df)
        if len(X) < MIN_SAMPLES:
            skipped.append({"symbol": symbol, "reason": f"only {len(X)} samples"})
            continue
        symbol_features[symbol] = (X, y)
    print(f"Features built for {len(symbol_features)} symbols in {time.time() - t_feat:.1f}s")

    # 4. Prepare jobs
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
    print(f"\nTotal jobs: {total} ({len(symbol_features)} symbols x {len(model_types)} models)")
    print(f"Running with {max_workers} parallel workers...\n")

    # 5. Train parallel
    all_results = []
    t_start = time.time()
    done = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(train_single_model, job): job for job in jobs}
        for future in as_completed(futures):
            done += 1
            result = future.result()
            sym = result["symbol"]
            mod = result["model"]
            if result["ok"]:
                print(f"  [{done}/{total}] {sym} + {mod}  R2={result['r2']}  {result['time']}s")
            else:
                print(f"  [{done}/{total}] {sym} + {mod}  FAIL: {result['error'][:40]}  {result['time']}s")
            all_results.append(result)

    total_time = time.time() - t_start

    # 6. Save to DB
    print(f"\nSaving {len(all_results)} results to database...")
    await save_results_to_db(engine, all_results, skipped, insufficient)
    print("Results saved to ml_symbol_results table!")

    # 7. Summary
    success = sum(1 for r in all_results if r["ok"])
    failed = total - success

    print(f"\n{'='*60}")
    print("  TRAINING COMPLETE")
    print(f"  Total: {total} | Success: {success} | Failed: {failed}")
    print(f"  Time: {total_time:.1f}s ({total_time/60:.1f}min)")
    print(f"  Speed: {total/total_time:.1f} jobs/sec")
    print(f"{'='*60}")

    good = [r for r in all_results if r.get("ok")]
    if good:
        best = max(good, key=lambda r: r["r2"])
        print(f"  Best: {best['symbol']} + {best['model']}  R2={best['r2']}")
        worst = min(good, key=lambda r: r["r2"])
        print(f"  Worst: {worst['symbol']} + {worst['model']}  R2={worst['r2']}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
