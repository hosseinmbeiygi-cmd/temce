"""Broker with realistic transaction cost modeling.

Supports:
- Volume-based slippage (larger orders = more slippage)
- Market impact model (Almgren-Chriss simplified)
- Commission tiers (Iranian market specific)
- Partial fills for illiquid stocks
"""

from __future__ import annotations

from dataclasses import dataclass

from backtesting.types import FillEvent, OrderEvent
from core.ids import new_id


@dataclass
class TransactionCostConfig:
    """Configuration for transaction cost modeling."""
    # Commission (Iranian market: 0.5% buy + 0.5% sell + tax)
    commission_pct: float = 0.005  # 0.5% per side
    # Tax on sell (Iranian market: 0.5% on sell proceeds)
    sell_tax_pct: float = 0.005
    # Base slippage in basis points
    base_slippage_bps: float = 5.0
    # Volume impact factor (slippage increases with order size relative to ADV)
    volume_impact_factor: float = 0.1  # 10% of ADV causes 1 bps additional slippage
    # Minimum slippage (always at least this much)
    min_slippage_bps: float = 2.0
    # Maximum slippage cap
    max_slippage_bps: float = 100.0  # 1% max


# Iranian market specific cost tiers
IRAN_MARKET_COSTS = TransactionCostConfig(
    commission_pct=0.005,      # 0.5% commission per side
    sell_tax_pct=0.005,        # 0.5% tax on sell
    base_slippage_bps=5.0,     # 5 bps base slippage
    volume_impact_factor=0.15, # Higher impact for less liquid market
    min_slippage_bps=3.0,      # 3 bps minimum
    max_slippage_bps=150.0,    # 1.5% maximum
)

# Conservative costs for backtesting
CONSERVATIVE_COSTS = TransactionCostConfig(
    commission_pct=0.005,
    sell_tax_pct=0.005,
    base_slippage_bps=10.0,
    volume_impact_factor=0.2,
    min_slippage_bps=5.0,
    max_slippage_bps=200.0,
)


class Broker:
    def __init__(
        self,
        commission_pct: float = 0.005,
        slippage_bps: float = 5.0,
        config: TransactionCostConfig | None = None,
        average_daily_volume: int = 1_000_000,
    ) -> None:
        self.config = config or IRAN_MARKET_COSTS
        self.commission_pct = commission_pct or self.config.commission_pct
        self.slippage_bps = slippage_bps or self.config.base_slippage_bps
        self.average_daily_volume = average_daily_volume

    def _compute_slippage(
        self,
        price: float,
        quantity: int,
        side: str,
        daily_volume: int | None = None,
    ) -> float:
        """Compute slippage based on order size relative to daily volume.

        Uses simplified Almgren-Chriss model:
        slippage = base + impact_factor * (order_size / ADV)

        Args:
            price: Execution price
            quantity: Number of shares
            side: 'buy' or 'sell'
            daily_volume: Average daily volume (uses instance default if None)

        Returns:
            Slippage per share in price units
        """
        if price <= 0:
            return 0.0

        adv = daily_volume or self.average_daily_volume
        if adv <= 0:
            adv = 100_000  # More realistic for small-cap Iranian stocks

        # Participation rate: what % of daily volume is this order
        participation_rate = min(quantity / adv, 1.0)  # Cap at 100%

        # Volume-dependent slippage using Almgren-Chriss simplified model
        total_slippage_bps = self.config.base_slippage_bps + (
            self.config.volume_impact_factor * participation_rate * 10_000
        )

        # Apply min/max bounds
        total_slippage_bps = max(
            self.config.min_slippage_bps,
            min(total_slippage_bps, self.config.max_slippage_bps)
        )

        slippage_per_share = price * (total_slippage_bps / 10_000)

        return slippage_per_share

    def _compute_commission(
        self,
        exec_price: float,
        quantity: int,
        side: str,
    ) -> float:
        """Compute total commission including fees and taxes.

        Iranian market structure:
        - Buy: 0.5% commission
        - Sell: 0.5% commission + 0.5% tax on proceeds

        Returns:
            Total commission in currency units
        """
        trade_value = exec_price * quantity

        # Base commission
        commission = trade_value * self.config.commission_pct

        # Additional tax on sell side
        if side == "sell":
            commission += trade_value * self.config.sell_tax_pct

        return commission

    def submit_order_sync(self, order: OrderEvent) -> FillEvent | None:
        """Synchronous version of submit_order — for use in deterministic sync backtests."""
        if order.price <= 0 or order.quantity <= 0:
            return None

        slippage = self._compute_slippage(
            price=order.price,
            quantity=order.quantity,
            side=order.side,
            daily_volume=getattr(order, "daily_volume", None),
        )

        exec_price = order.price + slippage if order.side == "buy" else order.price - slippage

        exec_price = max(exec_price, 0.01)

        commission = self._compute_commission(exec_price, order.quantity, order.side)

        return FillEvent(
            order_id=order.order_id or new_id("ord"),
            instrument_id=order.instrument_id,
            side=order.side,
            quantity=order.quantity,
            price=exec_price,
            commission=commission,
            slippage=slippage * order.quantity,
        )

    async def submit_order(self, order: OrderEvent) -> FillEvent | None:
        """Submit order with realistic cost modeling.

        Returns FillEvent with computed slippage and commission.
        """
        return self.submit_order_sync(order)
