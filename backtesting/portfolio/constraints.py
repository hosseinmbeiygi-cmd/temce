from __future__ import annotations


class PortfolioConstraints:
    def __init__(self) -> None:
        self._min_weight: dict[str, float] = {}
        self._max_weight: dict[str, float] = {}
        self._sector_limits: dict[str, tuple[float, float]] = {}

    def set_weight_range(self, instrument_id: str, min_w: float, max_w: float) -> None:
        self._min_weight[instrument_id] = min_w
        self._max_weight[instrument_id] = max_w

    def set_sector_limit(self, sector: str, min_pct: float, max_pct: float) -> None:
        self._sector_limits[sector] = (min_pct, max_pct)

    def check_weights(self, weights: dict[str, float]) -> list[str]:
        violations: list[str] = []
        for inst, w in weights.items():
            min_w = self._min_weight.get(inst, 0.0)
            max_w = self._max_weight.get(inst, 1.0)
            if w < min_w:
                violations.append(f"{inst}: weight {w:.4f} < min {min_w:.4f}")
            if w > max_w:
                violations.append(f"{inst}: weight {w:.4f} > max {max_w:.4f}")
        return violations

    def is_satisfied(self, weights: dict[str, float]) -> bool:
        return len(self.check_weights(weights)) == 0

    def clear(self) -> None:
        self._min_weight.clear()
        self._max_weight.clear()
        self._sector_limits.clear()
