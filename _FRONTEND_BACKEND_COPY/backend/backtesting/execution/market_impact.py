from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MarketImpactModel:
    linear_coeff: float = 0.1
    sqrt_coeff: float = 0.05
    permanent_impact_pct: float = 0.02

    def compute_impact(self, order_size: int, volume: int, price: float) -> dict[str, float]:
        participation = order_size / max(volume, 1)
        linear = self.linear_coeff * participation * price
        sqrt_impact = self.sqrt_coeff * (participation**0.5) * price
        permanent = self.permanent_impact_pct * price * participation
        total = linear + sqrt_impact + permanent
        return {
            "linear": linear,
            "sqrt": sqrt_impact,
            "permanent": permanent,
            "total": total,
            "participation": participation,
        }

    def get_effective_price(self, order_size: int, volume: int, price: float, side: str) -> float:
        impact = self.compute_impact(order_size, volume, price)
        return price + impact["total"] if side == "buy" else price - impact["total"]
