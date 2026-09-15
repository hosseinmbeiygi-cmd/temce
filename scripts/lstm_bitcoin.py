#!/usr/bin/env python
"""
مدل LSTM برای پیش‌بینی قیمت بیتکوین.

بر اساس مقاله: «تحلیل عوامل موثر در قیمت ارزهای مجازی»
ابوالحسنی و صمدی (۱۳۹۹)

متغیرهای ورودی:
  - قیمت بیتکوین
  - قیمت جهانی طلا
  - شاخص S&P 500
  - شاخص دلار (DXY)
  - حجم معاملات
  - ویژگی‌های تکنیکال (RSI, MACD, Bollinger, ...)

Usage:
    python scripts/lstm_bitcoin.py --fetch
    python scripts/lstm_bitcoin.py --input data.csv
    python scripts/lstm_bitcoin.py --fetch --epochs 200 --predict-days 30
    python scripts/lstm_bitcoin.py --fetch --compare
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

OUTPUT_DIR = _project_root / "exchange_rate_data" / "bitcoin_lstm"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
#  بخش ۱: جمع‌آوری داده
# ═══════════════════════════════════════════════════════════════


def fetch_bitcoin_data() -> pd.DataFrame:
    """دانلود داده‌های روزانه بیتکوین از Yahoo Finance."""
    import requests

    print("\n  [Yahoo] دریافت داده‌های بیتکوین (BTC-USD)...")
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD"
        params = {"period1": 1262304000, "period2": int(time.time()), "interval": "1d"}
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        quotes = result["indicators"]["quote"][0]
        df = pd.DataFrame(
            {
                "date": [pd.Timestamp(t, unit="s").date() for t in timestamps],
                "price": quotes["close"],
                "volume": quotes["volume"],
            }
        )
        df = df.dropna()
        print(f"    ✓ {len(df)} رکورد")
        return df.sort_values("date").reset_index(drop=True)
    except Exception as e:
        print(f"    ✗ خطا: {e}")
        return pd.DataFrame()


def fetch_yahoo(ticker: str, col_name: str) -> pd.DataFrame:
    """دانلود داده از Yahoo Finance."""
    import requests

    print(f"  [Yahoo] {ticker}...")
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        params = {"period1": 1262304000, "period2": int(time.time()), "interval": "1d"}
        resp = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        resp.raise_for_status()
        r = resp.json()["chart"]["result"][0]
        df = pd.DataFrame(
            {
                "date": [pd.Timestamp(t, unit="s").date() for t in r["timestamp"]],
                col_name: r["indicators"]["quote"][0]["close"],
            }
        )
        print(f"    ✓ {len(df)} رکورد")
        return df
    except Exception as e:
        print(f"    ✗ خطا: {e}")
        return pd.DataFrame()


def fetch_all() -> pd.DataFrame:
    """دریافت تمام داده‌ها."""
    print("\n" + "═" * 70)
    print("  جمع‌آوری داده‌ها")
    print("═" * 70)

    btc = fetch_bitcoin_data()
    if btc.empty:
        print("\n  ✗ داده بیتکوین دریافت نشد")
        return pd.DataFrame()

    gold = fetch_yahoo("GC=F", "gold")
    sp500 = fetch_yahoo("^GSPC", "sp500")
    dxy = fetch_yahoo("DX-Y.NYB", "dxy")

    df = btc.copy()
    for other in [gold, sp500, dxy]:
        if not other.empty and "date" in other.columns and "date" in df.columns:
            df = pd.merge(df, other, on="date", how="left")

    df = df.ffill().dropna()
    print(f"\n  ✓ نهایی: {len(df)} ردیف")
    return df


# ═══════════════════════════════════════════════════════════════
#  بخش ۲: ویژگی‌سازی
# ═══════════════════════════════════════════════════════════════


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """افزودن ویژگی‌های تکنیکال و لگاریتمی."""
    r = df.copy()
    p = r["price"]

    # لگاریتمی
    r["log_price"] = np.log(p)
    for c in ["gold", "sp500", "dxy", "volume"]:
        if c in r.columns:
            r[f"log_{c}"] = np.log(r[c] + 1)

    # میانگین متحرک
    for w in [7, 14, 21, 50]:
        r[f"sma_{w}"] = p.rolling(w, min_periods=1).mean()
    for s in [12, 26]:
        r[f"ema_{s}"] = p.ewm(span=s, adjust=False).mean()

    # RSI
    delta = p.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14, min_periods=1).mean()
    r["rsi_14"] = 100 - (100 / (1 + gain / (loss + 1e-10)))

    # MACD
    e12 = p.ewm(span=12, adjust=False).mean()
    e26 = p.ewm(span=26, adjust=False).mean()
    r["macd"] = e12 - e26
    r["macd_signal"] = r["macd"].ewm(span=9, adjust=False).mean()
    r["macd_hist"] = r["macd"] - r["macd_signal"]

    # Bollinger Bands
    sma20 = p.rolling(20, min_periods=1).mean()
    std20 = p.rolling(20, min_periods=1).std().fillna(0)
    r["bb_upper"] = sma20 + 2 * std20
    r["bb_lower"] = sma20 - 2 * std20
    r["bb_width"] = (r["bb_upper"] - r["bb_lower"]) / (sma20 + 1e-10)

    # بازده و نوسانات
    r["return_1d"] = p.pct_change(1)
    r["return_3d"] = p.pct_change(3)
    r["return_7d"] = p.pct_change(7)
    r["volatility_7"] = p.pct_change().rolling(7, min_periods=1).std()
    r["volatility_14"] = p.pct_change().rolling(14, min_periods=1).std()

    return r.dropna()


# ═══════════════════════════════════════════════════════════════
#  بخش ۳: آماده‌سازی داده
# ═══════════════════════════════════════════════════════════════


class Scaler:
    def __init__(self) -> None:
        self.min_: np.ndarray | None = None
        self.max_: np.ndarray | None = None

    def fit_transform(self, x: np.ndarray) -> np.ndarray:
        self.min_ = x.min(axis=0)
        self.max_ = x.max(axis=0)
        return self.transform(x)

    def transform(self, x: np.ndarray) -> np.ndarray:
        rng = self.max_ - self.min_
        rng[rng == 0] = 1.0
        return (x - self.min_) / rng

    def inverse(self, x: np.ndarray) -> np.ndarray:
        rng = self.max_ - self.min_
        rng[rng == 0] = 1.0
        return x * rng + self.min_


def prepare_data(
    df: pd.DataFrame, target: str, features: list[str], seq_len: int = 30, train_ratio: float = 0.8
) -> dict:
    """آماده‌سازی داده برای LSTM."""
    cols = [target] + [c for c in features if c in df.columns]
    clean = df[cols].dropna().reset_index(drop=True)
    feat_cols = [c for c in features if c in clean.columns]

    X_raw = clean[feat_cols].values
    y_raw = clean[target].values

    f_scaler, t_scaler = Scaler(), Scaler()
    X_scaled = f_scaler.fit_transform(X_raw)
    y_scaled = t_scaler.fit_transform(y_raw.reshape(-1, 1)).flatten()

    # ساخت دنباله‌ها
    X, y = [], []
    for i in range(len(X_scaled) - seq_len):
        X.append(X_scaled[i : i + seq_len])
        y.append(y_scaled[i + seq_len])
    X, y = np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)

    split = int(len(X) * train_ratio)
    return {
        "X_train": X[:split],
        "X_test": X[split:],
        "y_train": y[:split],
        "y_test": y[split:],
        "f_scaler": f_scaler,
        "t_scaler": t_scaler,
        "n_features": X_scaled.shape[1],
        "feature_names": feat_cols,
    }


# ═══════════════════════════════════════════════════════════════
#  بخش ۴: مدل‌ها
# ═══════════════════════════════════════════════════════════════


class LSTMModel:
    name = "LSTM"

    def __init__(self, n_feat: int, hidden: int = 64, layers: int = 2, drop: float = 0.2):
        import torch
        import torch.nn as nn

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        class Net(nn.Module):
            def __init__(self_inner):
                super().__init__()
                self_inner.lstm = nn.LSTM(n_feat, hidden, layers, batch_first=True, dropout=drop if layers > 1 else 0.0)
                self_inner.drop = nn.Dropout(drop)
                self_inner.fc = nn.Sequential(nn.Linear(hidden, hidden // 2), nn.ReLU(), nn.Linear(hidden // 2, 1))

            def forward(self_inner, x):
                out, _ = self_inner.lstm(x)
                return self_inner.fc(self_inner.drop(out[:, -1, :])).squeeze(-1)

        self.model = Net().to(self.device)
        self.criterion = torch.nn.MSELoss()
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-3)

    def train_step(self, X, y):
        import torch

        self.model.train()
        xb, yb = torch.FloatTensor(X).to(self.device), torch.FloatTensor(y).to(self.device)
        self.optimizer.zero_grad()
        loss = self.criterion(self.model(xb), yb)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()
        return loss.item()

    def predict(self, X):
        import torch

        self.model.eval()
        with torch.no_grad():
            return self.model(torch.FloatTensor(X).to(self.device)).cpu().numpy()


class GRUModel:
    name = "GRU"

    def __init__(self, n_feat: int, hidden: int = 64, layers: int = 2, drop: float = 0.2):
        import torch
        import torch.nn as nn

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        class Net(nn.Module):
            def __init__(self_inner):
                super().__init__()
                self_inner.gru = nn.GRU(n_feat, hidden, layers, batch_first=True, dropout=drop if layers > 1 else 0.0)
                self_inner.drop = nn.Dropout(drop)
                self_inner.fc = nn.Sequential(nn.Linear(hidden, hidden // 2), nn.ReLU(), nn.Linear(hidden // 2, 1))

            def forward(self_inner, x):
                out, _ = self_inner.gru(x)
                return self_inner.fc(self_inner.drop(out[:, -1, :])).squeeze(-1)

        self.model = Net().to(self.device)
        self.criterion = torch.nn.MSELoss()
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-3)

    def train_step(self, X, y):
        import torch

        self.model.train()
        xb, yb = torch.FloatTensor(X).to(self.device), torch.FloatTensor(y).to(self.device)
        self.optimizer.zero_grad()
        loss = self.criterion(self.model(xb), yb)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()
        return loss.item()

    def predict(self, X):
        import torch

        self.model.eval()
        with torch.no_grad():
            return self.model(torch.FloatTensor(X).to(self.device)).cpu().numpy()


class TransformerModel:
    name = "Transformer"

    def __init__(self, n_feat: int, hidden: int = 64, heads: int = 4, layers: int = 2, drop: float = 0.1):
        import torch
        import torch.nn as nn

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        class PosEnc(nn.Module):
            def __init__(self_inner, d, mx=500):
                super().__init__()
                pe = torch.zeros(mx, d)
                pos = torch.arange(0, mx).unsqueeze(1).float()
                div = torch.exp(torch.arange(0, d, 2).float() * -(np.log(10000) / d))
                pe[:, 0::2] = torch.sin(pos * div)
                pe[:, 1::2] = torch.cos(pos * div)
                self_inner.register_buffer("pe", pe.unsqueeze(0))

            def forward(self_inner, x):
                return x + self_inner.pe[:, : x.size(1), :]

        class Net(nn.Module):
            def __init__(self_inner):
                super().__init__()
                self_inner.proj = nn.Linear(n_feat, hidden)
                self_inner.pos = PosEnc(hidden)
                enc_layer = nn.TransformerEncoderLayer(
                    d_model=hidden, nhead=heads, dim_feedforward=hidden * 4, dropout=drop, batch_first=True
                )
                self_inner.transformer = nn.TransformerEncoder(enc_layer, num_layers=layers)
                self_inner.fc = nn.Sequential(
                    nn.Linear(hidden, hidden // 2), nn.ReLU(), nn.Dropout(drop), nn.Linear(hidden // 2, 1)
                )

            def forward(self_inner, x):
                x = self_inner.pos(self_inner.proj(x))
                return self_inner.fc(self_inner.transformer(x)[:, -1, :]).squeeze(-1)

        self.model = Net().to(self.device)
        self.criterion = torch.nn.MSELoss()
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-4)

    def train_step(self, X, y):
        import torch

        self.model.train()
        xb, yb = torch.FloatTensor(X).to(self.device), torch.FloatTensor(y).to(self.device)
        self.optimizer.zero_grad()
        loss = self.criterion(self.model(xb), yb)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()
        return loss.item()

    def predict(self, X):
        import torch

        self.model.eval()
        with torch.no_grad():
            return self.model(torch.FloatTensor(X).to(self.device)).cpu().numpy()


# ═══════════════════════════════════════════════════════════════
#  بخش ۵: آموزش و ارزیابی
# ═══════════════════════════════════════════════════════════════


def train_model(model, X_tr, y_tr, X_val, y_val, epochs=100, batch=32, patience=15, verbose=True):
    """آموزش با Early Stopping."""
    import torch

    best_val = float("inf")
    best_state = None
    counter = 0
    best_epoch = 0

    X_val_t = torch.FloatTensor(X_val).to(model.device)
    y_val_t = torch.FloatTensor(y_val).to(model.device)
    n = len(X_tr)

    for epoch in range(1, epochs + 1):
        idx = np.random.permutation(n)
        epoch_loss = 0.0
        nb = 0
        model.model.train()
        for s in range(0, n, batch):
            i = idx[s : s + batch]
            epoch_loss += model.train_step(X_tr[i], y_tr[i])
            nb += 1
        train_loss = epoch_loss / max(nb, 1)

        model.model.eval()
        with torch.no_grad():
            val_loss = model.criterion(model.model(X_val_t), y_val_t).item()

        marker = ""
        if val_loss < best_val:
            best_val = val_loss
            best_epoch = epoch
            best_state = {k: v.cpu().clone() for k, v in model.model.state_dict().items()}
            counter = 0
            marker = " ★"
        else:
            counter += 1

        if verbose and (epoch % 25 == 0 or epoch == 1 or marker):
            print(f"    Epoch {epoch:>4d}: train={train_loss:.6f}  val={val_loss:.6f} {marker}")

        if counter >= patience:
            if verbose:
                print(f"\n    Early stop at epoch {epoch}")
            break

    if best_state:
        model.model.load_state_dict(best_state)
        model.model = model.model.to(model.device)

    return {"best_epoch": best_epoch, "best_val_loss": best_val}


def evaluate(y_true, y_pred, name=""):
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    mask = np.abs(y_true) > 1e-10
    mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100) if mask.any() else 0
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1 - ss_res / (ss_tot + 1e-10)
    d_acc = float(np.mean((np.diff(y_true) > 0) == (np.diff(y_pred) > 0)) * 100) if len(y_true) > 1 else 0.0
    return {
        "name": name,
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape": round(mape, 2),
        "r2": round(float(r2), 6),
        "dir_acc": round(d_acc, 2),
    }


def print_eval(m):
    print(
        f"  [{m['name']}] MAE={m['mae']:.2f}  RMSE={m['rmse']:.2f}  "
        f"MAPE={m['mape']:.2f}%  R²={m['r2']:.6f}  DirAcc={m['dir_acc']:.2f}%"
    )


# ═══════════════════════════════════════════════════════════════
#  بخش ۶: مقایسه و Ensemble
# ═══════════════════════════════════════════════════════════════


def compare_models(data, hidden=64, layers=2, epochs=100, batch=32):
    """مقایسه LSTM، GRU، Transformer."""
    n = data["n_features"]
    X_tr, y_tr = data["X_train"], data["y_train"]
    X_te, y_te = data["X_test"], data["y_test"]

    split = int(len(X_tr) * 0.85)
    X_val, y_val = X_tr[split:], y_tr[split:]
    X_tr_f, y_tr_f = X_tr[:split], y_tr[:split]

    configs = [
        ("LSTM", LSTMModel(n, hidden, layers)),
        ("GRU", GRUModel(n, hidden, layers)),
        ("Transformer", TransformerModel(n, hidden)),
    ]

    results = {}
    trained = []

    for name, model in configs:
        print(f"\n  ── {name} ──")
        train_model(model, X_tr_f, y_tr_f, X_val, y_val, epochs, batch)
        preds = model.predict(X_te)
        actual = data["t_scaler"].inverse(y_te.reshape(-1, 1)).flatten()
        pred_actual = data["t_scaler"].inverse(preds.reshape(-1, 1)).flatten()
        metrics = evaluate(actual, pred_actual, name)
        print_eval(metrics)
        results[name] = metrics
        trained.append((name, model, metrics["r2"]))

    # Ensemble
    print("\n  ── Ensemble (وزن بر اساس R²) ──")
    total_w = sum(max(w, 0.01) for _, _, w in trained)
    ens_preds = np.zeros(len(X_te))
    for _name, model, w in trained:
        ens_preds += model.predict(X_te) * (max(w, 0.01) / total_w)
    ens_actual = data["t_scaler"].inverse(y_te.reshape(-1, 1)).flatten()
    ens_pred = data["t_scaler"].inverse(ens_preds.reshape(-1, 1)).flatten()
    ens_m = evaluate(ens_actual, ens_pred, "Ensemble")
    print_eval(ens_m)
    results["Ensemble"] = ens_m

    return results, trained


# ═══════════════════════════════════════════════════════════════
#  بخش ۷: پیش‌بینی آینده
# ═══════════════════════════════════════════════════════════════


def forecast(model, last_seq, t_scaler, n_days=30):
    """پیش‌بینی n روز آینده."""
    import torch

    model.model.eval()
    current = last_seq.copy()
    preds = []

    for d in range(1, n_days + 1):
        x = torch.FloatTensor(current).unsqueeze(0).to(model.device)
        with torch.no_grad():
            p = model.model(x).cpu().numpy()[0]
        val = t_scaler.inverse([[p]])[0, 0]
        preds.append({"day": d, "price": round(float(val), 2)})
        # به‌روزرسانی ساده
        new_row = current[-1].copy()
        new_row[0] = p
        current = np.vstack([current[1:], new_row.reshape(1, -1)])

    return preds


# ═══════════════════════════════════════════════════════════════
#  بخش ۸: CLI
# ═══════════════════════════════════════════════════════════════


def parse_args():
    p = argparse.ArgumentParser(description="LSTM پیش‌بینی قیمت بیتکوین")
    p.add_argument("--input", "-i", type=str, default=None, help="فایل CSV")
    p.add_argument("--fetch", action="store_true", help="دانلود داده")
    p.add_argument("--target", type=str, default="price", help="متغیر هدف")
    p.add_argument("--seq-length", type=int, default=30, help="طول دنباله")
    p.add_argument("--hidden", type=int, default=64, help="لایه پنهان")
    p.add_argument("--layers", type=int, default=2, help="تعداد لایه‌ها")
    p.add_argument("--epochs", type=int, default=100, help="Epoch")
    p.add_argument("--batch-size", type=int, default=32, help="Batch")
    p.add_argument("--patience", type=int, default=15, help="Early Stop")
    p.add_argument("--predict-days", type=int, default=0, help="پیش‌بینی آینده")
    p.add_argument("--compare", action="store_true", help="مقایسه مدل‌ها")
    p.add_argument("--model", choices=["lstm", "gru", "transformer"], default="lstm")
    p.add_argument("--save", type=str, default=None, help="ذخیره داده")
    return p.parse_args()


# ═══════════════════════════════════════════════════════════════
#  بخش ۹: اجرا
# ═══════════════════════════════════════════════════════════════


def main():
    args = parse_args()

    print("=" * 70)
    print("  LSTM پیش‌بینی قیمت بیتکوین")
    print("=" * 70)

    # ── داده ──
    if args.fetch or args.input is None:
        df = fetch_all()
    else:
        df = pd.read_csv(args.input, encoding="utf-8-sig")
        print(f"\n  ✓ {len(df)} ردیف")

    if df.empty:
        print("  ✗ داده‌ای موجود نیست")
        sys.exit(1)

    if args.save:
        df.to_csv(args.save, index=False)
        print(f"  💾 ذخیره: {args.save}")

    # ── ویژگی‌سازی ──
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
        "return_1d",
        "return_3d",
        "volatility_7",
    ]
    features = [c for c in features if c in df.columns]
    print(f"\n  ✓ {len(features)} ویژگی")

    # ── آماده‌سازی ──
    data = prepare_data(df, args.target, features, seq_len=args.seq_length)
    print(f"  ✓ Train={len(data['X_train'])} Test={len(data['X_test'])}")

    # ── مقایسه یا تکی ──
    if args.compare:
        results, trained = compare_models(data, args.hidden, args.layers, args.epochs, args.batch_size)
        out_path = OUTPUT_DIR / "model_comparison.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n  {'─' * 65}")
        print(f"  {'مدل':>12s}  {'MAE':>10s}  {'RMSE':>10s}  {'MAPE':>8s}  {'R²':>10s}  {'Dir%':>8s}")
        print(f"  {'─' * 65}")
        for name, m in results.items():
            print(
                f"  {name:>12s}  {m['mae']:>10.2f}  {m['rmse']:>10.2f}  "
                f"{m['mape']:>7.2f}%  {m['r2']:>10.6f}  {m['dir_acc']:>7.2f}%"
            )
        print(f"  {'─' * 65}")

        # ذخیره بهترین مدل
        best_name = max(results.items(), key=lambda x: x[1]["r2"])[0]
        best_model = dict(trained)[best_name]
        import torch

        torch.save(best_model.model.state_dict(), OUTPUT_DIR / "best_model.pt")
        print(f"\n  💾 بهترین مدل: {best_name}")
    else:
        n = data["n_features"]
        model_map = {
            "lstm": lambda: LSTMModel(n, args.hidden, args.layers),
            "gru": lambda: GRUModel(n, args.hidden, args.layers),
            "transformer": lambda: TransformerModel(n, args.hidden),
        }
        model = model_map[args.model]()

        split = int(len(data["X_train"]) * 0.85)
        print(f"\n  ── {args.model.upper()} ──")
        train_model(
            model,
            data["X_train"][:split],
            data["y_train"][:split],
            data["X_train"][split:],
            data["y_train"][split:],
            args.epochs,
            args.batch_size,
            args.patience,
        )

        preds = model.predict(data["X_test"])
        actual = data["t_scaler"].inverse(data["y_test"].reshape(-1, 1)).flatten()
        pred_actual = data["t_scaler"].inverse(preds.reshape(-1, 1)).flatten()
        metrics = evaluate(actual, pred_actual, args.model.upper())
        print_eval(metrics)

        # ذخیره
        import torch

        torch.save(model.model.state_dict(), OUTPUT_DIR / f"{args.model}_model.pt")
        print("  💾 مدل ذخیره شد")

        trained = [(args.model.upper(), model, metrics["r2"])]

    # ── پیش‌بینی آینده ──
    if args.predict_days > 0 and trained:
        print(f"\n  ── پیش‌بینی {args.predict_days} روز آینده ──")
        best_m = trained[-1][1]
        last_seq = data["X_test"][-1:]
        forecasts = forecast(best_m, last_seq[0], data["t_scaler"], args.predict_days)

        print(f"    {'روز':>6s}  {'قیمت پیش‌بینی':>15s}")
        print(f"    {'─' * 25}")
        for f in forecasts:
            print(f"    {f['day']:>6d}  ${f['price']:>14,.2f}")

        with open(OUTPUT_DIR / "forecast.json", "w") as fp:
            json.dump(forecasts, fp, indent=2)
        print(f"\n  💾 پیش‌بینی: {OUTPUT_DIR / 'forecast.json'}")

    print("\n" + "=" * 70)
    print("  ✅ تمام شد!")
    print("=" * 70)


if __name__ == "__main__":
    main()
