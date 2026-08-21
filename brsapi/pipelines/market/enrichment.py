from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.time import now_iran

logger = get_logger(__name__)


class MarketDataEnricher:
    def enrich_quote(self, data: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(data)
        price_close = enriched.get("price_close", 0)
        price_open = enriched.get("price_open", 0)
        price_high = enriched.get("price_high", 0)
        price_low = enriched.get("price_low", 0)
        volume = enriched.get("volume", 0)
        value = enriched.get("value", 0)

        if price_high > 0 and price_low > 0:
            enriched["spread_pct"] = round((price_high - price_low) / price_low * 100, 4)
        else:
            enriched["spread_pct"] = 0.0

        if price_open > 0 and price_close > 0:
            enriched["intraday_return_pct"] = round((price_close - price_open) / price_open * 100, 4)
        else:
            enriched["intraday_return_pct"] = 0.0

        if volume > 0 and price_close > 0:
            enriched["vwap"] = round(value / volume, 4) if value > 0 else price_close
        else:
            enriched["vwap"] = price_close

        bid_volume = enriched.get("bid_volume", 0)
        ask_volume = enriched.get("ask_volume", 0)
        total_depth = bid_volume + ask_volume
        if total_depth > 0:
            enriched["bid_ask_ratio"] = round(bid_volume / ask_volume, 4) if ask_volume > 0 else 999.0
            enriched["depth_imbalance"] = round((bid_volume - ask_volume) / total_depth, 4)
        else:
            enriched["bid_ask_ratio"] = 0.0
            enriched["depth_imbalance"] = 0.0

        enriched["enriched_at"] = now_iran().isoformat()
        enriched.setdefault("extra", {})
        return enriched

    def enrich_trade(self, data: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(data)
        price = enriched.get("price", 0)
        quantity = enriched.get("quantity", 0)
        enriched["trade_value"] = round(price * quantity, 2)
        enriched["enriched_at"] = now_iran().isoformat()
        enriched.setdefault("extra", {})
        return enriched

    def enrich_orderbook(self, data: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(data)
        bid_volumes = [enriched.get(f"bid_volume_{i}", 0) for i in range(1, 6)]
        ask_volumes = [enriched.get(f"ask_volume_{i}", 0) for i in range(1, 6)]
        bid_prices = [enriched.get(f"bid_price_{i}", 0) for i in range(1, 6)]
        ask_prices = [enriched.get(f"ask_price_{i}", 0) for i in range(1, 6)]

        total_bid = sum(bid_volumes)
        total_ask = sum(ask_volumes)
        enriched["total_bid_volume"] = total_bid
        enriched["total_ask_volume"] = total_ask

        non_zero_bids = [p for p, v in zip(bid_prices, bid_volumes, strict=False) if v > 0]
        non_zero_asks = [p for p, v in zip(ask_prices, ask_volumes, strict=False) if v > 0]
        enriched["best_bid"] = max(non_zero_bids) if non_zero_bids else 0
        enriched["best_ask"] = min(non_zero_asks) if non_zero_asks else 0

        if enriched["best_ask"] > 0 and enriched["best_bid"] > 0:
            enriched["spread"] = round(enriched["best_ask"] - enriched["best_bid"], 2)
            enriched["spread_pct"] = round(
                (enriched["best_ask"] - enriched["best_bid"]) / enriched["best_bid"] * 100, 4
            )
        else:
            enriched["spread"] = 0
            enriched["spread_pct"] = 0.0

        enriched["enriched_at"] = now_iran().isoformat()
        enriched.setdefault("extra", {})
        return enriched

    def enrich_batch(self, records: list[dict[str, Any]], record_type: str = "quote") -> list[dict[str, Any]]:
        enricher = {
            "quote": self.enrich_quote,
            "trade": self.enrich_trade,
            "orderbook": self.enrich_orderbook,
        }.get(record_type, self.enrich_quote)
        return [enricher(r) for r in records]
