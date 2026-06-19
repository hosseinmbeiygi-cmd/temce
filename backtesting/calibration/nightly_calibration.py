from __future__ import annotations

from datetime import date
from typing import Any

from backtesting.calibration.impact_calibration import calibrate_impact, estimate_cancel_rate, estimate_spread_pct
from backtesting.calibration.liquidity_depth_model import LiquidityDepthModel
from backtesting.calibration.order_arrival import estimate_trade_intensity, estimate_trade_rate_per_min
from backtesting.calibration.order_size_distribution import (
    estimate_adv,
    estimate_avg_trade_size,
    fit_order_size_distribution,
)
from backtesting.calibration.parameter_store import MarketParameters, ParameterStore
from backtesting.calibration.regime_transition import default_transition_matrix
from backtesting.calibration.validation import SimulationValidator
from backtesting.microstructure.calibration import MicrostructureCalibrator
from core.logging import get_logger

logger = get_logger(__name__)


class NightlyCalibrationPipeline:
    """Pipeline that runs nightly to calibrate market parameters from real data.

    Flow:
    1. Load real market data (trades, quotes)
    2. Extract microstructure features
    3. Estimate parameters (arrival rate, impact, liquidity, etc.)
    4. Store versioned parameters
    5. Validate simulation against real data
    """

    def __init__(self, parameter_store: ParameterStore | None = None) -> None:
        self.parameter_store = parameter_store or ParameterStore()
        self.micro_calibrator = MicrostructureCalibrator()
        self.validator = SimulationValidator()
        self._last_results: dict[str, Any] = {}

    def run(
        self,
        symbol: str,
        trades: list[dict[str, Any]],
        quotes: list[dict[str, Any]],
        calibration_date: str | None = None,
    ) -> MarketParameters:
        """Run the full calibration pipeline for a single symbol.

        Args:
            symbol: Symbol name
            trades: List of trade dicts
            quotes: List of quote dicts
            calibration_date: Date string (defaults to today)

        Returns:
            Calibrated MarketParameters
        """
        cal_date = calibration_date or date.today().isoformat()
        logger.info("Calibrating %s for %s", symbol, cal_date)

        # Step 1: Microstructure calibration (reuse existing calibrator)
        micro_params = self.micro_calibrator.calibrate_from_events(symbol, quotes, trades)

        # Step 2: Order arrival
        arrival_rate = estimate_trade_intensity(trades)
        trade_rate_min = estimate_trade_rate_per_min(trades)

        # Step 3: Order size distribution
        trade_sizes = [t.get("volume", 0) or t.get("quantity", 0) for t in trades if (t.get("volume", 0) or t.get("quantity", 0)) > 0]
        size_dist = fit_order_size_distribution(trade_sizes)

        # Step 4: ADV and average trade size
        adv = estimate_adv(trades)
        avg_trade_size = estimate_avg_trade_size(trades)

        # Step 5: Market impact parameters
        price_moves: list[float] = []
        trade_size_for_impact: list[float] = []
        for i in range(1, min(len(trades), 5000)):
            prev_price = trades[i - 1].get("price", 0) or 0
            curr_price = trades[i].get("price", 0) or 0
            if prev_price > 0:
                move = abs(curr_price - prev_price) / prev_price
                if 0 < move < 0.1:
                    price_moves.append(move)
                    trade_size_for_impact.append(float(trades[i].get("volume", 0) or 0))

        eta, alpha = calibrate_impact(trade_size_for_impact, price_moves, adv)

        # Step 6: Spread estimation
        spread_pct = estimate_spread_pct(quotes)

        # Step 7: Cancel rate
        cancel_rate = estimate_cancel_rate(quotes)

        # Step 8: Liquidity depth
        depth_model = LiquidityDepthModel()
        depth_model.calibrate_from_quotes(quotes)

        # Step 9: Fill probability lambda
        fill_prob_lambda = micro_params.fill_prob_lambda

        # Step 10: Regime transition matrix (use default for now)
        transition_matrix = default_transition_matrix()

        params = MarketParameters(
            symbol=symbol,
            calibration_date=cal_date,
            arrival_rate=arrival_rate,
            trade_intensity=trade_rate_min,
            cancel_rate=cancel_rate,
            avg_trade_size=avg_trade_size,
            adv=adv,
            spread_pct=spread_pct,
            impact_eta=eta,
            impact_alpha=alpha,
            liquidity_depth_k=depth_model.k,
            order_size_mu=size_dist["mu"],
            order_size_sigma=size_dist["sigma"],
            fill_prob_lambda=fill_prob_lambda,
            regime_transition_matrix=transition_matrix,
            metadata={
                "n_trades": len(trades),
                "n_quotes": len(quotes),
                "trade_rate_per_min": trade_rate_min,
                "micro_cancel_rate": micro_params.cancel_rate,
                "micro_arrival_rate": micro_params.arrival_rate,
            },
        )

        self.parameter_store.save(params)
        self._last_results[symbol] = params

        logger.info(
            "Calibration complete for %s: arrival=%.2f, impact_eta=%.4f, impact_alpha=%.4f, spread=%.4f",
            symbol, arrival_rate, eta, alpha, spread_pct,
        )
        return params

    def run_batch(
        self,
        data: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]],
        calibration_date: str | None = None,
    ) -> list[MarketParameters]:
        """Run calibration for multiple symbols."""
        results: list[MarketParameters] = []
        for symbol, (trades, quotes) in data.items():
            params = self.run(symbol, trades, quotes, calibration_date)
            results.append(params)
        return results

    def validate_simulation(
        self,
        symbol: str,
        real_data: dict[str, list[float]],
        sim_data: dict[str, list[float]],
    ) -> dict[str, Any]:
        """Validate simulation output against real market data."""
        results = self.validator.validate_all(real_data, sim_data)
        logger.info("Validation for %s: overall similarity=%.2f", symbol, results.get("overall_similarity", 0))
        return results

    def get_latest_params(self, symbol: str) -> MarketParameters | None:
        return self.parameter_store.load_latest(symbol)

    @property
    def last_results(self) -> dict[str, Any]:
        return dict(self._last_results)
