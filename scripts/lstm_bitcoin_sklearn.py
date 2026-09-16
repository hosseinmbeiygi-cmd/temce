#!/usr/bin/env python
"""
پیش‌بینی قیمت بیتکوین با MLP (جایگزین LSTM بدون PyTorch).

از sklearn.neural_network.MLPRegressor استفاده می‌کند.

Usage:
    python scripts/lstm_bitcoin_sklearn.py --fetch
    python scripts/lstm_bitcoin_sklearn.py --fetch --predict-days 30
    python scripts/lstm_bitcoin_sklearn.py --input data.csv
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import MinMaxScaler

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

OUTPUT_DIR = _project_root / "exchange_rate_data" / "bitcoin_mlp"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
#  ۱. جمع‌آوری داده
# ═══════════════════════════════════════════════════════════════


def fetch_yahoo(ticker: str, col: str) -> pd.DataFrame:
    import requests

    print(f"  [Yahoo] {ticker}...")
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        p = {"period1": 1262304000, "period2": int(time.time()), "interval": "1d"}
        r = requests.get(url, params=p, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        r.raise_for_status()
        res = r.json()["chart"]["result"][0]
        df = pd.DataFrame(
            {
                "date": [pd.Timestamp(t, unit="s").date() for t in res["timestamp"]],
                col: res["indicators"]["quote"][0]["close"],
            }
        )
        print(f"    ✓ {len(df)} رکورد")
        return df
    except Exception as e:
        print(f"    ✗ {e}")
        return pd.DataFrame()


def fetch_all() -> pd.DataFrame:
    print("\n" + "═" * 70)
    print("  جمع‌آوری داده‌ها")
    print("═" * 70)

    btc = fetch_yahoo("BTC-USD", "price")
    if btc.empty:
        print("  ✗ بیتکوین دریافت نشد")
        sys.exit(1)

    gold = fetch_yahoo("GC=F", "gold")
    sp500 = fetch_yahoo("^GSPC", "sp500")
    dxy = fetch_yahoo("DX-Y.NYB", "dxy")

    df = btc
    for o in [gold, sp500, dxy]:
        if not o.empty and "date" in o.columns:
            df = pd.merge(df, o, on="date", how="left")

    df = df.ffill().dropna()
    print(f"\n  ✓ {len(df)} ردیف نهایی")
    return df


# ═══════════════════════════════════════════════════════════════
#  ۲. ویژگی‌سازی
# ═══════════════════════════════════════════════════════════════


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    r = df.copy()
    p = r["price"]

    # لگاریتمی
    r["log_price"] = np.log(p)
    for c in ["gold", "sp500", "dxy", "volume"]:
        if c in r.columns:
            r[f"log_{c}"] = np.log(r[c] + 1)

    # SMA / EMA
    for w in [7, 14, 21, 50]:
        r[f"sma_{w}"] = p.rolling(w, min_periods=1).mean()
    for s in [12, 26]:
        r[f"ema_{s}"] = p.ewm(span=s, adjust=False).mean()

    # RSI
    d = p.diff()
    g = d.where(d > 0, 0).rolling(14, min_periods=1).mean()
    loss = (-d.where(d < 0, 0)).rolling(14, min_periods=1).mean()
    r["rsi_14"] = 100 - 100 / (1 + g / (loss + 1e-10))

    # MACD
    r["macd"] = p.ewm(span=12).mean() - p.ewm(span=26).mean()
    r["macd_signal"] = r["macd"].ewm(span=9).mean()

    # Bollinger
    sma20 = p.rolling(20, min_periods=1).mean()
    std20 = p.rolling(20, min_periods=1).std().fillna(0)
    r["bb_width"] = 4 * std20 / (sma20 + 1e-10)

    # بازده و نوسان
    r["ret_1d"] = p.pct_change(1)
    r["ret_3d"] = p.pct_change(3)
    r["vol_7"] = p.pct_change().rolling(7, min_periods=1).std()

    return r.dropna()


# ═══════════════════════════════════════════════════════════════
#  ۳. آماده‌سازی داده
# ═══════════════════════════════════════════════════════════════


def create_sequences(data: np.ndarray, target: np.ndarray, seq_len: int):
    X, y = [], []
    for i in range(len(data) - seq_len):
        X.append(data[i : i + seq_len].flatten())  # Flatten for MLP
        y.append(target[i + seq_len])
    return np.array(X), np.array(y)


def prepare(df, target, features, seq_len=30, train_ratio=0.8):
    cols = [target] + [c for c in features if c in df.columns]
    clean = df[cols].dropna().reset_index(drop=True)
    feat_cols = [c for c in features if c in clean.columns]

    X_raw = clean[feat_cols].values
    y_raw = clean[target].values

    f_sc = MinMaxScaler()
    t_sc = MinMaxScaler()

    X_scaled = f_sc.fit_transform(X_raw)
    y_scaled = t_sc.fit_transform(y_raw.reshape(-1, 1)).flatten()

    X, y = create_sequences(X_scaled, y_scaled, seq_len)

    split = int(len(X) * train_ratio)
    return {
        "X_train": X[:split],
        "X_test": X[split:],
        "y_train": y[:split],
        "y_test": y[split:],
        "f_scaler": f_sc,
        "t_scaler": t_sc,
        "n_features": len(feat_cols),
        "seq_len": seq_len,
        "feature_names": feat_cols,
    }


# ═══════════════════════════════════════════════════════════════
#  ۴. مدل‌ها
# ═══════════════════════════════════════════════════════════════


def build_models(n_features: int, seq_len: int):
    """ساخت مدل‌های MLP با معماری‌های مختلف."""
    n_features * seq_len

    return {
        "MLP-Small": MLPRegressor(
            hidden_layer_sizes=(64, 32),
            activation="relu",
            solver="adam",
            max_iter=500,
            early_stopping=True,
            validation_fraction=0.15,
            random_state=42,
        ),
        "MLP-Medium": MLPRegressor(
            hidden_layer_sizes=(128, 64, 32),
            activation="relu",
            solver="adam",
            max_iter=500,
            early_stopping=True,
            validation_fraction=0.15,
            random_state=42,
        ),
        "MLP-Large": MLPRegressor(
            hidden_layer_sizes=(256, 128, 64),
            activation="relu",
            solver="adam",
            max_iter=500,
            early_stopping=True,
            validation_fraction=0.15,
            random_state=42,
        ),
        "MLP-Deep": MLPRegressor(
            hidden_layer_sizes=(128, 64, 32, 16),
            activation="relu",
            solver="adam",
            max_iter=500,
            early_stopping=True,
            validation_fraction=0.15,
            random_state=42,
        ),
    }


def train_and_evaluate(name, model, X_train, y_train, X_test, y_test, t_scaler):
    """آموزش و ارزیابی."""
    print(f"\n  ── {name} ──")
    t0 = time.time()
    model.fit(X_train, y_train)
    train_time = time.time() - t0

    train_pred = model.predict(X_train)
    test_pred = model.predict(X_test)

    # تبدیل از مقیاس نرمال
    t_scaler.inverse_transform(y_train.reshape(-1, 1)).flatten()
    t_scaler.inverse_transform(train_pred.reshape(-1, 1)).flatten()
    test_actual = t_scaler.inverse_transform(y_test.reshape(-1, 1)).flatten()
    test_pred_actual = t_scaler.inverse_transform(test_pred.reshape(-1, 1)).flatten()

    # معیارها
    mae = mean_absolute_error(test_actual, test_pred_actual)
    rmse = np.sqrt(mean_squared_error(test_actual, test_pred_actual))
    mask = np.abs(test_actual) > 1e-10
    mape = np.mean(np.abs((test_actual[mask] - test_pred_actual[mask]) / test_actual[mask])) * 100
    r2 = r2_score(test_actual, test_pred_actual)
    d_acc = np.mean((np.diff(test_actual) > 0) == (np.diff(test_pred_actual) > 0)) * 100 if len(test_actual) > 1 else 0

    print(f"    MAE=${mae:.2f}  RMSE=${rmse:.2f}  MAPE={mape:.2f}%  R²={r2:.6f}  Dir={d_acc:.1f}%")
    print(f"    آموزش: {train_time:.1f}s | iterations: {model.n_iter_}")

    return {
        "name": name,
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape": round(mape, 2),
        "r2": round(r2, 6),
        "dir_acc": round(d_acc, 2),
        "train_time": round(train_time, 1),
        "n_iter": model.n_iter_,
    }


# ═══════════════════════════════════════════════════════════════
#  ۵. پیش‌بینی آینده
# ═══════════════════════════════════════════════════════════════


def forecast_future(model, last_seq_scaled, t_scaler, f_scaler, n_days=30):
    """پیش‌بینی n روز آینده."""
    current = last_seq_scaled.copy()
    preds = []
    for d in range(1, n_days + 1):
        x = current.flatten().reshape(1, -1)
        p = model.predict(x)[0]
        val = t_scaler.inverse_transform([[p]])[0, 0]
        preds.append({"day": d, "price": round(float(val), 2)})
        # به‌روزرسانی ساده
        new_row = current[-1:].copy()
        new_row[0, 0] = p
        current = np.vstack([current[1:], new_row])
    return preds


# ═══════════════════════════════════════════════════════════════
#  ۶. CLI + اجرا
# ═══════════════════════════════════════════════════════════════


def parse_args():
    p = argparse.ArgumentParser(description="پیش‌بینی قیمت بیتکوین با MLP")
    p.add_argument("--input", "-i", type=str, default=None)
    p.add_argument("--fetch", action="store_true")
    p.add_argument("--target", default="price")
    p.add_argument("--seq-length", type=int, default=30)
    p.add_argument("--predict-days", type=int, default=0)
    p.add_argument("--save", type=str, default=None)
    return p.parse_args()


def main():
    args = parse_args()

    print("=" * 70)
    print("  پیش‌بینی قیمت بیتکوین با MLP")
    print("=" * 70)

    # ── داده ──
    if args.fetch or args.input is None:
        df = fetch_all()
    else:
        df = pd.read_csv(args.input, encoding="utf-8-sig")
        print(f"\n  ✓ {len(df)} ردیف")

    if df.empty:
        sys.exit("✗ داده‌ای موجود نیست")

    if args.save:
        df.to_csv(args.save, index=False)
        print(f"  💾 {args.save}")

    # ── ویژگی‌ها ──
    df = add_features(df)
    features = [
        "log_price",
        "log_gold",
        "log_sp500",
        "log_dxy",
        "log_volume",
        "sma_7",
        "sma_21",
        "ema_12",
        "ema_26",
        "rsi_14",
        "macd",
        "macd_signal",
        "bb_width",
        "ret_1d",
        "ret_3d",
        "vol_7",
    ]
    features = [c for c in features if c in df.columns]
    print(f"\n  ✓ {len(features)} ویژگی")

    # ── آماده‌سازی ──
    data = prepare(df, args.target, features, seq_len=args.seq_length)
    print(f"  ✓ Train={len(data['X_train'])} Test={len(data['X_test'])}")
    print(f"  ✓ Input size: {data['X_train'].shape[1]}")

    # ── مدل‌ها ──
    models = build_models(data["n_features"], data["seq_len"])
    results = []
    best_model = None
    best_r2 = -999

    for name, model in models.items():
        res = train_and_evaluate(
            name,
            model,
            data["X_train"],
            data["y_train"],
            data["X_test"],
            data["y_test"],
            data["t_scaler"],
        )
        results.append(res)
        if res["r2"] > best_r2:
            best_r2 = res["r2"]
            best_model = (name, model)

    # ── جدول مقایسه ──
    print(f"\n{'═' * 70}")
    print("  مقایسه مدل‌ها")
    print(f"{'═' * 70}")
    print(f"  {'مدل':>12s}  {'MAE':>12s}  {'RMSE':>12s}  {'MAPE':>8s}  {'R²':>10s}  {'Dir%':>6s}")
    print(f"  {'─' * 65}")
    for r in results:
        marker = " ←" if r["name"] == best_model[0] else ""
        print(
            f"  {r['name']:>12s}  ${r['mae']:>10,.2f}  ${r['rmse']:>10,.2f}  "
            f"{r['mape']:>7.2f}%  {r['r2']:>10.6f}  {r['dir_acc']:>5.1f}%{marker}"
        )
    print(f"  {'─' * 65}")

    # ── ذخیره ──
    with open(OUTPUT_DIR / "model_comparison.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  💾 نتایج: {OUTPUT_DIR / 'model_comparison.json'}")

    # ── پیش‌بینی آینده ──
    if args.predict_days > 0 and best_model:
        print(f"\n{'═' * 70}")
        print(f"  پیش‌بینی {args.predict_days} روز آینده ({best_model[0]})")
        print(f"{'═' * 70}")

        last_seq = data["X_test"][-1:].reshape(data["seq_len"], data["n_features"])
        forecasts = forecast_future(best_model[1], last_seq, data["t_scaler"], data["f_scaler"], args.predict_days)

        print(f"    {'روز':>6s}  {'قیمت پیش‌بینی':>15s}")
        print(f"    {'─' * 25}")
        for f in forecasts:
            print(f"    {f['day']:>6d}  ${f['price']:>14,.2f}")

        with open(OUTPUT_DIR / "forecast.json", "w", encoding="utf-8") as fp:
            json.dump(forecasts, fp, indent=2)
        print(f"\n  💾 پیش‌بینی: {OUTPUT_DIR / 'forecast.json'}")

    print(f"\n{'═' * 70}")
    print("  ✅ تمام شد!")
    print(f"{'═' * 70}")


if __name__ == "__main__":
    main()
