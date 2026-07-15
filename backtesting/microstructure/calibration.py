from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from core.paths import validate_safe_path


@dataclass
class SymbolMicrostructureParams:
    symbol: str = ""
    trade_rate: float = 0.8
    trade_intensity: float = 0.0
    cancel_rate: float = 0.12
    arrival_rate: float = 0.5
    impact_eta: float = 0.11
    impact_alpha: float = 0.6
    avg_queue: int = 1_200_000
    avg_trade_size: float = 10_000
    adv: float = 1_000_000
    hidden_liquidity_mult: float = 1.3
    queue_decay: float = 0.0
    trade_volume_std: float = 0.5
    fill_prob_lambda: float = 0.0001
    queue_lifetime_minutes: float = 0.0
    avg_queue_bid: int = 0
    avg_queue_ask: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "trade_rate": self.trade_rate,
            "trade_intensity": self.trade_intensity,
            "cancel_rate": self.cancel_rate,
            "arrival_rate": self.arrival_rate,
            "impact_eta": self.impact_eta,
            "impact_alpha": self.impact_alpha,
            "avg_queue": self.avg_queue,
            "avg_trade_size": self.avg_trade_size,
            "adv": self.adv,
            "hidden_liquidity_mult": self.hidden_liquidity_mult,
            "queue_decay": self.queue_decay,
            "fill_prob_lambda": self.fill_prob_lambda,
            "queue_lifetime_minutes": self.queue_lifetime_minutes,
            "avg_queue_bid": self.avg_queue_bid,
            "avg_queue_ask": self.avg_queue_ask,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class MicrostructureCalibrator:
    def calibrate_from_events(
        self,
        symbol: str,
        quotes: list[dict[str, Any]],
        trades: list[dict[str, Any]],
    ) -> SymbolMicrostructureParams:
        params = SymbolMicrostructureParams(symbol=symbol)
        if not trades:
            return params

        # 1. Basic trade metrics
        total_seconds = self._calculate_total_seconds(trades)
        total_minutes = total_seconds / 60.0
        total_trades = len(trades)
        total_volume = sum(t.get("volume", 0) for t in trades)

        params.trade_rate = total_trades / max(total_minutes, 1)
        params.trade_intensity = total_trades / total_seconds
        params.avg_trade_size = total_volume / max(total_trades, 1)
        params.adv = int(total_volume)
        params.arrival_rate = params.trade_rate * 0.6

        # 2. Volume distribution
        trade_volumes = [t.get("volume", 0) for t in trades if t.get("volume", 0) > 0]
        if len(trade_volumes) > 1:
            params.trade_volume_std = float(np.std(np.log(trade_volumes)))

        # 3. Queue metrics
        if quotes:
            self._calibrate_queue_metrics(params, quotes, total_seconds)

        # 4. Impact calibration
        self._calibrate_impact(params, trades)

        # 5. Final adjustments
        if params.avg_queue > 0:
            params.fill_prob_lambda = max(params.trade_rate / params.avg_queue, 1e-6)

        drain_rate = params.trade_rate + (params.cancel_rate * params.avg_queue / 60.0)
        params.queue_lifetime_minutes = (params.avg_queue / max(drain_rate, 1)) if drain_rate > 0 else 0.0

        return params

    def _calculate_total_seconds(self, trades: list[dict[str, Any]]) -> float:
        trade_timestamps = [t.get("timestamp") for t in trades if t.get("timestamp") is not None]
        if len(trade_timestamps) <= 1:
            return 1.0
        ordered = sorted(trade_timestamps)
        span = ordered[-1] - ordered[0]
        if isinstance(span, (int, float)):
            return max(float(span), 1.0)
        if hasattr(span, "total_seconds"):
            return max(span.total_seconds(), 1.0)
        return 1.0

    def _calibrate_queue_metrics(self, params: SymbolMicrostructureParams, quotes: list[dict[str, Any]], total_seconds: float) -> None:
        bid_volumes = [q.get("bid_volume", 0) for q in quotes if q.get("bid_volume") is not None]
        ask_volumes = [q.get("ask_volume", 0) for q in quotes if q.get("ask_volume") is not None]

        if bid_volumes:
            params.avg_queue_bid = int(sum(bid_volumes) / len(bid_volumes))
        if ask_volumes:
            params.avg_queue_ask = int(sum(ask_volumes) / len(ask_volumes))

        params.avg_queue = int((params.avg_queue_bid + params.avg_queue_ask) / 2) if (params.avg_queue_bid + params.avg_queue_ask) > 0 else 0

        total_cancel_bid = 0
        total_cancel_ask = 0
        n_obs = min(len(quotes), 10000)
        for i in range(1, n_obs):
            q_prev, q_curr = quotes[i - 1], quotes[i]
            prev_bid, curr_bid = q_prev.get("bid_volume", 0) or 0, q_curr.get("bid_volume", 0) or 0
            prev_ask, curr_ask = q_prev.get("ask_volume", 0) or 0, q_curr.get("ask_volume", 0) or 0
            trade_vol = q_curr.get("trade_volume", 0) or 0
            total_cancel_bid += max(0, prev_bid - curr_bid - trade_vol)
            total_cancel_ask += max(0, prev_ask - curr_ask - trade_vol)

        avg_queue = max((params.avg_queue_bid + params.avg_queue_ask) / 2, 1)
        cancel_per_obs = (total_cancel_bid + total_cancel_ask) / max(n_obs, 1)
        params.cancel_rate = cancel_per_obs / avg_queue if avg_queue > 0 else 0.12
        params.queue_decay = (total_cancel_bid + total_cancel_ask) / max(total_seconds, 1)

    def _calibrate_impact(self, params: SymbolMicrostructureParams, trades: list[dict[str, Any]]) -> None:
        price_moves, trade_sizes = [], []
        for i in range(1, len(trades)):
            prev_price = trades[i - 1].get("price", 0) or 0
            curr_price = trades[i].get("price", 0) or 0
            if prev_price > 0:
                move = abs(curr_price - prev_price) / prev_price
                if 0 < move < 0.1:
                    price_moves.append(move)
                    trade_sizes.append(float(trades[i].get("volume", 0) or 0))

        if len(price_moves) >= 5:
            log_sizes = np.log([max(s / max(params.adv, 1), 1e-10) for s in trade_sizes])
            log_moves = np.log([max(abs(m), 1e-10) for m in price_moves])
            valid = np.isfinite(log_sizes) & np.isfinite(log_moves)
            if len(log_sizes[valid]) >= 5:
                coeffs = np.polyfit(log_sizes[valid], log_moves[valid], 1)
                params.impact_alpha = float(np.clip(coeffs[0], 0.1, 1.5))
                params.impact_eta = float(np.clip(np.exp(coeffs[1]), 0.001, 1.0))

    def fill_probability(self, traded_volume: float, queue_ahead: float, lambda_trade: float | None = None) -> float:
        lam = lambda_trade or self._last_params.fill_prob_lambda if hasattr(self, "_last_params") else 0.0001
        if queue_ahead <= 0:
            return 1.0
        return 1.0 - math.exp(-lam * traded_volume / queue_ahead)

    def estimate_queue_lifetime(
        self,
        queue_size: int,
        trade_rate_per_min: float,
        cancel_rate_per_min: float,
    ) -> float:
        drain = trade_rate_per_min + cancel_rate_per_min
        if drain <= 0:
            return float("inf")
        return queue_size / drain

    def calibrate_batch(
        self,
        data: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]],
    ) -> list[SymbolMicrostructureParams]:
        return [self.calibrate_from_events(symbol, quotes, trades) for symbol, (quotes, trades) in data.items()]

    def save_params(self, params: list[SymbolMicrostructureParams], path: str | Path) -> None:
        safe = validate_safe_path(path)
        data = [p.to_dict() for p in params]
        safe.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def load_params(self, path: str | Path) -> list[SymbolMicrostructureParams]:
        safe = validate_safe_path(path)
        raw = json.loads(safe.read_text(encoding="utf-8"))
        return [SymbolMicrostructureParams(**item) for item in raw]

    def calibrate_iran_market(
        self,
        symbol: str,
        quotes: list[dict[str, Any]],
        trades: list[dict[str, Any]],
    ) -> SymbolMicrostructureParams:
        params = self.calibrate_from_events(symbol, quotes, trades)

        bid_volumes = [q.get("bid_volume", 0) for q in quotes if q.get("bid_volume") is not None]
        ask_volumes = [q.get("ask_volume", 0) for q in quotes if q.get("ask_volume") is not None]

        if bid_volumes and ask_volumes and trades:
            last_price = trades[-1].get("price", 0) or 0
            if last_price > 0:
                limit_up_events = sum(1 for q in quotes if q.get("bid_volume", 0) > params.avg_queue_bid * 2)
                limit_down_events = sum(1 for q in quotes if q.get("ask_volume", 0) > params.avg_queue_ask * 2)
                params.metadata["limit_up_events"] = limit_up_events
                params.metadata["limit_down_events"] = limit_down_events
                params.metadata["iran_queue_growth_rate"] = (limit_up_events + limit_down_events) / max(len(quotes), 1)

        return params
