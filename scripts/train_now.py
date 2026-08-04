#!/usr/bin/env python
"""Check DB schema and train ML models directly from brsapi_historical_daily."""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import uuid

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings
from ml.artifacts import ArtifactManager
from ml.features.price_features import PriceFeatures
from ml.features.technical_features import TechnicalFeatures
from ml.models.registry import model_registry

SYMBOLS = ["فولاد", "فملی", "وبانک", "کگل", "خودرو", "شستا", "شپنا"]
MODELS = ["xgboost", "lightgbm", "random_forest"]

FETCH_SQL = text("""
    SELECT symbol, date, price_first AS open, price_last AS close,
           price_max AS high, price_min AS low, trade_volume AS volume
    FROM brsapi_historical_daily
    WHERE symbol = :symbol
    ORDER BY date ASC
""")


async def fetch_ohlcv(session, symbol: str) -> pd.DataFrame:
    result = await session.execute(FETCH_SQL, {"symbol": symbol})
    rows = result.fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["symbol", "date", "open", "close", "high", "low", "volume"])
    for col in ["open", "close", "high", "low", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close"])
    df = df[df["close"] > 0]
    if "symbol" in df.columns:
        df = df.drop(columns=["symbol"])
    if "date" in df.columns:
        df = df.drop(columns=["date"])
    return df


def build_features(df: pd.DataFrame):
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
    # Align by common index
    common_idx = X.index.intersection(y.index)
    X = X.loc[common_idx]
    y = y.loc[common_idx]
    # Drop first 30 rows (NaN from rolling)
    X = X.iloc[30:]
    y = y.iloc[30:]
    return X, y


def train_model(model_type: str, X_train, y_train, X_val, y_val):
    model = model_registry.create(model_type)
    model.fit(X_train, y_train)
    train_pred = model.predict(X_train)
    val_pred = model.predict(X_val) if X_val is not None and len(X_val) > 0 else None

    from ml.evaluation.metrics import MetricsCalculator
    mc = MetricsCalculator()
    train_metrics = mc.calculate(y_train, train_pred)
    val_metrics = mc.calculate(y_val, val_pred) if val_metrics_available(y_val, val_pred) else {}
    return model, train_metrics, val_metrics


def val_metrics_available(y_val, y_pred):
    try:
        return y_val is not None and y_pred is not None and len(y_val) > 0
    except Exception:
        return False


async def main():
    engine = create_async_engine(settings.database_url_async, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    total = 0
    success = 0
    failed = 0
    results = []

    async with factory() as session:
        for model_type in MODELS:
            print(f"\n{'='*60}")
            print(f"  Training: {model_type.upper()}")
            print(f"{'='*60}")

            for symbol in SYMBOLS:
                total += 1
                print(f"  [{total}] {symbol} ({model_type})...", end=" ", flush=True)
                t0 = time.time()
                try:
                    df = await fetch_ohlcv(session, symbol)
                    if df.empty or len(df) < 60:
                        print(f"SKIP  only {len(df)} rows")
                        failed += 1
                        results.append({"symbol": symbol, "model": model_type, "ok": False, "error": f"only {len(df)} rows"})
                        continue

                    X, y = build_features(df)
                    if len(X) < 30:
                        print(f"SKIP  only {len(X)} samples after features")
                        failed += 1
                        results.append({"symbol": symbol, "model": model_type, "ok": False, "error": f"only {len(X)} samples"})
                        continue

                    split = int(len(X) * 0.8)
                    X_train, X_val = X.iloc[:split], X.iloc[split:]
                    y_train, y_val = y.iloc[:split], y.iloc[split:]

                    model = model_registry.create(model_type)
                    model.fit(X_train, y_train)

                    from ml.evaluation.metrics import MetricsCalculator
                    mc = MetricsCalculator()
                    train_pred = model.predict(X_train)
                    val_pred = model.predict(X_val)
                    # Extract numpy arrays from PredictionResult
                    import numpy as np
                    if hasattr(train_pred, "predictions"):
                        train_pred = np.asarray(train_pred.predictions)
                    if hasattr(val_pred, "predictions"):
                        val_pred = np.asarray(val_pred.predictions)

                    train_m = mc.compute(y_train, train_pred)
                    val_m = mc.compute(y_val, val_pred)

                    r2 = val_m.get("r2", "N/A")
                    mae = val_m.get("mae", "N/A")

                    # Save artifact
                    am = ArtifactManager()
                    from ml.types import ModelArtifactMeta
                    meta = ModelArtifactMeta(
                        model_id=f"{model_type}_{symbol}",
                        version="v1",
                        metrics={"train": train_m, "val": val_m},
                        params={},
                        feature_names=list(X.columns),
                        stage="development",
                    )
                    am.save_model(model, meta)

                    elapsed = time.time() - t0
                    print(f"OK  R2={r2:.4f}  MAE={mae:.6f}  samples={len(X_train)}/{len(X_val)}  {elapsed:.1f}s")
                    success += 1
                    results.append({"symbol": symbol, "model": model_type, "ok": True, "r2": round(r2, 4) if isinstance(r2, float) else r2, "mae": round(mae, 6) if isinstance(mae, float) else mae, "train": len(X_train), "val": len(X_val), "time": round(elapsed, 1)})

                except Exception as e:
                    elapsed = time.time() - t0
                    print(f"ERROR  {str(e)[:80]}  {elapsed:.1f}s")
                    failed += 1
                    results.append({"symbol": symbol, "model": model_type, "ok": False, "error": str(e)[:200], "time": round(elapsed, 1)})

    print(f"\n{'='*60}")
    print(f"  DONE: {success}/{total} succeeded, {failed} failed")
    print(f"{'='*60}")

    # Save to DB
    print("\nSaving to database...")
    await _save_results_to_db(engine, results)

    await engine.dispose()


async def _save_results_to_db(engine, results: list[dict]) -> int:
    """Upsert all results into ml_symbol_results table."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    saved = 0
    async with factory() as session:
        for r in results:
            rid = f"train_{uuid.uuid4().hex[:12]}"
            if r["ok"]:
                await session.execute(text("""
                    INSERT INTO ml_symbol_results
                        (id, symbol, data_type, model_type, status, metrics,
                         train_samples, val_samples, feature_count,
                         duration_seconds, trained_at)
                    VALUES (:id, :symbol, 'historical_daily', :model_type, 'completed', :metrics,
                            :train_samples, :val_samples, 0,
                            :duration_seconds, NOW())
                    ON CONFLICT (symbol, data_type, model_type) DO UPDATE SET
                        status = 'completed', metrics = EXCLUDED.metrics,
                        train_samples = EXCLUDED.train_samples, val_samples = EXCLUDED.val_samples,
                        duration_seconds = EXCLUDED.duration_seconds, trained_at = NOW(), updated_at = NOW()
                """), {
                    "id": rid, "symbol": r["symbol"], "model_type": r["model"],
                    "metrics": json.dumps({"r2": r.get("r2", 0), "mae": r.get("mae", 0)}, ensure_ascii=False),
                    "train_samples": r.get("train", 0),
                    "val_samples": r.get("val", 0),
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
                    "id": rid, "symbol": r["symbol"], "model_type": r["model"],
                    "error": r.get("error", "")[:500],
                    "duration_seconds": r.get("time", 0),
                })
            saved += 1
        await session.commit()
    print(f"  Saved {saved} rows to ml_symbol_results")
    return saved


if __name__ == "__main__":
    asyncio.run(main())
