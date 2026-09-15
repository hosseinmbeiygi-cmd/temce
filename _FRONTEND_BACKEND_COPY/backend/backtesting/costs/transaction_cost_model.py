from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TransactionCostBreakdown:
    """Detailed breakdown of transaction costs for a single order."""

    spread_cost: float = 0.0
    temporary_impact: float = 0.0
    permanent_impact: float = 0.0
    queue_loss: float = 0.0
    adverse_selection: float = 0.0
    commission: float = 0.0
    tax: float = 0.0
    total_cost: float = 0.0
    total_cost_bps: float = 0.0
    implementation_shortfall: float = 0.0


class TransactionCostModel:
    """Advanced transaction cost model for institutional-grade execution analysis.

    Components:
    - Spread cost: bid-ask spread at order entry
    - Temporary impact: short-term price pressure that reverts
    - Permanent impact: long-term information leakage
    - Queue loss: opportunity cost of not being filled in queue
    - Adverse selection: price moves against order after submission
    - Commission + tax: fixed costs per trade
    """

    def __init__(
        self,
        spread_cost_pct: float = 0.0005,
        temp_impact_coeff: float = 0.1,
        perm_impact_coeff: float = 0.02,
        queue_loss_rate: float = 0.05,
        adverse_selection_rate: float = 0.03,
        commission_pct: float = 0.0003,
        tax_pct: float = 0.0005,
    ) -> None:
        self.spread_cost_pct = spread_cost_pct
        self.temp_impact_coeff = temp_impact_coeff
        self.perm_impact_coeff = perm_impact_coeff
        self.queue_loss_rate = queue_loss_rate
        self.adverse_selection_rate = adverse_selection_rate
        self.commission_pct = commission_pct
        self.tax_pct = tax_pct

    def compute_cost(
        self,
        side: str,
        quantity: int,
        price: float,
        adv: int = 1_000_000,
        spread_bps: float | None = None,
        queue_position: int = 0,
        queue_depth: int = 0,
    ) -> TransactionCostBreakdown:
        """Compute full transaction cost breakdown for an order.

        Args:
            side: 'buy' or 'sell'
            quantity: Order size
            price: Expected execution price
            adv: Average Daily Volume
            spread_bps: Current spread in bps (default uses model spread)
            queue_position: Position in queue (0 = first)
            queue_depth: Total queue depth

        Returns:
            TransactionCostBreakdown with all cost components
        """
        breakdown = TransactionCostBreakdown()
        order_value = quantity * price
        participation = quantity / max(adv, 1)
        spread = spread_bps if spread_bps is not None else self.spread_cost_pct * 10000

        # 1. Spread cost (half-spread for market orders)
        breakdown.spread_cost = order_value * (spread / 10000) * 0.5

        # 2. Temporary market impact (decays after execution)
        breakdown.temporary_impact = order_value * self.temp_impact_coeff * (participation**0.6)

        # 3. Permanent impact (information leakage)
        breakdown.permanent_impact = order_value * self.perm_impact_coeff * (participation**0.3)

        # 4. Queue loss (opportunity cost of non-execution)
        if queue_depth > 0 and queue_position > 0:
            queue_ratio = queue_position / queue_depth
            breakdown.queue_loss = order_value * self.queue_loss_rate * queue_ratio

        # 5. Adverse selection
        breakdown.adverse_selection = order_value * self.adverse_selection_rate * (participation**0.5)

        # 6. Commission
        breakdown.commission = order_value * self.commission_pct

        # 7. Tax
        breakdown.tax = order_value * self.tax_pct

        # Total cost
        breakdown.total_cost = (
            breakdown.spread_cost
            + breakdown.temporary_impact * 0.5  # only half realized
            + breakdown.permanent_impact
            + breakdown.queue_loss
            + breakdown.adverse_selection
            + breakdown.commission
            + breakdown.tax
        )

        breakdown.total_cost_bps = (breakdown.total_cost / max(order_value, 1)) * 10000
        breakdown.implementation_shortfall = breakdown.total_cost

        return breakdown

    def compute_vwap_shortfall(
        self,
        side: str,
        quantity: int,
        price: float,
        arrival_price: float,
        adv: int = 1_000_000,
    ) -> float:
        """Compute implementation shortfall relative to arrival price.

        Implementation Shortfall = (execution_price - arrival_price) * quantity
        """
        if side == "buy":
            return (price - arrival_price) * quantity
        return (arrival_price - price) * quantity

    def estimate_total_cost_bps(
        self,
        quantity: int,
        adv: int = 1_000_000,
        is_participant: bool = True,
    ) -> float:
        """Quick estimation of total cost in bps for a given participation rate."""
        participation = quantity / max(adv, 1)
        spread_bps = self.spread_cost_pct * 10000
        impact_bps = self.temp_impact_coeff * (participation**0.6) * 10000
        fixed_bps = (self.commission_pct + self.tax_pct) * 10000
        return spread_bps * 0.5 + impact_bps * 0.5 + fixed_bps

    def cost_curve(self, quantities: list[int], adv: int = 1_000_000) -> list[float]:
        """Generate cost curve for a range of quantities."""
        return [self.estimate_total_cost_bps(q, adv) for q in quantities]

    def __repr__(self) -> str:
        return (
            f"TransactionCostModel(spread={self.spread_cost_pct * 10000:.1f}bps, "
            f"temp_impact={self.temp_impact_coeff:.2f}, "
            f"perm_impact={self.perm_impact_coeff:.2f})"
        )
