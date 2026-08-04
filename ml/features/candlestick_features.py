from __future__ import annotations

import numpy as np
import pandas as pd

from core.logging import get_logger
from ml.features.base import BaseFeatureBuilder
from ml.types import FeatureMatrix

logger = get_logger(__name__)


class CandlestickPatternFeatures(BaseFeatureBuilder):
    """Extract candlestick pattern scores as numeric features from OHLCV data.

    All scores are floats in [0.0, 1.0] where:
    - 0.0 = pattern not present
    - 1.0 = pattern fully present

    Patterns: Doji, Hammer, Engulfing, Marubozu, Star, Three Soldiers/Crows.
    """

    def compute(self, data: pd.DataFrame) -> FeatureMatrix:
        df = data.copy()

        open_ = df.get("open", df.get("price_open"))
        high = df.get("high", df.get("price_high"))
        low = df.get("low", df.get("price_low"))
        close = df.get("close", df.get("price_close"))

        if open_ is None or high is None or low is None or close is None:
            logger.warning("CandlestickPatternFeatures: missing OHLC columns")
            return FeatureMatrix(
                data=df,
                feature_names=[c for c in df.columns if c not in ("date", "time", "symbol")],
            )

        o = open_.values.astype(np.float64)
        h = high.values.astype(np.float64)
        lo = low.values.astype(np.float64)
        c = close.values.astype(np.float64)
        n = len(o)

        body = np.abs(c - o)
        full_range = h - lo
        upper_shadow = h - np.maximum(o, c)
        lower_shadow = np.minimum(o, c) - lo

        # Avoid division by zero
        safe_range = np.where(full_range > 0, full_range, 1.0)

        # ── Doji: body ≈ 0 relative to full range ──────────────
        df["doji_score"] = np.clip(1.0 - (body / safe_range), 0.0, 1.0)

        # ── Hammer: small body, long lower shadow, short upper ──
        lower_ratio = lower_shadow / safe_range
        upper_ratio = upper_shadow / safe_range
        body_ratio = body / safe_range
        df["hammer_score"] = np.clip(
            np.where(
                (lower_ratio > 0.6) & (upper_ratio < 0.15) & (body_ratio < 0.35),
                1.0 - body_ratio,
                0.0,
            ),
            0.0, 1.0,
        )

        # ── Engulfing: current body fully covers previous body ──
        engulfing = np.zeros(n, dtype=np.float64)
        prev_o = np.roll(o, 1)
        prev_c = np.roll(c, 1)
        prev_o[0] = o[0]
        prev_c[0] = c[0]
        prev_body = np.abs(prev_c - prev_o)
        safe_prev_body = np.where(prev_body > 0, prev_body, 1.0)

        bull_engulf = (
            (c > o) & (prev_c < prev_o)
            & (o <= prev_c) & (c >= prev_o)
        )
        bear_engulf = (
            (c < o) & (prev_c > prev_o)
            & (o >= prev_c) & (c <= prev_o)
        )
        engulfing_strength = np.clip(body / safe_prev_body, 0.0, 1.0)
        engulfing[bull_engulf] = engulfing_strength[bull_engulf]
        engulfing[bear_engulf] = engulfing_strength[bear_engulf]
        df["engulfing_score"] = engulfing

        # ── Marubozu: large body, negligible shadows ────────────
        shadow_ratio = (upper_shadow + lower_shadow) / safe_range
        df["marubozu_score"] = np.clip(
            np.where(
                (body_ratio > 0.7) & (shadow_ratio < 0.1),
                body_ratio,
                0.0,
            ),
            0.0, 1.0,
        )

        # ── Star (morning/evening): gap + small body between ────
        prev_close_2 = np.roll(c, 2)
        prev_close_2[:2] = c[:2]
        (prev_close_2 > np.maximum(np.roll(o, 1)[:1], o[:1])) if n > 1 else np.zeros(n, dtype=bool)
        (prev_close_2 < np.minimum(np.roll(o, 1)[:1], o[:1])) if n > 1 else np.zeros(n, dtype=bool)
        # Recompute with proper rolling for all positions
        star = np.zeros(n, dtype=np.float64)
        for i in range(2, n):
            prev2_close = c[i - 2]
            prev1_open = o[i - 1]
            prev1_close = c[i - 1]
            prev1_body_mid = (prev1_open + prev1_close) / 2.0
            curr_mid = (o[i] + c[i]) / 2.0
            prev1_body_size = abs(prev1_close - prev1_open) / safe_range[i - 1] if safe_range[i - 1] > 0 else 0
            # Morning star: bearish candle → small body → bullish candle
            if prev2_close > prev1_open and prev1_body_size < 0.3 and curr_mid > prev1_body_mid or prev2_close < prev1_open and prev1_body_size < 0.3 and curr_mid < prev1_body_mid:
                star[i] = 1.0 - prev1_body_size
        df["star_score"] = np.clip(star, 0.0, 1.0)

        # ── Three White Soldiers / Three Black Crows ────────────
        soldiers_crows = np.zeros(n, dtype=np.float64)
        for i in range(2, n):
            b0 = c[i - 2] > o[i - 2]  # bullish
            b1 = c[i - 1] > o[i - 1]
            b2 = c[i] > o[i]
            # Three white soldiers: 3 consecutive bullish, each close higher
            if b0 and b1 and b2:
                if c[i] > c[i - 1] > c[i - 2]:
                    avg_body = (body[i] + body[i - 1] + body[i - 2]) / 3.0
                    soldiers_crows[i] = np.clip(avg_body / safe_range[i], 0.0, 1.0)
            # Three black crows: 3 consecutive bearish, each close lower
            elif (not b0) and (not b1) and (not b2):
                if c[i] < c[i - 1] < c[i - 2]:
                    avg_body = (body[i] + body[i - 1] + body[i - 2]) / 3.0
                    soldiers_crows[i] = np.clip(avg_body / safe_range[i], 0.0, 1.0)
        df["three_soldiers_crows_score"] = soldiers_crows

        feature_names = [
            "doji_score", "hammer_score", "engulfing_score",
            "marubozu_score", "star_score", "three_soldiers_crows_score",
        ]
        return FeatureMatrix(
            data=df,
            feature_names=feature_names,
        )

    def get_feature_names(self) -> list[str]:
        return [
            "doji_score", "hammer_score", "engulfing_score",
            "marubozu_score", "star_score", "three_soldiers_crows_score",
        ]
