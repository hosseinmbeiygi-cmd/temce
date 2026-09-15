from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExposureLimitRule:
    instrument_id: str = ""
    max_notional: float = float("inf")
    max_weight: float = 0.1
    max_leverage: float = 1.0


class ExposureLimits:
    def __init__(self) -> None:
        self._rules: dict[str, ExposureLimitRule] = {}

    def add_rule(self, rule: ExposureLimitRule) -> None:
        self._rules[rule.instrument_id] = rule

    def remove_rule(self, instrument_id: str) -> None:
        self._rules.pop(instrument_id, None)

    def check_exposure(self, instrument_id: str, notional: float, total_capital: float) -> bool:
        rule = self._rules.get(instrument_id)
        if rule is None:
            return True
        if notional > rule.max_notional:
            return False
        weight = notional / total_capital if total_capital > 0 else 0.0
        if weight > rule.max_weight:
            return False
        total_exposure = sum(abs(n) for n in [notional])
        return not total_exposure / total_capital > rule.max_leverage

    def get_max_position_size(self, instrument_id: str, total_capital: float, price: float) -> int:
        rule = self._rules.get(instrument_id)
        if rule is None:
            return int(total_capital / price) if price > 0 else 0
        max_by_weight = int((total_capital * rule.max_weight) / price) if price > 0 else 0
        max_by_notional = int(rule.max_notional / price) if price > 0 else 0
        return min(max_by_weight, max_by_notional)

    def clear(self) -> None:
        self._rules.clear()
