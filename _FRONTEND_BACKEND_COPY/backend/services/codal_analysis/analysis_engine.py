from __future__ import annotations

from dataclasses import dataclass, field

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FinancialSnapshot:
    symbol: str
    fiscal_period: str
    revenue: float = 0
    cost_of_goods_sold: float = 0
    gross_profit: float = 0
    operating_expenses: float = 0
    operating_profit: float = 0
    financial_cost: float = 0
    financial_income: float = 0
    net_profit: float = 0
    eps: float = 0
    current_assets: float = 0
    non_current_assets: float = 0
    total_assets: float = 0
    current_liabilities: float = 0
    non_current_liabilities: float = 0
    total_liabilities: float = 0
    equity: float = 0
    total_equity: float = 0
    inventory: float = 0
    cash: float = 0
    accounts_receivable: float = 0
    accounts_payable: float = 0
    operating_cash_flow: float = 0
    investing_cash_flow: float = 0
    financing_cash_flow: float = 0
    capital: float = 0
    retained_earnings: float = 0
    depreciation: float = 0
    net_fixed_assets: float = 0
    raw_data: dict[str, float] = field(default_factory=dict)
    prev: FinancialSnapshot | None = None


def build_snapshot(classified: dict[str, float], symbol: str = "", period: str = "") -> FinancialSnapshot:
    snap = FinancialSnapshot(symbol=symbol, fiscal_period=period, raw_data=classified)
    for key, val in classified.items():
        key_upper = key.upper().strip()
        if hasattr(snap, key_upper):
            setattr(snap, key_upper, val)
        elif hasattr(snap, key):
            setattr(snap, key, val)
    snap.total_equity = snap.total_equity or snap.equity
    snap.total_assets = max(snap.total_assets, snap.current_assets + snap.non_current_assets)
    return snap


@dataclass
class HorizontalAnalysis:
    revenue_growth: float | None = None
    gross_profit_growth: float | None = None
    operating_profit_growth: float | None = None
    net_profit_growth: float | None = None
    total_assets_growth: float | None = None
    total_liabilities_growth: float | None = None
    equity_growth: float | None = None


def compute_growth(current: float, previous: float) -> float | None:
    if previous == 0:
        return None if current == 0 else float("inf")
    return (current - previous) / abs(previous)


def horizontal_analysis(snap: FinancialSnapshot) -> HorizontalAnalysis:
    prev = snap.prev
    if not prev:
        return HorizontalAnalysis()
    return HorizontalAnalysis(
        revenue_growth=compute_growth(snap.revenue, prev.revenue),
        gross_profit_growth=compute_growth(snap.gross_profit, prev.gross_profit),
        operating_profit_growth=compute_growth(snap.operating_profit, prev.operating_profit),
        net_profit_growth=compute_growth(snap.net_profit, prev.net_profit),
        total_assets_growth=compute_growth(snap.total_assets, prev.total_assets),
        total_liabilities_growth=compute_growth(snap.total_liabilities, prev.total_liabilities),
        equity_growth=compute_growth(snap.total_equity, prev.total_equity),
    )


@dataclass
class VerticalAnalysis:
    pl_items: dict[str, float] = field(default_factory=dict)
    bs_items: dict[str, float] = field(default_factory=dict)


def vertical_analysis(snap: FinancialSnapshot) -> VerticalAnalysis:
    va = VerticalAnalysis()
    if snap.revenue:
        va.pl_items["cost_of_goods_sold_pct"] = (
            (snap.cost_of_goods_sold / snap.revenue * 100) if snap.cost_of_goods_sold else 0
        )
        va.pl_items["gross_profit_pct"] = (snap.gross_profit / snap.revenue * 100) if snap.gross_profit else 0
        va.pl_items["operating_expenses_pct"] = (
            (snap.operating_expenses / snap.revenue * 100) if snap.operating_expenses else 0
        )
        va.pl_items["operating_profit_pct"] = (
            (snap.operating_profit / snap.revenue * 100) if snap.operating_profit else 0
        )
        va.pl_items["net_profit_pct"] = (snap.net_profit / snap.revenue * 100) if snap.net_profit else 0
        va.pl_items["financial_cost_pct"] = (snap.financial_cost / snap.revenue * 100) if snap.financial_cost else 0
    if snap.total_assets:
        va.bs_items["current_assets_pct"] = (
            (snap.current_assets / snap.total_assets * 100) if snap.current_assets else 0
        )
        va.bs_items["non_current_assets_pct"] = (
            (snap.non_current_assets / snap.total_assets * 100) if snap.non_current_assets else 0
        )
        va.bs_items["current_liabilities_pct"] = (
            (snap.current_liabilities / snap.total_assets * 100) if snap.current_liabilities else 0
        )
        va.bs_items["non_current_liabilities_pct"] = (
            (snap.non_current_liabilities / snap.total_assets * 100) if snap.non_current_liabilities else 0
        )
        va.bs_items["equity_pct"] = (snap.total_equity / snap.total_assets * 100) if snap.total_equity else 0
        va.bs_items["cash_pct"] = (snap.cash / snap.total_assets * 100) if snap.cash else 0
        va.bs_items["inventory_pct"] = (snap.inventory / snap.total_assets * 100) if snap.inventory else 0
        va.bs_items["accounts_receivable_pct"] = (
            (snap.accounts_receivable / snap.total_assets * 100) if snap.accounts_receivable else 0
        )
    return va


@dataclass
class RatioAnalysis:
    profitability: dict[str, float | None] = field(default_factory=dict)
    liquidity: dict[str, float | None] = field(default_factory=dict)
    leverage: dict[str, float | None] = field(default_factory=dict)
    activity: dict[str, float | None] = field(default_factory=dict)
    cash_flow: dict[str, float | None] = field(default_factory=dict)


def _safe_div(a: float, b: float) -> float | None:
    if b == 0:
        return None
    return a / b


def compute_ratios(snap: FinancialSnapshot) -> RatioAnalysis:
    ratios = RatioAnalysis()

    ratios.profitability["gross_margin"] = _safe_div(snap.gross_profit, snap.revenue)
    ratios.profitability["operating_margin"] = _safe_div(snap.operating_profit, snap.revenue)
    ratios.profitability["net_margin"] = _safe_div(snap.net_profit, snap.revenue)
    ratios.profitability["roa"] = _safe_div(snap.net_profit, snap.total_assets) if snap.total_assets else None
    ratios.profitability["roe"] = _safe_div(snap.net_profit, snap.total_equity) if snap.total_equity else None
    ratios.profitability["return_on_capital"] = (
        _safe_div(snap.operating_profit, snap.total_equity + snap.non_current_liabilities)
        if (snap.total_equity + snap.non_current_liabilities)
        else None
    )

    ratios.liquidity["current_ratio"] = _safe_div(snap.current_assets, snap.current_liabilities)
    quick_assets = snap.current_assets - snap.inventory
    ratios.liquidity["quick_ratio"] = _safe_div(quick_assets, snap.current_liabilities)
    ratios.liquidity["cash_ratio"] = _safe_div(snap.cash, snap.current_liabilities)

    ratios.leverage["debt_to_assets"] = _safe_div(snap.total_liabilities, snap.total_assets)
    ratios.leverage["debt_to_equity"] = _safe_div(snap.total_liabilities, snap.total_equity)
    ratios.leverage["equity_multiplier"] = _safe_div(snap.total_assets, snap.total_equity)
    ratios.leverage["interest_coverage"] = (
        _safe_div(snap.operating_profit, snap.financial_cost) if snap.financial_cost else None
    )

    ratios.activity["inventory_turnover"] = (
        _safe_div(snap.cost_of_goods_sold, snap.inventory or 1) if snap.inventory else None
    )
    ratios.activity["receivables_turnover"] = (
        _safe_div(snap.revenue, snap.accounts_receivable or 1) if snap.accounts_receivable else None
    )
    ratios.activity["asset_turnover"] = _safe_div(snap.revenue, snap.total_assets) if snap.total_assets else None
    ratios.activity["fixed_asset_turnover"] = (
        _safe_div(snap.revenue, snap.net_fixed_assets or 1) if snap.net_fixed_assets else None
    )

    ratios.cash_flow["cfo_to_net_profit"] = (
        _safe_div(snap.operating_cash_flow, snap.net_profit) if snap.net_profit else None
    )
    ratios.cash_flow["cfo_to_revenue"] = _safe_div(snap.operating_cash_flow, snap.revenue) if snap.revenue else None

    return ratios


@dataclass
class DuPontAnalysis:
    net_profit_margin: float | None = None
    asset_turnover: float | None = None
    equity_multiplier: float | None = None
    roe: float | None = None
    roe_dupont: float | None = None


def dupont_analysis(snap: FinancialSnapshot) -> DuPontAnalysis:
    npm = _safe_div(snap.net_profit, snap.revenue)
    at = _safe_div(snap.revenue, snap.total_assets) if snap.total_assets else None
    em = _safe_div(snap.total_assets, snap.total_equity) if snap.total_equity else None
    roe_direct = _safe_div(snap.net_profit, snap.total_equity) if snap.total_equity else None
    roe_dupont_val = None
    if npm is not None and at is not None and em is not None:
        roe_dupont_val = npm * at * em

    return DuPontAnalysis(
        net_profit_margin=npm,
        asset_turnover=at,
        equity_multiplier=em,
        roe=roe_direct,
        roe_dupont=roe_dupont_val,
    )


@dataclass
class EarningsQuality:
    cash_conversion_ratio: float | None = None
    accruals_ratio: float | None = None
    receivables_growth_vs_revenue: float | None = None
    quality_score: float = 0
    warnings: list[str] = field(default_factory=list)


def earnings_quality(snap: FinancialSnapshot) -> EarningsQuality:
    eq = EarningsQuality()
    eq.cash_conversion_ratio = _safe_div(snap.operating_cash_flow, snap.net_profit) if snap.net_profit else None

    if eq.cash_conversion_ratio is not None:
        if eq.cash_conversion_ratio < 0.5:
            eq.warnings.append(f"نسبت تبدیل نقدی پایین ({eq.cash_conversion_ratio:.2f}) - کیفیت سود ضعیف")
        elif eq.cash_conversion_ratio < 0.8:
            eq.warnings.append(f"نسبت تبدیل نقدی متوسط ({eq.cash_conversion_ratio:.2f}) - نیاز به بررسی")

    if snap.prev:
        prev_noa = snap.prev.total_assets - snap.prev.cash - snap.prev.total_liabilities
        curr_noa = snap.total_assets - snap.cash - snap.total_liabilities
        avg_noa = (prev_noa + curr_noa) / 2
        if avg_noa != 0:
            eq.accruals_ratio = (curr_noa - prev_noa) / abs(avg_noa)

        rev_growth = compute_growth(snap.revenue, snap.prev.revenue) or 0
        ar_growth = compute_growth(snap.accounts_receivable, snap.prev.accounts_receivable) or 0
        if rev_growth != 0:
            eq.receivables_growth_vs_revenue = ar_growth / abs(rev_growth)
            if eq.receivables_growth_vs_revenue > 1.2:
                eq.warnings.append(
                    f"رشد مطالبات ({ar_growth:.1%}) بسیار بیشتر از رشد فروش ({rev_growth:.1%}) - احتمال Channel Stuffing"
                )

    score = 0.5
    if eq.cash_conversion_ratio is not None:
        score += min(eq.cash_conversion_ratio, 2.0) * 0.2
    if eq.accruals_ratio is not None:
        score += max(0, 1 - abs(eq.accruals_ratio)) * 0.15
    if len(eq.warnings) == 0:
        score += 0.15
    eq.quality_score = min(max(score, 0), 1)

    return eq


@dataclass
class ComprehensiveAnalysis:
    symbol: str
    fiscal_period: str
    snapshot: FinancialSnapshot
    horizontal: HorizontalAnalysis
    vertical: VerticalAnalysis
    ratios: RatioAnalysis
    dupont: DuPontAnalysis
    earnings_quality: EarningsQuality
    analysis_status: str = "full"
    missing_components: list[str] = field(default_factory=list)


def analyze(snap: FinancialSnapshot) -> ComprehensiveAnalysis:
    return ComprehensiveAnalysis(
        symbol=snap.symbol,
        fiscal_period=snap.fiscal_period,
        snapshot=snap,
        horizontal=horizontal_analysis(snap),
        vertical=vertical_analysis(snap),
        ratios=compute_ratios(snap),
        dupont=dupont_analysis(snap),
        earnings_quality=earnings_quality(snap),
    )
