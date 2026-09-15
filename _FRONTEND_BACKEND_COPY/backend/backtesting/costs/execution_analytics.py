from __future__ import annotations

import numpy as np


class ExecutionAnalytics:
    """Analytics for execution quality measurement.

    Supports:
    - VWAP (Volume Weighted Average Price)
    - TWAP (Time Weighted Average Price)
    - POV (Percentage of Volume)
    - Implementation Shortfall
    - Slippage attribution
    """

    @staticmethod
    def vwap(prices: list[float], volumes: list[int]) -> float:
        """Compute Volume Weighted Average Price."""
        total_value = sum(p * v for p, v in zip(prices, volumes, strict=False))
        total_volume = sum(volumes)
        return total_value / total_volume if total_volume > 0 else 0.0

    @staticmethod
    def twap(prices: list[float]) -> float:
        """Compute Time Weighted Average Price."""
        return float(np.mean(prices)) if prices else 0.0

    @staticmethod
    def implementation_shortfall(
        execution_price: float,
        arrival_price: float,
        quantity: int,
        side: str,
    ) -> float:
        """Compute implementation shortfall in currency units."""
        if side == "buy":
            return (execution_price - arrival_price) * quantity
        return (arrival_price - execution_price) * quantity

    @staticmethod
    def slippage_bps(execution_price: float, benchmark_price: float) -> float:
        """Compute slippage in basis points."""
        if benchmark_price <= 0:
            return 0.0
        return ((execution_price - benchmark_price) / benchmark_price) * 10000

    @staticmethod
    def participation_rate(traded_volume: int, market_volume: int) -> float:
        """Compute participation rate as percentage of market volume."""
        return traded_volume / max(market_volume, 1) * 100

    @staticmethod
    def fill_rate(filled_quantity: int, ordered_quantity: int) -> float:
        """Compute fill rate as percentage of ordered quantity."""
        return filled_quantity / max(ordered_quantity, 1) * 100

    def execute_vwap(
        self,
        total_quantity: int,
        volumes: list[int],
        start_idx: int = 0,
    ) -> list[int]:
        """Slice an order according to historical volume profile (VWAP algo).

        Args:
            total_quantity: Total order size
            volumes: Historical volume profile (list of volumes per time slice)
            start_idx: Index to start slicing from

        Returns:
            List of quantities to trade per time slice
        """
        total_market_vol = sum(volumes[start_idx:])
        if total_market_vol <= 0:
            return [0] * len(volumes)

        slices: list[int] = []
        remaining = total_quantity
        for i in range(start_idx, len(volumes)):
            if remaining <= 0:
                slices.append(0)
                continue
            slice_qty = int(total_quantity * (volumes[i] / max(total_market_vol, 1)))
            slice_qty = min(slice_qty, remaining)
            slices.append(slice_qty)
            remaining -= slice_qty

        return slices

    def execute_twap(
        self,
        total_quantity: int,
        n_slices: int,
    ) -> list[int]:
        """Slice an order evenly across time (TWAP algo).

        Args:
            total_quantity: Total order size
            n_slices: Number of time slices

        Returns:
            List of quantities to trade per slice
        """
        base = total_quantity // n_slices
        remainder = total_quantity % n_slices
        slices = [base + (1 if i < remainder else 0) for i in range(n_slices)]
        return slices

    def execute_pov(
        self,
        total_quantity: int,
        volumes: list[int],
        target_pct: float = 0.1,
    ) -> list[int]:
        """Slice an order as fixed percentage of volume (POV algo).

        Args:
            total_quantity: Total order size
            volumes: Market volume per time slice
            target_pct: Target participation rate (e.g. 0.1 = 10%)

        Returns:
            List of quantities to trade per slice
        """
        slices: list[int] = []
        remaining = total_quantity
        for vol in volumes:
            if remaining <= 0:
                slices.append(0)
                continue
            slice_qty = int(vol * target_pct)
            slice_qty = min(slice_qty, remaining)
            slices.append(slice_qty)
            remaining -= slice_qty
        return slices
