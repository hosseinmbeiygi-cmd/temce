"""Compose snapshot -> MarketSummary -> arbitrage rows -> signals -> kill-switch.

Single entry point: ``SignalEngine.overview()`` returns the full payload the
``/api/v1/currency/overview`` endpoint serves.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.currency_service.domain import (
    ArbitrageRow,
    KillSwitch,
    MarketSummary,
    RateSnapshot,
    Signal,
    arbitrage_status_for,
    bubble_index,
    check_kill_switch,
    classify_sentiment,
    generate_signals,
    spread_pct,
    tether_arbitrage_pct,
)
from apps.currency_service.services.collector import get_collector


@dataclass(frozen=True)
class OverviewPayload:
    snapshot: RateSnapshot
    market_summary: MarketSummary
    arbitrage_matrix: list[ArbitrageRow]
    signals: list[Signal]
    kill_switch: KillSwitch


class SignalEngine:
    """Stateless orchestrator. Pass any collector."""

    def __init__(self, collector=None) -> None:
        self._collector = collector or get_collector()

    async def snapshot(self) -> RateSnapshot:
        return await self._collector.fetch()

    @staticmethod
    def build_summary(snap: RateSnapshot) -> MarketSummary:
        free = snap.free.sell_price
        bubble = bubble_index(free, snap.official_cbi)
        arb = tether_arbitrage_pct(snap.usdt.sell_price, free)
        spread = spread_pct(snap.free.sell_price, snap.free.buy_price)
        return MarketSummary(
            free_market_usd=free,
            official_cbi_usd=snap.official_cbi,
            nima_usd=snap.nima.sell_price,
            usdt_irt=snap.usdt.sell_price,
            bubble_index=bubble,
            daily_volatility=snap.free.daily_change_pct,
            bid_ask_spread=spread,
            tether_arbitrage=arb,
            sentiment=classify_sentiment(bubble, snap.free.daily_change_pct),  # type: ignore[arg-type]
        )

    @staticmethod
    def build_arbitrage_matrix(snap: RateSnapshot) -> list[ArbitrageRow]:
        free = snap.free.sell_price
        rows: list[ArbitrageRow] = []

        for name, price in [
            ("نرخ رسمی (CBI)", snap.official_cbi),
            ("نرخ نیما", snap.nima.sell_price),
            ("تتر (USDT)", snap.usdt.sell_price),
        ]:
            diff = price - free
            spread_pct_value = ((price - free) / free) * 100.0 if free else 0.0
            rows.append(
                ArbitrageRow(
                    name=name,
                    price=price,
                    difference_with_free_market=diff,
                    spread_pct=spread_pct_value,
                    status=arbitrage_status_for(spread_pct_value),  # type: ignore[arg-type]
                )
            )

        return rows

    async def overview(self, hourly_change_pct: float = 0.0) -> OverviewPayload:
        snap = await self.snapshot()
        market = self.build_summary(snap)
        return OverviewPayload(
            snapshot=snap,
            market_summary=market,
            arbitrage_matrix=self.build_arbitrage_matrix(snap),
            signals=generate_signals(market),
            kill_switch=check_kill_switch(market, hourly_change_pct=hourly_change_pct),
        )
