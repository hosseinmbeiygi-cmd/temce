#!/usr/bin/env python
"""Quick test: Train subset of models on subset of symbols."""
import asyncio
import json
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings
from ml.evaluation.metrics import MetricsCalculator
from ml.features.price_features import PriceFeatures
from ml.features.technical_features import TechnicalFeatures
from ml.models.registry import model_registry

# Only these symbols (skip وبانک, شپنا which have 0 data)
SYMBOLS = ["فولاد", "خودرو"]
# Skip heavy models for speed; test basic ones first
FAST_MODELS = ["linear_regression", "random_forest", "xgboost", "huber_regressor"]

FETCH_SQL = text("""
    SELECT symbol, date, price_first AS open, price_last AS close,
           price_max AS high, price_min AS low, trade_volume AS volume
    FROM brsapi_historical_daily
    WHERE symbol = :symbol
    ORDER BY date ASC
""")


async def fetch_ohlcv(session, symbol):
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


def build_features(df):
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
    engine = create_async_engine(settings.database_url_async, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    all_results = []
    total = 0
    success = 0
    failed = 0

    async with factory() as session:
        for symbol in SYMBOLS:
            print(f"\n{'='*60}")
            print(f"  Symbol: {symbol}")
            print(f"{'='*60}")

            df = await fetch_ohlcv(session, symbol)
            if df.empty or len(df) < 60:
                print(f"  SKIP - only {len(df)} rows (need >= 60)")
                continue

            X, y = build_features(df)
            if len(X) < 30:
                print(f"  SKIP - only {len(X)} samples after features")
                continue

            split = int(len(X) * 0.8)
            X_train, X_val = X.iloc[:split], X.iloc[split:]
            y_train, y_val = y.iloc[:split], y.iloc[split:]

            print(f"  Data: {len(df)} rows -> {len(X)} samples (train={len(X_train)}, val={len(X_val)})")
            print(f"  Features: {list(X.columns)}")

            for model_type in FAST_MODELS:
                if model_type not in model_registry.list_models():
                    print(f"  [{total+1}] {model_type}... SKIP (not registered)")
                    continue
                total += 1
                print(f"  [{total}] {model_type}...", end=" ", flush=True)
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

                    r2 = val_m.get("r2", "N/A")
                    mae = val_m.get("mae", "N/A")

                    from ml.artifacts import ArtifactManager
                    from ml.types import ModelArtifactMeta
                    am = ArtifactManager()
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
                    print(f"OK  R2={r2:.4f}  MAE={mae:.6f}  {elapsed:.1f}s")
                    success += 1
                    all_results.append({
                        "symbol": symbol, "model": model_type, "ok": True,
                        "r2": round(r2, 4) if isinstance(r2, float) else r2,
                        "mae": round(mae, 6) if isinstance(mae, float) else mae,
                        "train_samples": len(X_train), "val_samples": len(X_val),
                        "time": round(elapsed, 1)
                    })
                except Exception as e:
                    elapsed = time.time() - t0
                    print(f"ERROR  {str(e)[:80]}  {elapsed:.1f}s")
                    failed += 1
                    all_results.append({
                        "symbol": symbol, "model": model_type, "ok": False,
                        "error": str(e)[:200], "time": round(elapsed, 1)
                    })

    print(f"\n{'='*60}")
    print(f"  TOTAL: {success}/{total} succeeded, {failed} failed")
    print(f"{'='*60}")

    # Save results
    out_path = Path(__file__).resolve().parent / "test_train_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {"total": total, "success": success, "failed": failed},
            "results": all_results
        }, f, ensure_ascii=False, indent=2)
    print(f"  Saved to {out_path}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
