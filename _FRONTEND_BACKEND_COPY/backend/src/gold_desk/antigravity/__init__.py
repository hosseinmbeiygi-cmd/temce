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
]
