#!/usr/bin/env python
"""
مدل LSTM برای پیش‌بینی نرخ ارز (USD/IRR).

این اسکریپت شامل موارد زیر است:
  ۱. آماده‌سازی داده‌ها (ویژگی‌سازی، نرمال‌سازی، دنباله‌ها)
  ۲. معماری LSTM با PyTorch
  ۳. آموزش مدل با Early Stopping
  ۴. پیش‌بینی و ارزیابی
  ۵. ذخیره/بارگذاری مدل

Usage:
    python scripts/lstm_forex_predictor.py --input exchange_rate_data/merged_daily_all.csv
    python scripts/lstm_forex_predictor.py --input data.csv --epochs 200 --hidden 128
    python scripts/lstm_forex_predictor.py --input data.csv --predict-days 30
    python scripts/lstm_forex_predictor.py --input data.csv --backtest
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

OUTPUT_DIR = _project_root / "exchange_rate_data" / "lstm_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
#  بخش ۱: ویژگی‌سازی (Feature Engineering)
# ═══════════════════════════════════════════════════════════════


def create_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    ساخت ویژگی‌های تکنیکال از قیمت نرخ ارز.
    """
    result = df.copy()
    price_col = "usd_close" if "usd_close" in df.columns else "NER"
    if price_col not in result.columns:
        return result

    p = result[price_col]

    # ── میانگین متحرک ──
    for window in [7, 14, 21, 50]:
        result[f"sma_{window}"] = p.rolling(window=window, min_periods=1).mean()

    # ── میانگین متحرک نمایی ──
    for span in [7, 14, 21]:
        result[f"ema_{span}"] = p.ewm(span=span, adjust=False).mean()

    # ── RSI (14 روزه) ──
    delta = p.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14, min_periods=1).mean()
    rs = gain / (loss + 1e-10)
    result["rsi_14"] = 100 - (100 / (1 + rs))

    # ── MACD ──
    ema12 = p.ewm(span=12, adjust=False).mean()
    ema26 = p.ewm(span=26, adjust=False).mean()
    result["macd"] = ema12 - ema26
    result["macd_signal"] = result["macd"].ewm(span=9, adjust=False).mean()
    result["macd_hist"] = result["macd"] - result["macd_signal"]

    # ── Bollinger Bands ──
    sma20 = p.rolling(20, min_periods=1).mean()
    std20 = p.rolling(20, min_periods=1).std().fillna(0)
    result["bb_upper"] = sma20 + 2 * std20
    result["bb_lower"] = sma20 - 2 * std20
    result["bb_width"] = (result["bb_upper"] - result["bb_lower"]) / (sma20 + 1e-10)

    # ── نرخ تغییر ──
    for lag in [1, 3, 7]:
        result[f"return_{lag}d"] = p.pct_change(lag)

    # ── نوسانات ──
    result["volatility_7"] = p.pct_change().rolling(7, min_periods=1).std()
    result["volatility_14"] = p.pct_change().rolling(14, min_periods=1).std()

    # ── حجم (اگر موجود باشد) ──
    if "volume" in result.columns:
        result["volume_sma_7"] = result["volume"].rolling(7, min_periods=1).mean()
        result["volume_ratio"] = result["volume"] / (result["volume_sma_7"] + 1e-10)

    return result


def create_lag_features(df: pd.DataFrame, target_col: str, lags: list[int]) -> pd.DataFrame:
    """ساخت ویژگی‌های تاخیری."""
    result = df.copy()
    for lag in lags:
        result[f"{target_col}_lag_{lag}"] = result[target_col].shift(lag)
    return result


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    آماده‌سازی نهایی ویژگی‌ها.
    """
    result = df.copy()

    # ── تبدیل تاریخ ──
    if "date" in result.columns:
        result["date"] = pd.to_datetime(result["date"], errors="coerce")
        result = result.sort_values("date").reset_index(drop=True)
        result["day_of_week"] = result["date"].dt.dayofweek
        result["month"] = result["date"].dt.month
        result["quarter"] = result["date"].dt.quarter

    # ── ویژگی‌های تکنیکال ──
    result = create_technical_features(result)

    # ── لگاریتم قیمت ──
    price_col = "usd_close" if "usd_close" in result.columns else "NER"
    if price_col in result.columns:
        result["log_price"] = np.log(result[price_col] + 1)
        result["log_return"] = result["log_price"].diff()

    return result


# ═══════════════════════════════════════════════════════════════
#  بخش ۲: آماده‌سازی داده برای LSTM
# ═══════════════════════════════════════════════════════════════


class DataScaler:
    """نرمال‌ساز داده (Min-Max Scaling)."""

    def __init__(self) -> None:
        self.min_vals: np.ndarray | None = None
        self.max_vals: np.ndarray | None = None

    def fit_transform(self, data: np.ndarray) -> np.ndarray:
        self.min_vals = data.min(axis=0)
        self.max_vals = data.max(axis=0)
        return self.transform(data)

    def transform(self, data: np.ndarray) -> np.ndarray:
        if self.min_vals is None or self.max_vals is None:
            raise ValueError("Scaler not fitted")
        range_vals = self.max_vals - self.min_vals
        range_vals[range_vals == 0] = 1.0
        return (data - self.min_vals) / range_vals

    def inverse_transform(self, data: np.ndarray) -> np.ndarray:
        if self.min_vals is None or self.max_vals is None:
            raise ValueError("Scaler not fitted")
        range_vals = self.max_vals - self.min_vals
        range_vals[range_vals == 0] = 1.0
        return data * range_vals + self.min_vals


def create_sequences(
    features: np.ndarray,
    target: np.ndarray,
    seq_length: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    ساخت دنباله‌های ورودی برای LSTM.

    X: (samples, seq_length, n_features)
    y: (samples,)
    """
    X, y = [], []
    for i in range(len(features) - seq_length):
        X.append(features[i : i + seq_length])
        y.append(target[i + seq_length])
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


def prepare_lstm_data(
    df: pd.DataFrame,
    target_col: str,
    feature_cols: list[str],
    seq_length: int = 20,
    train_ratio: float = 0.8,
) -> dict[str, Any]:
    """
    آماده‌سازی کامل داده برای LSTM.
    """
    # حذف ردیف‌های NaN
    all_cols = [target_col] + [c for c in feature_cols if c in df.columns]
    clean = df[all_cols].dropna().reset_index(drop=True)

    if len(clean) < seq_length + 20:
        raise ValueError(f"داده کافی نیست: {len(clean)} مشاهده (حداقل {seq_length + 20} لازم است)")

    features = clean[[c for c in feature_cols if c in df.columns]].values
    target = clean[target_col].values

    # نرمال‌سازی
    feature_scaler = DataScaler()
    target_scaler = DataScaler()

    features_scaled = feature_scaler.fit_transform(features)
    target_scaled = target_scaler.fit_transform(target.reshape(-1, 1)).flatten()

    # ساخت دنباله‌ها
    X, y = create_sequences(features_scaled, target_scaled, seq_length)

    # تقسیم آموزش/تست (بدون درهم‌ریختن ترتیب زمانی)
    split_idx = int(len(X) * train_ratio)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    n_features = features_scaled.shape[1]

    return {
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
        "feature_scaler": feature_scaler,
        "target_scaler": target_scaler,
        "n_features": n_features,
        "seq_length": seq_length,
        "feature_names": [c for c in feature_cols if c in df.columns],
        "target_name": target_col,
        "n_total": len(X),
        "n_train": len(X_train),
        "n_test": len(X_test),
    }


# ═══════════════════════════════════════════════════════════════
#  بخش ۳: معماری LSTM
# ═══════════════════════════════════════════════════════════════


class LSTMForexPredictor:
    """
    مدل LSTM برای پیش‌بینی نرخ ارز.

    معماری:
      Input → LSTM (چند لایه) → Dropout → FC → Output
    """

    def __init__(
        self,
        n_features: int,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.2,
        learning_rate: float = 1e-3,
        device: str | None = None,
    ) -> None:
        import torch
        import torch.nn as nn

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout

        # ── معماری مدل ──
        class _LSTMNet(nn.Module):
            def __init__(self_inner) -> None:
                super().__init__()
                self_inner.lstm = nn.LSTM(
                    input_size=n_features,
                    hidden_size=hidden_size,
                    num_layers=num_layers,
                    batch_first=True,
                    dropout=dropout if num_layers > 1 else 0.0,
                )
                self_inner.dropout = nn.Dropout(dropout)
                self_inner.fc1 = nn.Linear(hidden_size, hidden_size // 2)
                self_inner.relu = nn.ReLU()
                self_inner.fc2 = nn.Linear(hidden_size // 2, 1)

            def forward(self_inner, x: Any) -> Any:
                # x: (batch, seq_len, features)
                lstm_out, _ = self_inner.lstm(x)
                last_hidden = lstm_out[:, -1, :]  # آخرین تایم‌استپ
                out = self_inner.dropout(last_hidden)
                out = self_inner.relu(self_inner.fc1(out))
                out = self_inner.fc2(out)
                return out.squeeze(-1)

        self.model = _LSTMNet().to(self.device)
        self.criterion = nn.MSELoss()
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="min", factor=0.5, patience=5, verbose=False
        )

        self.train_losses: list[float] = []
        self.val_losses: list[float] = []
        self.best_val_loss = float("inf")
        self.best_model_state: dict | None = None

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        epochs: int = 100,
        batch_size: int = 32,
        patience: int = 15,
        verbose: bool = True,
    ) -> dict[str, Any]:
        """
        آموزش مدل با Early Stopping.
        """
        import torch

        X_train_t = torch.FloatTensor(X_train).to(self.device)
        y_train_t = torch.FloatTensor(y_train).to(self.device)
        X_val_t = torch.FloatTensor(X_val).to(self.device)
        y_val_t = torch.FloatTensor(y_val).to(self.device)

        train_dataset = torch.utils.data.TensorDataset(X_train_t, y_train_t)
        train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=False)

        best_epoch = 0
        patience_counter = 0

        if verbose:
            print("\n  [LSTM] شروع آموزش...")
            print(f"    Device: {self.device}")
            print(f"    Epochs: {epochs} | Batch: {batch_size} | Patience: {patience}")
            print(f"    Train: {len(X_train)} | Val: {len(X_val)}")
            print(f"    {'Epoch':>6s}  {'Train Loss':>12s}  {'Val Loss':>12s}  {'LR':>10s}")
            print(f"    {'─' * 50}")

        for epoch in range(1, epochs + 1):
            # ── آموزش ──
            self.model.train()
            epoch_loss = 0.0
            for batch_X, batch_y in train_loader:
                self.optimizer.zero_grad()
                pred = self.model(batch_X)
                loss = self.criterion(pred, batch_y)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.optimizer.step()
                epoch_loss += loss.item() * len(batch_y)

            train_loss = epoch_loss / len(X_train)
            self.train_losses.append(train_loss)

            # ── اعتبارسنجی ──
            self.model.eval()
            with torch.no_grad():
                val_pred = self.model(X_val_t)
                val_loss = self.criterion(val_pred, y_val_t).item()
            self.val_losses.append(val_loss)

            current_lr = self.optimizer.param_groups[0]["lr"]
            self.scheduler.step(val_loss)

            # ── ذخیره بهترین مدل ──
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self.best_model_state = {k: v.cpu().clone() for k, v in self.model.state_dict().items()}
                best_epoch = epoch
                patience_counter = 0
                marker = " ★"
            else:
                patience_counter += 1
                marker = ""

            if verbose and (epoch % 10 == 0 or epoch == 1 or marker):
                print(f"    {epoch:>6d}  {train_loss:>12.6f}  {val_loss:>12.6f}  {current_lr:>10.2e}  {marker}")

            # ── Early Stopping ──
            if patience_counter >= patience:
                if verbose:
                    print(f"\n    Early stopping at epoch {epoch}")
                break

        # بازگرداندن بهترین مدل
        if self.best_model_state is not None:
            self.model.load_state_dict(self.best_model_state)
            self.model = self.model.to(self.device)

        if verbose:
            print(f"\n    بهترین مدل: epoch {best_epoch}, val_loss={self.best_val_loss:.6f}")

        return {
            "best_epoch": best_epoch,
            "best_val_loss": self.best_val_loss,
            "final_train_loss": self.train_losses[-1] if self.train_losses else None,
            "epochs_trained": len(self.train_losses),
        }

    def predict(self, X: np.ndarray) -> np.ndarray:
        """پیش‌بینی روی داده جدید."""
        import torch

        self.model.eval()
        X_t = torch.FloatTensor(X).to(self.device)
        with torch.no_grad():
            pred = self.model(X_t)
        return pred.cpu().numpy()

    def save(self, path: str) -> None:
        """ذخیره مدل."""
        import torch

        torch.save(
            {
                "model_state_dict": self.model.state_dict(),
                "hidden_size": self.hidden_size,
                "num_layers": self.num_layers,
                "dropout": self.dropout,
                "train_losses": self.train_losses,
                "val_losses": self.val_losses,
                "best_val_loss": self.best_val_loss,
            },
            path,
        )

    def load(self, path: str) -> None:
        """بارگذاری مدل."""
        import torch

        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.train_losses = checkpoint.get("train_losses", [])
        self.val_losses = checkpoint.get("val_losses", [])
        self.best_val_loss = checkpoint.get("best_val_loss", float("inf"))


# ═══════════════════════════════════════════════════════════════
#  بخش ۴: ارزیابی
# ═══════════════════════════════════════════════════════════════


def evaluate_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    name: str = "model",
) -> dict[str, float]:
    """
    محاسبه معیارهای ارزیابی.
    """
    mae = np.mean(np.abs(y_true - y_pred))
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))

    # MAPE (بدون تقسیم بر صفر)
    mask = np.abs(y_true) > 1e-10
    mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100 if mask.sum() > 0 else float("inf")

    # R²
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r_squared = 1 - (ss_res / (ss_tot + 1e-10))

    # Direction Accuracy (دقت جهت)
    if len(y_true) > 1:
        true_dir = np.diff(y_true) > 0
        pred_dir = np.diff(y_pred) > 0
        direction_accuracy = np.mean(true_dir == pred_dir) * 100
    else:
        direction_accuracy = 0.0

    return {
        "name": name,
        "mae": round(float(mae), 6),
        "rmse": round(float(rmse), 6),
        "mape": round(float(mape), 4),
        "r_squared": round(float(r_squared), 6),
        "direction_accuracy": round(float(direction_accuracy), 2),
        "n_observations": len(y_true),
    }


def print_evaluation(metrics: dict[str, float]) -> None:
    """چاپ زیبای معیارها."""
    print(f"\n  ── ارزیابی مدل: {metrics['name']} ──")
    print(f"    MAE:              {metrics['mae']:>12.4f}")
    print(f"    RMSE:             {metrics['rmse']:>12.4f}")
    print(f"    MAPE:             {metrics['mape']:>11.2f}%")
    print(f"    R²:               {metrics['r_squared']:>12.6f}")
    print(f"    Direction Acc:    {metrics['direction_accuracy']:>11.2f}%")
    print(f"    Observations:     {metrics['n_observations']:>12d}")


# ═══════════════════════════════════════════════════════════════
#  بخش ۵: پیش‌بینی آینده
# ═══════════════════════════════════════════════════════════════


def forecast_future(
    model: LSTMForexPredictor,
    last_sequence: np.ndarray,
    feature_scaler: DataScaler,
    target_scaler: DataScaler,
    n_days: int,
) -> list[dict]:
    """
    پیش‌بینی n روز آینده (iterative forecasting).
    """
    import torch

    predictions = []
    current_seq = last_sequence.copy()

    model.model.eval()

    for day in range(1, n_days + 1):
        # تبدیل به tensor
        x = torch.FloatTensor(current_seq).unsqueeze(0).to(model.device)

        with torch.no_grad():
            pred_scaled = model.model(x).cpu().numpy()[0]

        # تبدیل از مقیاس نرمال‌سازی
        pred_actual = target_scaler.inverse_transform(np.array([[pred_scaled]]))[0, 0]

        predictions.append(
            {
                "day": day,
                "predicted_price": round(float(pred_actual), 2),
            }
        )

        # به‌روزرسانی دنباله (ساده: فقط قیمت پیش‌بینی‌شده)
        # در حالت واقعی باید ویژگی‌های دیگر هم به‌روز شوند
        new_row = current_seq[-1].copy()
        # فرض: اولین ویژگی قیمت است
        new_row[0] = pred_scaled
        current_seq = np.vstack([current_seq[1:], new_row.reshape(1, -1)])

    return predictions


# ═══════════════════════════════════════════════════════════════
#  بخش ۶: Backtest
# ═══════════════════════════════════════════════════════════════


def walk_forward_backtest(
    df: pd.DataFrame,
    target_col: str,
    feature_cols: list[str],
    seq_length: int = 20,
    retrain_every: int = 30,
    train_window: int = 252,
    epochs: int = 50,
    verbose: bool = True,
) -> dict[str, Any]:
    """
    Walk-Forward Backtest.

    هر N روز، مجدداً مدل آموزش داده می‌شود و روی روزهای بعد پیش‌بینی می‌کند.
    """
    if verbose:
        print("\n" + "═" * 70)
        print("  Walk-Forward Backtest")
        print("═" * 70)

    # آماده‌سازی اولیه
    all_cols = [target_col] + [c for c in feature_cols if c in df.columns]
    clean = df[all_cols].dropna().reset_index(drop=True)

    if len(clean) < train_window + retrain_every + seq_length:
        raise ValueError("داده کافی نیست")

    all_preds = []
    all_actuals = []

    n = len(clean)
    start_idx = train_window

    iteration = 0
    while start_idx + retrain_every <= n:
        iteration += 1
        train_end = start_idx
        test_end = min(start_idx + retrain_every, n)

        # داده آموزشی
        train_data = clean.iloc[:train_end]
        test_data = clean.iloc[train_end - seq_length : test_end]

        # آماده‌سازی
        features = train_data[[c for c in feature_cols if c in train_data.columns]].values
        target = train_data[target_col].values

        f_scaler = DataScaler()
        t_scaler = DataScaler()

        features_scaled = f_scaler.fit_transform(features)
        target_scaled = t_scaler.fit_transform(target.reshape(-1, 1)).flatten()

        X_train, y_train = create_sequences(features_scaled, target_scaled, seq_length)

        if len(X_train) < 20:
            start_idx += retrain_every
            continue

        # آموزش مدل
        predictor = LSTMForexPredictor(
            n_features=features_scaled.shape[1],
            hidden_size=32,
            num_layers=1,
            dropout=0.1,
        )

        split = int(len(X_train) * 0.9)
        predictor.train(
            X_train[:split],
            y_train[:split],
            X_train[split:],
            y_train[split],
            epochs=epochs,
            batch_size=16,
            patience=5,
            verbose=False,
        )

        # پیش‌بینی روی بازه تست
        test_features = test_data[[c for c in feature_cols if c in test_data.columns]].values
        test_target = test_data[target_col].values

        test_features_scaled = f_scaler.transform(test_features)
        X_test, y_test_actual = create_sequences(
            test_features_scaled, t_scaler.transform(test_target.reshape(-1, 1)).flatten(), seq_length
        )

        if len(X_test) == 0:
            start_idx += retrain_every
            continue

        preds_scaled = predictor.predict(X_test)
        preds = t_scaler.inverse_transform(preds_scaled.reshape(-1, 1)).flatten()
        actuals = t_scaler.inverse_transform(y_test_actual.reshape(-1, 1)).flatten()

        all_preds.extend(preds.tolist())
        all_actuals.extend(actuals.tolist())

        if verbose:
            rmse = np.sqrt(np.mean((preds - actuals) ** 2))
            print(f"    Iteration {iteration:>3d}: train=0-{train_end}, test={train_end}-{test_end}, RMSE={rmse:.2f}")

        start_idx += retrain_every

    if not all_preds:
        return {"status": "no predictions"}

    all_preds = np.array(all_preds)
    all_actuals = np.array(all_actuals)

    metrics = evaluate_predictions(all_actuals, all_preds, name="Walk-Forward Backtest")

    if verbose:
        print_evaluation(metrics)

    return {
        "status": "completed",
        "metrics": metrics,
        "predictions": all_preds.tolist(),
        "actuals": all_actuals.tolist(),
        "n_iterations": iteration,
    }


# ═══════════════════════════════════════════════════════════════
#  بخش ۷: CLI
# ═══════════════════════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="مدل LSTM برای پیش‌بینی نرخ ارز",
    )
    parser.add_argument("--input", "-i", type=str, required=True, help="فایل CSV داده‌ها")
    parser.add_argument("--target", "-t", type=str, default="usd_close", help="متغیر هدف")
    parser.add_argument("--seq-length", type=int, default=20, help="طول دنباله")
    parser.add_argument("--hidden", type=int, default=64, help="اندازه لایه پنهان")
    parser.add_argument("--layers", type=int, default=2, help="تعداد لایه‌های LSTM")
    parser.add_argument("--dropout", type=float, default=0.2, help="نرخ Dropout")
    parser.add_argument("--epochs", type=int, default=100, help="حداکثر Epoch")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch Size")
    parser.add_argument("--patience", type=int, default=15, help="Early Stopping Patience")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning Rate")
    parser.add_argument("--train-ratio", type=float, default=0.8, help="نسبت داده آموزش")
    parser.add_argument("--predict-days", type=int, default=0, help="پیش‌بینی n روز آینده")
    parser.add_argument("--backtest", action="store_true", help="Walk-Forward Backtest")
    parser.add_argument("--save-model", type=str, default=None, help="مسیر ذخیره مدل")
    parser.add_argument("--load-model", type=str, default=None, help="مسیر بارگذاری مدل")
    parser.add_argument("--output", "-o", type=str, default=None, help="مسیر فایل خروجی")
    return parser.parse_args()


# ═══════════════════════════════════════════════════════════════
#  بخش ۸: اجرای اصلی
# ═══════════════════════════════════════════════════════════════


def main():
    args = parse_args()

    print("=" * 70)
    print("  مدل LSTM برای پیش‌بینی نرخ ارز")
    print(f"  فایل ورودی: {args.input}")
    print(f"  متغیر هدف: {args.target}")
    print("=" * 70)

    # ── بارگذاری داده ──
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"\n  ✗ فایل یافت نشد: {input_path}")
        sys.exit(1)

    df = pd.read_csv(input_path, encoding="utf-8-sig") if input_path.suffix == ".csv" else pd.read_json(input_path)

    print(f"\n  ✓ {len(df)} ردیف، {len(df.columns)} ستون")

    # ── ویژگی‌سازی ──
    print("\n  [1/4] ویژگی‌سازی...")
    df = prepare_features(df)

    # تعیین ویژگی‌ها
    feature_cols = [
        "usd_close",
        "usd_open",
        "usd_high",
        "usd_low",
        "oil_brent",
        "gold_intl_usd",
        "dollar_index",
        "sma_7",
        "sma_21",
        "ema_7",
        "ema_14",
        "rsi_14",
        "macd",
        "macd_signal",
        "bb_width",
        "return_1d",
        "return_3d",
        "volatility_7",
        "volatility_14",
    ]

    # فقط ویژگی‌های موجود را نگه دار
    feature_cols = [c for c in feature_cols if c in df.columns]
    print(f"    ✓ {len(feature_cols)} ویژگی: {', '.join(feature_cols[:10])}...")

    # ── Backtest ──
    if args.backtest:
        bt_result = walk_forward_backtest(
            df,
            args.target,
            feature_cols,
            seq_length=args.seq_length,
            epochs=args.epochs,
        )
        if bt_result.get("status") == "completed":
            bt_path = OUTPUT_DIR / "backtest_results.json"
            with open(bt_path, "w", encoding="utf-8") as f:
                json.dump(bt_result, f, ensure_ascii=False, indent=2, default=float)
            print(f"\n    💾 نتایج: {bt_path}")
        return

    # ── آماده‌سازی داده ──
    print("\n  [2/4] آماده‌سازی داده...")
    data = prepare_lstm_data(
        df,
        args.target,
        feature_cols,
        seq_length=args.seq_length,
        train_ratio=args.train_ratio,
    )

    print(f"    ✓ Train: {data['n_train']} | Test: {data['n_test']}")
    print(f"    ✓ ویژگی‌ها: {data['n_features']}")

    # ── ساخت/بارگذاری مدل ──
    print("\n  [3/4] ساخت مدل...")

    if args.load_model:
        predictor = LSTMForexPredictor(n_features=data["n_features"])
        predictor.load(args.load_model)
        print(f"    ✓ مدل بارگذاری شد: {args.load_model}")
    else:
        predictor = LSTMForexPredictor(
            n_features=data["n_features"],
            hidden_size=args.hidden,
            num_layers=args.layers,
            dropout=args.dropout,
            learning_rate=args.lr,
        )
        print("    ✓ مدل ساخته شد")
        print(f"      Hidden: {args.hidden} | Layers: {args.layers} | Dropout: {args.dropout}")

    # ── آموزش ──
    print("\n  [4/4] آموزش...")
    train_result = predictor.train(
        data["X_train"],
        data["y_train"],
        data["X_test"],
        data["y_test"],
        epochs=args.epochs,
        batch_size=args.batch_size,
        patience=args.patience,
    )

    # ── ارزیابی روی داده تست ──
    print("\n  ── ارزیابی نهایی ──")
    test_preds_scaled = predictor.predict(data["X_test"])

    test_preds = data["target_scaler"].inverse_transform(test_preds_scaled.reshape(-1, 1)).flatten()
    test_actuals = data["target_scaler"].inverse_transform(data["y_test"].reshape(-1, 1)).flatten()

    metrics = evaluate_predictions(test_actuals, test_preds, name="Test Set")
    print_evaluation(metrics)

    # ── پیش‌بینی آینده ──
    if args.predict_days > 0:
        print(f"\n  ── پیش‌بینی {args.predict_days} روز آینده ──")
        last_seq = data["X_test"][-1:]
        forecasts = forecast_future(
            predictor,
            last_seq[0],
            data["feature_scaler"],
            data["target_scaler"],
            args.predict_days,
        )

        print(f"    {'روز':>6s}  {'قیمت پیش‌بینی':>15s}")
        for f in forecasts:
            print(f"    {f['day']:>6d}  {f['predicted_price']:>15,.2f}")

    # ── ذخیره ──
    save_path = args.save_model or str(OUTPUT_DIR / "lstm_forex_model.pt")
    predictor.save(save_path)
    print(f"\n    💾 مدل ذخیره شد: {save_path}")

    # ذخیره نتایج
    results = {
        "train_result": train_result,
        "test_metrics": metrics,
        "config": {
            "target": args.target,
            "seq_length": args.seq_length,
            "hidden_size": args.hidden,
            "num_layers": args.layers,
            "dropout": args.dropout,
            "learning_rate": args.lr,
            "epochs": args.epochs,
            "n_features": data["n_features"],
            "feature_names": data["feature_names"],
        },
    }

    results_path = OUTPUT_DIR / "training_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=float)
    print(f"    💾 نتایج: {results_path}")

    print("\n" + "=" * 70)
    print("  ✅ تمام شد!")
    print("=" * 70)


if __name__ == "__main__":
    main()
