from __future__ import annotations


class CommissionModel:
    """Commission model for backtesting calculations.

    .. deprecated::
        Legacy model — kept for backward compatibility. Use
        :class:`backtesting.costs.iran_costs.IranTransactionCosts` or
        :class:`backtesting.engine.commission.CommissionModel` instead.
        Its flat rate (0.35%) is LOWER than the real Iranian broker fee
        (0.4%) and it applies tax on both sides, which understates costs.
    """

    def __init__(
        self,
        commission_pct: float = 0.0035,
        tax_pct: float = 0.005,
        min_commission: float = 0.0,
        max_commission: float = float("inf"),
        fee_per_order: float = 0.0,
    ) -> None:
        self.commission_pct = commission_pct
        self.tax_pct = tax_pct
        self.min_commission = min_commission
        self.max_commission = max_commission
        self.fee_per_order = fee_per_order

    def calculate(self, trade_value: float) -> float:
        if trade_value == 0:
            return 0.0
        commission = trade_value * self.commission_pct + self.fee_per_order
        commission = max(commission, self.min_commission)
        commission = min(commission, self.max_commission)
        return commission
