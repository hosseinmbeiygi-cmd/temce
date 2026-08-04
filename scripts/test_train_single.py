#!/usr/bin/env python
"""Test: Train ALL models on a single symbol and save to DB.

Usage:
    python scripts/test_train_single.py                 # default: فولاد
    python scripts/test_train_single.py --symbol فملی
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
from ml.evaluation.metrics import MetricsCalculator
from ml.features.price_features import PriceFeatures
from ml.features.technical_features import TechnicalFeatures
from ml.models.registry import model_registry

FETCH_SQL = text("""
    SELECT price_first AS open, price_last AS close,
           price_max AS high, price_min AS low, trade_volume AS volume
    FROM brsapi_historical_daily
    WHERE symbol = :symbol
    ORDER BY date ASC
""")


def parse_symbol() -> str:
    if "--symbol" in sys.argv:
        idx = sys.argv.index("--symbol")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return "فولاد"


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
    common_idx = X.index.intersection(y.index)
    X = X.loc[common_idx]
    y = y.loc[common_idx]
    X = X.iloc[30:]
    y = y.iloc[30:]
    return X, y


async def main():
    symbol = parse_symbol()
    engine = create_async_engine(settings.database_url_async, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print(f"{'=' * 60}")
    print("  SINGLE SYMBOL TRAINING TEST")
    print(f"  Symbol: {symbol}")
    print(f"  Models: {model_registry.list_models()}")
    print(f"{'=' * 60}")

    # 1. Fetch data
    async with factory() as session:
        result = await session.execute(FETCH_SQL, {"symbol": symbol})
        rows = result.fetchall()

    if not rows:
        print(f"\n  ERROR: No data found for '{symbol}'")
        await engine.dispose()
        return

    df = pd.DataFrame(rows, columns=["open", "close", "high", "low", "volume"])
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close"])
    df = df[df["close"] > 0]

    print(f"\n  Data rows: {len(df)}")

    if len(df) < 60:
        print(f"  ERROR: Not enough data ({len(df)} < 60)")
        await engine.dispose()
        return

    # 2. Build features
    X, y = build_features(df)
    print(f"  Feature samples: {len(X)}")
    print(f"  Feature count: {len(X.columns)}")

    if len(X) < 30:
        print(f"  ERROR: Not enough samples after features ({len(X)} < 30)")
        await engine.dispose()
        return

    # 3. Split
    split = int(len(X) * 0.8)
    X_train, X_val = X.iloc[:split], X.iloc[split:]
    y_train, y_val = y.iloc[:split], y.iloc[split:]
    print(f"  Train: {len(X_train)}  |  Val: {len(X_val)}")

    # 4. Train all models
    model_types = model_registry.list_models()
    mc = MetricsCalculator()
    all_results = []

    for model_type in model_types:
        t0 = time.time()
        print(f"\n  [{model_type}] training...", end=" ", flush=True)
        try:
            model = model_registry.create(model_type)
            model.fit(X_train, y_train)

            train_pred = model.predict(X_train)
            val_pred = model.predict(X_val)

            if hasattr(train_pred, "predictions"):
                train_pred = np.asarray(train_pred.predictions)
            if hasattr(val_pred, "predictions"):
                val_pred = np.asarray(val_pred.predictions)

            train_m = mc.compute(y_train, train_pred)
            val_m = mc.compute(y_val, val_pred)

            elapsed = time.time() - t0
            r2 = val_m.get("r2", 0)
            mae = val_m.get("mae", 0)

            print(f"OK  R2={r2:+.4f}  MAE={mae:.6f}  ({elapsed:.1f}s)")

            # Save artifact
            from ml.artifacts import ArtifactManager
            from ml.types import ModelArtifactMeta
            am = ArtifactManager()
            meta = ModelArtifactMeta(
                model_id=f"{model_type}_{symbol}",
                version=f"v1-{uuid.uuid4().hex[:8]}",
                metrics={"train": train_m, "val": val_m},
                params={},
                feature_names=list(X.columns),
                stage="development",
            )
            artifact_path = am.save_model(model, meta)

            all_results.append({
                "symbol": symbol,
                "model": model_type,
                "ok": True,
                "r2": round(r2, 4),
                "mae": round(mae, 6),
                "train_samples": len(X_train),
                "val_samples": len(X_val),
                "feature_count": len(X.columns),
                "train_metrics": train_m,
                "val_metrics": val_m,
                "artifact_path": str(artifact_path),
                "duration_seconds": round(elapsed, 2),
            })

        except Exception as e:
            elapsed = time.time() - t0
            print(f"ERROR  {str(e)[:60]}  ({elapsed:.1f}s)")
            all_results.append({
                "symbol": symbol,
                "model": model_type,
                "ok": False,
                "error": str(e)[:500],
                "duration_seconds": round(elapsed, 2),
            })

    # 5. Save to DB
    print(f"\n  Saving {len(all_results)} results to ml_symbol_results...")
    async with factory() as session:
        for r in all_results:
            run_id = f"test_{uuid.uuid4().hex[:12]}"
            if r["ok"]:
                await session.execute(text("""
                    INSERT INTO ml_symbol_results
                        (id, symbol, data_type, model_type, status, metrics,
                         train_samples, val_samples, feature_count, artifact_path,
                         duration_seconds, trained_at)
                    VALUES (:id, :symbol, 'daily', :model_type, 'completed', :metrics,
                            :train_samples, :val_samples, :feature_count, :artifact_path,
                            :duration_seconds, NOW())
                    ON CONFLICT (symbol, data_type, model_type) DO UPDATE SET
                        status = 'completed', metrics = EXCLUDED.metrics,
                        train_samples = EXCLUDED.train_samples, val_samples = EXCLUDED.val_samples,
                        feature_count = EXCLUDED.feature_count, artifact_path = EXCLUDED.artifact_path,
                        duration_seconds = EXCLUDED.duration_seconds, trained_at = NOW(), updated_at = NOW()
                """), {
                    "id": run_id, "symbol": r["symbol"], "model_type": r["model"],
                    "metrics": json.dumps(r.get("val_metrics", {}), default=str),
                    "train_samples": r.get("train_samples", 0),
                    "val_samples": r.get("val_samples", 0),
                    "feature_count": r.get("feature_count", 0),
                    "artifact_path": r.get("artifact_path", ""),
                    "duration_seconds": r.get("duration_seconds", 0),
                })
            else:
                await session.execute(text("""
                    INSERT INTO ml_symbol_results
                        (id, symbol, data_type, model_type, status, error, duration_seconds, trained_at)
                    VALUES (:id, :symbol, 'daily', :model_type, 'failed', :error, :duration_seconds, NOW())
                    ON CONFLICT (symbol, data_type, model_type) DO UPDATE SET
                        status = 'failed', error = EXCLUDED.error,
                        duration_seconds = EXCLUDED.duration_seconds, trained_at = NOW(), updated_at = NOW()
                """), {
                    "id": run_id, "symbol": r["symbol"], "model_type": r["model"],
                    "error": r.get("error", ""), "duration_seconds": r.get("duration_seconds", 0),
                })
        await session.commit()

    # 6. Summary
    ok = [r for r in all_results if r["ok"]]
    fail = [r for r in all_results if not r["ok"]]

    print(f"\n{'=' * 60}")
    print(f"  DONE: {len(ok)} succeeded, {len(fail)} failed")
    if ok:
        best = max(ok, key=lambda r: r["r2"])
        print(f"  Best: {best['model']}  R2={best['r2']:+.4f}")
    print("  Saved to: ml_symbol_results table")
    print(f"{'=' * 60}")

    # Save JSON too
    with open("test_train_single_result.json", "w", encoding="utf-8") as f:
        json.dump({"symbol": symbol, "results": all_results}, f, ensure_ascii=False, indent=2)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
