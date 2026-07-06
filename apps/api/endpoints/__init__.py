from .alpha import router as alpha_router
from .alerts import router as alerts_router
from .anomalies import router as anomalies_router
from .analysis import router as analysis_router
from .auth import router as auth_router
from .backtests import router as backtests_router
from .brsapi import router as brsapi_router
from .chat import router as chat_router
from .codal import router as codal_router
from .data_import import router as data_import_router
from .economic_calendar import router as economic_calendar_router
from .fundamental import router as fundamental_router
from .health import router as health_router
from .indicators import router as indicators_router
from .jobs import router as jobs_router
from .macro import router as macro_router
from .market import router as market_router
from .market_dashboard import router as market_dashboard_router
from .market_info import router as market_info_router
from .ml import router as ml_router
from .news import router as news_router
from .orderbooks import router as orderbooks_router
from .portfolios import router as portfolios_router
from .quotes import router as quotes_router
from .recommendations import router as recommendations_router
from .reports import router as reports_router
from .risk import router as risk_router
from .screener import router as screener_router
from .stock_assistant import router as stock_assistant_router
from .watchlist import router as watchlist_router
from .signals import router as signals_router
from .smart_money import router as smart_money_router
from .symbols import router as symbols_router
from .tables import router as tables_router
from .tests_runner import router as tests_router
from .trades import router as trades_router

__all__ = [
    "alpha_router",
    "alerts_router",
    "anomalies_router",
    "analysis_router",
    "auth_router",
    "backtests_router",
    "brsapi_router",
    "chat_router",
    "codal_router",
    "data_import_router",
    "economic_calendar_router",
    "fundamental_router",
    "health_router",
    "indicators_router",
    "jobs_router",
    "macro_router",
    "market_router",
    "market_dashboard_router",
    "market_info_router",
    "ml_router",
    "news_router",
    "orderbooks_router",
    "portfolios_router",
    "quotes_router",
    "recommendations_router",
    "reports_router",
    "risk_router",
    "screener_router",
    "stock_assistant_router",
    "signals_router",
    "tables_router",
    "watchlist_router",
    "smart_money_router",
    "symbols_router",
    "tests_router",
    "trades_router",
]
