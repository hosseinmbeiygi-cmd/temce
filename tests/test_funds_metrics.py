"""تست‌های unit برای Metrics Engine.

هر شاخص با داده‌های fixture شناخته‌شده تأیید می‌شود.
"""

from __future__ import annotations

from apps.funds.metrics.engine import METRIC_REGISTRY, compute_all_metrics
from apps.funds.metrics.helpers import (
    beta_to_market,
    calmar_ratio,
    correlation,
    downside_deviation,
    hhi,
    max_drawdown,
    percentile_rank,
    safe_std,
    sharpe_ratio,
)
from apps.funds.scoring import ScoringConfig, compute_score


def test_sharpe_ratio_known_value():
    """Sharpe برای returns شناخته‌شده — مقدار دقیق."""
    returns = [0.01, 0.02, -0.01, 0.03, 0.00, 0.015]
    sd = safe_std(returns)
    assert sd is not None and sd > 0
    expected = sum(returns) / len(returns) / sd
    result = sharpe_ratio(returns, 0.0)
    assert result is not None
    assert abs(result - expected) < 1e-9


def test_max_drawdown():
    nav = [100.0, 120.0, 90.0, 95.0, 80.0, 110.0]
    mdd, recovery = max_drawdown(nav)
    # اوج ۱۲۰ → کف ۸۰ → ۳۳.۳٪ افت (نسبت = 0.3333)
    assert mdd is not None
    assert abs(mdd - (-1 / 3)) < 0.01
    # recovery: بعد از کف ۸۰ در index 4، به اوج ۱۲۰ در index 5 نمی‌رسد → None
    assert recovery is None


def test_beta_to_market():
    fund = [0.01, 0.02, 0.015, 0.005, 0.03, 0.0]
    market = [0.005, 0.01, 0.0075, 0.0025, 0.015, 0.0]
    b = beta_to_market(fund, market)
    assert b is not None
    assert abs(b - 2.0) < 0.2


def test_hhi():
    # تمرکز کامل = ۱
    assert hhi([1.0]) == 1.0
    # توزیع یکنواخت ۵ سهم = ۰.۲
    assert abs(hhi([0.2, 0.2, 0.2, 0.2, 0.2]) - 0.2) < 1e-9
    assert hhi([]) is None


def test_percentile_rank():
    peers = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile_rank(3.0, peers) == 0.5
    assert percentile_rank(1.0, peers) == 0.0
    assert percentile_rank(5.0, peers) == 1.0
    assert percentile_rank(3.0, [1.0]) is None


def test_correlation():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [2.0, 4.0, 6.0, 8.0, 10.0]
    c = correlation(xs, ys)
    assert c is not None and abs(c - 1.0) < 1e-9


def test_downside_deviation():
    returns = [0.02, -0.01, 0.03, -0.02, 0.0]
    dd = downside_deviation(returns, threshold=0.0)
    assert dd is not None and dd > 0


def test_calmar():
    assert calmar_ratio(0.1, -0.5) == 0.2
    assert calmar_ratio(None, -0.5) is None


def test_compute_all_metrics_known():
    """Metrics کامل با nav rising — همه لایه‌ها محاسبه می‌شوند."""
    inp = _mk_input(history_len=500, rising=True)
    result = compute_all_metrics(inp)
    values = result["values"]
    # لایه ۱
    assert values["return_1y"] is not None and values["return_1y"] > 0
    assert values["return_inception"] is not None
    # لایه ۲
    assert values["sharpe"] is not None
    assert values["max_drawdown"] is not None
    # لایه ۳
    assert values["active_share"] is not None
    # لایه ۵
    assert values["fx_beta_nima"] is not None
    # Cold start نباید بلوک شود (۵۰۰ روز سابقه)
    assert result["block_scoring"] is False


def test_compute_all_metrics_cold_start():
    """Cold Start: صندوق جدید با NAV کوتاه → block_scoring=True.

    صندوق تازه فقط NAV کوتاه دارد — بقیه شاخص‌ها Cold Start می‌شوند.
    """
    from apps.funds.metrics.engine import MetricsInput

    inp = MetricsInput(
        symbol="NEW",
        type_code="EQ",
        nav_history=[10000.0 + i * 5.0 for i in range(10)],  # ۱۰ روز
        nav_redeem=10050.0,
        market_price=10060.0,
        aum_btoman=800.0,
    )
    weighted = set(ScoringConfig().weights["EQ"].keys())
    result = compute_all_metrics(inp, weighted_keys=weighted)
    assert result["cold_start_pct"] > 0.4
    assert result["block_scoring"] is True


def test_metric_registry_has_56():
    """۵۶ شاخص در registry — شرط پذیرش: هیچ شاخصی مخفی نیست."""
    assert len(METRIC_REGISTRY) >= 56
    layers = {v["layer"] for v in METRIC_REGISTRY.values()}
    assert layers == {1, 2, 3, 4, 5}


def test_scoring_weights_sum_100():
    """جمع وزن‌های هر ستون = ۱۰۰ (شرط spec — با normalize)."""
    config = ScoringConfig()
    for type_code, weights in config.weights.items():
        total = sum(weights.values())
        assert abs(total - 100.0) < 0.05, f"{type_code}: {total}"


def test_scoring_output_signal():
    inp = _mk_input(history_len=500, rising=True)
    metrics = compute_all_metrics(inp)
    score = compute_score(metrics["values"], type_code="EQ")
    assert score["score_total"] is not None
    assert score["signal"] in ("strong_buy", "buy", "hold", "caution", "avoid")
    assert score["scoring_version"] == "v1.0"
    assert 0 <= score["score_total"] <= 100


def test_scoring_reason_vector():
    inp = _mk_input(history_len=500, rising=True)
    metrics = compute_all_metrics(inp)
    score = compute_score(metrics["values"], type_code="EQ")
    assert len(score["reasons"]) >= 1
    assert all("metric" in r and "description_fa" in r for r in score["reasons"])


def _mk_input(history_len: int = 500, rising: bool = True) -> object:
    from apps.funds.metrics.engine import MetricsInput

    # نوسان منفی دوره‌ای — برای محاسبه sortino و MDD واقعی
    nav = [
        10000.0 + i * 3.0 + ((i % 7) - 3) * 10 if rising else 10000.0 - i * 0.5 + ((i % 7) - 3) * 10
        for i in range(history_len)
    ]
    fx = [0.0008 + 0.0001 * (i % 5) for i in range(history_len)]
    market = [0.001 + 0.0002 * (i % 4) for i in range(history_len)]
    fund_r = [0.01 + 0.002 * (i % 3) for i in range(history_len)]
    bench_r = [0.005 + 0.001 * (i % 3) for i in range(history_len)]
    return MetricsInput(
        symbol="TEST",
        type_code="EQ",
        nav_history=nav,
        nav_redeem=10300.0,
        market_price=10400.0,
        aum_btoman=15000.0,
        market_returns=market,
        fx_nima_returns=fx,
        fx_azad_returns=fx,
        cpi_returns=[0.0001 for _ in range(history_len)],
        peer_bubbles=[1.0, 2.0, 3.0, 4.0],
        self_bubble=1.5,
        portfolio_weights=[0.3, 0.3, 0.2, 0.2],
        benchmark_weights=[0.25, 0.25, 0.25, 0.25],
        fund_returns=fund_r,
        benchmark_returns=bench_r,
        ter=0.015,
        turnover=0.4,
        cash_weight=0.05,
        # داده‌های لایه ۴ و ۵ برای جلوگیری از Cold Start block
        twr=0.5,
        dwr=0.42,
        redemption_rate=0.03,
        flow_performance=0.6,
        volatility_decay=0.02,
        suspension_risk=0.05,
        leverage_ratio=1.0,
        holdings_history=[{"a": 0.5, "b": 0.5}],
        declared_style={"a": 0.5, "b": 0.5},
        pre_change_returns=[0.01, 0.012, 0.011],
        post_change_returns=[0.02, 0.019, 0.021],
        fund_excess=fund_r,
        market_excess=bench_r,
        peer_returns=[0.001 + 0.0001 * (i % 3) for i in range(history_len)],
        geopolitical_event_returns=[0.01, -0.015, 0.008],
        esfand_monthly_returns=[0.02, 0.03],
        khordad_monthly_returns=[0.015, 0.02],
        ramadan_monthly_returns=[-0.005, 0.005],
    )
