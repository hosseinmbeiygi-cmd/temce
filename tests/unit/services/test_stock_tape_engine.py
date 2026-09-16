"""Unit tests for TSE tape-reading engine (services/stock_tape_engine.py).

فرمول‌های بومی بورس تهران — بدون دیتابیس.
"""

from __future__ import annotations

import pytest

from services.stock_tape_engine import (
    base_volume_status,
    buyer_seller_power_ratio,
    close_manipulation_index,
    compute_tape_reading,
    order_book_imbalance,
    per_capita_toman,
    queue_value,
    slippage_estimate,
    smart_money_inflow,
    unusual_volume_ratio,
)

# ── قدرت خریدار (فرمول استاندارد TSE) ──


def test_buyer_power_basic():
    # میانگین خرید 2000، میانگین فروش 1000 → ratio=2.0 × min(1, 1000/1000)=1 → 2.0
    r = buyer_seller_power_ratio(
        real_buy_volume=200_000, real_buy_count=100,
        real_sell_volume=100_000, real_sell_count=100,
        total_volume=1_000_000, base_volume=1_000_000,
    )
    assert r == pytest.approx(2.0)


def test_buyer_power_adjusted_by_base_volume():
    # حجم کل نصف حجم مبنا → ضریب 0.5
    r = buyer_seller_power_ratio(
        real_buy_volume=200_000, real_buy_count=100,
        real_sell_volume=100_000, real_sell_count=100,
        total_volume=500_000, base_volume=1_000_000,
    )
    assert r == pytest.approx(1.0)


def test_buyer_power_insufficient_data():
    assert buyer_seller_power_ratio(0, 0, 100, 10, 1000, 100) is None


# ── سرانه ──


def test_per_capita_million_toman():
    # ۱ میلیارد ریال / ۱۰ کد = ۱۰۰ میلیون ریال = ۱۰ میلیون تومان
    assert per_capita_toman(1_000_000_000, 10) == pytest.approx(10.0)
    assert per_capita_toman(1_000, 0) is None


# ── پول هوشمند ──


def test_smart_money_inflow():
    # سرانه خرید ۱۰ م.ت، سرانه فروش ۱ م.ت → ۱۰× > آستانه ۵×
    res = smart_money_inflow(
        real_buy_value=1_000_000_000, real_sell_value=100_000_000,
        real_buy_count=100, real_sell_count=100,
        trade_value=2_000_000_000,
    )
    assert res == "inflow"


def test_smart_money_outflow():
    res = smart_money_inflow(
        real_buy_value=100_000_000, real_sell_value=1_000_000_000,
        real_buy_count=100, real_sell_count=100,
        trade_value=2_000_000_000,
    )
    assert res == "outflow"


def test_smart_money_neutral_moderate_ratio():
    # سرانه خرید ۲۰ م.ت، سرانه فروش ۵ م.ت → نسبت ۴× < آستانه ۵× → خنثی
    res = smart_money_inflow(
        real_buy_value=20_000_000_000, real_sell_value=10_000_000_000,
        real_buy_count=1000, real_sell_count=2000,
        trade_value=30_000_000_000,
    )
    assert res == "neutral"


def test_smart_money_neutral_small_values():
    res = smart_money_inflow(
        real_buy_value=10_000_000, real_sell_value=1_000_000,
        real_buy_count=10, real_sell_count=10,
        trade_value=20_000_000,
    )
    # نسبت ۱۰× ولی ارزش خرید زیر آستانه ۱۰۰ م.تومان
    assert res == "neutral"


# ── رنج‌کشی ──


def test_close_manipulation_positive():
    res = close_manipulation_index(last_price=1030, close_price=1000)
    assert res is not None
    assert res["kind"] == "positive_manipulation"
    assert res["spread_pct"] == pytest.approx(3.0)


def test_close_manipulation_normal():
    res = close_manipulation_index(last_price=1010, close_price=1000)
    assert res["kind"] == "normal"


# ── حجم مبنا ──


def test_base_volume_states():
    assert base_volume_status(1_000_000, 1_000_000)["state"] == "filled"
    assert base_volume_status(600_000, 1_000_000)["state"] == "filling"
    assert base_volume_status(100_000, 1_000_000)["state"] == "low"


# ── حجم مشکوک ──


def test_unusual_volume_extreme():
    hist = [100.0] * 20
    res = unusual_volume_ratio(1000.0, hist)
    assert res is not None
    assert res["level"] == "extreme"


def test_unusual_volume_normal():
    hist = [100.0] * 20
    assert unusual_volume_ratio(110.0, hist)["level"] == "normal"


# ── Order Book ──


def test_obi_balanced_and_imbalanced():
    bids = [{"price": 100, "volume": 500}, {"price": 99, "volume": 500}]
    asks = [{"price": 101, "volume": 1000}]
    obi = order_book_imbalance(bids, asks)
    # (1000-1000)/2000 = 0
    assert obi == pytest.approx(0.0)
    obi2 = order_book_imbalance(bids, [{"price": 101, "volume": 100}])
    assert obi2 > 0.8  # صف خرید سنگین


def test_queue_value_buy_queue():
    bids = [{"price": 100, "volume": 900}]
    asks = [{"price": 101, "volume": 100}]
    q = queue_value(bids, asks, price_last=100)
    assert q is not None
    assert q["state"] == "buy_queue"


def test_slippage_multilevel():
    asks = [
        {"price": 100, "volume": 100},
        {"price": 101, "volume": 100},
        {"price": 102, "volume": 100},
    ]
    res = slippage_estimate(asks, order_volume=250)
    assert res is not None
    # 100 در ۱۰۰، ۱۰۰ در ۱۰۱، ۵۰ در ۱۰۲
    assert res["avg_exec_price"] == pytest.approx((100 * 100 + 100 * 101 + 50 * 102) / 250)
    assert res["slippage_pct"] > 0


def test_slippage_insufficient_depth():
    asks = [{"price": 100, "volume": 50}]
    assert slippage_estimate(asks, order_volume=100) is None


# ── Aggregate ──


def test_compute_tape_reading_full():
    tape = {
        "buy_real_volume": 2_000_000, "buy_real_count": 1000,
        "sell_real_volume": 1_000_000, "sell_real_count": 2000,
        "buy_real_value": 20_000_000_000, "sell_real_value": 1_000_000_000,
        "trade_volume": 5_000_000, "base_volume": 5_000_000,
        "last_price": 1000, "close_price": 1005,
        "close_change_pct": 1.0,
    }
    out = compute_tape_reading(tape, volume_history_20d=[100.0] * 20)
    assert 0 <= out["tape_score"] <= 100
    assert out["buyer_power_ratio"] is not None
    assert out["smart_money"] == "inflow"
