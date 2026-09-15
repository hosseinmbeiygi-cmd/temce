from __future__ import annotations


class CapitalAllocation:
    def __init__(self, total_capital: float = 0.0) -> None:
        self.total_capital = total_capital
        self._allocations: dict[str, float] = {}

    def allocate(self, strategy_weights: dict[str, float]) -> dict[str, float]:
        total_w = sum(strategy_weights.values())
        if total_w <= 0:
            return dict.fromkeys(strategy_weights, 0.0)
        self._allocations = {k: self.total_capital * (v / total_w) for k, v in strategy_weights.items()}
        return dict(self._allocations)

    def get_allocation(self, strategy_name: str) -> float:
        return self._allocations.get(strategy_name, 0.0)

    def get_allocations(self) -> dict[str, float]:
        return dict(self._allocations)

    def adjust(self, strategy_name: str, new_capital: float) -> None:
        self._allocations[strategy_name] = new_capital

    def remaining(self) -> float:
        used = sum(self._allocations.values())
        return max(0.0, self.total_capital - used)

    def reset(self) -> None:
        self._allocations.clear()
