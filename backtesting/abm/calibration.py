from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from backtesting.abm.agents import (
    MarketMaker,
    MeanReversionAgent,
    NoiseTrader,
    TrendFollower,
)
from backtesting.abm.simulation import Simulation
from core.paths import validate_safe_path


@dataclass
class ABMConfig:
    n_market_makers: int = 2
    n_noise_traders: int = 20
    n_trend_followers: int = 5
    n_mean_reversion: int = 5
    market_maker_spread_pct: float = 0.01
    market_maker_order_size: int = 1000
    noise_min_size: int = 100
    noise_max_size: int = 2000
    noise_market_order_prob: float = 0.3
    trend_lookback: int = 20
    trend_order_size: int = 1000
    trend_threshold_pct: float = 0.005
    mean_reversion_lookback: int = 50
    mean_reversion_order_size: int = 1000
    mean_reversion_entry_z: float = 1.0
    n_steps: int = 10000
    random_seed: int = 42


class ABMCalibrator:
    def create_simulation(self, config: ABMConfig) -> Simulation:
        sim = Simulation(random_seed=config.random_seed)
        for i in range(config.n_market_makers):
            sim.add_agent(
                MarketMaker(
                    agent_id=f"mm_{i}",
                    spread_pct=config.market_maker_spread_pct,
                    order_size=config.market_maker_order_size,
                )
            )
        for i in range(config.n_noise_traders):
            sim.add_agent(
                NoiseTrader(
                    agent_id=f"noise_{i}",
                    min_size=config.noise_min_size,
                    max_size=config.noise_max_size,
                    market_order_prob=config.noise_market_order_prob,
                )
            )
        for i in range(config.n_trend_followers):
            sim.add_agent(
                TrendFollower(
                    agent_id=f"trend_{i}",
                    lookback=config.trend_lookback,
                    order_size=config.trend_order_size,
                    threshold_pct=config.trend_threshold_pct,
                )
            )
        for i in range(config.n_mean_reversion):
            sim.add_agent(
                MeanReversionAgent(
                    agent_id=f"mr_{i}",
                    lookback=config.mean_reversion_lookback,
                    order_size=config.mean_reversion_order_size,
                    entry_z=config.mean_reversion_entry_z,
                )
            )
        return sim

    def run_calibration(
        self,
        config: ABMConfig,
        target_volatility: float = 0.02,
        target_spread: float = 10.0,
        target_trade_rate: float = 10.0,
    ) -> ABMConfig:
        best_config = config
        best_score = float("inf")
        for trial in range(20):
            trial_config = ABMConfig(**asdict(config))
            trial_config.n_noise_traders = max(5, int(config.n_noise_traders * random.uniform(0.5, 1.5)))
            trial_config.market_maker_spread_pct = config.market_maker_spread_pct * random.uniform(0.5, 2.0)
            trial_config.noise_market_order_prob = random.uniform(0.1, 0.5)

            sim = self.create_simulation(trial_config)
            result = sim.run(trial_config.n_steps)

            if len(result.price_series) < 10:
                continue

            returns = np.diff(result.price_series) / result.price_series[:-1]
            volatility = float(np.std(returns)) if len(returns) > 0 else 0
            avg_spread = float(np.mean(result.spread_series)) if result.spread_series else 0
            trade_rate = result.total_trades / max(result.steps, 1)

            vol_score = abs(volatility - target_volatility) / target_volatility if target_volatility > 0 else 0.0
            spread_score = abs(avg_spread - target_spread) / target_spread if target_spread > 0 else 0.0
            trade_score = abs(trade_rate - target_trade_rate) / target_trade_rate if target_trade_rate > 0 else 0.0
            score = vol_score + spread_score + trade_score

            if score < best_score:
                best_score = score
                best_config = trial_config
                logger.info("Calibration trial %s: score=%.4f, vol=%.4f, spread=%.2f, trade_rate=%.2f",
                          trial, score, volatility, avg_spread, trade_rate)

        return best_config

    def save_config(self, config: ABMConfig, path: str | Path) -> None:
        safe = validate_safe_path(path)
        data = asdict(config)
        safe.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def load_config(self, path: str | Path) -> ABMConfig:
        safe = validate_safe_path(path)
        data = json.loads(safe.read_text(encoding="utf-8"))
        return ABMConfig(**data)


from core.logging import get_logger

logger = get_logger(__name__)
