"""Confidence Scorer — computes calibrated confidence scores for trading signals.

Factors considered:
  - Historical accuracy of the source (market, model, strategy)
  - Model agreement (how many models agree on direction)
  - Market condition (trend strength, volatility regime)
  - Signal strength (how strong are the technical indicators)
  - Recent performance (accuracy in last N signals)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.calibration_bootstrap import BOOTSTRAP_PRIOR_WEIGHT, get_accuracy_prior
from core.db_utils import safe_row_float
from core.logging import get_logger

logger = get_logger(__name__)

# Market condition is a market-wide aggregate (full-table scan on the snapshot
# table) that changes slowly. Share it across ALL scorer instances with a TTL
# so the whole signal pipeline (and every background rebuild) doesn't re-scan
# the table per run.
_MARKET_CONDITION_TTL_SECONDS = 300.0
_market_condition_ttl_cache: dict[str, tuple[float, float]] = {}  # market -> (value, at)


@dataclass
class ConfidenceFactors:
    """Breakdown of factors contributing to a confidence score."""
    historical_accuracy: float = 0.0
    model_agreement: float = 0.0
    trend_strength: float = 0.0
    volatility_regime: float = 0.0
    signal_strength: float = 0.0
    recent_performance: float = 0.0
    market_condition: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "historical_accuracy": round(self.historical_accuracy, 3),
            "model_agreement": round(self.model_agreement, 3),
            "trend_strength": round(self.trend_strength, 3),
            "volatility_regime": round(self.volatility_regime, 3),
            "signal_strength": round(self.signal_strength, 3),
            "recent_performance": round(self.recent_performance, 3),
            "market_condition": round(self.market_condition, 3),
        }


@dataclass
class CalibratedConfidence:
    """Calibrated confidence score for a single signal."""
    confidence: float           # 0-1 final score
    factors: ConfidenceFactors
    calibration_level: str      # low / medium / high / very_high
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": round(self.confidence, 3),
            "calibration_level": self.calibration_level,
            "factors": self.factors.to_dict(),
            "notes": self.notes,
        }


class ConfidenceScorer:
    """Computes calibrated confidence scores for signals using multiple factors."""

    # Weights for each factor (must sum to 1.0)
    WEIGHTS = {
        "historical_accuracy": 0.30,
        "model_agreement": 0.20,
        "trend_strength": 0.15,
        "volatility_regime": 0.10,
        "signal_strength": 0.15,
        "recent_performance": 0.10,
    }

    def __init__(self, session: Any = None) -> None:
        self._session = session
        # Memoization: historical accuracy / recent performance are per
        # (market, source) and market condition is per market — NOT per
        # symbol. Without this cache the pipeline runs N full-table scans
        # (e.g. AVG over brsapi_symbol_snapshots) per signal, turning a
        # 120-signal run into 120+ expensive DB scans (minutes of latency).
        self._hist_accuracy_cache: dict[tuple[str, str], float] = {}
        self._recent_performance_cache: dict[tuple[str, str], float] = {}
        self._market_condition_cache: dict[str, float] = {}

    async def compute_confidence(
        self,
        symbol: str,
        market: str,
        direction: str,
        source: str,
        signal_strength: float,
        ml_prediction: dict[str, Any] | None = None,
        closes: list[float] | None = None,
        models_used: list[str] | None = None,
    ) -> CalibratedConfidence:
        """Compute calibrated confidence score for a signal."""
        factors = ConfidenceFactors()
        notes: list[str] = []

        # 1. Historical accuracy of the source (bootstrap prior = market-adapted default)
        factors.historical_accuracy = await self._get_historical_accuracy(
            market=market, source=source, symbol=symbol
        )
        if factors.historical_accuracy > 0.6:
            notes.append(f"تاریخچه خوب: {factors.historical_accuracy:.0%} دقت")

        # 2. Model agreement (how many models agree on this direction)
        # Use bootstrap prior when no ML models available (fix #5: cold-start)
        if ml_prediction and models_used:
            factors.model_agreement = self._compute_model_agreement(
                ml_prediction, direction, models_used
            )
        else:
            # Bootstrap: assume moderate agreement based on market accuracy prior
            factors.model_agreement = min(1.0, get_accuracy_prior(market))
        if factors.model_agreement > 0.7:
            notes.append(f"توافق مدل‌ها: {factors.model_agreement:.0%}")

        # 3. Trend strength (from price closes if available, else bootstrap prior)
        if closes and len(closes) >= 20:
            factors.trend_strength = self._compute_trend_strength(closes)
        else:
            # Bootstrap: use market accuracy prior as trend strength baseline
            factors.trend_strength = get_accuracy_prior(market) * 0.8
        if factors.trend_strength > 0.6:
            notes.append(f"روند قوی: {factors.trend_strength:.0%}")

        # 4. Volatility regime (from price closes if available)
        if closes and len(closes) >= 20:
            factors.volatility_regime = self._compute_volatility_regime(closes)
        else:
            # Bootstrap: moderate volatility by default
            factors.volatility_regime = 0.5
        if factors.volatility_regime < 0.3:
            notes.append("بازار با ثبات (نوسان کم)")
        elif factors.volatility_regime > 0.7:
            notes.append("بازار پرنوسان — احتیاط")
            factors.volatility_regime *= 0.7  # penalty in high volatility

        # 5. Signal strength (from technical analysis — this comes from rule engine)
        factors.signal_strength = min(1.0, max(0.0, signal_strength))
        if factors.signal_strength > 0.6:
            notes.append(f"قدرت سیگنال: {factors.signal_strength:.0%}")

        # 6. Recent performance (with bootstrap prior)
        factors.recent_performance = await self._get_recent_performance(
            market=market, source=source, symbol=symbol, days=30
        )
        if factors.recent_performance > 0.6:
            notes.append(f"عملکرد اخیر: {factors.recent_performance:.0%}")

        # 7. Market condition adjustment
        factors.market_condition = await self._get_market_condition(market)
        if factors.market_condition < 0.4:
            notes.append("شرایط بازار نامطلوب")
            factors.market_condition *= 0.8

        # Weighted combination
        confidence = (
            factors.historical_accuracy * self.WEIGHTS["historical_accuracy"] +
            factors.model_agreement * self.WEIGHTS["model_agreement"] +
            factors.trend_strength * self.WEIGHTS["trend_strength"] +
            factors.volatility_regime * self.WEIGHTS["volatility_regime"] +
            factors.signal_strength * self.WEIGHTS["signal_strength"] +
            factors.recent_performance * self.WEIGHTS["recent_performance"]
        )

        # Apply market condition as final multiplier (0.8x to 1.2x)
        confidence *= 0.8 + factors.market_condition * 0.4

        # Ensure valid range
        confidence = max(0.05, min(0.95, confidence))

        # Calibration level
        if confidence >= 0.75:
            calibration = "very_high"
            notes.append("اعتماد بسیار بالا")
        elif confidence >= 0.60:
            calibration = "high"
            notes.append("اعتماد بالا")
        elif confidence >= 0.40:
            calibration = "medium"
            notes.append("اعتماد متوسط")
        else:
            calibration = "low"
            notes.append("اعتماد پایین — تأیید اضافی لازم است")

        return CalibratedConfidence(
            confidence=confidence,
            factors=factors,
            calibration_level=calibration,
            notes=notes,
        )

    async def _get_historical_accuracy(
        self, market: str, source: str, symbol: str = ""
    ) -> float:
        """Get historical accuracy for this market/source from DB."""
        key = (market, source)
        cached = self._hist_accuracy_cache.get(key)
        if cached is not None:
            return cached
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            # Use bootstrap prior as base (market-adapted default)
            bootstrap_prior = get_accuracy_prior(market)

            if async_session_factory is None:
                return bootstrap_prior

            async with async_session_factory() as session:
                r = await session.execute(text("""
                    SELECT AVG(CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END),
                           COUNT(*) as total
                    FROM signal_accuracy
                    WHERE market = :market AND source = :source
                      AND outcome_set_at >= NOW() - INTERVAL '90 days'
                """), {"market": market, "source": source})
                row = r.fetchone()
                if row and row[0] is not None:
                    real_accuracy = float(row[0])
                    total = row[1] or 0
                    # Bayesian blend: bootstrap prior + real data
                    prior_weight = 100  # equivalent sample size for prior
                    blended = (bootstrap_prior * prior_weight + real_accuracy * total) / (prior_weight + total)
                    self._hist_accuracy_cache[key] = round(blended, 4)
                    return self._hist_accuracy_cache[key]
                self._hist_accuracy_cache[key] = bootstrap_prior
                return bootstrap_prior
        except Exception as e:
            logger.debug("Could not get historical accuracy: %s", e)
            return 0.55

    async def _get_recent_performance(
        self, market: str, source: str, symbol: str, days: int = 30
    ) -> float:
        """Get accuracy in the most recent N signals."""
        key = (market, source)
        cached = self._recent_performance_cache.get(key)
        if cached is not None:
            return cached
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            bootstrap_prior = get_accuracy_prior(market)

            if async_session_factory is None:
                return bootstrap_prior

            async with async_session_factory() as session:
                r = await session.execute(text("""
                    SELECT AVG(CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END),
                           COUNT(*) as total
                    FROM (
                        SELECT direction_correct
                        FROM signal_accuracy
                        WHERE market = :market AND source = :source
                        ORDER BY outcome_set_at DESC
                        LIMIT 20
                    ) recent
                """), {"market": market, "source": source})
                row = r.fetchone()
                if row and row[0] is not None:
                    real_accuracy = float(row[0])
                    total = row[1] or 0
                    blended = (bootstrap_prior * BOOTSTRAP_PRIOR_WEIGHT + real_accuracy * total) / (BOOTSTRAP_PRIOR_WEIGHT + total)
                    self._recent_performance_cache[key] = round(blended, 4)
                    return self._recent_performance_cache[key]
                self._recent_performance_cache[key] = bootstrap_prior
                return bootstrap_prior
        except Exception as e:
            logger.debug("Could not get recent performance: %s", e)
            return 0.5

    @staticmethod
    def _compute_model_agreement(
        ml_prediction: dict[str, Any] | None,
        direction: str,
        models_used: list[str] | None = None,
    ) -> float:
        """Compute how much models agree on the direction."""
        if not ml_prediction or not models_used:
            return 0.0

        scores = ml_prediction.get("direction_scores", {})
        total = len(models_used)
        if total == 0:
            return 0.0

        # Count models predicting this direction
        direction_score = scores.get(direction, 0)
        return float(min(1.0, direction_score * 2))  # amplify

    @staticmethod
    def _compute_trend_strength(closes: list[float], period: int = 20) -> float:
        """Compute trend strength (0-1) based on ADX-like logic."""
        if len(closes) < period:
            return 0.5

        # Directional movement
        up_days = 0
        down_days = 0
        for i in range(1, period):
            if closes[-i] > closes[-i - 1]:
                up_days += 1
            elif closes[-i] < closes[-i - 1]:
                down_days += 1

        total = up_days + down_days
        if total == 0:
            return 0.5

        # Trend strength: how directional vs. choppy
        strength = abs(up_days - down_days) / total
        return min(1.0, strength * 1.5)

    @staticmethod
    def _compute_volatility_regime(closes: list[float], period: int = 20) -> float:
        """Compute volatility regime (0-1). Lower = more stable."""
        if len(closes) < period:
            return 0.5

        returns = [(closes[i] - closes[i - 1]) / max(closes[i - 1], 0.001)
                   for i in range(-period, 0) if closes[i - 1] > 0]
        if not returns:
            return 0.5

        import numpy as np
        vol = float(np.std(returns))
        # Normalize: vol of 0.01 (1%) → 0.3, vol of 0.05 (5%) → 0.7
        normalized = min(1.0, vol * 20)
        return float(normalized)

    async def _get_market_condition(self, market: str) -> float:
        """Get overall market condition score (0-1).

        This is a market-wide aggregate (a full-table scan on the snapshot
        table), so it is computed once per market and memoized — running it
        once per signal is what made the pipeline take minutes.
        """
        cached = self._market_condition_cache.get(market)
        if cached is not None:
            return cached
        import time as _t
        now = _t.monotonic()
        global_entry = _market_condition_ttl_cache.get(market)
        if global_entry and (now - global_entry[1]) < _MARKET_CONDITION_TTL_SECONDS:
            self._market_condition_cache[market] = global_entry[0]
            return global_entry[0]
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            if async_session_factory is None:
                return 0.5

            async with async_session_factory() as session:
                # Use top gainers/losers ratio as market sentiment
                table_map = {
                    "stock": ("brsapi_symbol_snapshots", "price_close_change_pct"),
                    "gold": ("brsapi_gold_coin_prices", "change_percent"),
                    "currency": ("brsapi_currency_prices", "change_percent"),
                    "crypto": ("brsapi_crypto_prices", "change_percent"),
                }
                table, pct_col = table_map.get(market, ("brsapi_symbol_snapshots", "price_close_change_pct"))

                r = await session.execute(text(f"""
                    SELECT
                        AVG(CASE WHEN {pct_col} > 0 THEN 1.0 ELSE 0.0 END) as positive_ratio,
                        AVG(ABS({pct_col})) as avg_volatility
                    FROM {table}
                    WHERE {pct_col} IS NOT NULL
                """))
                row = r.fetchone()
                if row:
                    positive_ratio = safe_row_float(row, idx=0, default=0.5)
                    # Market condition: 0.5 base + adjustment for bullish/bearish
                    value = 0.5 + (positive_ratio - 0.5) * 0.4
                    self._market_condition_cache[market] = value
                    _market_condition_ttl_cache[market] = (value, now)
                    return value
        except Exception as e:
            logger.debug("Could not get market condition: %s", e)

        self._market_condition_cache[market] = 0.5
        _market_condition_ttl_cache[market] = (0.5, now)
        return 0.5
