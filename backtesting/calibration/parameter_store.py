from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from core.paths import safe_resolve


@dataclass
class MarketParameters:
    """Versioned parameters for a single market/symbol, updated nightly."""
    symbol: str = ""
    calibration_date: str = ""
    arrival_rate: float = 0.0
    trade_intensity: float = 0.0
    cancel_rate: float = 0.12
    avg_trade_size: float = 10_000
    adv: float = 1_000_000
    spread_pct: float = 0.01
    impact_eta: float = 0.1
    impact_alpha: float = 0.6
    liquidity_depth_k: float = 0.001
    order_size_mu: float = 8.0
    order_size_sigma: float = 1.5
    fill_prob_lambda: float = 0.0001
    regime_transition_matrix: dict[str, dict[str, float]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "calibration_date": self.calibration_date,
            "arrival_rate": self.arrival_rate,
            "trade_intensity": self.trade_intensity,
            "cancel_rate": self.cancel_rate,
            "avg_trade_size": self.avg_trade_size,
            "adv": self.adv,
            "spread_pct": self.spread_pct,
            "impact_eta": self.impact_eta,
            "impact_alpha": self.impact_alpha,
            "liquidity_depth_k": self.liquidity_depth_k,
            "order_size_mu": self.order_size_mu,
            "order_size_sigma": self.order_size_sigma,
            "fill_prob_lambda": self.fill_prob_lambda,
            "regime_transition_matrix": self.regime_transition_matrix,
            "metadata": self.metadata,
        }


class ParameterStore:
    """Versioned storage for market parameters, organized by date and symbol."""

    def __init__(self, base_path: str | Path | None = None) -> None:
        self.base_path = safe_resolve(Path.cwd(), "parameters") if base_path is None else Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, MarketParameters] = {}

    def save(self, params: MarketParameters) -> Path:
        cal_date = params.calibration_date or date.today().isoformat()
        date_dir = self.base_path / cal_date
        date_dir.mkdir(parents=True, exist_ok=True)

        file_path = date_dir / f"{params.symbol}.json"
        file_path.write_text(
            json.dumps(params.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        cache_key = f"{cal_date}_{params.symbol}"
        self._cache[cache_key] = params
        return file_path

    def load(self, symbol: str, calibration_date: str | None = None) -> MarketParameters | None:
        cal_date = calibration_date or date.today().isoformat()
        cache_key = f"{cal_date}_{symbol}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        file_path = self.base_path / cal_date / f"{symbol}.json"
        if not file_path.exists():
            return None

        raw = json.loads(file_path.read_text(encoding="utf-8"))
        params = MarketParameters(**raw)
        self._cache[cache_key] = params
        return params

    def load_latest(self, symbol: str) -> MarketParameters | None:
        dates = sorted([d.name for d in self.base_path.iterdir() if d.is_dir()], reverse=True)
        for cal_date in dates:
            params = self.load(symbol, cal_date)
            if params is not None:
                return params
        return None

    def list_available_dates(self) -> list[str]:
        return sorted([d.name for d in self.base_path.iterdir() if d.is_dir()], reverse=True)

    def list_symbols(self, calibration_date: str | None = None) -> list[str]:
        cal_date = calibration_date or date.today().isoformat()
        date_dir = self.base_path / cal_date
        if not date_dir.exists():
            return []
        return [f.stem for f in date_dir.glob("*.json")]

    def clear_cache(self) -> None:
        self._cache.clear()
