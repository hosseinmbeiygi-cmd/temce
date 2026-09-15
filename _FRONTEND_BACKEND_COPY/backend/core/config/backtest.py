from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class BacktestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BACKTEST_", env_file=".env", extra="ignore")

    default_capital: float = 1_000_000_000
    default_commission_pct: float = 0.0035
    default_slippage_bps: float = 10.0
    max_positions: int = 50
    max_leverage: float = 1.0
    allow_short: bool = False
    default_timeframe: str = "1d"
    output_dir: str = "./data/backtest"
    parallel_runs: int = 4
    max_optimization_workers: int = 4
    cache_results: bool = True
    max_optimization_trials: int = 100
