from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AuctionSession(Enum):
    PREOPEN = "preopen"
    CONTINUOUS = "continuous"
    PRE_CLOSE = "pre_close"
    CLOSING = "closing"
    POST_CLOSE = "post_close"


@dataclass
class AuctionResult:
    clearing_price: float = 0.0
    matched_volume: int = 0
    imbalance: int = 0
    imbalance_pct: float = 0.0
    buy_volume: int = 0
    sell_volume: int = 0
    total_bids: int = 0
    total_asks: int = 0
    is_valid: bool = False
    uncrossed_bids: dict[float, int] = field(default_factory=dict)
    uncrossed_asks: dict[float, int] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
    price_limit_lower: float = 0.0
    price_limit_upper: float = 0.0


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

        total_buy = sum(bids.values())
        total_sell = sum(asks.values())

        for price in all_prices:
            buy_volume = sum(v for p, v in bids.items() if p >= price)
            sell_volume = sum(v for p, v in asks.items() if p <= price)
            matched = min(buy_volume, sell_volume)
            imbalance_val = abs(buy_volume - sell_volume)

            if matched > max_volume or (matched == max_volume and imbalance_val < min_imbalance):
                max_volume = matched
                best_price = price
                min_imbalance = imbalance_val

        # All unmatched bids/asks (orders that exceed matched volume)
        all_uncrossed_bids = {}
        all_uncrossed_asks = {}
        buy_cum = 0
        for p, v in sorted(bids.items(), reverse=True):
            if buy_cum >= max_volume:
                all_uncrossed_bids[p] = v
            buy_cum += v
        sell_cum = 0
        for p, v in sorted(asks.items()):
            if sell_cum >= max_volume:
                all_uncrossed_asks[p] = v
            sell_cum += v

        imbalance_pct = (min_imbalance / max_volume * 100.0) if max_volume > 0 else 0.0

        return AuctionResult(
            clearing_price=best_price,
            matched_volume=max_volume,
            imbalance=min_imbalance,
            imbalance_pct=imbalance_pct,
            buy_volume=total_buy,
            sell_volume=total_sell,
            total_bids=len(bids),
            total_asks=len(asks),
            is_valid=max_volume > 0,
            uncrossed_bids=all_uncrossed_bids,
            uncrossed_asks=all_uncrossed_asks,
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

    def calculate_periodic_auction(
        self,
        bids: dict[float, int],
        asks: dict[float, int],
        reference_price: float | None = None,
        price_limit_pct: float = 5.0,
    ) -> AuctionResult:
        """Periodic auction (e.g. opening auction with price limits)."""
        return self.calculate_opening_auction(bids, asks, reference_price, price_limit_pct)

    def calculate_base_market_auction(
        self,
        bids: dict[float, int],
        asks: dict[float, int],
        reference_price: float = 0.0,
        yellow_band_pct: float = 5.0,
        orange_band_pct: float = 3.0,
        red_band_pct: float = 1.5,
    ) -> AuctionResult:
        """Base market auction with tiered price bands."""
        result = self.calculate_clearing_price(bids, asks)
        if not result.is_valid:
            return result

        if reference_price > 0:
            yellow_limit = reference_price * (yellow_band_pct / 100.0)
            orange_limit = reference_price * (orange_band_pct / 100.0)
            red_limit = reference_price * (red_band_pct / 100.0)

            # Ensure tighter bands take precedence
            price_limit = max(red_limit, orange_limit, yellow_limit)
            lower = reference_price - price_limit
            upper = reference_price + price_limit
            result.price_limit_lower = lower
            result.price_limit_upper = upper
            result.clearing_price = max(lower, min(result.clearing_price, upper))

        return result

    def calculate_ime_auction(
        self,
        bids: dict[float, int],
        asks: dict[float, int],
        reference_price: float = 0.0,
        contract_spec: dict[str, Any] | None = None,
    ) -> AuctionResult:
        """IME (Iran Mercantile Exchange) auction with contract specifications."""
        result = self.calculate_clearing_price(bids, asks)
        if not result.is_valid:
            return result
        result.extra = dict(contract_spec or {})
        return result

    def apply_session_auction(
        self,
        bids: dict[float, int],
        asks: dict[float, int],
        session: AuctionSession,
        reference_price: float = 0.0,
    ) -> AuctionResult:
        """Apply auction logic based on the trading session type."""
        if session == AuctionSession.PREOPEN:
            return self.calculate_opening_auction(bids, asks, reference_price)
        elif session == AuctionSession.PRE_CLOSE:
            return self.calculate_closing_auction([], bids, asks)
        else:
            return self.calculate_clearing_price(bids, asks)
