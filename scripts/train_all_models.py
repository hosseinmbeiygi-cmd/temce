#!/usr/bin/env python
"""Train ALL models on ALL symbols with enough data (with Resume support)."""
import asyncio
import json
import os
import sys
import time
import warnings
from pathlib import Path

# ========== غیرفعال‌سازی اخطارها ==========
warnings.filterwarnings("ignore")

# Fix Windows console encoding for Persian characters
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uuid

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings
from ml.evaluation.metrics import MetricsCalculator
from ml.features.price_features import PriceFeatures
from ml.features.technical_features import TechnicalFeatures
from ml.models.registry import model_registry

# ========== تنظیمات ==========
SPECIFIC_SYMBOLS = []  # خالی = همه نمادها
MIN_ROWS = 60
CHECKPOINT_FILE = "train_checkpoint.json"
RESULT_FILE = "train_all_models_results.json"

# ========== کوئری دریافت داده ==========
FETCH_SQL = text("""
    SELECT symbol, date, price_first AS open, price_last AS close,
           price_max AS high, price_min AS low, trade_volume AS volume
    FROM brsapi_historical_daily
    WHERE symbol = :symbol
    ORDER BY date ASC
""")


# ========== توابع مدیریت Checkpoint ==========
def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_checkpoint(symbol: str, model_type: str, results: list, total: int, success: int, failed: int):
    checkpoint = {
        "last_symbol": symbol,
        "last_model": model_type,
        "results": results,
        "total": total,
        "success": success,
        "failed": failed,
        "timestamp": time.time()
    }
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)


async def get_all_symbols(session, min_rows: int = MIN_ROWS) -> list[str]:
    if SPECIFIC_SYMBOLS:
        result = await session.execute(text("""
            SELECT symbol, COUNT(*) as row_count
            FROM brsapi_historical_daily
            WHERE symbol = ANY(:symbols)
            GROUP BY symbol
            HAVING COUNT(*) >= :min_rows
            ORDER BY symbol
        """), {"symbols": SPECIFIC_SYMBOLS, "min_rows": min_rows})
        symbols = [row[0] for row in result.fetchall()]
    else:
        result = await session.execute(text("""
            SELECT symbol, COUNT(*) as row_count
            FROM brsapi_historical_daily
            GROUP BY symbol
            HAVING COUNT(*) >= :min_rows
            ORDER BY symbol
        """), {"min_rows": min_rows})
        symbols = [row[0] for row in result.fetchall()]
    return symbols


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

    X = pd.concat([X_price, X_tech], axis=1)

    y = df["close"].pct_change().shift(-1)

    # Winsorize
    lower = y.quantile(0.01)
    upper = y.quantile(0.99)
    y = y.clip(lower, upper)

    valid_idx = y.index[~y.isna()]
    X = X.loc[valid_idx]
    y = y.loc[valid_idx]

    X = X.iloc[30:]
    y = y.iloc[30:]

    return X, y


async def main():
    # ========== بارگذاری Checkpoint ==========
    checkpoint = load_checkpoint()
    all_results = checkpoint.get("results", [])
    total = checkpoint.get("total", 0)
    success = checkpoint.get("success", 0)
    failed = checkpoint.get("failed", 0)
    last_symbol = checkpoint.get("last_symbol", None)
    last_model = checkpoint.get("last_model", None)

    processed_models = set()
    for r in all_results:
        processed_models.add(f"{r['symbol']}_{r['model']}")

    if checkpoint:
        print(f"🔄 Resuming from checkpoint (last symbol: {last_symbol}, last model: {last_model})")
        print(f"   Already processed: {len({r['symbol'] for r in all_results})} symbols, {len(all_results)} results")

    engine = create_async_engine(settings.database_url_async, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        symbols = await get_all_symbols(session)
        if not symbols:
            print("⚠️ No symbols found!")
            await engine.dispose()
            return

        all_models = model_registry.list_models()
        MODELS = [m for m in all_models if "logistic" not in m.lower()]

        # ========== پیدا کردن نقطه شروع ==========
        start_symbol_index = 0
        if last_symbol and last_symbol in symbols:
            start_symbol_index = symbols.index(last_symbol)
            # اگر مدل آخر کامل شده بود، از نماد بعدی شروع کن
            if last_model and last_model == MODELS[-1]:
                start_symbol_index += 1

        print(f"📊 Total symbols: {len(symbols)}, Starting from index: {start_symbol_index}")
        print(f"📊 Models to train: {MODELS}")

        # ========== پچ صحیح CatBoost (بدون خطا) ==========
        import catboost as cb

        import ml.models.shallow.boosting_models as boosting_models

        # پچ کردن مستقیم کلاس CatBoostModel
        def patched_catboost_fit(self, X, y):
            # مقداردهی اولیه مدل اگر وجود نداشت
            if not hasattr(self, 'model') or self.model is None:
                self.model = cb.CatBoostRegressor(
                    iterations=100,
                    learning_rate=0.1,
                    depth=6,
                    verbose=0
                )
            self.model.fit(X, y, verbose=0)
        boosting_models.CatBoostModel.fit = patched_catboost_fit

        # ========== حلقه اصلی ==========
        for idx, symbol in enumerate(symbols[start_symbol_index:], start=start_symbol_index+1):
            print(f"\n{'='*60}")
            print(f"  [{idx}/{len(symbols)}] Symbol: {symbol}")
            print(f"{'='*60}")

            df = await fetch_ohlcv(session, symbol)
            if df.empty or len(df) < MIN_ROWS:
                print(f"  SKIP - only {len(df)} rows")
                continue

            X, y = build_features(df)
            if len(X) < 30:
                print(f"  SKIP - only {len(X)} samples")
                continue

            split = int(len(X) * 0.8)
            X_train, X_val = X.iloc[:split], X.iloc[split:]
            y_train, y_val = y.iloc[:split], y.iloc[split:]

            X_train = pd.DataFrame(X_train, columns=X.columns)
            X_val = pd.DataFrame(X_val, columns=X.columns)

            for model_type in MODELS:
                result_key = f"{symbol}_{model_type}"
                if result_key in processed_models:
                    print(f"  [{total+1}] {model_type}... SKIP (already done)")
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

                    result = {
                        "symbol": symbol, "model": model_type, "ok": True,
                        "r2": round(r2, 4) if isinstance(r2, float) else r2,
                        "mae": round(mae, 6) if isinstance(mae, float) else mae,
                        "train_samples": len(X_train), "val_samples": len(X_val),
                        "time": round(elapsed, 1)
                    }
                    all_results.append(result)
                    processed_models.add(result_key)

                except KeyboardInterrupt:
                    print("INTERRUPTED  (saving checkpoint...)")
                    save_checkpoint(symbol, model_type, all_results, total, success, failed)
                    raise
                except Exception as e:
                    elapsed = time.time() - t0
                    print(f"ERROR  {str(e)[:60]}  {elapsed:.1f}s")
                    failed += 1
                    result = {
                        "symbol": symbol, "model": model_type, "ok": False,
                        "error": str(e)[:200], "time": round(elapsed, 1)
                    }
                    all_results.append(result)
                    processed_models.add(result_key)

            # ========== ذخیره Checkpoint بعد از هر نماد ==========
            save_checkpoint(symbol, MODELS[-1], all_results, total, success, failed)
            print(f"💾 Checkpoint saved after {symbol}")

    print(f"\n{'='*60}")
    print(f"  TOTAL: {success}/{total} succeeded, {failed} failed")
    print(f"{'='*60}")

    # Save final
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {"total": total, "success": success, "failed": failed},
            "results": all_results
        }, f, ensure_ascii=False, indent=2)
    print(f"  Saved to {RESULT_FILE}")

    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        print("  Checkpoint file removed (completed)")

    print("\nSaving to database...")
    await _save_results_to_db(engine, all_results)
    await engine.dispose()


async def _save_results_to_db(engine, results: list[dict]) -> int:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    saved = 0
    async with factory() as session:
        for r in results:
            rid = f"train_{uuid.uuid4().hex[:12]}"
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
                    "id": rid, "symbol": r["symbol"], "model_type": r["model"],
                    "metrics": json.dumps({"r2": r.get("r2", 0), "mae": r.get("mae", 0)}, ensure_ascii=False),
                    "train_samples": r.get("train_samples", 0),
                    "val_samples": r.get("val_samples", 0),
                    "feature_count": 0, "artifact_path": "",
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
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user. Checkpoint saved. Run again to resume.")
