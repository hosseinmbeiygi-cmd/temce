"""Gold module services — Iranian gold market business logic."""

from services.gold.arbitrage import scan_gold_arbitrage
from services.gold.calculator import (
    GoldCalculator,
    calculate_coin_bubble,
    calculate_dollar_adjusted_return,
    calculate_nav_premium,
)
from services.gold.futures_risk import FuturesRiskCalculator
from services.gold.kill_switch import evaluate_kill_switch
from services.gold.live_service import GoldLiveService
from services.gold.position_service import GoldFuturesPositionService

__all__ = [
    "GoldCalculator",
    "GoldFuturesPositionService",
    "GoldLiveService",
    "FuturesRiskCalculator",
    "calculate_coin_bubble",
    "calculate_dollar_adjusted_return",
    "calculate_nav_premium",
    "evaluate_kill_switch",
    "scan_gold_arbitrage",
]
