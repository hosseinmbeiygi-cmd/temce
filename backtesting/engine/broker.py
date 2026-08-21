"""Broker with realistic transaction cost modeling.

Supports:
- Volume-based slippage (larger orders = more slippage)
- Market impact model (Almgren-Chriss simplified)
- Commission tiers (Iranian market specific)
- Partial fills for illiquid stocks
- Per-symbol ADV resolution (audit F5) — no silent generic 1M default
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backtesting.costs.iran_costs import (
    BROKER_PCT,
    CLEARING_FEE_PCT,
    SELL_TAX_PCT,
    IranTransactionCosts,
)
from backtesting.types import FillEvent, OrderEvent
from core.ids import new_id

if TYPE_CHECKING:
    from backtesting.engine.adv import AdvResolver

logger = logging.getLogger(__name__)


@dataclass
class TransactionCostConfig:
    """Configuration for transaction cost modeling.

    Note: rates are single-sourced from ``backtesting.costs.iran_costs``
    (audit F1). The canonical commission is computed through
    ``Broker.cost_model`` which also includes the CSD clearing fee; the
    fields below mirror the same rates for inspection/compat.
    """
    # Commission (Iranian market: 0.4% buy + 0.4% sell + 0.5% tax on sell)
    commission_pct: float = BROKER_PCT  # 0.4% per side (canonical)
    # Tax on sell (Iranian market: 0.5% on sell proceeds)
    sell_tax_pct: float = SELL_TAX_PCT
    # CSD clearing fee per side
    clearing_fee_pct: float = CLEARING_FEE_PCT
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
    commission_pct=BROKER_PCT,      # 0.4% commission per side (canonical)
    sell_tax_pct=SELL_TAX_PCT,      # 0.5% tax on sell
    clearing_fee_pct=CLEARING_FEE_PCT,
    base_slippage_bps=5.0,          # 5 bps base slippage
    volume_impact_factor=0.15,      # Higher impact for less liquid market
    min_slippage_bps=3.0,           # 3 bps minimum
    max_slippage_bps=150.0,         # 1.5% maximum
)

# Conservative costs for backtesting
CONSERVATIVE_COSTS = TransactionCostConfig(
    commission_pct=BROKER_PCT,
    sell_tax_pct=SELL_TAX_PCT,
    clearing_fee_pct=CLEARING_FEE_PCT,
    base_slippage_bps=10.0,
    volume_impact_factor=0.2,
    min_slippage_bps=5.0,
    max_slippage_bps=200.0,
)


class Broker:
    def __init__(
        self,
        commission_pct: float | None = None,
        slippage_bps: float | None = None,
        config: TransactionCostConfig | None = None,
        average_daily_volume: int = 1_000_000,
        cost_model: IranTransactionCosts | None = None,
        adv_resolver: AdvResolver | None = None,
        require_daily_volume: bool = False,
    ) -> None:
        self.config = config or IRAN_MARKET_COSTS
        self.commission_pct = commission_pct if commission_pct is not None else self.config.commission_pct
        self.slippage_bps = slippage_bps if slippage_bps is not None else self.config.base_slippage_bps
        # Per-symbol ADV (audit F5): when an order carries no daily_volume and
        # the resolver cache has no value, fail fast (dev mode) or warn and fall
        # back to `average_daily_volume` instead of silently under-pricing
        # slippage for every symbol.
        self.average_daily_volume = average_daily_volume
        self.adv_resolver = adv_resolver
        self.require_daily_volume = require_daily_volume
        self._warned_fallback: set[str] = set()
        # Canonical cost model — single source of truth for commission/tax/clearing
        # (audit F1/F3). Custom rates via commission_pct are still honoured.
        if cost_model is not None:
            self.cost_model = cost_model
        else:
            self.cost_model = IranTransactionCosts(
                broker_pct=commission_pct if commission_pct is not None else BROKER_PCT,
                sell_tax_pct=self.config.sell_tax_pct,
                clearing_fee_pct=self.config.clearing_fee_pct,
            )

    def _resolve_daily_volume(self, order: OrderEvent) -> int | None:
        """Resolve the ADV for an order (audit F5).

        Priority: ``order.daily_volume`` → AdvResolver cache (sync peek) →
        fail-fast (if ``require_daily_volume``) → None (warned fallback).
        """
        adv = getattr(order, "daily_volume", None)
        if adv:
            return int(adv)
        if self.adv_resolver is not None:
            cached = self.adv_resolver.peek(order.instrument_id)
            if cached:
                return int(cached)
        if self.require_daily_volume:
            raise ValueError(
                f"ADV unknown for '{order.instrument_id}': set OrderEvent.daily_volume "
                "or pre-warm the AdvResolver (audit F5 — no silent generic default)"
            )
        return None

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

        Iranian market structure (canonical — audit F1/F3):
        - Buy:  0.4% broker + 0.085% clearing
        - Sell: 0.4% broker + 0.085% clearing + 0.5% tax on proceeds

        Returns:
            Total commission in currency units
        """
        return self.cost_model.compute(side, exec_price, quantity)

    def submit_order_sync(self, order: OrderEvent) -> FillEvent | None:
        """Synchronous version of submit_order — for use in deterministic sync backtests."""
        if order.price <= 0 or order.quantity <= 0:
            return None

        daily_volume = self._resolve_daily_volume(order)
        if daily_volume is None and order.instrument_id not in self._warned_fallback:
            self._warned_fallback.add(order.instrument_id)
            logger.warning(
                "No ADV resolved for '%s' — using fallback %d for slippage. "
                "Set OrderEvent.daily_volume or pre-warm the AdvResolver (audit F5).",
                order.instrument_id, self.average_daily_volume,
            )

        slippage = self._compute_slippage(
            price=order.price,
            quantity=order.quantity,
            side=order.side,
            daily_volume=daily_volume,
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

        When the order carries no ``daily_volume``, the ADV is resolved
        automatically from the market DB (via the AdvResolver) so slippage
        reflects the symbol's real liquidity (audit F5).

        Returns FillEvent with computed slippage and commission.
        """
        if not getattr(order, "daily_volume", None) and self.adv_resolver is not None:
            resolved = await self.adv_resolver.resolve(order.instrument_id)
            if resolved:
                order.daily_volume = resolved
        return self.submit_order_sync(order)
