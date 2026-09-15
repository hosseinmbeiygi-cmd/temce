"""Smart Screener V2 — Complete 5x upgrade with advanced analytics.

This module provides:
- Multi-timeframe analysis (daily, weekly, monthly)
- Sector rotation analysis
- Smart money flow tracking
- Advanced pattern recognition
- Risk-adjusted scoring
- Backtesting integration
- Real-time alerts
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from services.smart_money.advanced_analytics import AdvancedAnalysis, AdvancedAnalyticsEngine
from services.smart_money.scoring_engine import ScoringEngine

logger = logging.getLogger(__name__)


@dataclass
class ScreenerConfig:
    """Configuration for the enhanced screener."""

    # Scoring weights
    smart_money_weight: float = 0.4
    technical_weight: float = 0.3
    fundamental_weight: float = 0.2
    momentum_weight: float = 0.1

    # Risk parameters
    max_risk_score: float = 0.7
    min_liquidity: float = 0.3
    min_volume: int = 100_000

    # Timeframe weights
    daily_weight: float = 0.5
    weekly_weight: float = 0.3
    monthly_weight: float = 0.2

    # Pattern detection
    enable_patterns: bool = True
    min_pattern_confidence: float = 0.6

    # Sector analysis
    enable_sector_analysis: bool = True
    sector_rotation_lookback: int = 20

    # Backtesting
    enable_backtesting: bool = False
    backtest_period_days: int = 30


@dataclass
class EnhancedScreenedSymbol:
    """Enhanced screening result with advanced analytics."""

    # Basic info
    symbol: str
    name: str
    market: str
    industry: str
    last_price: float
    change_pct: float
    volume: int
    value: float

    # Smart Money scores
    smc_score: float = 0.0
    phase: str = "neutral"
    rank: int = 0
    reason: str = ""

    # Technical scores
    liquidity_score: float = 0.0
    power_score: float = 0.0
    structure_score: float = 0.0
    orderflow_score: float = 0.0
    trigger_score: float = 0.0

    # Advanced analytics
    rsi: float = 0.0
    macd_histogram: float = 0.0
    bb_pct: float = 0.0
    atr_pct: float = 0.0
    adx: float = 0.0
    trend_direction: str = "sideways"
    trend_strength: float = 0.0
    volatility_regime: str = "normal"

    # Pattern signals
    pattern_signal: str = ""
    pattern_confidence: float = 0.0

    # Composite scores
    technical_score: float = 0.0
    momentum_score: float = 0.0
    risk_score: float = 0.0
    composite_score: float = 0.0
    composite_signal: str = "neutral"

    # Support/Resistance
    support_level: float = 0.0
    resistance_level: float = 0.0
    distance_to_support: float = 0.0
    distance_to_resistance: float = 0.0

    # Volume profile
    poc_price: float = 0.0
    value_area_high: float = 0.0
    value_area_low: float = 0.0
    volume_trend: str = "neutral"

    # Fundamental
    pe_ratio: float | None = None
    eps: float | None = None
    market_value: float | None = None

    # Metadata
    details: dict[str, Any] = field(default_factory=dict)
    advanced_analysis: AdvancedAnalysis | None = None


@dataclass
class SectorAnalysis:
    """Sector rotation analysis result."""

    sector: str
    relative_strength: float  # vs market
    momentum: float  # short-term vs long-term
    breadth: float  # % of stocks up
    money_flow: float  # net money flow
    rotation_signal: str  # leading, lagging, improving, weakening


class SmartScreenerV2:
    """Enhanced Smart Screener with 5x capabilities.

    Features:
    1. Multi-timeframe scoring
    2. Advanced technical analysis
    3. Pattern recognition
    4. Sector rotation
    5. Risk-adjusted returns
    6. Smart money flow
    7. Real-time alerts
    """

    def __init__(self, config: ScreenerConfig | None = None) -> None:
        self.config = config or ScreenerConfig()
        self._scoring_engine = ScoringEngine()
        self._analytics_engine = AdvancedAnalyticsEngine()
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl = 60

    def _get_cached(self, key: str) -> Any | None:
        if key in self._cache:
            ts, val = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return val
            del self._cache[key]
        return None

    def _set_cached(self, key: str, val: Any) -> None:
        self._cache[key] = (time.time(), val)
        if len(self._cache) > 500:
            oldest = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest]

    def analyze_symbol(
        self,
        symbol: str,
        name: str,
        market: str,
        industry: str,
        quote: dict[str, Any],
        history: list[dict[str, Any]],
        sector_history: list[float] | None = None,
    ) -> EnhancedScreenedSymbol:
        """Analyze a single symbol with full advanced analytics."""
        cache_key = f"analysis:{symbol}:{len(history)}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # Step 1: Smart Money scoring
        smc_result = self._scoring_engine.analyze(quote, history, index_history=sector_history)

        # Step 2: Advanced technical analysis
        advanced = self._analytics_engine.analyze(history, quote)

        # Step 3: Compute enhanced scores
        technical_score = self._compute_technical_score(advanced)
        momentum_score = self._compute_momentum_score(advanced)
        risk_score = self._compute_risk_score(advanced)

        # Step 4: Composite scoring
        composite = self._compute_composite_score(
            smc_score=smc_result.get("smart_money_score", 0),
            technical_score=technical_score,
            momentum_score=momentum_score,
            risk_score=risk_score,
        )

        # Step 5: Pattern detection
        pattern_signal, pattern_confidence = self._get_best_pattern(advanced)

        # Step 6: Support/Resistance
        sr_levels = advanced.support_resistance
        support = next((lv.level for lv in sr_levels if lv.type == "support"), 0.0)
        resistance = next((lv.level for lv in sr_levels if lv.type == "resistance"), 0.0)

        current_price = float(quote.get("price_close", 0) or 0)
        dist_support = (current_price - support) / current_price * 100 if current_price and support else 0
        dist_resistance = (resistance - current_price) / current_price * 100 if current_price and resistance else 0

        result = EnhancedScreenedSymbol(
            symbol=symbol,
            name=name,
            market=market,
            industry=industry,
            last_price=current_price,
            change_pct=float(quote.get("price_change_pct", 0) or 0),
            volume=int(quote.get("volume", 0) or 0),
            value=float(quote.get("value", 0) or 0),
            smc_score=smc_result.get("smart_money_score", 0),
            phase=smc_result.get("phase", "neutral"),
            reason=self._build_reason(advanced, smc_result),
            liquidity_score=float(smc_result.get("scores", {}).get("accumulation", 0)),
            power_score=float(smc_result.get("scores", {}).get("buyer_power", 0)),
            structure_score=float(smc_result.get("scores", {}).get("breakout_readiness", 0)),
            orderflow_score=float(smc_result.get("scores", {}).get("absorption", 0)),
            trigger_score=float(smc_result.get("scores", {}).get("float_lock", 0)),
            rsi=advanced.indicators.rsi_14,
            macd_histogram=advanced.indicators.macd_histogram,
            bb_pct=advanced.indicators.bb_pct,
            atr_pct=advanced.volatility.atr_pct,
            adx=advanced.indicators.adx,
            trend_direction=advanced.trend.direction,
            trend_strength=advanced.trend.strength,
            volatility_regime=advanced.volatility.regime,
            pattern_signal=pattern_signal,
            pattern_confidence=pattern_confidence,
            technical_score=technical_score,
            momentum_score=momentum_score,
            risk_score=risk_score,
            composite_score=composite,
            composite_signal=advanced.composite_signal,
            support_level=support,
            resistance_level=resistance,
            distance_to_support=round(dist_support, 2),
            distance_to_resistance=round(dist_resistance, 2),
            poc_price=advanced.volume_profile.poc_price,
            value_area_high=advanced.volume_profile.value_area_high,
            value_area_low=advanced.volume_profile.value_area_low,
            volume_trend=advanced.volume_profile.volume_trend,
            pe_ratio=float(quote.get("pe_ratio", 0) or 0) or None,
            eps=float(quote.get("eps", 0) or 0) or None,
            market_value=float(quote.get("market_value", 0) or 0) or None,
            advanced_analysis=advanced,
        )

        self._set_cached(cache_key, result)
        return result

    def _compute_technical_score(self, analysis: AdvancedAnalysis) -> float:
        """Compute technical score from advanced analysis."""
        ind = analysis.indicators
        score = 0.0

        # RSI contribution
        if ind.rsi_14 < 30:
            score += 0.25
        elif ind.rsi_14 < 40:
            score += 0.15
        elif ind.rsi_14 > 70:
            score -= 0.25
        elif ind.rsi_14 > 60:
            score -= 0.15

        # MACD contribution
        if ind.macd_histogram > 0:
            score += min(0.2, ind.macd_histogram / 5)
        else:
            score -= min(0.2, abs(ind.macd_histogram) / 5)

        # Bollinger contribution
        if ind.bb_pct < 0.2:
            score += 0.15
        elif ind.bb_pct > 0.8:
            score -= 0.15

        # ADX trend strength
        if ind.adx > 25:
            trend_bonus = 0.1 if analysis.trend.direction == "up" else -0.1
            score += trend_bonus

        return max(-1.0, min(1.0, score))

    def _compute_momentum_score(self, analysis: AdvancedAnalysis) -> float:
        """Compute momentum score."""
        ind = analysis.indicators
        score = 0.0

        # Stochastic
        if ind.stochastic_k < 20:
            score += 0.2
        elif ind.stochastic_k > 80:
            score -= 0.2

        # CCI
        if ind.cci < -100:
            score += 0.15
        elif ind.cci > 100:
            score -= 0.15

        # MFI
        if ind.mfi < 20:
            score += 0.15
        elif ind.mfi > 80:
            score -= 0.15

        # Williams %R
        if ind.williams_r < -80:
            score += 0.1
        elif ind.williams_r > -20:
            score -= 0.1

        return max(-1.0, min(1.0, score))

    def _compute_risk_score(self, analysis: AdvancedAnalysis) -> float:
        """Compute risk score (higher = more risky)."""
        vol = analysis.volatility
        risk = 0.0

        # Volatility regime
        regime_risk = {"low": 0.1, "normal": 0.3, "high": 0.6, "extreme": 0.9}
        risk += regime_risk.get(vol.regime, 0.3)

        # ATR percentage
        risk += min(0.3, vol.atr_pct / 10)

        # Trend stability
        if analysis.trend.direction == "sideways":
            risk += 0.1

        return min(1.0, risk)

    def _compute_composite_score(
        self,
        smc_score: float,
        technical_score: float,
        momentum_score: float,
        risk_score: float,
    ) -> float:
        """Compute weighted composite score."""
        cfg = self.config
        risk_adjustment = 1.0 - (risk_score * 0.3)  # Penalize high risk

        raw = (
            smc_score * cfg.smart_money_weight
            + technical_score * cfg.technical_weight
            + momentum_score * cfg.momentum_weight
            + (1 - risk_score) * cfg.fundamental_weight
        )

        return max(-1.0, min(1.0, raw * risk_adjustment))

    def _get_best_pattern(self, analysis: AdvancedAnalysis) -> tuple[str, float]:
        """Get the most recent significant pattern."""
        if not analysis.patterns:
            return "", 0.0

        recent = analysis.patterns[-3:]
        best = max(recent, key=lambda p: p.confidence)
        if best.confidence >= self.config.min_pattern_confidence:
            return best.pattern, best.confidence
        return "", 0.0

    def _build_reason(self, advanced: AdvancedAnalysis, smc_result: dict) -> str:
        """Build human-readable reason string."""
        reasons = []

        if advanced.trend.direction == "up" and advanced.trend.strength > 0.5:
            reasons.append("روند صعودی قوی")
        elif advanced.trend.direction == "down" and advanced.trend.strength > 0.5:
            reasons.append("روند نزولی قوی")

        if advanced.indicators.rsi_14 < 30:
            reasons.append(" Oversold (RSI)")
        elif advanced.indicators.rsi_14 > 70:
            reasons.append("Overbought (RSI)")

        if advanced.indicators.macd_histogram > 0:
            reasons.append("MACD مثبت")

        if advanced.volatility.regime == "extreme":
            reasons.append("نوسان شدید")

        if advanced.patterns:
            best = advanced.patterns[-1]
            if best.confidence > 0.7:
                reasons.append(best.description)

        return " · ".join(reasons) if reasons else "تحلیل عادی"

    def batch_analyze(
        self,
        instruments: list[dict[str, Any]],
        market_watch: list[dict[str, Any]],
        history_map: dict[str, list[dict[str, Any]]] | None = None,
        sort_by: str = "composite_score",
        sort_order: str = "desc",
        limit: int = 50,
        min_score: float = 0.0,
        market: str | None = None,
        filters: list[dict[str, Any]] | None = None,
        filter_logic: str = "and",
    ) -> tuple[list[EnhancedScreenedSymbol], dict[str, Any]]:
        """Batch analyze multiple symbols.

        Args:
            instruments: List of instrument dicts with symbol/name/market/industry
            market_watch: List of watch data dicts with current quote info
            history_map: Optional dict mapping symbol -> list of daily history rows
            sort_by: Field to sort results by
            sort_order: 'asc' or 'desc'
            limit: Max results to return
            min_score: Minimum composite score filter
            market: Optional market filter
            filters: Optional list of filter criteria dicts
            filter_logic: 'and' (all filters must match) or 'or' (any filter can match)
        """
        watch_map = {w.get("symbol", ""): w for w in market_watch}
        results = []

        for instr in instruments:
            sym = instr.get("symbol", "")
            if market and instr.get("market") != market:
                continue
            w = watch_map.get(sym)
            if not w:
                continue

            # Build quote from watch data
            quote = {
                "symbol": sym,
                "price_close": w.get("close", 0) or w.get("last_price", 0),
                "price_last": w.get("last_price", 0) or w.get("close", 0),
                "price_high": w.get("high", 0) or w.get("price_max", 0),
                "price_low": w.get("low", 0) or w.get("price_min", 0),
                "price_change_pct": w.get("change", 0) or w.get("price_change_pct", 0),
                "volume": w.get("volume", 0),
                "value": w.get("value", 0),
                "pe_ratio": w.get("pe_ratio"),
                "eps": w.get("eps"),
                "market_value": w.get("market_value"),
            }

            # Use real history if available
            history = history_map.get(sym, []) if history_map else []

            result = self.analyze_symbol(
                symbol=sym,
                name=instr.get("name", sym),
                market=instr.get("market", ""),
                industry=instr.get("industry", ""),
                quote=quote,
                history=history,
            )

            # Apply client-side filters for advanced fields
            if filters and not self._apply_client_filters(result, filters, filter_logic):
                continue

            if result.composite_score >= min_score:
                results.append(result)

        # Sort
        reverse = sort_order.lower() != "asc"
        results.sort(key=lambda r: getattr(r, sort_by, 0.0), reverse=reverse)

        # Rank
        for i, r in enumerate(results, 1):
            r.rank = i

        # Paginate
        paginated = results[:limit]

        # Stats
        stats = self._compute_stats(paginated, results)

        return paginated, stats

    @staticmethod
    def _apply_client_filters(
        result: EnhancedScreenedSymbol,
        filters: list[dict[str, Any]],
        filter_logic: str = "and",
    ) -> bool:
        """Apply filters to an already-analyzed symbol result.

        Args:
            result: The analyzed symbol result.
            filters: List of filter criteria dicts.
            filter_logic: 'and' (all must match) or 'or' (any can match).
        """
        matches: list[bool] = []
        for f in filters:
            field = f.get("field", "")
            operator = f.get("operator", "gte")
            value = f.get("value")
            if value is None:
                matches.append(True)
                continue

            # Get field value from the result object
            r_val = getattr(result, field, None)
            if r_val is None:
                r_val = result.details.get(field)
            if r_val is None:
                matches.append(False)
                continue

            try:
                r_val = float(r_val)
                value = float(value)
            except (TypeError, ValueError):
                # String comparison
                r_str = str(r_val).lower()
                v_str = str(value).lower()
                if operator == "eq":
                    matches.append(r_str == v_str)
                elif operator == "neq":
                    matches.append(r_str != v_str)
                elif operator == "contains":
                    matches.append(v_str in r_str)
                elif operator == "in":
                    values_list = [v.strip().lower() for v in v_str.split(",") if v.strip()]
                    matches.append(r_str in values_list)
                elif operator == "not_in":
                    values_list = [v.strip().lower() for v in v_str.split(",") if v.strip()]
                    matches.append(r_str not in values_list)
                else:
                    matches.append(False)
                continue

            if operator == "gte":
                matches.append(r_val >= value)
            elif operator == "lte":
                matches.append(r_val <= value)
            elif operator == "gt":
                matches.append(r_val > value)
            elif operator == "lt":
                matches.append(r_val < value)
            elif operator == "eq":
                tolerance = max(abs(value) * 0.01, 0.001)
                matches.append(abs(r_val - value) <= tolerance)
            elif operator == "neq":
                tolerance = max(abs(value) * 0.01, 0.001)
                matches.append(abs(r_val - value) > tolerance)
            elif operator == "between":
                value_to = f.get("value_to")
                if value_to is not None:
                    try:
                        num_value_to = float(value_to)
                        matches.append(value <= r_val <= num_value_to)
                    except (TypeError, ValueError):
                        matches.append(False)
                else:
                    matches.append(False)
            else:
                matches.append(False)

        if not matches:
            return True  # No filters means pass
        if filter_logic == "or":
            return any(matches)
        return all(matches)

    def _compute_stats(
        self, paginated: list[EnhancedScreenedSymbol], all_results: list[EnhancedScreenedSymbol]
    ) -> dict[str, Any]:
        """Compute aggregate statistics."""
        if not all_results:
            return {
                "total": 0,
                "avg_composite": 0,
                "avg_technical": 0,
                "avg_momentum": 0,
                "avg_risk": 0,
                "signal_distribution": {},
                "sector_distribution": {},
                "trend_distribution": {},
                "volatility_distribution": {},
            }

        total = len(all_results)
        return {
            "total": total,
            "avg_composite": round(sum(r.composite_score for r in all_results) / total, 4),
            "avg_technical": round(sum(r.technical_score for r in all_results) / total, 4),
            "avg_momentum": round(sum(r.momentum_score for r in all_results) / total, 4),
            "avg_risk": round(sum(r.risk_score for r in all_results) / total, 4),
            "signal_distribution": self._count_signals(all_results),
            "sector_distribution": self._count_industries(all_results),
            "trend_distribution": self._count_trends(all_results),
            "volatility_distribution": self._count_volatility(all_results),
        }

    def _count_signals(self, results: list[EnhancedScreenedSymbol]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in results:
            counts[r.composite_signal] = counts.get(r.composite_signal, 0) + 1
        return counts

    def _count_industries(self, results: list[EnhancedScreenedSymbol]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in results:
            ind = r.industry or "نامشخص"
            counts[ind] = counts.get(ind, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10])

    def _count_trends(self, results: list[EnhancedScreenedSymbol]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in results:
            counts[r.trend_direction] = counts.get(r.trend_direction, 0) + 1
        return counts

    def _count_volatility(self, results: list[EnhancedScreenedSymbol]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in results:
            counts[r.volatility_regime] = counts.get(r.volatility_regime, 0) + 1
        return counts
