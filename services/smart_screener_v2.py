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

import time
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger
from services.smart_money.advanced_analytics import AdvancedAnalysis, AdvancedAnalyticsEngine
from services.smart_money.scoring_engine import ScoringEngine

logger = get_logger(__name__)

#: Categorical value for an analytics field the history was too short to measure. Distinct
#: from ``"sideways"``/``"normal"``/``"neutral"``, which are readings, not absences.
NOT_MEASURED = "not_measured"


def _as_sort_value(value: Any) -> Any:
    """Numeric where it can be, otherwise a string — so one column never mixes types."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


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

    # Advanced analytics. Every numeric here is ``None`` when the history was too short to
    # measure it: these fields used to default to 0.0, and 0.0 is a real reading for several
    # of them (RSI 0 = maximum oversold, %B 0 = a close sitting on the lower band), so an
    # unmeasured symbol was being ranked as a buy opportunity by the absence of data. The
    # categoricals use ``NOT_MEASURED`` for the same reason — "sideways" is a claim about the
    # trend, not a statement that no trend was computed.
    rsi: float | None = None
    macd_histogram: float | None = None
    bb_pct: float | None = None
    atr_pct: float | None = None
    adx: float | None = None
    trend_direction: str = NOT_MEASURED
    trend_strength: float | None = None
    volatility_regime: str = NOT_MEASURED

    # Pattern signals
    pattern_signal: str = ""
    pattern_confidence: float | None = None

    # Composite scores
    technical_score: float | None = None
    momentum_score: float | None = None
    risk_score: float | None = None
    composite_score: float = 0.0
    composite_signal: str = NOT_MEASURED

    # Support/Resistance
    support_level: float | None = None
    resistance_level: float | None = None
    distance_to_support: float | None = None
    distance_to_resistance: float | None = None

    # Volume profile
    poc_price: float | None = None
    value_area_high: float | None = None
    value_area_low: float | None = None
    volume_trend: str = NOT_MEASURED

    # Fundamental
    pe_ratio: float | None = None
    eps: float | None = None
    market_value: float | None = None

    # Analytics provenance: why the ``None``s above are ``None`` — shown next to them so the
    # reader sees «۱۸ کندل» rather than an unexplained blank.
    analytics_bars: int = 0
    analytics_computed: bool = True

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

        # Step 6: Support/Resistance — a missing level is None, not 0.0: a support at price
        # zero is a number the UI would happily turn into a "+∞% above support" distance.
        measured = advanced.indicators.computed
        sr_levels = advanced.support_resistance
        support = next((lv.level for lv in sr_levels if lv.type == "support"), None) if measured else None
        resistance = next((lv.level for lv in sr_levels if lv.type == "resistance"), None) if measured else None

        current_price = float(quote.get("price_close", 0) or 0)
        dist_support = (
            round((current_price - support) / current_price * 100, 2)
            if measured and current_price and support
            else None
        )
        dist_resistance = (
            round((resistance - current_price) / current_price * 100, 2)
            if measured and current_price and resistance
            else None
        )

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
            analytics_bars=advanced.indicators.bars,
            analytics_computed=measured,
            rsi=advanced.indicators.rsi_14 if measured else None,
            macd_histogram=advanced.indicators.macd_histogram if measured else None,
            bb_pct=advanced.indicators.bb_pct if measured else None,
            atr_pct=advanced.volatility.atr_pct if measured else None,
            adx=advanced.indicators.adx if measured else None,
            trend_direction=advanced.trend.direction if measured else NOT_MEASURED,
            trend_strength=advanced.trend.strength if measured else None,
            volatility_regime=advanced.volatility.regime if measured else NOT_MEASURED,
            pattern_signal=pattern_signal,
            pattern_confidence=pattern_confidence if measured else None,
            technical_score=technical_score,
            momentum_score=momentum_score,
            risk_score=risk_score,
            composite_score=composite,
            composite_signal=advanced.composite_signal if measured else NOT_MEASURED,
            support_level=support,
            resistance_level=resistance,
            distance_to_support=dist_support,
            distance_to_resistance=dist_resistance,
            poc_price=advanced.volume_profile.poc_price if measured else None,
            value_area_high=advanced.volume_profile.value_area_high if measured else None,
            value_area_low=advanced.volume_profile.value_area_low if measured else None,
            volume_trend=advanced.volume_profile.volume_trend if measured else NOT_MEASURED,
            pe_ratio=float(quote.get("pe_ratio", 0) or 0) or None,
            eps=float(quote.get("eps", 0) or 0) or None,
            market_value=float(quote.get("market_value", 0) or 0) or None,
            advanced_analysis=advanced,
        )

        self._set_cached(cache_key, result)
        return result

    def _compute_technical_score(self, analysis: AdvancedAnalysis) -> float | None:
        """Compute technical score from advanced analysis, or ``None`` if not measurable."""
        ind = analysis.indicators
        if not ind.computed:
            return None
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

    def _compute_momentum_score(self, analysis: AdvancedAnalysis) -> float | None:
        """Compute momentum score, or ``None`` if not measurable."""
        ind = analysis.indicators
        if not ind.computed:
            return None
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

    def _compute_risk_score(self, analysis: AdvancedAnalysis) -> float | None:
        """Compute risk score (higher = more risky), or ``None`` if not measurable.

        Every input below is an analytics output — regime, ATR, trend stability — so below
        the compute window there is no risk reading to report, only a guess.
        """
        if not analysis.indicators.computed:
            return None
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
        technical_score: float | None,
        momentum_score: float | None,
        risk_score: float | None,
    ) -> float:
        """Weighted composite over the legs that were actually measured.

        ``fundamental_weight`` is applied to ``1 - risk_score``: the configuration name is
        older than this formula and there is no fundamental input in it. It stays a risk
        inversion — renaming the arithmetic would change every rank in the screener — but it
        is no longer described as a fundamental leg.

        A leg arrives as ``None`` when the history was too short to compute it; its weight is
        then dropped and the rest renormalised. Scoring an unmeasured leg as 0.0 let a
        three-week-old symbol inherit a penalty or a bonus from data that does not exist.
        """

        cfg = self.config
        contributions: dict[str, float] = {"smart_money": smc_score}
        weights: dict[str, float] = {"smart_money": cfg.smart_money_weight}
        if technical_score is not None:
            contributions["technical"] = technical_score
            weights["technical"] = cfg.technical_weight
        if momentum_score is not None:
            contributions["momentum"] = momentum_score
            weights["momentum"] = cfg.momentum_weight
        if risk_score is not None:
            contributions["risk_inversion"] = 1 - risk_score
            weights["risk_inversion"] = cfg.fundamental_weight

        total_weight = sum(weights.values())
        if total_weight <= 0:
            return 0.0
        raw = sum(contributions[name] * weights[name] for name in weights) / total_weight

        risk_adjustment = 1.0 if risk_score is None else 1.0 - (risk_score * 0.3)
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
        """Build human-readable reason string.

        Below the compute window the sentence is the count of candles, not "تحلیل عادی":
        calling an unanalysed symbol "normal" is the same fabricated reading as RSI 0.
        """
        ind = advanced.indicators
        if not ind.computed:
            bars = ind.bars
            return (
                "داده کافی برای تحلیل تکنیکال نیست (کمتر از ۵ کندل)"
                if bars < 5
                else f"تاریخچه کوتاه: {bars} کندل، اندیکاتورها محاسبه نشده‌اند"
            )

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

        return " · ".join(reasons) if reasons else "هیچ شرط برجسته‌ای در داده‌های محاسبه‌شده دیده نشد"

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

        # Sort. Unmeasured values sort last in both directions: ``None`` is not the smallest
        # number, and treating it as one would push every short-history symbol to the top of
        # an ascending sort.
        reverse = sort_order.lower() != "asc"
        measured_rows = [r for r in results if getattr(r, sort_by, None) is not None]
        unmeasured_rows = [r for r in results if getattr(r, sort_by, None) is None]
        measured_rows.sort(key=lambda r: _as_sort_value(getattr(r, sort_by)), reverse=reverse)
        results = measured_rows + unmeasured_rows

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
        """Compute aggregate statistics.

        Averages are taken over the symbols that actually have the leg measured, and the
        measured/unmeasured split is reported next to them: an average of nothing is ``None``,
        not 0, because 0 would read as "the market scored zero".
        """
        total = len(all_results)

        def _avg(field: str) -> float | None:
            vals = [getattr(r, field) for r in all_results if getattr(r, field) is not None]
            return round(sum(vals) / len(vals), 4) if vals else None

        measured = sum(1 for r in all_results if r.analytics_computed)
        return {
            "total": total,
            "avg_composite": _avg("composite_score"),
            "avg_technical": _avg("technical_score"),
            "avg_momentum": _avg("momentum_score"),
            "avg_risk": _avg("risk_score"),
            "analyticsMeasured": measured,
            "analyticsNotMeasured": total - measured,
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
