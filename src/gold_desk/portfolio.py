"""Portfolio Service — P&L calculator + DCA tracking.

هر holding → قیمت فعلی از snapshot → P&L.
هر DCA plan → current tranche وضعیت + چه زمانی پله بعدی فعال می‌شود.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import GoldDCAPlanModel, GoldHoldingModel, GoldTradeModel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HoldingPnL:
    symbol: str
    display_name: str
    quantity: float
    avg_buy_price: float
    current_price: float
    cost_basis: float
    current_value: float
    pnl_irt: float
    pnl_pct: float
    n_purchases: int


@dataclass(frozen=True)
class PortfolioSummary:
    total_cost: float
    total_value: float
    total_pnl: float
    total_pnl_pct: float
    holdings: list[HoldingPnL]
    by_symbol: dict[str, HoldingPnL]


def get_current_prices(snap: dict | None) -> dict[str, float]:
    """استخراج قیمت فعلی از snapshot."""
    if not snap:
        return {}
    prices: dict[str, float] = {}
    coins = snap.get("coins", {})
    for k, a in coins.items():
        prices[a.get("symbol", k)] = float(a.get("market_price", 0))
    gold = snap.get("gold", {})
    for k, a in gold.items():
        prices[a.get("symbol", k)] = float(a.get("market_price", 0))
    return prices


async def get_holdings_grouped(
    session: AsyncSession,
    current_prices: dict[str, float],
) -> PortfolioSummary:
    """Holdings گروه‌شده بر اساس symbol با P&L."""
    stmt = select(GoldHoldingModel).order_by(GoldHoldingModel.symbol, GoldHoldingModel.bought_at)
    rows = (await session.execute(stmt)).scalars().all()

    by_symbol: dict[str, list] = {}
    for h in rows:
        by_symbol.setdefault(h.symbol, []).append(h)

    holdings: list[HoldingPnL] = []
    total_cost = 0.0
    total_value = 0.0

    for sym, items in by_symbol.items():
        total_qty = sum(h.quantity for h in items)
        total_cost_sym = sum(h.buy_amount_irt for h in items)
        avg_buy = total_cost_sym / total_qty if total_qty else 0
        current = current_prices.get(sym, avg_buy)
        current_val = total_qty * current
        pnl_irt = current_val - total_cost_sym
        pnl_pct = (pnl_irt / total_cost_sym * 100) if total_cost_sym else 0
        holdings.append(
            HoldingPnL(
                symbol=sym,
                display_name=items[0].display_name,
                quantity=total_qty,
                avg_buy_price=avg_buy,
                current_price=current,
                cost_basis=total_cost_sym,
                current_value=current_val,
                pnl_irt=pnl_irt,
                pnl_pct=pnl_pct,
                n_purchases=len(items),
            )
        )
        total_cost += total_cost_sym
        total_value += current_val

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0

    holdings.sort(key=lambda h: h.symbol)
    return PortfolioSummary(
        total_cost=total_cost,
        total_value=total_value,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        holdings=holdings,
        by_symbol={h.symbol: h for h in holdings},
    )


# ── DCA Plan helpers ──────────────────────────────────────────


@dataclass(frozen=True)
class DCAPlanStatus:
    plan_id: int
    name: str
    total_capital: float
    executed: int
    remaining: int
    next_tranche_pct: float
    next_tranche_amount: float
    next_trigger: str
    current_score: int
    stop_loss_pct: float
    take_profit_pct: float


def get_plan_status(plan: GoldDCAPlanModel, current_score: int) -> DCAPlanStatus:
    """وضعیت فعلی پلن DCA + شرط پله بعدی."""
    try:
        ladder = json.loads(plan.ladder_json)
    except Exception:
        ladder = []

    executed = plan.executed_tranches
    if executed >= len(ladder):
        return DCAPlanStatus(
            plan_id=plan.id,
            name=plan.name,
            total_capital=plan.total_capital_irt,
            executed=executed,
            remaining=0,
            next_tranche_pct=0,
            next_tranche_amount=0,
            next_trigger="پلن کامل اجرا شد",
            current_score=current_score,
            stop_loss_pct=plan.stop_loss_pct,
            take_profit_pct=plan.take_profit_pct,
        )

    next_t = ladder[executed]
    return DCAPlanStatus(
        plan_id=plan.id,
        name=plan.name,
        total_capital=plan.total_capital_irt,
        executed=executed,
        remaining=len(ladder) - executed,
        next_tranche_pct=next_t.get("pct", 0),
        next_tranche_amount=next_t.get("amount_irt", 0),
        next_trigger=next_t.get("trigger", "—"),
        current_score=current_score,
        stop_loss_pct=plan.stop_loss_pct,
        take_profit_pct=plan.take_profit_pct,
    )


# ── P&L snapshot (روزانه) ────────────────────────────────────


async def record_trade(
    session: AsyncSession,
    *,
    symbol: str,
    action: str,
    quantity: float,
    price: float,
    amount_irt: float,
    fee_pct: float = 0.0,
    holding_id: int | None = None,
    plan_id: int | None = None,
    note: str | None = None,
) -> GoldTradeModel:
    fee_irt = amount_irt * (fee_pct / 100.0)
    pnl = 0.0
    if action == "sell" and holding_id:
        h = await session.get(GoldHoldingModel, holding_id)
        if h:
            pnl = (price - h.buy_price) * quantity
    trade = GoldTradeModel(
        symbol=symbol,
        action=action,
        quantity=quantity,
        price=price,
        amount_irt=amount_irt,
        fee_irt=fee_irt,
        pnl_irt=pnl,
        holding_id=holding_id,
        plan_id=plan_id,
        note=note,
    )
    session.add(trade)
    await session.commit()
    await session.refresh(trade)
    return trade
