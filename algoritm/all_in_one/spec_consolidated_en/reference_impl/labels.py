"""Executable label with explicit ineligibility reasons (never a silent zero)."""
from __future__ import annotations


def executable_label(entry_price: float, exit_price: float, fee_buy: float, fee_sell: float,
                     slip_buy: float, slip_sell: float, tradable_entry: bool, tradable_exit: bool,
                     rule_known: bool) -> dict:
    if not rule_known:
        return {"label": None, "eligible": False, "reason": "missing_execution_rule"}
    if not tradable_entry:
        return {"label": None, "eligible": False, "reason": "untradable_entry"}
    if not tradable_exit:
        return {"label": None, "eligible": False, "reason": "untradable_exit"}
    y = exit_price * (1 - fee_sell - slip_sell) / (entry_price * (1 + fee_buy + slip_buy)) - 1.0
    return {"label": y, "eligible": True, "reason": None}
