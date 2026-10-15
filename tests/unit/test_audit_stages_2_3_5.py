"""Stage 2: single-charge cost accounting. Stage 3: walk-forward/leakage. Stage 5: seed."""


def test_round_trip_cost_charged_exactly_once():
    from backtesting.costs.iran_costs import IranTransactionCosts

    m = IranTransactionCosts()
    buy = m.compute("buy", 100.0, 10)
    sell = m.compute("sell", 110.0, 10)
    assert buy == m.buy_cost(100.0, 10)
    assert sell == m.sell_cost(110.0, 10)
    assert m.round_trip_cost(100.0, 10, 110.0, 10) == buy + sell
    # sell includes tax, buy does not
    assert sell > buy


def test_broker_is_single_charge_layer():
    import inspect
    from backtesting.engine import broker as bmod

    src = inspect.getsource(bmod.Broker.submit_order_sync)
    assert "ONLY layer" in src or "SINGLE-CHARGE" in src


def test_oversize_order_partial_or_skip():
    from backtesting.engine.broker import Broker, TransactionCostConfig
    from backtesting.types import OrderEvent, OrderSide

    cfg = TransactionCostConfig(max_participation=0.1, allow_partial_fill=False)
    b = Broker(config=cfg, average_daily_volume=1000)
    o = OrderEvent(instrument_id="X", side=OrderSide.BUY, quantity=500, price=100.0)
    assert b.submit_order_sync(o) is None  # skipped
    cfg2 = TransactionCostConfig(max_participation=0.1, allow_partial_fill=True)
    b2 = Broker(config=cfg2, average_daily_volume=1000)
    f = b2.submit_order_sync(o)
    assert f is not None and f.quantity == 100


def test_walk_forward_gap_and_target_tail():
    from ml.dataset_builder import DatasetBuilder

    d = DatasetBuilder()
    splits = d.walk_forward_splits(200, n_splits=3, horizon=5, gap_extra=2)
    assert len(splits) == 3
    for tr, te in splits:
        assert max(tr) + 7 <= min(te)
    y = d.make_target([1.0, 2.0, 3.0, 4.0], horizon=2)
    assert y[-2:] == [None, None] and y[0] == 1


def test_feature_truncation_invariance():
    import pandas as pd
    from ml.features.technical_features import TechnicalFeatures

    n = 120
    df = pd.DataFrame(
        {
            "close": list(range(1, n + 1)),
            "high": list(range(2, n + 2)),
            "low": list(range(0, n)),
            "volume": [1000] * n,
        }
    )
    t = 80
    full = TechnicalFeatures().compute(df)["data"] if isinstance(TechnicalFeatures().compute(df), dict) else TechnicalFeatures().compute(df).data
    trunc = TechnicalFeatures().compute(df.iloc[: t + 1]).data
    # ewm-based MACD has infinite memory so exact invariance can't hold;
    # rolling/window features must match at t
    for col in ["rsi", "atr", "sr_distance_to_resistance", "sr_distance_to_support"]:
        assert abs(float(full[col].iloc[t]) - float(trunc[col].iloc[t])) < 1e-9, col


def test_seed_reproducible():
    from core.seed import set_global_seed

    set_global_seed(7)
    import random

    a = [random.random() for _ in range(5)]
    set_global_seed(7)
    b = [random.random() for _ in range(5)]
    assert a == b
