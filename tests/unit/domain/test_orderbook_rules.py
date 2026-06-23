from __future__ import annotations


def test_orderbook_bids_ascending():
    from domain.orderbook.rules import OrderBookBidRule

    rule = OrderBookBidRule()
    assert rule.validate(bids=[{"price": 100, "volume": 10}, {"price": 99, "volume": 20}]) is True
    assert rule.validate(bids=[{"price": 100, "volume": 10}, {"price": 101, "volume": 20}]) is False


def test_orderbook_asks_ascending():
    from domain.orderbook.rules import OrderBookAskRule

    rule = OrderBookAskRule()
    assert rule.validate(asks=[{"price": 101, "volume": 10}, {"price": 102, "volume": 20}]) is True
    assert rule.validate(asks=[{"price": 102, "volume": 10}, {"price": 101, "volume": 20}]) is False


def test_orderbook_no_cross():
    from domain.orderbook.rules import NoCrossRule

    rule = NoCrossRule()
    assert rule.validate(best_bid=100, best_ask=101) is True
    assert rule.validate(best_bid=101, best_ask=100) is False


def test_orderbook_positive_volume():
    from domain.orderbook.rules import PositiveVolumeRule

    rule = PositiveVolumeRule()
    assert rule.validate(volume=1000) is True
    assert rule.validate(volume=0) is False
    assert rule.validate(volume=-100) is False


def test_orderbook_reasonable_spread():
    from domain.orderbook.rules import SpreadRule

    rule = SpreadRule(max_spread_bps=500)
    assert rule.validate(bid=100, ask=101) is True
    assert rule.validate(bid=100, ask=200) is False

