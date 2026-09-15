"""Risk-Adjusted Signal Filter — filters and adjusts signals based on risk metrics.

Applies multiple risk checks before accepting a signal:
  - CVaR (Conditional Value at Risk) — expected loss in worst 5% scenarios
  - Max drawdown — estimated maximum decline
  - Volatility regime — is current volatility acceptable?
  - Position sizing — risk-based capital allocation
  - Correlation check — avoid correlated bets
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RiskMetrics:
    """Risk metrics for a single symbol."""

    symbol: str
    market: str
    daily_volatility: float = 0.0
    annualized_volatility: float = 0.0
    cvar_95: float = 0.0  # Expected shortfall at 95% confidence
    max_drawdown_90d: float = 0.0
    var_95: float = 0.0  # Value at Risk at 95%
    sharpe_90d: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0
    is_acceptable: bool = True
    risk_score: float = 0.5  # 0-1, higher = riskier

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "market": self.market,
            "daily_volatility_pct": round(self.daily_volatility * 100, 2),
            "annualized_volatility_pct": round(self.annualized_volatility * 100, 2),
            "cvar_95_pct": round(self.cvar_95 * 100, 2),
            "max_drawdown_90d_pct": round(self.max_drawdown_90d * 100, 2),
            "var_95_pct": round(self.var_95 * 100, 2),
            "sharpe_90d": round(self.sharpe_90d, 3),
            "risk_score": round(self.risk_score, 3),
            "is_acceptable": self.is_acceptable,
        }


@dataclass
class FilteredSignal:
    """A signal after passing through the risk filter."""

    original_signal: dict[str, Any]
    risk_metrics: RiskMetrics
    is_passed: bool
    rejection_reason: str | None = None
    adjusted_position_size: float = 0.0  # fraction of max position
    adjusted_score: float = 0.0  # score after risk adjustment
    adjusted_confidence: float = 0.0  # confidence after risk adjustment

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.original_signal.get("symbol", ""),
            "market": self.original_signal.get("market", ""),
            "direction": self.original_signal.get("direction", ""),
            "is_passed": self.is_passed,
            "rejection_reason": self.rejection_reason,
            "adjusted_position_size": round(self.adjusted_position_size, 3),
            "adjusted_score": round(self.adjusted_score, 2),
            "adjusted_confidence": round(self.adjusted_confidence, 3),
            "risk_metrics": self.risk_metrics.to_dict(),
        }


class RiskAdjustedFilter:
    """Risk filter for signals — ensures only acceptable-risk trades pass."""

    # Risk thresholds
    MAX_DAILY_VOLATILITY = 0.05  # 5% daily vol max
    MAX_CVAR = 0.08  # 8% CVaR max
    MAX_DRAWDOWN_90D = 0.25  # 25% drawdown max
    MIN_SHARPE = -0.5  # Minimum Sharpe ratio
    MAX_CORRELATION = 0.80  # Max correlation with existing positions

    # Position sizing
    BASE_POSITION_FRACTION = 0.03  # 3% of capital per trade
    MAX_POSITION_FRACTION = 0.10  # 10% max per trade

    def __init__(self, session: Any = None) -> None:
        self._session = session

    async def filter_signal(
        self,
        signal: dict[str, Any],
        portfolio_holdings: list[dict[str, Any]] | None = None,
        risk_tolerance: str = "moderate",
    ) -> FilteredSignal:
        """Apply risk filter to a single signal.

        Args:
            signal: the signal dict (must have symbol, market, direction, score, confidence)
            portfolio_holdings: current portfolio holdings for correlation check
            risk_tolerance: conservative / moderate / aggressive

        Returns:
            FilteredSignal with pass/fail and adjusted metrics
        """
        symbol = signal.get("symbol", "")
        market = signal.get("market", "stock")

        # 1. Compute risk metrics
        risk_metrics = await self._compute_risk_metrics(symbol, market)

        if not risk_metrics:
            # Can't compute risk — pass with reduced confidence
            return FilteredSignal(
                original_signal=signal,
                risk_metrics=RiskMetrics(symbol=symbol, market=market),
                is_passed=True,
                adjusted_position_size=self.BASE_POSITION_FRACTION,
                adjusted_score=signal.get("score", 50),
                adjusted_confidence=signal.get("confidence", 0.5) * 0.8,
            )

        # 2. Apply risk thresholds based on tolerance
        if risk_tolerance == "conservative":
            max_vol = self.MAX_DAILY_VOLATILITY * 0.6
            max_cvar = self.MAX_CVAR * 0.6
            max_dd = self.MAX_DRAWDOWN_90D * 0.6
        elif risk_tolerance == "aggressive":
            max_vol = self.MAX_DAILY_VOLATILITY * 1.5
            max_cvar = self.MAX_CVAR * 1.5
            max_dd = self.MAX_DRAWDOWN_90D * 1.5
        else:
            max_vol = self.MAX_DAILY_VOLATILITY
            max_cvar = self.MAX_CVAR
            max_dd = self.MAX_DRAWDOWN_90D

        # 3. Check each risk metric
        rejection_reason = None

        if risk_metrics.daily_volatility > max_vol:
            rejection_reason = (
                f"نوسان بالا: {risk_metrics.daily_volatility * 100:.1f}% (حداکثر مجاز: {max_vol * 100:.1f}%)"
            )
        elif risk_metrics.cvar_95 > max_cvar:
            rejection_reason = f"CVaR بالا: {risk_metrics.cvar_95 * 100:.1f}% (حداکثر مجاز: {max_cvar * 100:.1f}%)"
        elif risk_metrics.max_drawdown_90d > max_dd:
            rejection_reason = (
                f"Drawdown بالا: {risk_metrics.max_drawdown_90d * 100:.1f}% (حداکثر مجاز: {max_dd * 100:.1f}%)"
            )
        elif risk_metrics.sharpe_90d < self.MIN_SHARPE:
            rejection_reason = f"Sharpe پایین: {risk_metrics.sharpe_90d:.2f}"

        # 4. Correlation check with portfolio
        if not rejection_reason and portfolio_holdings:
            correlation = await self._check_correlation(symbol, portfolio_holdings)
            if correlation > self.MAX_CORRELATION:
                rejection_reason = "همبستگی بالا با دارایی‌های فعلی"

        # 5. Position sizing
        if rejection_reason:
            risk_metrics.is_acceptable = False
            return FilteredSignal(
                original_signal=signal,
                risk_metrics=risk_metrics,
                is_passed=False,
                rejection_reason=rejection_reason,
                adjusted_position_size=0,
                adjusted_score=0,
                adjusted_confidence=0,
            )

        # Compute adjusted position size
        position_fraction = self._compute_position_size(
            risk_metrics, signal.get("score", 50) / 100.0, signal.get("confidence", 0.5), risk_tolerance
        )

        # Score and confidence adjustments
        risk_penalty = risk_metrics.risk_score * 0.2  # up to 20% penalty
        adjusted_score = signal.get("score", 50) * (1 - risk_penalty)
        adjusted_confidence = signal.get("confidence", 0.5) * (1 - risk_penalty * 0.5)

        return FilteredSignal(
            original_signal=signal,
            risk_metrics=risk_metrics,
            is_passed=True,
            adjusted_position_size=position_fraction,
            adjusted_score=max(0, adjusted_score),
            adjusted_confidence=max(0.1, adjusted_confidence),
        )

    async def _compute_risk_metrics(self, symbol: str, market: str) -> RiskMetrics | None:
        """Compute risk metrics from historical price data."""
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            if async_session_factory is None:
                return None

            async with async_session_factory() as session:
                table_map = {
                    "stock": "brsapi_historical_daily",
                    "gold": "brsapi_gold_coin_history",
                    "currency": "brsapi_currency_history",
                    "crypto": "brsapi_gold_currency_pro_daily_history",
                }
                table = table_map.get(market, "brsapi_historical_daily")

                r = await session.execute(
                    text(f"""
                    SELECT price_close, price_max, price_min
                    FROM {table}
                    WHERE symbol = :symbol AND price_close > 0
                    ORDER BY date DESC
                    LIMIT 100
                """),
                    {"symbol": symbol},
                )

                rows = r.fetchall()
                if len(rows) < 20:
                    return None

                closes = [float(row[0]) for row in reversed(rows) if row[0] > 0]

                if len(closes) < 20:
                    return None

                # Daily returns
                returns = [(closes[i] - closes[i - 1]) / max(closes[i - 1], 0.001) for i in range(1, len(closes))]

                if not returns:
                    return None

                returns_arr = np.array(returns)

                # Metrics
                daily_vol = float(np.std(returns_arr, ddof=1))
                annual_vol = daily_vol * np.sqrt(252)

                # VaR and CVaR at 95%
                sorted_returns = np.sort(returns_arr)
                var_idx = max(1, int(len(sorted_returns) * 0.05))
                var_95 = float(sorted_returns[var_idx - 1])
                cvar_95 = float(np.mean(sorted_returns[:var_idx]))

                # Max drawdown
                cumulative = np.cumprod(1 + returns_arr)
                peak = np.maximum.accumulate(cumulative)
                drawdowns = (peak - cumulative) / np.maximum(peak, 0.001)
                max_dd = float(np.max(drawdowns))

                # Sharpe
                mean_ret = float(np.mean(returns_arr))
                sharpe = mean_ret / max(daily_vol, 0.0001) * np.sqrt(252)

                # Skewness and Kurtosis
                n = len(returns_arr)
                if n > 2:
                    skew = float(
                        n * np.sum((returns_arr - mean_ret) ** 3) / ((n - 1) * (n - 2) * max(daily_vol**3, 0.0001))
                    )
                    kurt = float(
                        (
                            n
                            * (n + 1)
                            * np.sum((returns_arr - mean_ret) ** 4)
                            / ((n - 1) * (n - 2) * (n - 3) * max(daily_vol**4, 0.0001))
                        )
                        - (3 * (n - 1) ** 2 / ((n - 2) * (n - 3)))
                    )
                else:
                    skew = 0.0
                    kurt = 0.0

                # Composite risk score (0-1)
                vol_score = min(1.0, daily_vol / self.MAX_DAILY_VOLATILITY)
                cvar_score = min(1.0, abs(cvar_95) / self.MAX_CVAR)
                dd_score = min(1.0, max_dd / self.MAX_DRAWDOWN_90D)
                risk_score = vol_score * 0.4 + cvar_score * 0.3 + dd_score * 0.3

                return RiskMetrics(
                    symbol=symbol,
                    market=market,
                    daily_volatility=daily_vol,
                    annualized_volatility=annual_vol,
                    cvar_95=cvar_95,
                    max_drawdown_90d=max_dd,
                    var_95=var_95,
                    sharpe_90d=sharpe,
                    skewness=skew,
                    kurtosis=kurt,
                    risk_score=risk_score,
                    is_acceptable=risk_score < 0.6,
                )

        except Exception as e:
            logger.debug("Could not compute risk for %s: %s", symbol, e)
            return None

    async def _check_correlation(self, symbol: str, holdings: list[dict[str, Any]]) -> float:
        """Check correlation of new symbol with existing holdings."""
        if not holdings:
            return 0.0

        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            if async_session_factory is None:
                return 0.0

            async with async_session_factory() as session:
                # Get returns for new symbol
                r1 = await session.execute(
                    text("""
                    SELECT price_close FROM brsapi_historical_daily
                    WHERE symbol = :symbol AND price_close > 0
                    ORDER BY date DESC LIMIT 60
                """),
                    {"symbol": symbol},
                )
                new_closes = [float(row[0]) for row in reversed(r1.fetchall()) if row[0] > 0]
                if len(new_closes) < 20:
                    return 0.0
                new_returns = [
                    (new_closes[i] - new_closes[i - 1]) / max(new_closes[i - 1], 0.001)
                    for i in range(1, len(new_closes))
                ]

                max_corr = 0.0
                for holding in holdings[:5]:  # check top 5 holdings
                    h_symbol = holding.get("symbol", "")
                    if not h_symbol:
                        continue
                    r2 = await session.execute(
                        text("""
                        SELECT price_close FROM brsapi_historical_daily
                        WHERE symbol = :symbol AND price_close > 0
                        ORDER BY date DESC LIMIT 60
                    """),
                        {"symbol": h_symbol},
                    )
                    h_closes = [float(row[0]) for row in reversed(r2.fetchall()) if row[0] > 0]
                    if len(h_closes) < 20:
                        continue
                    h_returns = [
                        (h_closes[i] - h_closes[i - 1]) / max(h_closes[i - 1], 0.001) for i in range(1, len(h_closes))
                    ]

                    # Align lengths
                    min_len = min(len(new_returns), len(h_returns))
                    if min_len < 10:
                        continue

                    corr = float(np.corrcoef(new_returns[-min_len:], h_returns[-min_len:])[0, 1])
                    max_corr = max(max_corr, abs(corr))

                return max_corr

        except Exception as e:
            logger.debug("Correlation check failed: %s", e)
            return 0.0

    @staticmethod
    def _compute_position_size(
        risk: RiskMetrics,
        signal_score: float,
        confidence: float,
        risk_tolerance: str,
    ) -> float:
        """Compute position size as fraction of max position."""
        risk_penalty = 1.0 - risk.risk_score * 0.5  # 0.5 to 1.0
        score_factor = signal_score  # 0-1
        confidence_factor = confidence  # 0-1

        # Combine factors
        raw_size = risk_penalty * 0.4 + score_factor * 0.3 + confidence_factor * 0.3

        # Scale based on risk tolerance
        tolerance_factors = {
            "conservative": 0.5,
            "moderate": 1.0,
            "aggressive": 1.5,
        }
        scale = tolerance_factors.get(risk_tolerance, 1.0)

        return min(
            raw_size * scale * RiskAdjustedFilter.BASE_POSITION_FRACTION, RiskAdjustedFilter.MAX_POSITION_FRACTION
        )

    async def filter_batch(
        self,
        signals: list[dict[str, Any]],
        portfolio_holdings: list[dict[str, Any]] | None = None,
        risk_tolerance: str = "moderate",
    ) -> list[FilteredSignal]:
        """Apply risk filter to a batch of signals."""
        results: list[FilteredSignal] = []

        for signal in signals:
            result = await self.filter_signal(
                signal=signal,
                portfolio_holdings=portfolio_holdings,
                risk_tolerance=risk_tolerance,
            )
            results.append(result)

        # Sort: passed signals first, then by adjusted score
        results.sort(key=lambda r: (r.is_passed, r.adjusted_score), reverse=True)

        return results
