"""Unit tests for technical + signal engines (stock_technical_engine, stock_signal_engine)."""

from __future__ import annotations

import random

import pytest

from services.stock_signal_engine import (
    compute_composite_signal,
    compute_tech_score,
    detect_market_regime,
    fibonacci_targets,
    kelly_position_size,
)
from services.stock_technical_engine import (
    atr,
    bollinger,
    compute_indicator_snapshot,
    detect_rsi_divergence,
    ema_cross,
    ichimoku,
    macd,
    mfi,
    pivot_points,
    rsi,
    squeeze_state,
    trend_alignment_score,
    vwap_intraday,
)

# ── Fixtures ──


def _candles(n=260, drift=0.0008, seed=42, base=10_000.0):
    rng = random.Random(seed)
    close = base
    out = []
    for i in range(n):
        ch = drift * base + rng.gauss(0, base * 0.012)
        o = close
        close = close + ch
        h = max(o, close) + abs(rng.gauss(0, base * 0.004))
        low_v = min(o, close) - abs(rng.gauss(0, base * 0.004))
        out.append({"date": f"d{i}", "open": o, "high": h, "low": low_v, "close": close, "volume": rng.uniform(5e6, 2e7)})
    return out


# ── RSI ──


def test_rsi_range_and_trend():
    candles = _candles(drift=0.002)
    closes = [c["close"] for c in candles]
    r = [v for v in rsi(closes) if v is not None]
    assert all(0 <= v <= 100 for v in r)
    assert r[-1] > 55  # روند صعودی → RSI بالا


def test_rsi_all_down_gives_low():
    closes = [10_000 - i * 10 for i in range(50)]
    r = [v for v in rsi(closes) if v is not None]
    assert r[-1] < 20


def test_divergence_returns_known_labels():
    closes = [10_000 + i * 20 for i in range(60)]
    div = detect_rsi_divergence(closes, rsi(closes))
    assert div is None or div in ("RD+", "RD-", "HD+", "HD-")


# ── MACD / EMA ──


def test_macd_structure():
    candles = _candles()
    closes = [c["close"] for c in candles]
    res = macd(closes)
    assert res["cross"] in ("none", "bullish_cross", "bearish_cross")
    vals = [v for v in res["macd"] if v is not None]
    assert len(vals) > 30


def test_ema_cross_labels():
    vals, cross = ema_cross([c["close"] for c in _candles()])
    assert cross in ("none", "golden", "death")
    assert vals["ema_20"] is not None


# ── Ichimoku ──


def test_ichimoku_complete():
    candles = _candles(drift=0.003)
    ich = ichimoku(candles)
    assert ich["state"] in ("above_kumo", "below_kumo", "inside_kumo", "insufficient")
    if ich["state"] != "insufficient":
        assert ich["tenkan"] is not None and ich["kijun"] is not None
        assert ich["kumo_twist"] in ("bullish_twist", "bearish_twist")


def test_ichimoku_insufficient_data():
    ich = ichimoku(_candles(30))
    assert ich["state"] == "insufficient"


# ── Bollinger / Squeeze ──


def test_bollinger_bands():
    candles = _candles()
    closes = [c["close"] for c in candles]
    bb = bollinger(closes)
    assert bb["upper"] > bb["middle"] > bb["lower"]
    kc = {"upper": bb["upper"] * 2, "lower": bb["lower"] * 0.5}
    assert squeeze_state(bb, kc) == "squeeze"


# ── ATR / MFI / VWAP ──


def test_atr_positive():
    assert atr(_candles()) is not None and atr(_candles()) > 0


def test_mfi_range():
    v = mfi(_candles())
    assert v is None or 0 <= v <= 100


def test_vwap_weighted():
    items = [
        {"price": 100, "volume": 300},
        {"price": 110, "volume": 100},
    ]
    assert vwap_intraday(items) == pytest.approx((100 * 300 + 110 * 100) / 400)


# ── Pivots ──


def test_pivots_structure():
    p = pivot_points(high=1100, low=1000, close=1050)
    assert p["classic"]["R1"] > p["classic"]["P"] > p["classic"]["S1"]
    assert p["camarilla"]["H4"] > p["camarilla"]["H3"] > p["camarilla"]["L3"] > p["camarilla"]["L4"]


# ── MTF ──


def test_trend_alignment_bull_and_bear():
    up = [10_000 * (1.001 ** i) for i in range(120)]
    down = [10_000 * (0.999 ** i) for i in range(120)]
    assert trend_alignment_score(up, up) == 100.0
    assert trend_alignment_score(down, down) == 0.0


# ── Snapshot aggregate ──


def test_indicator_snapshot_ok():
    snap = compute_indicator_snapshot(_candles())
    assert snap["ok"] is True
    assert 0 <= compute_tech_score(snap) <= 100


def test_indicator_snapshot_insufficient():
    assert compute_indicator_snapshot(_candles(10))["ok"] is False


# ── Signal engine ──


def test_fibonacci_targets_ordering():
    t = fibonacci_targets(swing_low=1000, swing_high=1100, entry=1050)
    assert t[0] < t[1] < t[2]


def test_kelly_fractional():
    frac, pct = kelly_position_size(win_probability=0.6, win_loss_ratio=2.0)
    # f = (0.6×3−1)/2 = 0.4 → نصف = 0.2 → 20% اما سقف ۱۰٪
    assert frac == pytest.approx(0.2)
    assert pct == 10.0  # capped


def test_kelly_invalid_inputs():
    assert kelly_position_size(1.5, 2.0) == (None, None)


def test_regime_detection():
    assert detect_market_regime(-1.0, None, None) == "falling"
    assert detect_market_regime(0.5, 2e12, 1e12) == "high_volume"
    assert detect_market_regime(0.1, 1e12, 1e12) == "eroding"


def test_composite_signal_strong_buy_path():
    res = compute_composite_signal(
        __import__("services.stock_signal_engine", fromlist=["LayerInputs"]).LayerInputs(
            tape_score=85, tech_score=80, fund_score=75, peer_score=60, macro_score=60,
        ),
        price_last=10_500,
        price_close=10_500,
        atr_14=100,
        structural_support=9_800,
        swing_low=9_500,
        swing_high=10_600,
        market_regime="high_volume",
        win_probability=0.55,
        win_loss_ratio=3.0,
    )
    assert res.action in ("strong_buy", "accumulate")
    assert res.stop_loss is not None
    assert res.stop_loss < 10_500
    assert res.targets[0] > 10_500
    assert res.risk_reward is not None


def test_rr_filter_downgrades_buy():
    # آستانه R/R = 2.5؛ با تارگت نزدیک باید به hold تنزل کند
    res = compute_composite_signal(
        __import__("services.stock_signal_engine", fromlist=["LayerInputs"]).LayerInputs(
            tape_score=90, tech_score=90, fund_score=90, peer_score=90, macro_score=90,
        ),
        price_last=10_000,
        price_close=10_000,
        atr_14=1000,               # حد ضرر خیلی دور
        structural_support=None,
        swing_low=9_990,
        swing_high=10_010,         # تارگت خیلی نزدیک
        market_regime="eroding",
    )
    # با R/R کم، خرید رد می‌شود
    if res.risk_reward is not None and res.risk_reward < 2.5:
        assert res.action == "hold"
        assert res.rr_filtered is True


def test_no_look_ahead_stop_below_entry():
    res = compute_composite_signal(
        __import__("services.stock_signal_engine", fromlist=["LayerInputs"]).LayerInputs(
            tape_score=80, tech_score=75, fund_score=70, peer_score=60, macro_score=55,
        ),
        price_last=5_000,
        price_close=5_000,
        atr_14=50,
        structural_support=4_900,
        swing_low=4_800,
        swing_high=5_100,
    )
    # حد ضرر باید زیر ورود باشد (فرمول: max(support, entry−2.5×ATR))
    assert res.stop_loss < 5_000
    assert res.stop_loss == pytest.approx(max(4_900, 5_000 - 2.5 * 50), abs=1.0)
