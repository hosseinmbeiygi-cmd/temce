"""Cross-Gold Arbitrage Scanner — ETF vs فیزیکی (آب‌شده / سکه).

فرمول:
  spread_pct = ((physical - etf) / etf) * 100
  net_spread = spread - tx_cost

اگر net > +1.5% → خرید ETF + فروش فیزیکی
اگر net < -1.5% → خرید فیزیکی + فروش ETF
غیر اینصورت → بی‌تفاوت (NO_ARBITRAGE)
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_TX_COST_PCT = 0.5  # 0.5% مجموع کارمزد صرافی + اسپرد بازار
MIN_NET_SPREAD = 2.0  # % حداقل اسپرد خالص برای توجیه آربیتراژ


@dataclass(frozen=True)
class ArbitrageResult:
    pair: str
    gross_spread_pct: float
    net_spread_pct: float
    action: str  # BUY_ETF_SELL_PHYSICAL / BUY_PHYSICAL_SELL_ETF / NO_ARBITRAGE
    strategy: str
    estimated_profit_pct: float


def scan_gold_arbitrage(
    etf_price_per_gram: float,
    physical_gold_price_per_gram: float,
    pair_label: str = "ETF_زرافشان ↔ طلای_فیزیکی",
    transaction_cost_pct: float = DEFAULT_TX_COST_PCT,
) -> ArbitrageResult:
    """شناسایی فرصت آربیتراژ بین صندوق طلا در بورس و طلای فیزیکی."""
    if etf_price_per_gram <= 0 or physical_gold_price_per_gram <= 0:
        raise ValueError("prices must be > 0")

    gross = ((physical_gold_price_per_gram - etf_price_per_gram) / etf_price_per_gram) * 100.0
    net = gross - (transaction_cost_pct * 100)

    if net > MIN_NET_SPREAD:
        action = "BUY_ETF_SELL_PHYSICAL"
        strategy = "خرید صندوق طلا در بورس و فروش طلای آب‌شده در بازار فیزیکی"
    elif net < -MIN_NET_SPREAD:
        action = "BUY_PHYSICAL_SELL_ETF"
        strategy = "خرید طلای فیزیکی و فروش/ردیم واحدهای صندوق طلا"
    else:
        action = "NO_ARBITRAGE"
        strategy = "اختلاف قیمت کمتر از هزینه تراکنش است؛ آربیتراژ توجیه‌پذیر نیست."

    return ArbitrageResult(
        pair=pair_label,
        gross_spread_pct=round(gross, 2),
        net_spread_pct=round(net, 2),
        action=action,
        strategy=strategy,
        estimated_profit_pct=round(net, 2),
    )
