from __future__ import annotations

import numpy as np
import pandas as pd

from core.logging import get_logger
from ml.features.base import BaseFeatureBuilder
from ml.types import FeatureMatrix

logger = get_logger(__name__)


class TechnicalFeatures(BaseFeatureBuilder):
    def compute(self, data: pd.DataFrame) -> FeatureMatrix:
        df = data.copy()
        close = df.get("close", df.get("price_close"))
        high = df.get("high", df.get("price_high"))
        low = df.get("low", df.get("price_low"))
        volume = df.get("volume", 0)

        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()

        # ── RSI ──────────────────────────────────────────────────────
        zero_loss = (avg_loss == 0).sum()
        if zero_loss > 0:
            logger.info(
                "TechnicalFeatures: %d rows have zero avg_loss — RSI will be set to 100",
                zero_loss,
            )

        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))
        df["rsi"] = df["rsi"].fillna(100)

        # ── MACD ─────────────────────────────────────────────────────
        df["macd"] = close.ewm(span=12).mean() - close.ewm(span=26).mean()
        df["macd_signal"] = df["macd"].ewm(span=9).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # ── ATR ──────────────────────────────────────────────────────
        if high is not None and low is not None:
            df["atr"] = (high - low).rolling(14).mean()
            df["atr"] = df["atr"].fillna(method='ffill').fillna(0)

        # ── Volume ───────────────────────────────────────────────────
        if volume is not None:
            df["volume_sma"] = volume.rolling(20).mean()
            zero_vol = (df["volume_sma"] == 0).sum()
            if zero_vol > 0:
                logger.info(
                    "TechnicalFeatures: %d rows have zero volume_sma — volume_ratio will be set to 1",
                    zero_vol,
                )
            df["volume_ratio"] = volume / df["volume_sma"].replace(0, np.nan)
            df["volume_ratio"] = df["volume_ratio"].fillna(1)

        # ── Half Trend ───────────────────────────────────────────────
        if high is not None and low is not None:
            h_list = high.tolist()
            l_list = low.tolist()
            c_list = close.tolist()
            ema_vals = self._ema_list(c_list, 2)
            atr_vals = self._atr_list(h_list, l_list, c_list, 2)
            prev_trend = 0
            ht_signal = []
            for i in range(len(c_list)):
                if atr_vals[i] is None or ema_vals[i] is None:
                    ht_signal.append(0)
                    continue
                upper = ema_vals[i] + 2.0 * atr_vals[i]
                lower = ema_vals[i] - 2.0 * atr_vals[i]
                if c_list[i] > upper:
                    curr = 1
                elif c_list[i] < lower:
                    curr = -1
                else:
                    curr = prev_trend
                if curr == 1 and prev_trend != 1:
                    ht_signal.append(1)
                elif curr == -1 and prev_trend != -1:
                    ht_signal.append(-1)
                else:
                    ht_signal.append(0)
                prev_trend = curr
            df["half_trend_signal"] = ht_signal

        # ── Squeeze Momentum ─────────────────────────────────────────
        if high is not None and low is not None:
            h_list = high.tolist()
            l_list = low.tolist()
            c_list = close.tolist()
            ema_vals = self._ema_list(c_list, 20)
            atr_vals = self._atr_list(h_list, l_list, c_list, 20)
            sq_on = []
            sq_mom = []
            for i in range(len(c_list)):
                if ema_vals[i] is None or atr_vals[i] is None:
                    sq_on.append(0)
                    sq_mom.append(0.0)
                    continue
                kc_mid = ema_vals[i]
                kc_upper = kc_mid + 1.5 * atr_vals[i]
                kc_lower = kc_mid - 1.5 * atr_vals[i]
                start = max(0, i - 19)
                window = c_list[start : i + 1]
                bb_mean = sum(window) / len(window)
                bb_std_val = (sum((x - bb_mean) ** 2 for x in window) / len(window)) ** 0.5
                bb_upper = bb_mean + 2.0 * bb_std_val
                bb_lower = bb_mean - 2.0 * bb_std_val
                is_sq = 1 if (bb_lower > kc_lower and bb_upper < kc_upper) else 0
                sq_on.append(is_sq)
                lr_window = [c_list[j] - bb_mean for j in range(start, i + 1)]
                if len(lr_window) >= 2:
                    n_lr = len(lr_window)
                    x_mean = (n_lr - 1) / 2
                    y_mean = sum(lr_window) / n_lr
                    num = sum((j - x_mean) * (lr_window[j] - y_mean) for j in range(n_lr))
                    den = sum((j - x_mean) ** 2 for j in range(n_lr))
                    mom_val = num / den if den != 0 else 0.0
                else:
                    mom_val = 0.0
                sq_mom.append(mom_val)
            df["squeeze_squeeze_on"] = sq_on
            df["squeeze_momentum"] = sq_mom

        # ── Support & Resistance ─────────────────────────────────────
        if high is not None and low is not None:
            h_list = high.tolist()
            l_list = low.tolist()
            c_list = close.tolist()
            v_list = volume.tolist() if volume is not None else [0.0] * len(c_list)
            sr_res = []
            sr_sup = []
            sr_break = []
            for i in range(len(c_list)):
                start = max(0, i - 19)
                sup = min(l_list[start : i + 1])
                res = max(h_list[start : i + 1])
                sr_sup.append(sup)
                sr_res.append(res)
                avg_vol = sum(v_list[start : i + 1]) / len(v_list[start : i + 1]) if v_list[start : i + 1] else 0
                vol_ok = v_list[i] > 1.5 * avg_vol if avg_vol > 0 else True
                is_up = 1 if (c_list[i] > res and vol_ok) else 0
                is_dn = -1 if (c_list[i] < sup and vol_ok) else 0
                sr_break.append(is_up if is_up else is_dn)
            df["sr_distance_to_resistance"] = [(c - r) / c if c and r else 0.0 for c, r in zip(c_list, sr_res, strict=False)]
            df["sr_distance_to_support"] = [(c - s) / c if c and s else 0.0 for c, s in zip(c_list, sr_sup, strict=False)]
            df["sr_break_signal"] = sr_break

        df = df.fillna(0)

        return FeatureMatrix(
            data=df,
            feature_names=[c for c in df.columns if c not in ("date", "time", "symbol")],
        )

    def get_feature_names(self) -> list[str]:
        return [
            "rsi", "macd", "macd_signal", "macd_hist", "atr", "volume_sma", "volume_ratio",
            "half_trend_signal", "squeeze_squeeze_on", "squeeze_momentum",
            "sr_distance_to_resistance", "sr_distance_to_support", "sr_break_signal",
        ]

    @staticmethod
    def _ema_list(data: list[float], period: int) -> list[float | None]:
        result: list[float | None] = []
        k = 2 / (period + 1)
        for i, val in enumerate(data):
            if i < period - 1:
                result.append(None)
            elif i == period - 1:
                result.append(sum(data[:period]) / period)
            else:
                prev = result[-1]
                result.append((val - prev) * k + prev if prev is not None else None)
        return result

    @staticmethod
    def _atr_list(high: list[float], low: list[float], close: list[float], period: int) -> list[float | None]:
        trs: list[float] = []
        for i in range(len(high)):
            if i == 0:
                trs.append(high[i] - low[i])
            else:
                trs.append(max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])))
        result: list[float | None] = []
        for i in range(len(trs)):
            if i < period - 1:
                result.append(None)
            else:
                result.append(sum(trs[i - period + 1 : i + 1]) / period)
        return result
