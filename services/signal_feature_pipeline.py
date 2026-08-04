"""Signal Feature Pipeline — converts raw market data into ML-ready feature vectors
for each market type supported by the platform.

Each market has its own feature extractor that produces a consistent feature vector
consumable by the ModelRegistry models (LSTM, XGBoost, RandomForest, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

from core.logging import get_logger
from ml.types import FeatureMatrix, TargetVector

logger = get_logger(__name__)


@dataclass
class MarketFeatures:
    """Container for extracted features from any market."""
    symbol: str
    market: str
    timestamp: str = ""
    vector: list[float] = field(default_factory=list)
    feature_names: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_feature_matrix(self) -> FeatureMatrix:
        """Convert to ML-ready FeatureMatrix."""
        import pandas as pd
        df = pd.DataFrame([self.vector], columns=self.feature_names)
        return FeatureMatrix(data=df, feature_names=self.feature_names)

    @property
    def shape(self) -> tuple[int, int]:
        return (1, len(self.vector))


class SignalFeaturePipeline:
    """Converts market data to feature vectors for each market type.

    Feature groups (all markets):
      - Price action: returns, volatility, momentum
      - Volume: volume ratio, value changes
      - Technical: RSI, MA cross, ATR-normalized
      - Market-specific: PCR for options, put/call OI, etc.
    """

    # Market-specific feature extractors
    EXTRACTORS: dict[str, str] = {
        "stock": "_extract_stock_features",
        "gold": "_extract_gold_features",
        "currency": "_extract_currency_features",
        "crypto": "_extract_crypto_features",
        "option": "_extract_option_features",
        "commodity": "_extract_commodity_features",
        "ime": "_extract_ime_features",
    }

    def __init__(self, market: str = "stock") -> None:
        self.market = market

    async def extract(
        self,
        symbol: str,
        market: str,
        price_data: dict[str, Any],
        volume_data: dict[str, Any] | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> MarketFeatures:
        """Extract features from raw market data."""
        extractor_name = self.EXTRACTORS.get(market, "_extract_stock_features")
        extractor = getattr(self, extractor_name, self._extract_stock_features)
        return await extractor(symbol, market, price_data, volume_data, extra_data or {})

    async def _extract_stock_features(
        self, symbol: str, market: str,
        price_data: dict[str, Any],
        volume_data: dict[str, Any] | None,
        extra: dict[str, Any],
    ) -> MarketFeatures:
        closes = price_data.get("closes", [])
        highs = price_data.get("highs", [])
        lows = price_data.get("lows", [])
        volumes = price_data.get("volumes", [])
        values = price_data.get("values", [])

        vector: list[float] = []
        names: list[str] = []

        # 1. Returns (1d, 5d, 10d, 20d)
        for period in [1, 5, 10, 20]:
            ret = (closes[-1] - closes[-period - 1]) / max(closes[-period - 1], 0.001) if len(closes) > period else 0.0
            vector.append(ret)
            names.append(f"return_{period}d")

        # 2. Volatility (5d, 10d, 20d)
        for period in [5, 10, 20]:
            if len(closes) > period:
                returns = [(closes[i] - closes[i - 1]) / max(closes[i - 1], 0.001)
                           for i in range(-period, 0) if closes[i - 1] > 0]
                vol = float(np.std(returns)) if returns else 0.0
            else:
                vol = 0.0
            vector.append(vol)
            names.append(f"volatility_{period}d")

        # 3. RSI (14)
        rsi = self._compute_rsi(closes)
        vector.append(rsi / 100.0)
        names.append("rsi_14")

        # 4. MA cross (5/20)
        if len(closes) >= 20:
            ma5 = sum(closes[-5:]) / 5
            ma20 = sum(closes[-20:]) / 20
            ma_cross = (ma5 - ma20) / max(ma20, 0.001)
        else:
            ma_cross = 0.0
        vector.append(ma_cross)
        names.append("ma_cross_5_20")

        # 5. Volume ratio (5d/20d avg)
        vol_ratio = sum(volumes[-5:]) / 5 / max(sum(volumes[-20:]) / 20, 1) if len(volumes) >= 20 else 1.0
        vector.append(min(vol_ratio, 5.0) / 5.0)
        names.append("volume_ratio")

        # 6. Value change (1d)
        val_chg = (values[-1] - values[-2]) / max(values[-2], 1) if len(values) >= 2 else 0.0
        vector.append(val_chg)
        names.append("value_change_1d")

        # 7. Real/Legal buy ratio
        real_buy = extra.get("buy_real_volume", 0)
        legal_buy = extra.get("buy_legal_volume", 0)
        total_buy = real_buy + legal_buy
        real_ratio = real_buy / max(total_buy, 1)
        vector.append(real_ratio)
        names.append("real_buy_ratio")

        # 8. ATR-normalized position
        atr = self._compute_atr(highs, lows, closes) or price_data.get("last_price", 0) * 0.02
        last_price = closes[-1] if closes else price_data.get("last_price", 0)
        atr_norm = atr / max(last_price, 0.001)
        vector.append(min(atr_norm, 0.2) / 0.2)
        names.append("atr_normalized")

        # 9. Price position in range (20d)
        if len(highs) >= 20 and len(lows) >= 20:
            h20 = max(highs[-20:])
            l20 = min(lows[-20:])
            pos = (last_price - l20) / max(h20 - l20, 0.001)
        else:
            pos = 0.5
        vector.append(pos)
        names.append("price_position_20d")

        # 10. Trend strength (ADX-like)
        vector.append(self._trend_strength(closes))
        names.append("trend_strength")

        return MarketFeatures(
            symbol=symbol, market=market,
            timestamp=datetime.now(UTC).isoformat(),
            vector=vector, feature_names=names,
            metadata={"last_price": last_price, "closes_count": len(closes)},
        )

    async def _extract_gold_features(
        self, symbol: str, market: str,
        price_data: dict[str, Any],
        volume_data: dict[str, Any] | None,
        extra: dict[str, Any],
    ) -> MarketFeatures:
        # Gold uses similar features but with different parameterization
        return await self._extract_stock_features(symbol, market, price_data, volume_data, extra)

    async def _extract_currency_features(
        self, symbol: str, market: str,
        price_data: dict[str, Any],
        volume_data: dict[str, Any] | None,
        extra: dict[str, Any],
    ) -> MarketFeatures:
        return await self._extract_stock_features(symbol, market, price_data, volume_data, extra)

    async def _extract_crypto_features(
        self, symbol: str, market: str,
        price_data: dict[str, Any],
        volume_data: dict[str, Any] | None,
        extra: dict[str, Any],
    ) -> MarketFeatures:
        features = await self._extract_stock_features(symbol, market, price_data, volume_data, extra)

        # Crypto-specific: market cap ratio, 24h volume/cap
        mcap = extra.get("market_cap", 0)
        vol24h = extra.get("volume_24h", 0)
        vol_cap_ratio = vol24h / mcap if mcap > 0 else 0.0
        features.vector.append(min(vol_cap_ratio, 1.0))
        features.feature_names.append("volume_cap_ratio")

        rank = extra.get("rank", 50)
        features.vector.append(1.0 - (rank / 100.0))
        features.feature_names.append("normalized_rank")

        return features

    async def _extract_option_features(
        self, symbol: str, market: str,
        price_data: dict[str, Any],
        volume_data: dict[str, Any] | None,
        extra: dict[str, Any],
    ) -> MarketFeatures:
        features = await self._extract_stock_features(symbol, market, price_data, volume_data, extra)

        # Options-specific: PCR, OI ratio, IV
        pcr = extra.get("put_call_ratio", 1.0)
        features.vector.append(min(pcr, 3.0) / 3.0)
        features.feature_names.append("put_call_ratio")

        max_pain_dist = extra.get("max_pain_distance", 0.0)
        features.vector.append(min(abs(max_pain_dist), 0.1) / 0.1)
        features.feature_names.append("max_pain_distance")

        short_term_volume = extra.get("short_term_volume_ratio", 0.0)
        features.vector.append(short_term_volume)
        features.feature_names.append("short_term_volume_ratio")

        return features

    async def _extract_commodity_features(
        self, symbol: str, market: str,
        price_data: dict[str, Any],
        volume_data: dict[str, Any] | None,
        extra: dict[str, Any],
    ) -> MarketFeatures:
        return await self._extract_stock_features(symbol, market, price_data, volume_data, extra)

    async def _extract_ime_features(
        self, symbol: str, market: str,
        price_data: dict[str, Any],
        volume_data: dict[str, Any] | None,
        extra: dict[str, Any],
    ) -> MarketFeatures:
        features = await self._extract_stock_features(symbol, market, price_data, volume_data, extra)

        # IME-specific: days to expiry, OI change
        days = extra.get("days_remaining", 30)
        features.vector.append(1.0 - (days / 365.0))
        features.feature_names.append("days_to_expiry_norm")

        oi = extra.get("open_interest", 0)
        prev_oi = extra.get("prev_open_interest", 0)
        oi_chg = (oi - prev_oi) / max(prev_oi, 1)
        features.vector.append(min(oi_chg, 1.0))
        features.feature_names.append("oi_change")

        return features

    # ── Technical Helpers ──

    @staticmethod
    def _compute_rsi(closes: list[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        gains = []
        losses = []
        for i in range(1, len(closes)):
            delta = closes[i] - closes[i - 1]
            gains.append(max(delta, 0))
            losses.append(max(-delta, 0))
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss < 1e-10:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _compute_atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
        if len(closes) < period + 1:
            return None
        trs = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)
        return sum(trs[-period:]) / period

    @staticmethod
    def _trend_strength(closes: list[float], period: int = 14) -> float:
        """Simple trend strength: proportion of days moving in the same direction."""
        if len(closes) < period:
            return 0.5
        up_days = sum(1 for i in range(-period, 0) if closes[i] > closes[i - 1])
        return up_days / period

    @staticmethod
    def prepare_training_data(
        feature_sequence: list[MarketFeatures],
        returns: list[float],
        sequence_length: int = 20,
    ) -> tuple[FeatureMatrix, TargetVector]:
        """Convert a sequence of features + returns into supervised learning data."""
        import pandas as pd

        X_rows = []
        y_values = []

        for i in range(sequence_length, len(feature_sequence)):
            # Flatten the sequence: concatenate vectors from last `sequence_length` steps
            seq_vec = []
            for j in range(i - sequence_length, i):
                seq_vec.extend(feature_sequence[j].vector)
            X_rows.append(seq_vec)
            # Target: future return
            future_return = (returns[i] if i < len(returns) else 0.0)
            # Binary classification: was direction correct?
            y_values.append(1.0 if future_return > 0 else 0.0)

        if not X_rows:
            return FeatureMatrix(), TargetVector()

        feature_names = [
            f"{fname}_t{-lag}"
            for lag in range(sequence_length, 0, -1)
            for fname in feature_sequence[0].feature_names
        ]
        df = pd.DataFrame(X_rows, columns=feature_names[:len(X_rows[0])])
        y = pd.Series(y_values, name="direction_up")

        return FeatureMatrix(data=df, feature_names=list(df.columns)), TargetVector(data=y, name="direction_up", task_type="classification")
