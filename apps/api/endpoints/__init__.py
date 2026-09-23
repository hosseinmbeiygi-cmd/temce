"""
API endpoint routers.

Each endpoint module is imported lazily by Router.setup() —
never at module level — to keep import times under 1 second.
"""

# ── Namespace metadata ───────────────────────────────────────
# The __all__ list serves as documentation of available routers.
# Actual imports happen inside apps/api/router.py : setup().
__all__ = [
    "alerts_router",
    "alpha_router",
    "analysis_router",
    "anomalies_router",
    "assistant_router",
    "auth_router",
    "backtests_router",
    "brsapi_router",
    "chat_router",
    "codal_router",
    "compose_router",
    "data_import_router",
    "decision_engine_router",
    "economic_calendar_router",
    "fundamental_router",
    "funds_router",
    "health_router",
    "indicators_router",
    "jobs_router",
    "macro_router",
    "market_dashboard_router",
    "market_info_router",
    "market_insights_router",
    "market_router",
    "market_watch_router",
    "ml_router",
    "multi_market_signals_router",
    "news_router",
    "orderbooks_router",
    "pre_buy_router",
    "portfolios_router",
    "queue_analysis_router",
    "quotes_router",
    "recommendations_router",
    "reports_router",
    "risk_router",
    "saved_filters_router",
    "screener110_router",
    "screener_router",
    "screener_v2_router",
    "signal_insights_router",
    "signals_router",
    "smart_money_router",
    "stock_assistant_router",
    "symbol_search_router",
    "symbols_router",
    "tabdeal_router",
    "tables_router",
    "tests_router",
    "trades_router",
    "watchlist_router",
    "websocket_router",
]
