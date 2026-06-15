from __future__ import annotations

from domain.market_data.orderbook import OrderBook, OrderBookLevel


def sample_orderbook_level(price: float, volume: int, count: int = 1) -> OrderBookLevel:
    return OrderBookLevel(price=price, volume=volume, count=count)


def sample_orderbook(
    id: str = "ob_test_001",
    instrument_id: str = "inst_test_001",
    symbol: str = "فولاد",
) -> OrderBook:
    return OrderBook(
        id=id,
        instrument_id=instrument_id,
        symbol=symbol,
        bids=[
            sample_orderbook_level(15040, 15000, 5),
            sample_orderbook_level(15030, 22000, 8),
            sample_orderbook_level(15020, 18000, 3),
        ],
        asks=[
            sample_orderbook_level(15060, 10000, 4),
            sample_orderbook_level(15070, 25000, 7),
            sample_orderbook_level(15080, 12000, 2),
        ],
        time="12:30:00",
        date="2024-01-15",
    )
