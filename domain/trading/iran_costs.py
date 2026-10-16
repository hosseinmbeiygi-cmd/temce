"""Single Source of Truth — Iranian market transaction costs (نرخ‌های ۱۴۰۵).

Per-market (buy_pct, sell_pct, sell_tax_pct). The transfer tax is a SEPARATE
explicit parameter but is already INCLUDED in sell_pct — never add it on top:

    sell_pct == sell_fee_pct + sell_tax_pct
    round_trip == buy_pct + sell_fee_pct + sell_tax_pct

All cost modules must delegate to these helpers — no local fee formulas.
"""
from __future__ import annotations

# ── All-in rates: (buy, sell, sell-side transfer tax) per market ─────────────
# Source: reported 1405 brokerage/TSE fee tables. Re-verify against the SEO
# fee schedule + your broker's table before live use — rates change by
# resolution and differ slightly per broker.
MARKET_RATES: dict[str, tuple[float, float, float]] = {
    "tse_equity": (0.003712, 0.0088, 0.005),      # سهام و حق‌تقدم بورس تهران (RT 1.2512%)
    "ifb_equity": (0.003632, 0.0088, 0.005),      # سهام و حق‌تقدم فرابورس (RT 1.2432%)
    "taseh": (0.0049, 0.0024, 0.0),               # اوراق تسهیلات مسکن (RT 0.73%)
    "debt": (0.000725, 0.000725, 0.0),            # اوراق بدهی و گواهی سپرده (RT 0.145%)
    "etf_equity": (0.002245, 0.0023, 0.0),        # صندوق سهامی ETF (RT 0.4545%)
    "etf_mixed": (0.001175, 0.0012625, 0.0),      # صندوق مختلط ETF (RT 0.24375%)
    "etf_fixed": (0.00036875, 0.00036875, 0.0),   # صندوق درآمد ثابت ETF (RT 0.07375%)
    "etf_commodity": (0.0012, 0.0012, 0.0),       # صندوق کالایی/طلا (RT ~0.24%)
    "commodity_cert": (0.0024, 0.0024, 0.0),      # گواهی سپرده کالایی غیرسکه (RT ~0.48%)
    "coin_cert": (0.00125, 0.00125, 0.0),         # گواهی سپرده سکه طلا (RT ~0.25%)
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


def _row(market: str) -> tuple[float, float, float]:
    try:
        return MARKET_RATES[market]
    except KeyError:
        raise ValueError(f"Unknown market {market!r}; expected one of {sorted(MARKET_RATES)}")


def buy_rate(market: str = DEFAULT_MARKET) -> float:
    return _row(market)[0]


def sell_rate(market: str = DEFAULT_MARKET) -> float:
    return _row(market)[1]


def sell_tax(market: str = DEFAULT_MARKET) -> float:
    """Explicit transfer-tax parameter (already inside sell_rate)."""
    return _row(market)[2]


def sell_fee_rate(market: str = DEFAULT_MARKET) -> float:
    """Sell-side fee EXCLUDING transfer tax (sell_rate - sell_tax)."""
    b, s, t = _row(market)
    return s - t


def round_trip_rate(market: str = DEFAULT_MARKET) -> float:
    b, s, t = _row(market)
    return b + s


def buy_cost(price: float, quantity: int, market: str = DEFAULT_MARKET) -> float:
    principal = max(float(price), 0.0) * max(int(quantity), 0)
    return principal * buy_rate(market)


def sell_cost(price: float, quantity: int, market: str = DEFAULT_MARKET) -> float:
    principal = max(float(price), 0.0) * max(int(quantity), 0)
    return principal * sell_rate(market)


def sell_tax_cost(price: float, quantity: int, market: str = DEFAULT_MARKET) -> float:
    """Transfer-tax portion of a sell fill (subset of sell_cost, not extra)."""
    principal = max(float(price), 0.0) * max(int(quantity), 0)
    return principal * sell_tax(market)


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
