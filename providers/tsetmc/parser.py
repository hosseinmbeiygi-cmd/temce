from __future__ import annotations

from typing import Any


class TsetmcParser:
    """Parser for TSETMC (Tehran Stock Exchange) data."""

    def parse_quote(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "price_change": raw.get("PriceChange", 0),
            "price_change_pct": raw.get("PriceChangePercent", 0.0),
            "price_close": raw.get("ClosingPrice", 0),
            "price_last": raw.get("LastPrice", raw.get("ClosingPrice", 0)),
            "price_open": raw.get("OpeningPrice", 0),
            "price_high": raw.get("HighPrice", 0),
            "price_low": raw.get("LowPrice", 0),
            "volume": raw.get("Volume", 0),
            "value": raw.get("Value", 0),
            "trade_count": raw.get("TradeCount", 0),
        }

    def parse_trade(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "price": raw.get("Price", 0),
            "volume": raw.get("Quantity", 0),
            "date": str(raw.get("DateTime", "")),
        }

    def parse_orderbook(self, raw: dict[str, Any]) -> dict[str, Any]:
        bid_prices = raw.get("BidPrices", [])
        bid_volumes = raw.get("BidVolumes", [])
        ask_prices = raw.get("AskPrices", [])
        ask_volumes = raw.get("AskVolumes", [])

        bids = [{"price": p, "volume": v} for p, v in zip(bid_prices, bid_volumes, strict=False)]
        asks = [{"price": p, "volume": v} for p, v in zip(ask_prices, ask_volumes, strict=False)]
        return {"bids": bids, "asks": asks}

    def parse_instrument(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "symbol": raw.get("Symbol", ""),
            "name": raw.get("Name", ""),
            "isin": raw.get("ISIN", ""),
        }

    def normalize_symbol(self, symbol: str) -> str:
        return symbol.strip()
