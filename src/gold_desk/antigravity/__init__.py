"""Antigravity Gold Module — دستیار تحلیل و سیگنال‌دهی بازار طلا ایران.

KPI: Dollar-Adjusted Return
رژیم: Manual Decision Support (بدون اجرای خودکار)
"""

from .assets import (
    ETF_ASSETS,
    FUTURES_CONTRACTS,
    GLOBAL_GOLD,
    PHYSICAL_MARKET,
)
from .calculations import (
    ArbitrageResult,
    CoinBubbleResult,
    DollarAdjustedResult,
    FuturesRiskCalculator,
    NavPremiumResult,
    calculate_coin_bubble,
    calculate_dollar_adjusted_return,
    calculate_nav_premium,
    scan_gold_arbitrage,
)
from .engine import (
    calculate_bubble_pct,
    calculate_coin_intrinsic,
    calculate_implied_usd,
    calculate_pure_gold_18k,
    calculate_snapshot_fields,
)

__all__ = [
    "ETF_ASSETS",
    "FUTURES_CONTRACTS",
    "PHYSICAL_MARKET",
    "GLOBAL_GOLD",
    "calculate_nav_premium",
    "calculate_coin_bubble",
    "FuturesRiskCalculator",
    "calculate_dollar_adjusted_return",
    "scan_gold_arbitrage",
    "NavPremiumResult",
    "CoinBubbleResult",
    "DollarAdjustedResult",
    "ArbitrageResult",
    "calculate_pure_gold_18k",
    "calculate_coin_intrinsic",
    "calculate_bubble_pct",
    "calculate_implied_usd",
    "calculate_snapshot_fields",
]
