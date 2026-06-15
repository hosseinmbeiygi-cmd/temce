from __future__ import annotations

from domain.portfolios.entities import PortfolioTransaction
from domain.portfolios.portfolio import Portfolio


def validate_allocation_weight(weight: float) -> bool:
    return 0.0 <= weight <= 1.0


def validate_portfolio_cash(cash: float) -> bool:
    return cash >= 0


def can_buy(portfolio: Portfolio, cost: float) -> bool:
    return portfolio.cash >= cost


def can_sell(quantity: int, held_quantity: int) -> bool:
    return quantity <= held_quantity


def validate_transaction(transaction: PortfolioTransaction) -> bool:
    if transaction.quantity <= 0:
        return False
    return not transaction.price < 0
