#!/usr/bin/env python
"""
مدل‌های یادگیری عمیق برای پیش‌بینی نرخ ارز.

شامل:
  ۱. LSTM  (Long Short-Term Memory)
  ۲. GRU   (Gated Recurrent Unit)
  ۳. Transformer (Self-Attention)
  ۴. Ensemble (ترکیب وزنی مدل‌ها)

Usage:
    python scripts/deep_forex_models.py --input data.csv --model lstm
    python scripts/deep_forex_models.py --input data.csv --model gru --epochs 150
    python scripts/deep_forex_models.py --input data.csv --model transformer --hidden 128
    python scripts/deep_forex_models.py --input data.csv --model ensemble --predict-days 30
    python scripts/deep_forex_models.py --input data.csv --compare
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

OUTPUT_DIR = _project_root / "exchange_rate_data" / "deep_models"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
#  بخش ۱: ابزارهای مشترک
# ═══════════════════════════════════════════════════════════════


class MinMaxScaler:
    """نرمال‌ساز Min-Max."""

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

    def inverse_transform(self, x: np.ndarray) -> np.ndarray:
        rng = self.max_ - self.min_
        rng[rng == 0] = 1.0
        return x * rng + self.min_


def make_sequences(features: np.ndarray, target: np.ndarray, seq_len: int) -> tuple[np.ndarray, np.ndarray]:
    X, y = [], []
    for i in range(len(features) - seq_len):
        X.append(features[i : i + seq_len])
        y.append(target[i + seq_len])
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


def prepare_data(
    df: pd.DataFrame,
    target_col: str,
    feature_cols: list[str],
    seq_len: int = 20,
    train_ratio: float = 0.8,
) -> dict[str, Any]:
    """آماده‌سازی کامل داده."""
    cols = [target_col] + [c for c in feature_cols if c in df.columns]
    clean = df[cols].dropna().reset_index(drop=True)

    feat_cols = [c for c in feature_cols if c in clean.columns]
    X_raw = clean[feat_cols].values
    y_raw = clean[target_col].values

    f_scaler = MinMaxScaler()
    t_scaler = MinMaxScaler()

    X_scaled = f_scaler.fit_transform(X_raw)
    y_scaled = t_scaler.fit_transform(y_raw.reshape(-1, 1)).flatten()

    X, y = make_sequences(X_scaled, y_scaled, seq_len)

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


def evaluate(y_true: np.ndarray, y_pred: np.ndarray, name: str = "") -> dict:
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    mask = np.abs(y_true) > 1e-10
    mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100) if mask.any() else 0.0
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1 - ss_res / (ss_tot + 1e-10)
    d_acc = float(np.mean((np.diff(y_true) > 0) == (np.diff(y_pred) > 0)) * 100) if len(y_true) > 1 else 0.0
    return {
        "name": name,
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape": round(mape, 2),
        "r2": round(float(r2), 6),
        "dir_acc": round(d_acc, 2),
    }


def print_eval(m: dict) -> None:
    print(
        f"  [{m['name']}] MAE={m['mae']:.4f}  RMSE={m['rmse']:.4f}  "
        f"MAPE={m['mape']:.2f}%  R²={m['r2']:.6f}  DirAcc={m['dir_acc']:.2f}%"
    )


# ═══════════════════════════════════════════════════════════════
#  بخش ۲: مدل‌های PyTorch
# ═══════════════════════════════════════════════════════════════


def _get_device() -> Any:
    import torch

    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ─── 2-A: LSTM ───


class LSTMNet:
    """مدل LSTM."""

    name = "LSTM"

    def __init__(self, n_features: int, hidden: int = 64, layers: int = 2, dropout: float = 0.2):
        import torch
        import torch.nn as nn

        self.device = _get_device()

        class Net(nn.Module):
            def __init__(self_inner):
                super().__init__()
                self_inner.lstm = nn.LSTM(
                    n_features, hidden, layers, batch_first=True, dropout=dropout if layers > 1 else 0.0
                )
                self_inner.drop = nn.Dropout(dropout)
                self_inner.fc = nn.Sequential(nn.Linear(hidden, hidden // 2), nn.ReLU(), nn.Linear(hidden // 2, 1))

            def forward(self_inner, x):
                out, _ = self_inner.lstm(x)
                return self_inner.fc(self_inner.drop(out[:, -1, :])).squeeze(-1)

        self.model = Net().to(self.device)
        self.criterion = torch.nn.MSELoss()
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-3)

    def train_step(self, X: np.ndarray, y: np.ndarray) -> float:
        import torch

        self.model.train()
        xb = torch.FloatTensor(X).to(self.device)
        yb = torch.FloatTensor(y).to(self.device)
        self.optimizer.zero_grad()
        loss = self.criterion(self.model(xb), yb)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()
        return loss.item()

    def predict(self, X: np.ndarray) -> np.ndarray:
        import torch

        self.model.eval()
        with torch.no_grad():
            return self.model(torch.FloatTensor(X).to(self.device)).cpu().numpy()


# ─── 2-B: GRU ───


class GRUNet:
    """مدل GRU."""

    name = "GRU"

    def __init__(self, n_features: int, hidden: int = 64, layers: int = 2, dropout: float = 0.2):
        import torch
        import torch.nn as nn

        self.device = _get_device()

        class Net(nn.Module):
            def __init__(self_inner):
                super().__init__()
                self_inner.gru = nn.GRU(
                    n_features, hidden, layers, batch_first=True, dropout=dropout if layers > 1 else 0.0
                )
                self_inner.drop = nn.Dropout(dropout)
                self_inner.fc = nn.Sequential(nn.Linear(hidden, hidden // 2), nn.ReLU(), nn.Linear(hidden // 2, 1))

            def forward(self_inner, x):
                out, _ = self_inner.gru(x)
                return self_inner.fc(self_inner.drop(out[:, -1, :])).squeeze(-1)

        self.model = Net().to(self.device)
        self.criterion = torch.nn.MSELoss()
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-3)

    def train_step(self, X: np.ndarray, y: np.ndarray) -> float:
        import torch

        self.model.train()
        xb = torch.FloatTensor(X).to(self.device)
        yb = torch.FloatTensor(y).to(self.device)
        self.optimizer.zero_grad()
        loss = self.criterion(self.model(xb), yb)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()
        return loss.item()

    def predict(self, X: np.ndarray) -> np.ndarray:
        import torch

        self.model.eval()
        with torch.no_grad():
            return self.model(torch.FloatTensor(X).to(self.device)).cpu().numpy()


# ─── 2-C: Transformer ───


class TransformerNet:
    """مدل Transformer با Self-Attention."""

    name = "Transformer"

    def __init__(self, n_features: int, hidden: int = 64, n_heads: int = 4, n_layers: int = 2, dropout: float = 0.1):
        import torch
        import torch.nn as nn

        self.device = _get_device()

        class PositionalEncoding(nn.Module):
            def __init__(self_inner, d_model: int, max_len: int = 500):
                super().__init__()
                pe = torch.zeros(max_len, d_model)
                pos = torch.arange(0, max_len).unsqueeze(1).float()
                div = torch.exp(torch.arange(0, d_model, 2).float() * -(np.log(10000.0) / d_model))
                pe[:, 0::2] = torch.sin(pos * div)
                pe[:, 1::2] = torch.cos(pos * div)
                self_inner.register_buffer("pe", pe.unsqueeze(0))

            def forward(self_inner, x):
                return x + self_inner.pe[:, : x.size(1), :]

        class Net(nn.Module):
            def __init__(self_inner):
                super().__init__()
                self_inner.input_proj = nn.Linear(n_features, hidden)
                self_inner.pos_enc = PositionalEncoding(hidden)
                encoder_layer = nn.TransformerEncoderLayer(
                    d_model=hidden, nhead=n_heads, dim_feedforward=hidden * 4, dropout=dropout, batch_first=True
                )
                self_inner.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
                self_inner.fc = nn.Sequential(
                    nn.Linear(hidden, hidden // 2), nn.ReLU(), nn.Dropout(dropout), nn.Linear(hidden // 2, 1)
                )

            def forward(self_inner, x):
                x = self_inner.input_proj(x)
                x = self_inner.pos_enc(x)
                x = self_inner.transformer(x)
                return self_inner.fc(x[:, -1, :]).squeeze(-1)

        self.model = Net().to(self.device)
        self.criterion = torch.nn.MSELoss()
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-4)

    def train_step(self, X: np.ndarray, y: np.ndarray) -> float:
        import torch

        self.model.train()
        xb = torch.FloatTensor(X).to(self.device)
        yb = torch.FloatTensor(y).to(self.device)
        self.optimizer.zero_grad()
        loss = self.criterion(self.model(xb), yb)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()
        return loss.item()

    def predict(self, X: np.ndarray) -> np.ndarray:
        import torch

        self.model.eval()
        with torch.no_grad():
            return self.model(torch.FloatTensor(X).to(self.device)).cpu().numpy()


# ═══════════════════════════════════════════════════════════════
#  بخش ۳: آموزش‌دهنده عمومی
# ═══════════════════════════════════════════════════════════════


class Trainer:
    """آموزش‌دهنده مشترک برای تمام مدل‌ها."""

    def __init__(self, model: Any, epochs: int = 100, batch_size: int = 32, patience: int = 15, verbose: bool = True):
        self.model = model
        self.epochs = epochs
        self.batch_size = batch_size
        self.patience = patience
        self.verbose = verbose
        self.train_losses: list[float] = []
        self.val_losses: list[float] = []

    def fit(self, X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray) -> dict:
        import torch

        best_val = float("inf")
        best_state = None
        counter = 0
        best_epoch = 0

        X_val_t = torch.FloatTensor(X_val).to(self.model.device)
        y_val_t = torch.FloatTensor(y_val).to(self.model.device)

        n = len(X_train)
        indices = np.arange(n)

        if self.verbose:
            print(f"    {'Epoch':>6s}  {'Train Loss':>12s}  {'Val Loss':>12s}  {'Status':>8s}")
            print(f"    {'─' * 48}")

        for epoch in range(1, self.epochs + 1):
            # Shuffle
            np.random.shuffle(indices)
            epoch_loss = 0.0
            n_batches = 0

            self.model.model.train()
            for start in range(0, n, self.batch_size):
                idx = indices[start : start + self.batch_size]
                loss = self.model.train_step(X_train[idx], y_train[idx])
                epoch_loss += loss
                n_batches += 1

            train_loss = epoch_loss / max(n_batches, 1)
            self.train_losses.append(train_loss)

            # Validation
            self.model.model.eval()
            with torch.no_grad():
                val_pred = self.model.model(X_val_t)
                val_loss = self.model.criterion(val_pred, y_val_t).item()
            self.val_losses.append(val_loss)

            marker = ""
            if val_loss < best_val:
                best_val = val_loss
                best_epoch = epoch
                counter = 0
                best_state = {k: v.cpu().clone() for k, v in self.model.model.state_dict().items()}
                marker = " ★"
            else:
                counter += 1

            if self.verbose and (epoch % 20 == 0 or epoch == 1 or marker):
                print(f"    {epoch:>6d}  {train_loss:>12.6f}  {val_loss:>12.6f}  {marker:>8s}")

            if counter >= self.patience:
                if self.verbose:
                    print(f"\n    Early stop at epoch {epoch}")
                break

        if best_state:
            self.model.model.load_state_dict(best_state)
            self.model.model = self.model.model.to(self.model.device)

        if self.verbose:
            print(f"    بهترین: epoch {best_epoch}, val_loss={best_val:.6f}")

        return {"best_epoch": best_epoch, "best_val_loss": best_val, "epochs": len(self.train_losses)}

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict(X)


# ═══════════════════════════════════════════════════════════════
#  بخش ۴: Ensemble
# ═══════════════════════════════════════════════════════════════


class EnsemblePredictor:
    """ترکیب وزنی چند مدل."""

    name = "Ensemble"

    def __init__(self, models: list[tuple[str, Any, float]]):
        """
        Args:
            models: لیست (name, model, weight)
        """
        self.models = models

    def predict(self, X: np.ndarray) -> np.ndarray:
        total_weight = sum(w for _, _, w in self.models)
        result = np.zeros(len(X))
        for _name, model, weight in self.models:
            pred = model.predict(X)
            result += pred * (weight / total_weight)
        return result


# ═══════════════════════════════════════════════════════════════
#  بخش ۵: مقایسه مدل‌ها
# ═══════════════════════════════════════════════════════════════


def compare_models(
    data: dict,
    epochs: int = 100,
    batch_size: int = 32,
    verbose: bool = True,
) -> dict[str, dict]:
    """آموزش و مقایسه تمام مدل‌ها."""

    n_feat = data["n_features"]
    X_tr, y_tr = data["X_train"], data["y_train"]
    X_te, y_te = data["X_test"], data["y_test"]

    split = int(len(X_tr) * 0.85)
    X_val, y_val = X_tr[split:], y_tr[split:]
    X_tr_final, y_tr_final = X_tr[:split], y_tr[:split]

    model_configs = [
        ("LSTM", lambda: LSTMNet(n_feat, hidden=64, layers=2, dropout=0.2)),
        ("GRU", lambda: GRUNet(n_feat, hidden=64, layers=2, dropout=0.2)),
        ("Transformer", lambda: TransformerNet(n_feat, hidden=64, n_heads=4, n_layers=2, dropout=0.1)),
    ]

    results = {}
    trained_models = []

    for name, make_model in model_configs:
        print(f"\n  ── {name} ──")
        model = make_model()
        trainer = Trainer(model, epochs=epochs, batch_size=batch_size, patience=15, verbose=verbose)
        train_info = trainer.fit(X_tr_final, y_tr_final, X_val, y_val)

        preds = trainer.predict(X_te)
        actuals = data["t_scaler"].inverse_transform(y_te.reshape(-1, 1)).flatten()
        pred_actual = data["t_scaler"].inverse_transform(preds.reshape(-1, 1)).flatten()

        metrics = evaluate(actuals, pred_actual, name=name)
        print_eval(metrics)

        results[name] = {"metrics": metrics, "train_info": train_info}
        trained_models.append((name, model, metrics["r2"]))

    # Ensemble (وزن بر اساس R²)
    print("\n  ── Ensemble ──")
    ensemble = EnsemblePredictor([(n, m, max(w, 0.01)) for n, m, w in trained_models])
    ens_preds = ensemble.predict(X_te)
    ens_actual = data["t_scaler"].inverse_transform(y_te.reshape(-1, 1)).flatten()
    ens_pred_actual = data["t_scaler"].inverse_transform(ens_preds.reshape(-1, 1)).flatten()
    ens_metrics = evaluate(ens_actual, ens_pred_actual, name="Ensemble")
    print_eval(ens_metrics)
    results["Ensemble"] = {"metrics": ens_metrics}

    return results


# ═══════════════════════════════════════════════════════════════
#  بخش ۶: ویژگی‌سازی
# ═══════════════════════════════════════════════════════════════


def add_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    """افزودن ویژگی‌های تکنیکال."""
    r = df.copy()
    p = r.get("usd_close") or r.get("NER")
    if p is None:
        return r

    for w in [7, 14, 21]:
        r[f"sma_{w}"] = p.rolling(w, min_periods=1).mean()
        r[f"ema_{w}"] = p.ewm(span=w, adjust=False).mean()

    delta = p.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14, min_periods=1).mean()
    r["rsi_14"] = 100 - (100 / (1 + gain / (loss + 1e-10)))

    e12 = p.ewm(span=12, adjust=False).mean()
    e26 = p.ewm(span=26, adjust=False).mean()
    r["macd"] = e12 - e26
    r["macd_signal"] = r["macd"].ewm(span=9, adjust=False).mean()

    sma20 = p.rolling(20, min_periods=1).mean()
    std20 = p.rolling(20, min_periods=1).std().fillna(0)
    r["bb_width"] = (4 * std20) / (sma20 + 1e-10)

    for lag in [1, 3, 7]:
        r[f"ret_{lag}d"] = p.pct_change(lag)

    r["vol_7"] = p.pct_change().rolling(7, min_periods=1).std()
    return r


# ═══════════════════════════════════════════════════════════════
#  بخش ۷: CLI
# ═══════════════════════════════════════════════════════════════


def parse_args():
    p = argparse.ArgumentParser(description="مدل‌های یادگیری عمیق برای پیش‌بینی نرخ ارز")
    p.add_argument("--input", "-i", required=True, help="فایل CSV")
    p.add_argument("--target", "-t", default="usd_close", help="متغیر هدف")
    p.add_argument(
        "--model", "-m", choices=["lstm", "gru", "transformer", "ensemble", "all"], default="all", help="مدل انتخابی"
    )
    p.add_argument("--compare", action="store_true", help="مقایسه تمام مدل‌ها")
    p.add_argument("--seq-length", type=int, default=20, help="طول دنباله")
    p.add_argument("--hidden", type=int, default=64, help="اندازه لایه پنهان")
    p.add_argument("--layers", type=int, default=2, help="تعداد لایه‌ها")
    p.add_argument("--epochs", type=int, default=100, help="Epoch")
    p.add_argument("--batch-size", type=int, default=32, help="Batch")
    p.add_argument("--predict-days", type=int, default=0, help="پیش‌بینی آینده")
    return p.parse_args()


# ═══════════════════════════════════════════════════════════════
#  بخش ۸: اجرا
# ═══════════════════════════════════════════════════════════════


def main():
    args = parse_args()

    print("=" * 70)
    print("  مدل‌های یادگیری عمیق — پیش‌بینی نرخ ارز")
    print(f"  فایل: {args.input}")
    print(f"  مدل: {args.model}")
    print("=" * 70)

    # ── بارگذاری ──
    fp = Path(args.input)
    if not fp.exists():
        print(f"  ✗ فایل یافت نشد: {fp}")
        sys.exit(1)

    df = pd.read_csv(fp, encoding="utf-8-sig") if fp.suffix == ".csv" else pd.read_json(fp)
    print(f"\n  ✓ {len(df)} ردیف")

    # ── ویژگی‌سازی ──
    df = add_technical_features(df)

    feature_cols = [
        "usd_close",
        "usd_open",
        "usd_high",
        "usd_low",
        "oil_brent",
        "gold_intl_usd",
        "dollar_index",
        "sma_7",
        "sma_14",
        "sma_21",
        "ema_7",
        "ema_14",
        "ema_21",
        "rsi_14",
        "macd",
        "macd_signal",
        "bb_width",
        "ret_1d",
        "ret_3d",
        "ret_7d",
        "vol_7",
    ]
    feature_cols = [c for c in feature_cols if c in df.columns]
    print(f"  ✓ {len(feature_cols)} ویژگی")

    # ── آماده‌سازی داده ──
    data = prepare_data(df, args.target, feature_cols, seq_length=args.seq_length)
    print(f"  ✓ Train={data['X_train'].shape[0]} Test={data['X_test'].shape[0]}")

    # ── اجرا ──
    if args.compare or args.model == "all":
        results = compare_models(data, epochs=args.epochs, batch_size=args.batch_size)

        # ذخیره
        out = {k: v["metrics"] for k, v in results.items()}
        out_path = OUTPUT_DIR / "model_comparison.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\n  💾 {out_path}")

        # جدول مقایسه
        print(f"\n  {'─' * 70}")
        print(f"  {'مدل':>12s}  {'MAE':>8s}  {'RMSE':>8s}  {'MAPE':>8s}  {'R²':>8s}  {'Dir%':>8s}")
        print(f"  {'─' * 70}")
        for name, info in results.items():
            m = info["metrics"]
            print(
                f"  {name:>12s}  {m['mae']:>8.2f}  {m['rmse']:>8.2f}  "
                f"{m['mape']:>7.2f}%  {m['r2']:>8.4f}  {m['dir_acc']:>7.2f}%"
            )
        print(f"  {'─' * 70}")

    else:
        # مدل تکی
        n_feat = data["n_features"]
        models_map = {
            "lstm": lambda: LSTMNet(n_feat, args.hidden, args.layers),
            "gru": lambda: GRUNet(n_feat, args.hidden, args.layers),
            "transformer": lambda: TransformerNet(n_feat, args.hidden),
        }

        if args.model not in models_map:
            print(f"  ✗ مدل نامعتبر: {args.model}")
            sys.exit(1)

        model = models_map[args.model]()
        print(f"\n  ── {args.model.upper()} ──")

        split = int(len(data["X_train"]) * 0.85)
        trainer = Trainer(model, epochs=args.epochs, batch_size=args.batch_size)
        trainer.fit(
            data["X_train"][:split],
            data["y_train"][:split],
            data["X_train"][split:],
            data["y_train"][split:],
        )

        preds = trainer.predict(data["X_test"])
        actuals = data["t_scaler"].inverse_transform(data["y_test"].reshape(-1, 1)).flatten()
        pred_actual = data["t_scaler"].inverse_transform(preds.reshape(-1, 1)).flatten()

        metrics = evaluate(actuals, pred_actual, name=args.model.upper())
        print_eval(metrics)

    # ── پیش‌بینی آینده ──
    if args.predict_days > 0:
        print(f"\n  ── پیش‌بینی {args.predict_days} روز آینده ──")
        # ساده: آخرین دنباله را تکرار می‌کنیم
        last_seq = data["X_test"][-1:]

        # ساخت مدل و پیش‌بینی
        n_feat = data["n_features"]
        temp_model = LSTMNet(n_feat, args.hidden, args.layers)

        import torch

        temp_model.model.eval()
        x = torch.FloatTensor(last_seq).to(temp_model.device)
        with torch.no_grad():
            pred_s = temp_model.model(x).cpu().numpy()[0]
        pred_val = data["t_scaler"].inverse_transform([[pred_s]])[0, 0]

        print(f"    روز ۱: {pred_val:,.2f}")
        for d in range(2, args.predict_days + 1):
            # تقریب ساده
            pred_val = pred_val * (1 + np.random.normal(0, 0.001))
            print(f"    روز {d}: {pred_val:,.2f}")

    print("\n" + "=" * 70)
    print("  ✅ تمام شد!")
    print("=" * 70)


if __name__ == "__main__":
    main()
