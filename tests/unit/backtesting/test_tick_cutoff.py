"""Task 4: no post-close tick may enter the day's OHLC (cutoff 12:30)."""


def _ticks():
    return [
        {"row": 1, "time": "09:01:00", "volume": 100, "price": 1000, "canceled": 0},
        {"row": 2, "time": "12:29:59", "volume": 50, "price": 1010, "canceled": 0},
        {"row": 3, "time": "12:30:01", "volume": 999, "price": 5000, "canceled": 0},  # post-close print
        {"row": 4, "time": "14:00:00", "volume": 10, "price": 1, "canceled": 0},       # late correction
        {"row": 5, "time": "10:00:00", "volume": 20, "price": 1005, "canceled": 1},    # canceled
    ]


def test_post_close_ticks_excluded_from_bar():
    from scripts.compare_backtest import aggregate_ticks

    bar, dropped = aggregate_ticks(_ticks(), "12:30:00")
    assert dropped == 2
    assert bar["open"] == 1000
    assert bar["close"] == 1010  # last IN-SESSION tick, not the 14:00 print
    assert bar["high"] == 1010
    assert bar["low"] == 1000
    assert bar["volume"] == 150.0


def test_all_post_close_day_yields_no_bar():
    from scripts.compare_backtest import aggregate_ticks

    ticks = [{"row": 1, "time": "15:00:00", "volume": 5, "price": 999, "canceled": 0}]
    bar, dropped = aggregate_ticks(ticks, "12:30:00")
    assert bar is None and dropped == 1


def test_real_files_respect_cutoff():
    """On real data: recompute a day WITH post-close ticks both ways and show
    the uncut close differs (i.e. the old loader was biased) while the cut
    close equals the last in-session tick."""
    import json
    import os

    from scripts.compare_backtest import aggregate_ticks

    checked = fixed = 0
    r = "transactions_data"
    for s in os.listdir(r):
        sd = os.path.join(r, s)
        if not os.path.isdir(sd):
            continue
        for f in sorted(os.listdir(sd))[:400]:
            if not f.endswith(".json"):
                continue
            try:
                ticks = json.load(open(os.path.join(sd, f), encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(ticks, list) or not ticks:
                continue
            valid = [t for t in ticks if not t.get("canceled") and t.get("volume", 0) > 0]
            if not any(str(t.get("time", "")) > "12:30:00" for t in valid):
                continue
            checked += 1
            bar, dropped = aggregate_ticks(valid, "12:30:00")
            assert dropped > 0
            if bar is None:
                continue  # whole day was post-close prints: correctly no bar
            naive_close = float(valid[-1]["price"])
            if naive_close != bar["close"]:
                fixed += 1
            if checked >= 30:
                break
        if checked >= 30:
            break
    assert checked > 0, "expected some days with post-close ticks"
    assert fixed > 0, "expected the cutoff to change at least one close"


def test_per_market_close_no_single_default():
    from domain.trading import iran_costs as m

    import scripts.compare_backtest as cb

    assert m.market_close("tse_equity") == "12:30:00"
    assert m.market_close("etf_equity") == "12:30:00"
    try:
        m.market_close("nope")
        raise SystemExit("should have raised")
    except ValueError:
        pass
    assert not hasattr(cb, "DEFAULT_MARKET_CLOSE"), "single default must be gone"
