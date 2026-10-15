"""Single Source of Truth — Iranian market transaction costs (نرخ‌های ۱۴۰۵).

All-in buy/sell rates per market from the reported 1405 schedule (see
config/backtest_costs.yaml for the full table). The 0.5% transfer tax is
already INCLUDED in the equity sell rates below — do not add it again.

All cost modules must delegate to these helpers — no local fee formulas.
"""
from __future__ import annotations

# ── All-in rates: (buy_pct, sell_pct) per market ─────────────────────────────
# Source: reported 1405 brokerage/TSE fee tables. Re-verify against the SEO
# fee schedule + your broker's table before live use — rates change by
# resolution and differ slightly per broker.
MARKET_RATES: dict[str, tuple[float, float]] = {
    "tse_equity": (0.003712, 0.0088),      # سهام و حق‌تقدم بورس تهران (RT 1.2512%)
    "ifb_equity": (0.003632, 0.0088),      # سهام و حق‌تقدم فرابورس (RT 1.2432%)
    "taseh": (0.0049, 0.0024),             # اوراق تسهیلات مسکن (RT 0.73%)
    "debt": (0.000725, 0.000725),          # اوراق بدهی و گواهی سپرده (RT 0.145%)
    "etf_equity": (0.002245, 0.0023),      # صندوق سهامی ETF (RT 0.4545%)
    "etf_mixed": (0.001175, 0.0012625),     # صندوق مختلط ETF (RT 0.24375%)
    "etf_fixed": (0.00036875, 0.00036875),  # صندوق درآمد ثابت ETF (RT 0.07375%)
    "etf_commodity": (0.0012, 0.0012),      # صندوق کالایی/طلا (RT ~0.24%)
    "commodity_cert": (0.0024, 0.0024),     # گواهی سپرده کالایی غیرسکه (RT ~0.48%)
    "coin_cert": (0.00125, 0.00125),       # گواهی سپرده سکه طلا (RT ~0.25%)
}

DEFAULT_MARKET = "tse_equity"

# ── TSE-equity component decomposition (buy side only; informative) ──────────
# buy 0.3712% ≈ broker/exchange 0.2862% + CSD clearing 0.085%. The 0.5%
# transfer tax applies on SELL only and is already inside the 0.88% sell rate.
BROKER_PCT = 0.002862
CLEARING_FEE_PCT = 0.00085
SELL_TAX_PCT = 0.005

# ── Stock-option contracts (TSE/IFB derivatives board) ──────────────────────
# Sources: SEO derivatives fee schedule via broker disclosures
# (e.g. optionist.ir, armanbroker.ir): a flat 0.00125 (0.125%) of contract
# value per side (premium × contract size), identical for calls and puts.
# The 0.5% transfer tax does NOT apply to premium open/close trades — only
# to PHYSICAL settlement (share delivery on exercise), modelled explicitly.
OPTION_BUY_PCT = 0.00125
OPTION_SELL_PCT = 0.00125


def buy_rate(market: str = DEFAULT_MARKET) -> float:
    try:
        return MARKET_RATES[market][0]
    except KeyError:
        raise ValueError(f"Unknown market {market!r}; expected one of {sorted(MARKET_RATES)}")


def sell_rate(market: str = DEFAULT_MARKET) -> float:
    try:
        return MARKET_RATES[market][1]
    except KeyError:
        raise ValueError(f"Unknown market {market!r}; expected one of {sorted(MARKET_RATES)}")


def round_trip_rate(market: str = DEFAULT_MARKET) -> float:
    b, s = MARKET_RATES[market]
    return b + s


def buy_cost(price: float, quantity: int, market: str = DEFAULT_MARKET) -> float:
    principal = max(float(price), 0.0) * max(int(quantity), 0)
    return principal * buy_rate(market)


def sell_cost(price: float, quantity: int, market: str = DEFAULT_MARKET) -> float:
    principal = max(float(price), 0.0) * max(int(quantity), 0)
    return principal * sell_rate(market)


def compute(side: str, price: float, quantity: int, market: str = DEFAULT_MARKET) -> float:
    return sell_cost(price, quantity, market) if str(side).lower() == "sell" else buy_cost(price, quantity, market)


def round_trip_cost(buy_price: float, buy_qty: int, sell_price: float, sell_qty: int,
                    market: str = DEFAULT_MARKET) -> float:
    return buy_cost(buy_price, buy_qty, market) + sell_cost(sell_price, sell_qty, market)


def option_buy_cost(premium_value: float) -> float:
    """Buyer-side fee for one option leg: 0.125% of premium × size."""
    return max(float(premium_value), 0.0) * OPTION_BUY_PCT


def option_sell_cost(premium_value: float, physical_settlement: bool = False) -> float:
    """Seller-side fee: 0.125% of premium × size, plus 0.5% transfer tax
    ONLY on physical settlement (share delivery), never on premium closes."""
    cost = max(float(premium_value), 0.0) * OPTION_SELL_PCT
    if physical_settlement:
        cost += max(float(premium_value), 0.0) * SELL_TAX_PCT
    return cost
