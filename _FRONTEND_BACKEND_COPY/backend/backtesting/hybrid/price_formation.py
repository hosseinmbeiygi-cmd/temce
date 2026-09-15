from __future__ import annotations

from typing import Any


class PriceFormation:
    """Models how prices are formed in the hybrid market simulation.

    Two modes:
    - Anchored: simulated price stays anchored to historical price with impact adjustments
    - Endogenous: price is fully determined by order flow (no historical anchor)
    """

    def __init__(self, mode: str = "anchored") -> None:
        if mode not in ("anchored", "endogenous"):
            msg = f"Unknown price formation mode: {mode}. Use 'anchored' or 'endogenous'."
            raise ValueError(msg)
        self.mode = mode
        self._simulated_price: float = 0.0
        self._historical_price: float = 0.0
        self._price_series: list[float] = []

    def set_historical_price(self, price: float) -> None:
        self._historical_price = price
        if self._simulated_price <= 0:
            self._simulated_price = price

    def compute_price(
        self,
        historical_price: float,
        imbalance: float = 0.0,
        trade_volume: int = 0,
        adv: int = 1_000_000,
        eta: float = 0.1,
        alpha: float = 0.6,
        regime: str = "normal",
    ) -> float:
        """Compute the new simulated price based on order flow and market conditions."""
        self._historical_price = historical_price

        if self._simulated_price <= 0:
            self._simulated_price = historical_price

        # Market impact from order flow
        impact = 0.0
        if trade_volume > 0 and adv > 0:
            participation = trade_volume / max(adv, 1)
            impact = eta * (participation**alpha)

        # Imbalance pressure
        imbalance_impact = imbalance * 0.001 * eta

        if self.mode == "anchored":
            # Price stays near historical with deviations from impact
            adjustment = impact + imbalance_impact
            regime_mult = self._regime_multiplier(regime)
            self._simulated_price = historical_price * (1.0 + adjustment * regime_mult)
        else:  # endogenous
            # Price is fully driven by order flow
            regime_mult = self._regime_multiplier(regime)
            self._simulated_price *= 1.0 + (impact + imbalance_impact) * regime_mult

        self._simulated_price = max(self._simulated_price, 0.01)
        self._price_series.append(self._simulated_price)
        return round(self._simulated_price, 2)

    def compute_from_trades(
        self,
        trades: list[dict[str, Any]],
        adv: int = 1_000_000,
        eta: float = 0.1,
        alpha: float = 0.6,
    ) -> list[float]:
        """Compute a full price series from a list of trade events."""
        prices: list[float] = []
        for trade in trades:
            price = trade.get("price", 0)
            volume = trade.get("volume", 0)
            if price <= 0:
                continue
            self.set_historical_price(price)
            new_price = self.compute_price(
                historical_price=price,
                trade_volume=volume,
                adv=adv,
                eta=eta,
                alpha=alpha,
            )
            prices.append(new_price)
        return prices

    def apply_impact_from_order(
        self,
        order_side: str,
        order_quantity: int,
        order_price: float,
        adv: int = 1_000_000,
        eta: float = 0.1,
        alpha: float = 0.6,
    ) -> float:
        """Apply market impact from a single order and return the new price."""
        if order_quantity <= 0 or adv <= 0:
            return self._simulated_price
        participation = order_quantity / max(adv, 1)
        impact = eta * (participation**alpha)
        if order_side == "buy":
            self._simulated_price *= 1.0 + impact
        else:
            self._simulated_price *= 1.0 - impact
        self._simulated_price = max(self._simulated_price, 0.01)
        self._price_series.append(self._simulated_price)
        return round(self._simulated_price, 2)

    def get_price_series(self) -> list[float]:
        return list(self._price_series)

    @property
    def current_price(self) -> float:
        return self._simulated_price

    def reset(self, initial_price: float = 0.0) -> None:
        self._simulated_price = initial_price
        self._historical_price = initial_price
        self._price_series.clear()

    @staticmethod
    def _regime_multiplier(regime: str) -> float:
        multipliers = {
            "normal": 1.0,
            "trend": 1.2,
            "panic": 2.5,
            "low_liquidity": 1.8,
            "queue_lock": 1.5,
        }
        return multipliers.get(regime, 1.0)


class AnchoredPriceModel:
    """Simple anchored price model: P_sim = P_hist + Impact."""

    def __init__(self, eta: float = 0.1, alpha: float = 0.6) -> None:
        self.eta = eta
        self.alpha = alpha
        self._last_historical: float = 0.0
        self._last_simulated: float = 0.0

    def compute(self, historical_price: float, trade_volume: int = 0, adv: int = 1_000_000) -> float:
        self._last_historical = historical_price
        if self._last_simulated <= 0:
            self._last_simulated = historical_price
        impact = 0.0
        if trade_volume > 0 and adv > 0:
            impact = self.eta * ((trade_volume / max(adv, 1)) ** self.alpha)
        self._last_simulated = historical_price * (1.0 + impact)
        return round(self._last_simulated, 2)

    def reset(self) -> None:
        self._last_historical = 0.0
        self._last_simulated = 0.0


class EndogenousPriceModel:
    """Fully endogenous price model: price is driven entirely by order flow."""

    def __init__(self, initial_price: float = 1000.0, eta: float = 0.1, alpha: float = 0.6) -> None:
        self.price = initial_price
        self.eta = eta
        self.alpha = alpha

    def apply_order(self, side: str, quantity: int, adv: int = 1_000_000) -> float:
        if quantity <= 0 or adv <= 0:
            return self.price
        participation = quantity / max(adv, 1)
        impact = self.eta * (participation**self.alpha)
        if side == "buy":
            self.price *= 1.0 + impact
        else:
            self.price *= 1.0 - impact
        self.price = max(self.price, 0.01)
        return round(self.price, 2)

    def reset(self, price: float = 1000.0) -> None:
        self.price = price
