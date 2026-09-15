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
from backtesting.models.spread import SpreadEstimator
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
    Roadmap v1:68 + v2:36 -> combined volume × volatility slippage.
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
    # Volatility adjustment (roadmap combined model)
    reference_volatility: float = 0.02  # 2% daily vol as reference
    volatility_multiplier: float = 2.0  # how strongly vol scales slippage
    # Spread estimation (Corwin-Schultz when orderbook unavailable)
    spread_model: str = "fixed"  # fixed | corwin_schultz | historical
    fixed_spread_bps: float = 5.0  # fallback spread when no OHLC history


# Iranian market specific cost tiers
IRAN_MARKET_COSTS = TransactionCostConfig(
    commission_pct=BROKER_PCT,  # 0.4% commission per side (canonical)
    sell_tax_pct=SELL_TAX_PCT,  # 0.5% tax on sell
    clearing_fee_pct=CLEARING_FEE_PCT,
    base_slippage_bps=5.0,  # 5 bps base slippage
    volume_impact_factor=0.15,  # Higher impact for less liquid market
    min_slippage_bps=3.0,  # 3 bps minimum
    max_slippage_bps=150.0,  # 1.5% maximum
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
        spread_estimator: SpreadEstimator | None = None,
    ) -> None:
        self.config = config or IRAN_MARKET_COSTS
        self.commission_pct = commission_pct if commission_pct is not None else self.config.commission_pct
        self.slippage_bps = slippage_bps if slippage_bps is not None else self.config.base_slippage_bps
        self.spread_estimator = spread_estimator or SpreadEstimator(fixed_spread_bps=self.config.fixed_spread_bps)
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
        volatility: float | None = None,
        spread_bps: float | None = None,
    ) -> float:
        """Combined volume × volatility slippage (roadmap v1:68 + v2:36).

        Formula (estimate, tagged as approximation):
          total_bps = base + (volume_term * vol_adj) + spread_component
          volume_term = participation * volume_impact_factor * 10_000
          vol_adj = 1 + volatility_multiplier * (vol/reference_vol - 1)
          spread_component comes from SpreadEstimator (Corwin-Schultz) when available
        """
        if price <= 0:
            return 0.0

        adv = daily_volume or self.average_daily_volume
        if adv <= 0:
            adv = 100_000

        participation_rate = min(quantity / max(adv, 1), 1.0)

        volume_term_bps = self.config.volume_impact_factor * participation_rate * 10_000

        vol_adj = 1.0
        if volatility is not None and volatility > 0:
            vol_ratio = volatility / max(self.config.reference_volatility, 0.001)
            vol_adj = 1 + self.config.volatility_multiplier * (vol_ratio - 1)
            vol_adj = max(0.5, vol_adj)

        total_slippage_bps = self.config.base_slippage_bps + volume_term_bps * vol_adj

        # When no volume impact but vol is high, scale base by vol_adj (v2:37)
        if volume_term_bps == 0 and volatility is not None and volatility > 0:
            total_slippage_bps = self.config.base_slippage_bps * vol_adj

        if spread_bps is not None and spread_bps > 0:
            # Half-spread is paid on each side (buy at ask, sell at bid)
            total_slippage_bps += spread_bps / 2.0

        total_slippage_bps = max(self.config.min_slippage_bps, min(total_slippage_bps, self.config.max_slippage_bps))

        slippage_per_share = price * (total_slippage_bps / 10_000)

        return slippage_per_share

    def compute_slippage_bps(
        self,
        quantity: int,
        daily_volume: int | None = None,
        volatility: float | None = None,
        spread_bps: float | None = None,
    ) -> float:
        """Return slippage in bps for reporting (without price)."""
        dummy_price = 100.0
        slip = self._compute_slippage(dummy_price, quantity, "buy", daily_volume, volatility, spread_bps)
        return (slip / dummy_price) * 10_000

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

    def submit_order_sync(
        self,
        order: OrderEvent,
        volatility: float | None = None,
        spread_bps: float | None = None,
        stress_multiplier: float = 1.0,
    ) -> FillEvent | list[FillEvent] | None:
        """Synchronous execution with partial-fill and stress support (A4/A5).

        - Volatility/spread passed from bar for combined slippage (A1/A2)
        - If quantity > 10% ADV, simulate walk-the-book: split into 2 fills (A4)
        - stress_multiplier inflates slippage 3-5x for stress scenarios (A5)
        """
        if order.price <= 0 or order.quantity <= 0:
            return None

        daily_volume = self._resolve_daily_volume(order)
        if daily_volume is None and order.instrument_id not in self._warned_fallback:
            self._warned_fallback.add(order.instrument_id)
            logger.warning(
                "No ADV resolved for '%s' — using fallback %d for slippage. "
                "Set OrderEvent.daily_volume or pre-warm the AdvResolver (audit F5).",
                order.instrument_id,
                self.average_daily_volume,
            )

        # Resolve volatility from order if not passed (e.g. atr-derived)
        if volatility is None:
            volatility = getattr(order, "volatility", None)
        if spread_bps is None:
            spread_bps = getattr(order, "spread_bps", None)

        base_slippage = self._compute_slippage(
            price=order.price,
            quantity=order.quantity,
            side=order.side,
            daily_volume=daily_volume,
            volatility=volatility,
            spread_bps=spread_bps,
        )
        # stress multiplier (v2:51)
        if stress_multiplier and stress_multiplier != 1.0:
            base_slippage = base_slippage * stress_multiplier

        adv = daily_volume or self.average_daily_volume or 100_000
        participation = order.quantity / max(adv, 1)

        # Partial fill / walk-the-book (A4): participation > 10% -> split
        if participation > 0.1 and order.quantity > 100:
            # first fill at base price, second at worse price (+ extra impact)
            first_qty = int(order.quantity * 0.6)
            second_qty = order.quantity - first_qty
            # extra slippage for walking the book (0.5x base extra)
            extra_slip = base_slippage * 0.5
            exec_price_1 = order.price + base_slippage if order.side == "buy" else order.price - base_slippage
            exec_price_2 = (
                order.price + base_slippage + extra_slip
                if order.side == "buy"
                else order.price - base_slippage - extra_slip
            )
            exec_price_1 = max(exec_price_1, 0.01)
            exec_price_2 = max(exec_price_2, 0.01)
            fills = []
            for qty, px, slip in [
                (first_qty, exec_price_1, base_slippage),
                (second_qty, exec_price_2, base_slippage + extra_slip),
            ]:
                if qty <= 0:
                    continue
                commission = self._compute_commission(px, qty, order.side)
                fills.append(
                    FillEvent(
                        order_id=order.order_id or new_id("ord"),
                        instrument_id=order.instrument_id,
                        side=order.side,
                        quantity=qty,
                        price=px,
                        commission=commission,
                        slippage=slip * qty,
                    )
                )
            return fills

        exec_price = order.price + base_slippage if order.side == "buy" else order.price - base_slippage
        exec_price = max(exec_price, 0.01)
        commission = self._compute_commission(exec_price, order.quantity, order.side)
        return FillEvent(
            order_id=order.order_id or new_id("ord"),
            instrument_id=order.instrument_id,
            side=order.side,
            quantity=order.quantity,
            price=exec_price,
            commission=commission,
            slippage=base_slippage * order.quantity,
        )

    async def submit_order(self, order: OrderEvent) -> FillEvent | list[FillEvent] | None:
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
        vol = getattr(order, "volatility", None)
        spr = getattr(order, "spread_bps", None)
        return self.submit_order_sync(order, volatility=vol, spread_bps=spr)
