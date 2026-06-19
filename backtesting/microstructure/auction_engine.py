from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AuctionResult:
    clearing_price: float = 0.0
    matched_volume: int = 0
    imbalance: int = 0
    buy_volume: int = 0
    sell_volume: int = 0
    total_bids: int = 0
    total_asks: int = 0
    is_valid: bool = False


class AuctionEngine:
    def calculate_clearing_price(
        self,
        bids: dict[float, int],
        asks: dict[float, int],
    ) -> AuctionResult:
        if not bids or not asks:
            return AuctionResult()

        all_prices = sorted(set(bids.keys()) | set(asks.keys()))
        best_price = 0.0
        max_volume = 0
        min_imbalance = float("inf")

        for price in all_prices:
            buy_volume = sum(v for p, v in bids.items() if p >= price)
            sell_volume = sum(v for p, v in asks.items() if p <= price)
            matched = min(buy_volume, sell_volume)
            imbalance = abs(buy_volume - sell_volume)

            if matched > max_volume or (matched == max_volume and imbalance < min_imbalance):
                max_volume = matched
                best_price = price
                min_imbalance = imbalance

        return AuctionResult(
            clearing_price=best_price,
            matched_volume=max_volume,
            imbalance=min_imbalance,
            buy_volume=sum(bids.values()),
            sell_volume=sum(asks.values()),
            total_bids=len(bids),
            total_asks=len(asks),
            is_valid=max_volume > 0,
        )

    def calculate_opening_auction(
        self,
        bids: dict[float, int],
        asks: dict[float, int],
        reference_price: float | None = None,
        price_limit_pct: float = 5.0,
    ) -> AuctionResult:
        result = self.calculate_clearing_price(bids, asks)
        if not result.is_valid:
            return result

        if reference_price and reference_price > 0:
            limit = reference_price * (price_limit_pct / 100.0)
            lower = reference_price - limit
            upper = reference_price + limit
            if result.clearing_price < lower or result.clearing_price > upper:
                result.clearing_price = max(lower, min(result.clearing_price, upper))

        return result

    def calculate_closing_auction(
        self,
        last_trades: list[float],
        bids: dict[float, int],
        asks: dict[float, int],
    ) -> AuctionResult:
        return self.calculate_clearing_price(bids, asks)

    def calculate_volatility_auction(
        self,
        bids: dict[float, int],
        asks: dict[float, int],
        reference_price: float,
        band_pct: float,
    ) -> AuctionResult:
        result = self.calculate_clearing_price(bids, asks)
        if not result.is_valid:
            return result
        lower = reference_price * (1.0 - band_pct / 100.0)
        upper = reference_price * (1.0 + band_pct / 100.0)
        result.clearing_price = max(lower, min(result.clearing_price, upper))
        return result
