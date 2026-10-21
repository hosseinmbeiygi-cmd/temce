"""Gold module services — Iranian gold market business logic."""

from providers.macro_sources.tokenized_gold import (
    TOKENIZED_GOLD_CATEGORY,
    TOKENIZED_GOLD_TICKERS,
    compute_tokenized_gold_premium,
)
from services.gold.arbitrage import scan_gold_arbitrage
from services.gold.black76_engine import (
    black76_price,
    calculate_greeks,
    implied_volatility,
)
from services.gold.calculator import (
    GoldCalculator,
    calculate_coin_bubble,
    calculate_dollar_adjusted_return,
    calculate_nav_premium,
)
from services.gold.economic_calendar import (
    DEFAULT_HIGH_VOL_WINDOW_DAYS,
    add_iran_manual_event,
    is_high_vol_window,
    is_high_vol_window_from_events,
    list_economic_calendar,
    list_iran_manual_events,
)
from services.gold.feed_health import (
    DEFAULT_FEED_HEALTH_LIMIT,
    PRIMARY_GOLD_FEED_PROVIDER,
    check_gold_feed_health,
    load_recent_feed_health_attempts,
    summarize_primary_status,
)
from services.gold.futures_risk import FuturesRiskCalculator
from services.gold.futures_term import (
    DEFAULT_TRANSACTION_FRICTIONS,
    analyze_futures_curve,
)
from services.gold.kill_switch import evaluate_kill_switch
from services.gold.live_service import GoldLiveService
from services.gold.macro_indicators import (
    GoldFeedUnavailableError,
    calculate_aed_implied_usd,
    evaluate_gold_macro_posture,
    fetch_resilient_gold_spot,
)
from services.gold.macro_live import (
    FRED_DXY_BROAD_INDICATOR,
    FRED_TIPS_10Y_INDICATOR,
    MacroLiveResult,
    get_gold_macro_live,
)
from services.gold.macro_sync import (
    HIGH_VOLATILITY_CATEGORIES,
    MacroSyncService,
    SyncResult,
)
from services.gold.margin_model import simulate_margin_path
from services.gold.options_chain import (
    OptionsChainProvider,
    analyze_options_chain,
    build_options_chain_report,
)
from services.gold.options_chain_service import get_options_chain_report
from services.gold.options_matrix import (
    calculate_max_pain,
    calculate_pcr,
    enrich_options_chain,
)
from services.gold.physical_arbitrage import (
    adjust_melted_by_assay,
    calculate_coin_bubbles,
    calculate_gram18_from_mesghal,
    calculate_ime_vs_melted_arbitrage,
)
from services.gold.physical_market import (
    aed_hawala_spread,
    calculate_assay_variance_scenarios,
    calculate_coin_bubbles_with_history,
    calculate_gram18_from_mesghal_decimal,
    calculate_ime_certificate_spread,
    evaluate_aed_hawala_alert,
    rolling_zscore_percentile,
    validate_ime_position_limit,
)
from services.gold.physical_market_service import (
    AED_HISTORY_LIMIT,
    CACHE_TTL_SECONDS,
    COIN_HISTORY_LIMIT,
    get_aed_history_report,
    get_coin_bubble_report,
    get_ime_arbitrage_report,
)
from services.gold.position_service import GoldFuturesPositionService
from services.gold.risk_scenarios import (
    GOLD_RISK_SCENARIOS,
    GoldRiskScenario,
    list_risk_scenarios,
    stress_test_gold_portfolio,
)
from services.gold.strategies import (
    analyze_strategy,
    build_covered_call,
    build_iron_condor,
    build_straddle,
    build_strangle,
    build_vertical_spread,
)

__all__ = [
    "DEFAULT_TRANSACTION_FRICTIONS",
    "DEFAULT_FEED_HEALTH_LIMIT",
    "DEFAULT_HIGH_VOL_WINDOW_DAYS",
    "AED_HISTORY_LIMIT",
    "CACHE_TTL_SECONDS",
    "COIN_HISTORY_LIMIT",
    "FRED_DXY_BROAD_INDICATOR",
    "FRED_TIPS_10Y_INDICATOR",
    "HIGH_VOLATILITY_CATEGORIES",
    "TOKENIZED_GOLD_CATEGORY",
    "TOKENIZED_GOLD_TICKERS",
    "compute_tokenized_gold_premium",
    "GoldCalculator",
    "GoldFuturesPositionService",
    "GoldLiveService",
    "GoldRiskScenario",
    "GOLD_RISK_SCENARIOS",
    "MacroLiveResult",
    "MacroSyncService",
    "SyncResult",
    "OptionsChainProvider",
    "FuturesRiskCalculator",
    "GoldFeedUnavailableError",
    "PRIMARY_GOLD_FEED_PROVIDER",
    "analyze_futures_curve",
    "analyze_options_chain",
    "analyze_strategy",
    "adjust_melted_by_assay",
    "aed_hawala_spread",
    "black76_price",
    "build_covered_call",
    "build_iron_condor",
    "build_options_chain_report",
    "build_straddle",
    "build_strangle",
    "build_vertical_spread",
    "calculate_aed_implied_usd",
    "calculate_coin_bubble",
    "calculate_coin_bubbles",
    "calculate_coin_bubbles_with_history",
    "calculate_assay_variance_scenarios",
    "calculate_dollar_adjusted_return",
    "calculate_greeks",
    "calculate_gram18_from_mesghal",
    "calculate_gram18_from_mesghal_decimal",
    "calculate_ime_certificate_spread",
    "calculate_ime_vs_melted_arbitrage",
    "calculate_max_pain",
    "calculate_nav_premium",
    "calculate_pcr",
    "check_gold_feed_health",
    "enrich_options_chain",
    "evaluate_gold_macro_posture",
    "evaluate_aed_hawala_alert",
    "evaluate_kill_switch",
    "fetch_resilient_gold_spot",
    "get_aed_history_report",
    "get_coin_bubble_report",
    "get_gold_macro_live",
    "get_ime_arbitrage_report",
    "get_options_chain_report",
    "implied_volatility",
    "is_high_vol_window",
    "is_high_vol_window_from_events",
    "add_iran_manual_event",
    "list_economic_calendar",
    "list_iran_manual_events",
    "load_recent_feed_health_attempts",
    "list_risk_scenarios",
    "rolling_zscore_percentile",
    "simulate_margin_path",
    "stress_test_gold_portfolio",
    "summarize_primary_status",
    "scan_gold_arbitrage",
    "validate_ime_position_limit",
]
