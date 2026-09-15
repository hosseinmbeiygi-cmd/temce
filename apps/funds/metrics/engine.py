"""MetricsEngine — اورکستریشن لایه‌های ۱ تا ۵ + Cold Start handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..constants import (
    COLD_START_BLOCK_THRESHOLD,
    COLD_START_LABELS,
    MIN_HISTORY_DAYS,
)
from .layer2 import compute_layer2
from .layer3 import compute_layer3
from .layer4 import compute_layer4
from .layer5 import compute_layer5
from .layers import compute_layer1


@dataclass
class MetricsInput:
    symbol: str
    type_code: str
    nav_history: list[float] = field(default_factory=list)
    nav_redeem: float | None = None
    market_price: float | None = None
    aum_btoman: float | None = None
    daily_volume: float | None = None
    bid: float | None = None
    ask: float | None = None
    market_returns: list[float] | None = None
    fx_nima_returns: list[float] | None = None
    fx_azad_returns: list[float] | None = None
    cpi_returns: list[float] | None = None
    interbank_rate_changes: list[float] | None = None
    duration_years: float | None = None
    gold_world_returns: list[float] | None = None
    silver_world_returns: list[float] | None = None
    saffron_returns: list[float] | None = None
    peer_returns: list[float] | None = None
    peer_bubbles: list[float] | None = None
    self_bubble: float | None = None
    volume_to_aum: float | None = None
    order_book_depth: float | None = None
    portfolio_weights: list[float] | None = None
    benchmark_weights: list[float] | None = None
    fund_returns: list[float] | None = None
    benchmark_returns: list[float] | None = None
    ter: float | None = None
    performance_fee_type: str | None = None
    turnover: float | None = None
    holdings_history: list[dict[str, float]] | None = None
    declared_style: dict[str, float] | None = None
    cash_weight: float | None = None
    portfolio_returns: list[float] | None = None
    benchmark_returns_td: list[float] | None = None
    twr: float | None = None
    dwr: float | None = None
    has_defunct_siblings: bool | None = None
    redemption_rate: float | None = None
    market_impact_coef: float | None = None
    hidden_repo_pct: float | None = None
    volatility_decay: float | None = None
    suspension_risk: float | None = None
    leverage_ratio: float | None = None
    flow_performance: float | None = None
    fund_excess: list[float] | None = None
    market_excess: list[float] | None = None
    pre_change_returns: list[float] | None = None
    post_change_returns: list[float] | None = None
    family_fund_returns: list[list[float]] | None = None
    esfand_monthly_returns: list[float] | None = None
    khordad_monthly_returns: list[float] | None = None
    ramadan_monthly_returns: list[float] | None = None
    geopolitical_event_returns: list[float] | None = None


def compute_all_metrics(inp: MetricsInput, weighted_keys: set[str] | None = None) -> dict[str, Any]:
    """محاسبه همه ۵ لایه + Cold Start labeling.

    weighted_keys: مجموعه شاخص‌های وزن‌دار برای نوع صندوق (از Scoring Engine).
    Cold Start درصد روی شاخص‌های وزن‌دار حساب می‌شود (طبق spec:
    «بیش از ۴۰٪ شاخص‌های وزن‌دارش در Cold Start باشند»).

    خروجی:
    {
      "values": {metric_key: value, ...},
      "cold_start_pct": float,
      "cold_start_labels": {metric_key: label, ...},
      "block_scoring": bool,
      "computed_at": datetime,
    }
    """
    l1 = compute_layer1(
        nav_history=inp.nav_history,
        nav_redeem=inp.nav_redeem,
        market_price=inp.market_price,
        aum_btoman=inp.aum_btoman,
        daily_volume=inp.daily_volume,
        bid=inp.bid,
        ask=inp.ask,
    )

    nav_returns = []
    if inp.nav_history and len(inp.nav_history) >= 2:
        nav_returns = [
            inp.nav_history[i] / inp.nav_history[i - 1] - 1
            for i in range(1, len(inp.nav_history))
            if inp.nav_history[i - 1] > 0
        ]

    # هم‌طول‌سازی سری‌های ورودی (برای beta/correlation)
    n = len(nav_returns)

    def _tail(x: list[float] | None) -> list[float] | None:
        if not x:
            return x
        return x[-n:] if len(x) > n else x

    l2 = compute_layer2(
        nav_series=inp.nav_history,
        market_returns=_tail(inp.market_returns),
    )

    l3 = compute_layer3(
        portfolio_weights=inp.portfolio_weights,
        benchmark_weights=inp.benchmark_weights,
        fund_returns=inp.fund_returns,
        benchmark_returns=inp.benchmark_returns,
        ter=inp.ter,
        performance_fee_type=inp.performance_fee_type,
        turnover=inp.turnover,
        holdings_history=inp.holdings_history,
        declared_style=inp.declared_style,
        cash_weight=inp.cash_weight,
        portfolio_returns=inp.portfolio_returns,
        benchmark_returns_td=inp.benchmark_returns_td,
    )

    l4 = compute_layer4(
        twr=inp.twr,
        dwr=inp.dwr,
        has_defunct_siblings=inp.has_defunct_siblings,
        portfolio_weights=inp.portfolio_weights,
        daily_volume_per_stock=inp.portfolio_weights,
        redemption_rate=inp.redemption_rate,
        market_impact_coef=inp.market_impact_coef,
        hidden_repo_pct=inp.hidden_repo_pct,
        benchmark_returns=inp.benchmark_returns,
        fund_returns=inp.fund_returns,
        fund_excess=inp.fund_excess,
        market_excess=inp.market_excess,
        manager_change_at=None,
        pre_change_returns=inp.pre_change_returns,
        post_change_returns=inp.post_change_returns,
        family_fund_returns=inp.family_fund_returns,
        survivorship_adjusted=inp.has_defunct_siblings,
    )

    l5 = compute_layer5(
        nav_returns=nav_returns,
        fx_nima_returns=_tail(inp.fx_nima_returns),
        fx_azad_returns=_tail(inp.fx_azad_returns),
        cpi_returns=_tail(inp.cpi_returns),
        interbank_rate_changes=_tail(inp.interbank_rate_changes),
        duration_years=inp.duration_years,
        gold_world_returns=_tail(inp.gold_world_returns),
        silver_world_returns=_tail(inp.silver_world_returns),
        saffron_returns=_tail(inp.saffron_returns),
        peer_returns=_tail(inp.peer_returns),
        peer_bubbles=inp.peer_bubbles,
        self_bubble=inp.self_bubble,
        volume_to_aum=inp.volume_to_aum,
        order_book_depth=inp.order_book_depth,
        esfand_monthly_returns=inp.esfand_monthly_returns,
        khordad_monthly_returns=inp.khordad_monthly_returns,
        ramadan_monthly_returns=inp.ramadan_monthly_returns,
        geopolitical_event_returns=inp.geopolitical_event_returns,
    )

    values = {**l1, **l2, **l3, **l4, **l5}

    # شاخص‌های ویژه اهرمی (LV) — از ورودی
    values["volatility_decay"] = inp.volatility_decay
    values["suspension_risk"] = inp.suspension_risk
    values["leverage_ratio"] = inp.leverage_ratio
    values["flow_performance"] = inp.flow_performance if hasattr(inp, "flow_performance") else None

    cold_start_labels: dict[str, str] = {}
    history_days = len(inp.nav_history)
    for metric, min_days in MIN_HISTORY_DAYS.items():
        if values.get(metric) is None and history_days < min_days:
            cold_start_labels[metric] = (
                COLD_START_LABELS["insufficient_history"] if min_days >= 60 else COLD_START_LABELS["short_window"]
            )

    # Cold Start: درصد روی شاخص‌های وزن‌دار (طبق spec)
    if weighted_keys:
        cs_count = sum(1 for k in weighted_keys if values.get(k) is None)
        cs_pct = cs_count / max(1, len(weighted_keys))
    else:
        cs_count = len(cold_start_labels)
        cs_pct = cs_count / max(1, len(values))
    block = cs_pct > COLD_START_BLOCK_THRESHOLD

    return {
        "values": values,
        "cold_start_pct": cs_pct,
        "cold_start_labels": cold_start_labels,
        "block_scoring": block,
        "computed_at": datetime.utcnow(),
    }


# ── تعریف ۵۶ شاخص به‌صورت یکپارچه برای Config Versioning ──────────
# هر شاخص: key (در DB), label فارسی, layer, weight per type, unit
METRIC_REGISTRY: dict[str, dict[str, Any]] = {
    # لایه ۱ — ۸
    "return_1m": {"label_fa": "بازدهی ۱ ماهه", "layer": 1, "unit": "%"},
    "return_3m": {"label_fa": "بازدهی ۳ ماهه", "layer": 1, "unit": "%"},
    "return_6m": {"label_fa": "بازدهی ۶ ماهه", "layer": 1, "unit": "%"},
    "return_1y": {"label_fa": "بازدهی ۱ ساله", "layer": 1, "unit": "%"},
    "return_3y": {"label_fa": "بازدهی ۳ ساله", "layer": 1, "unit": "%"},
    "return_inception": {"label_fa": "بازدهی از تأسیس", "layer": 1, "unit": "%"},
    "p_nav_ratio": {"label_fa": "نسبت P/NAV", "layer": 1, "unit": "%"},
    "aum_btoman": {"label_fa": "دارایی تحت مدیریت", "layer": 1, "unit": "میلیارد تومان"},
    "daily_volume": {"label_fa": "حجم معاملات روزانه", "layer": 1, "unit": "تومان"},
    "bid_ask_spread": {"label_fa": "اسپرد Bid-Ask", "layer": 1, "unit": "%"},
    # لایه ۲ — ۱۰ (با recovery_days و UCR/DCR)
    "sharpe": {"label_fa": "نسبت شارپ", "layer": 2, "unit": "ratio"},
    "sortino": {"label_fa": "نسبت سورتینو", "layer": 2, "unit": "ratio"},
    "calmar": {"label_fa": "نسبت کالمار", "layer": 2, "unit": "ratio"},
    "max_drawdown": {"label_fa": "حداکثر افت", "layer": 2, "unit": "%"},
    "recovery_days": {"label_fa": "زمان بازیابی", "layer": 2, "unit": "روز"},
    "beta": {"label_fa": "بتا", "layer": 2, "unit": "ratio"},
    "std_dev": {"label_fa": "انحراف معیار", "layer": 2, "unit": "%"},
    "info_ratio": {"label_fa": "نسبت اطلاعات", "layer": 2, "unit": "ratio"},
    "upside_capture": {"label_fa": "جذب صعود", "layer": 2, "unit": "ratio"},
    "downside_capture": {"label_fa": "جذب نزول", "layer": 2, "unit": "ratio"},
    # لایه ۳ — ۱۰
    "active_share": {"label_fa": "سهم فعال", "layer": 3, "unit": "%"},
    "bootstrap_alpha_pvalue": {"label_fa": "p-value بوت‌استرپ", "layer": 3, "unit": "p"},
    "style_drift": {"label_fa": "رانش سبک", "layer": 3, "unit": "score"},
    "ter": {"label_fa": "نسبت هزینه کل", "layer": 3, "unit": "%"},
    "performance_fee_type": {"label_fa": "نوع کارمزد عملکرد", "layer": 3, "unit": "str"},
    "hhi": {"label_fa": "HHI تمرکز", "layer": 3, "unit": "index"},
    "turnover": {"label_fa": "نرخ گردش", "layer": 3, "unit": "%"},
    "cash_drag": {"label_fa": "افت نقدینگی", "layer": 3, "unit": "%"},
    "window_dressing": {"label_fa": "نمره آرایش پنجره", "layer": 3, "unit": "score"},
    "tracking_difference": {"label_fa": "اختلاف ردیابی", "layer": 3, "unit": "%"},
    # لایه ۴ — ۱۲
    "behavior_gap": {"label_fa": "شکاف رفتاری", "layer": 4, "unit": "%"},
    "survivorship_flag": {"label_fa": "پرچم سوگیری بازماندگی", "layer": 4, "unit": "bool"},
    "liquidity_spiral": {"label_fa": "نمره مارپیچ نقدینگی", "layer": 4, "unit": "score"},
    "hidden_leverage": {"label_fa": "اهرم پنهان", "layer": 4, "unit": "%"},
    "benchmark_gaming": {"label_fa": "بازی با بنچمارک", "layer": 4, "unit": "bool"},
    "performance_persistence": {"label_fa": "پیوستگی عملکرد", "layer": 4, "unit": "ratio"},
    "market_timing": {"label_fa": "زمان‌بندی بازار", "layer": 4, "unit": "coef"},
    "flow_performance": {"label_fa": "رابطه جریان-عملکرد", "layer": 4, "unit": "score"},
    "redemption_pressure": {"label_fa": "فشار ابطال", "layer": 4, "unit": "%"},
    "diseconomies_of_scale": {"label_fa": "نابهنجاری مقیاس", "layer": 4, "unit": "score"},
    "manager_tenure_days": {"label_fa": "سابقه مدیر", "layer": 4, "unit": "روز"},
    "post_change_alpha": {"label_fa": "آلفا پس از تغییر مدیر", "layer": 4, "unit": "%"},
    "fund_family_correlation": {"label_fa": "همبستگی خانوادگی", "layer": 4, "unit": "ratio"},
    # لایه ۵ — ۱۸ (طبق spec: betafX نیما + آزاد به‌عنوان ۲ شاخص مستقل)
    "fx_beta_nima": {"label_fa": "بتای ارزی نیمایی", "layer": 5, "unit": "ratio"},
    "fx_beta_azad": {"label_fa": "بتای ارزی آزاد", "layer": 5, "unit": "ratio"},
    "inflation_beta": {"label_fa": "بتای تورمی", "layer": 5, "unit": "ratio"},
    "real_return": {"label_fa": "بازده واقعی", "layer": 5, "unit": "%"},
    "geopolitical_sensitivity": {"label_fa": "حساسیت ژئوپلیتیک", "layer": 5, "unit": "score"},
    "calendar_esfand": {"label_fa": "اثر اسفند", "layer": 5, "unit": "%"},
    "calendar_khordad": {"label_fa": "اثر خرداد", "layer": 5, "unit": "%"},
    "calendar_ramadan": {"label_fa": "اثر رمضان", "layer": 5, "unit": "%"},
    "interbank_rate_beta": {"label_fa": "بتای نرخ بین‌بانکی", "layer": 5, "unit": "ratio"},
    "duration_years": {"label_fa": "Duration", "layer": 5, "unit": "سال"},
    "gold_world_corr": {"label_fa": "همبستگی طلای جهانی", "layer": 5, "unit": "ratio"},
    "silver_world_corr": {"label_fa": "همبستگی نقره جهانی", "layer": 5, "unit": "ratio"},
    "saffron_corr": {"label_fa": "همبستگی زعفران", "layer": 5, "unit": "ratio"},
    "peer_correlation": {"label_fa": "همبستگی هم‌گروه", "layer": 5, "unit": "ratio"},
    "pnav_peer_percentile": {"label_fa": "صدک P/NAV هم‌گروه", "layer": 5, "unit": "percentile"},
    "liquidity_score": {"label_fa": "نمره نقدشوندگی", "layer": 5, "unit": "score"},
    "order_book_depth": {"label_fa": "عمق دفتر سفارش", "layer": 5, "unit": "تومان"},
}


def total_metric_count() -> int:
    return len(METRIC_REGISTRY)
