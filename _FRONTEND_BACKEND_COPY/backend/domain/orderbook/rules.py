from __future__ import annotations

from domain.common.enum_types import OrderSide


class OrderBookBidRule:
    """Validate that bids are in descending order (best bid first)."""

    def validate(self, bids: list[dict]) -> bool:
        if len(bids) < 2:
            return True
        prices = [b.get("price", 0) for b in bids]
        return all(prices[i] >= prices[i + 1] for i in range(len(prices) - 1))


class OrderBookAskRule:
    """Validate that asks are in ascending order (best ask first)."""

    def validate(self, asks: list[dict]) -> bool:
        if len(asks) < 2:
            return True
        prices = [a.get("price", 0) for a in asks]
        return all(prices[i] <= prices[i + 1] for i in range(len(prices) - 1))


class NoCrossRule:
    """Validate that best_bid is less than best_ask (no cross)."""

    def validate(self, best_bid: float, best_ask: float) -> bool:
        return best_bid < best_ask


class PositiveVolumeRule:
    """Validate that volume is positive."""

    def validate(self, volume: int) -> bool:
        return volume > 0


class SpreadRule:
    """Validate that the bid-ask spread is within acceptable limits."""

    def __init__(self, max_spread_bps: float = 1000.0) -> None:
        self.max_spread_bps = max_spread_bps

    def validate(self, bid: float, ask: float) -> bool:
        if bid <= 0:
            return False
        spread_bps = ((ask - bid) / bid) * 10000
        return spread_bps <= self.max_spread_bps


def validate_orderbook_price(price: float) -> bool:
    return price > 0


def validate_orderbook_volume(volume: int) -> bool:
    return volume >= 0


def validate_orderbook_side(side: str) -> bool:
    return side in ("buy", "sell")


def is_bid_side(side: OrderSide) -> bool:
    return side == OrderSide.BUY


def is_ask_side(side: OrderSide) -> bool:
    return side == OrderSide.SELL


def calculate_imbalance(bid_volume: int, ask_volume: int) -> float:
    total = bid_volume + ask_volume
    if total == 0:
        return 0.0
    return (bid_volume - ask_volume) / total
