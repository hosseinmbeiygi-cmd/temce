from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np


@dataclass
class PnLAttribution:
    """Breakdown of PnL by source."""
    strategy_pnl: float = 0.0
    market_movement: float = 0.0
    spread_cost: float = 0.0
    impact_cost: float = 0.0
    commission_total: float = 0.0
    tax_total: float = 0.0
    slippage_total: float = 0.0
    total_pnl: float = 0.0
    attribution_pct: dict[str, float] = field(default_factory=dict)


@dataclass
class SlippageRecord:
    """Record of slippage for a single trade."""
    trade_id: str = ""
    instrument_id: str = ""
    side: str = ""
    expected_price: float = 0.0
    execution_price: float = 0.0
    quantity: int = 0
    slippage_bps: float = 0.0
    slippage_cost: float = 0.0
    timestamp: datetime | None = None
    market_impact_bps: float = 0.0
    spread_cost_bps: float = 0.0


class PnLAttributionEngine:
    """Attribution analysis for backtest results.

    Breaks down PnL into:
    - Strategy alpha (signal-based)
    - Market movement (beta)
    - Execution costs (spread, impact, commission)
    - Slippage
    """

    @staticmethod
    def attribute_pnl(
        trades: list[dict[str, Any]],
        market_returns: list[float] | None = None,
    ) -> PnLAttribution:
        """Compute full PnL attribution from trade list.

        Args:
            trades: List of trade dicts with keys: side, price, quantity, commission, slippage
            market_returns: Optional market return series for beta adjustment

        Returns:
            PnLAttribution with breakdown
        """
        attr = PnLAttribution()

        for t in trades:
            qty = t.get("quantity", 0)
            price = t.get("price", 0)
            side = t.get("side", "buy")
            commission = t.get("commission", 0)
            slippage = t.get("slippage", 0)
            expected_price = t.get("expected_price", price)

            trade_value = price * qty
            attr.commission_total += commission
            attr.slippage_total += slippage

            if side == "buy":
                attr.spread_cost += trade_value * 0.0005  # half-spread estimate
                attr.strategy_pnl -= slippage
            else:
                attr.spread_cost += trade_value * 0.0005
                attr.strategy_pnl += price * qty - slippage

        attr.total_pnl = attr.strategy_pnl - attr.commission_total - attr.spread_cost - attr.slippage_total

        # Attribution percentages
        total_costs = abs(attr.commission_total) + abs(attr.spread_cost) + abs(attr.slippage_total)
        total_abs = abs(attr.strategy_pnl) + total_costs
        if total_abs > 0:
            attr.attribution_pct = {
                "strategy_alpha": (attr.strategy_pnl / total_abs) * 100,
                "spread_cost": (-abs(attr.spread_cost) / total_abs) * 100,
                "commission": (-abs(attr.commission_total) / total_abs) * 100,
                "slippage": (-abs(attr.slippage_total) / total_abs) * 100,
            }

        return attr

    @staticmethod
    def compute_slippage_analysis(fills: list[dict[str, Any]]) -> dict[str, float]:
        """Compute detailed slippage statistics from fill data.

        Args:
            fills: List of fill dicts with: side, price, expected_price, quantity, timestamp

        Returns:
            Dict with slippage statistics: mean, median, std, positive_rate, total_cost
        """
        if not fills:
            return {"mean_bps": 0, "median_bps": 0, "std_bps": 0, "positive_rate": 0, "total_cost": 0}

        slippages_bps: list[float] = []
        total_cost = 0.0

        for f in fills:
            exe_p = f.get("price", 0)
            exp_p = f.get("expected_price", exe_p)
            qty = f.get("quantity", 0)
            side = f.get("side", "buy")

            if exp_p > 0:
                if side == "buy":
                    bps = ((exe_p - exp_p) / exp_p) * 10000
                else:
                    bps = ((exp_p - exe_p) / exp_p) * 10000
                slippages_bps.append(bps)
                total_cost += bps * qty * exp_p / 10000

        if not slippages_bps:
            return {"mean_bps": 0, "median_bps": 0, "std_bps": 0, "positive_rate": 0, "total_cost": 0}

        arr = np.array(slippages_bps)
        return {
            "mean_bps": float(np.mean(arr)),
            "median_bps": float(np.median(arr)),
            "std_bps": float(np.std(arr)),
            "positive_rate": float(np.mean(arr > 0)),
            "total_cost": total_cost,
            "min_bps": float(np.min(arr)),
            "max_bps": float(np.max(arr)),
        }

    @staticmethod
    def execution_quality_report(fills: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate an execution quality report.

        Args:
            fills: List of fill dicts

        Returns:
            Dict with execution quality metrics
        """
        slippage = PnLAttributionEngine.compute_slippage_analysis(fills)
        n_fills = len(fills)

        # Fill by side
        buy_fills = [f for f in fills if f.get("side") == "buy"]
        sell_fills = [f for f in fills if f.get("side") == "sell"]

        return {
            "n_fills": n_fills,
            "n_buy_fills": len(buy_fills),
            "n_sell_fills": len(sell_fills),
            "total_volume": sum(f.get("quantity", 0) for f in fills),
            "avg_fill_size": sum(f.get("quantity", 0) for f in fills) / max(n_fills, 1),
            "slippage": slippage,
            "execution_quality_score": max(0.0, 100.0 - abs(slippage.get("mean_bps", 0)) * 10),
        }


class SlippageTracker:
    """Tracks and analyzes slippage for trade execution."""

    def __init__(self) -> None:
        self._records: list[SlippageRecord] = []

    def record_fill(
        self,
        trade_id: str,
        instrument_id: str,
        side: str,
        expected_price: float,
        execution_price: float,
        quantity: int,
        spread_bps: float = 0.0,
        impact_bps: float = 0.0,
    ) -> SlippageRecord:
        """Record a fill and compute its slippage."""
        if expected_price > 0:
            if side == "buy":
                bps = ((execution_price - expected_price) / expected_price) * 10000
            else:
                bps = ((expected_price - execution_price) / expected_price) * 10000
        else:
            bps = 0.0

        record = SlippageRecord(
            trade_id=trade_id,
            instrument_id=instrument_id,
            side=side,
            expected_price=expected_price,
            execution_price=execution_price,
            quantity=quantity,
            slippage_bps=bps,
            slippage_cost=abs(execution_price - expected_price) * quantity,
            market_impact_bps=impact_bps,
            spread_cost_bps=spread_bps,
        )
        self._records.append(record)
        return record

    def summary(self) -> dict[str, float]:
        """Get summary statistics of all tracked slippage."""
        if not self._records:
            return {"n_records": 0, "avg_slippage_bps": 0, "total_cost": 0}

        bps = [r.slippage_bps for r in self._records]
        return {
            "n_records": len(self._records),
            "avg_slippage_bps": float(np.mean(bps)),
            "median_slippage_bps": float(np.median(bps)),
            "max_slippage_bps": float(np.max(bps)),
            "total_cost": sum(r.slippage_cost for r in self._records),
            "positive_slippage_rate": float(np.mean([b > 0 for b in bps])),
        }

    def reset(self) -> None:
        self._records.clear()
