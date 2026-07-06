from __future__ import annotations
from apps.api.endpoints import market_dashboard_router, quotes_router
from fastapi import APIRouter, Depends

from apps.api.dependencies import get_optional_user
from apps.api.endpoints import (
    alpha_router,
    alerts_router,
    anomalies_router,
    analysis_router,
    auth_router,
    backtests_router,
    brsapi_router,
    chat_router,
    data_import_router,
    economic_calendar_router,
    fundamental_router,
    jobs_router,
    codal_router,
    health_router,
    indicators_router,
    macro_router,
    market_router,
    ml_router,
    news_router,
    orderbooks_router,
    quotes_router,
    recommendations_router,
    reports_router,
    risk_router,
    screener_router,
    signals_router,
    smart_money_router,
    stock_assistant_router,
    symbols_router,
    tables_router,
    tests_router,
    trades_router,
    portfolios_router,
    market_info_router,
    watchlist_router,
)
from apps.admin.dashboard import router as admin_dashboard_router
from schemas.common.responses import ApiResponse

# Auth dependency that makes user info available if token is provided (optional)
_optional_auth = [Depends(get_optional_user)]

_ENDPOINTS = [
    {"path": "/health", "tag": "Health", "description": "Health check"},
    {
        "path": "/chat",
        "tag": "Chat",
        "description": "AI chatbot for market questions",
    },
    {
        "path": "/auth",
        "tag": "Authentication",
        "description": "Login, register, token refresh",
    },
    {"path": "/alerts", "tag": "Alerts", "description": "Price & indicator alerts"},
    {"path": "/market", "tag": "Market", "description": "Market overview & indices"},
    {
        "path": "/instruments",
        "tag": "Symbols",
        "description": "Stock & instrument data",
    },
    {
        "path": "/quotes",
        "tag": "Quotes",
        "description": "Real-time & historical quotes",
    },
    {"path": "/orderbooks", "tag": "Orderbooks", "description": "Order book snapshots"},
    {"path": "/trades", "tag": "Trades", "description": "Trade history"},
    {"path": "/signals", "tag": "Signals", "description": "Trading signals"},
    {
        "path": "/recommendations",
        "tag": "Recommendations",
        "description": "Buy/sell recommendations",
    },
    {"path": "/indicators", "tag": "Indicators", "description": "Technical indicators"},
    {"path": "/codal", "tag": "Codal", "description": "Codal disclosures"},
    {"path": "/news", "tag": "News", "description": "Market news"},
    {"path": "/macro", "tag": "Macro", "description": "Macroeconomic data"},
    {
        "path": "/fundamental",
        "tag": "Fundamental",
        "description": "Fundamental analysis",
    },
    {"path": "/backtests", "tag": "Backtests", "description": "Strategy backtesting"},
    {"path": "/ml", "tag": "ML", "description": "Machine learning models"},
    {"path": "/reports", "tag": "Reports", "description": "Generated reports"},
    {
        "path": "/smart-money",
        "tag": "Smart Money",
        "description": "Smart money flow analysis",
    },
    {
        "path": "/analysis",
        "tag": "Analysis",
        "description": "Technical & sentiment analysis",
    },
    {
        "path": "/anomalies",
        "tag": "Anomalies",
        "description": "Price & volume anomaly detection",
    },
    {"path": "/alpha", "tag": "Alpha", "description": "Alpha generation"},
    {"path": "/risk", "tag": "Risk", "description": "Risk management"},
    {
        "path": "/screener",
        "tag": "Screener",
        "description": "Smart money stock screener",
    },
    {
        "path": "/stock-assistant",
        "tag": "Stock Assistant",
        "description": "Conversational Q&A stock assistant",
    },
    {"path": "/tests", "tag": "Tests", "description": "Test runner"},
    {"path": "/portfolios", "tag": "Portfolios", "description": "Portfolio management"},
    {"path": "/watchlist", "tag": "Watchlist", "description": "User watchlists"},
    {"path": "/dashboard", "tag": "Admin Dashboard", "description": "Admin dashboard"},
    {
        "path": "/data-import",
        "tag": "Data Import",
        "description": "CSV & bulk data import",
    },
    {
        "path": "/economic-calendar",
        "tag": "Economic Calendar",
        "description": "Economic events calendar",
    },
    {
        "path": "/brsapi",
        "tag": "BrsApi",
        "description": "Commodities, crypto, global data",
    },
]


class Router:
    def setup(self) -> APIRouter:
        router = APIRouter()

        @router.get("", summary="API root", description="List all available endpoints")
        async def api_root() -> ApiResponse[dict]:
            return ApiResponse[dict](
                success=True,
                data={
                    "version": "v1",
                    "endpoints": _ENDPOINTS,
                },
            )

        # Health and auth routers are intentionally unprotected
        router.include_router(health_router, prefix="/health", tags=["Health"])
        router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
        # All data routers have optional auth — token is checked if provided, but not required
        # Note: alerts_router has its own endpoint-level Depends(get_current_user), so no router-level dep needed
        router.include_router(alerts_router, prefix="/alerts", tags=["Alerts"])
        router.include_router(
            market_router,
            prefix="/market",
            tags=["Market"],
            dependencies=_optional_auth,
        )
        router.include_router(
            market_dashboard_router,
            prefix="/market-dashboard",
            tags=["Market Dashboard"],
            dependencies=_optional_auth,
        )
        router.include_router(
            symbols_router,
            prefix="/instruments",
            tags=["Symbols"],
            dependencies=_optional_auth,
        )
        router.include_router(
            quotes_router,
            prefix="/quotes",
            tags=["Quotes"],
            dependencies=_optional_auth,
        )
        router.include_router(
            orderbooks_router,
            prefix="/orderbooks",
            tags=["Orderbooks"],
            dependencies=_optional_auth,
        )
        router.include_router(
            trades_router,
            prefix="/trades",
            tags=["Trades"],
            dependencies=_optional_auth,
        )
        router.include_router(
            signals_router,
            prefix="/signals",
            tags=["Signals"],
            dependencies=_optional_auth,
        )
        router.include_router(
            recommendations_router,
            prefix="/recommendations",
            tags=["Recommendations"],
            dependencies=_optional_auth,
        )
        router.include_router(
            indicators_router,
            prefix="/indicators",
            tags=["Indicators"],
            dependencies=_optional_auth,
        )
        router.include_router(
            chat_router, prefix="/chat", tags=["Chat"], dependencies=_optional_auth
        )
        router.include_router(
            codal_router, prefix="/codal", tags=["Codal"], dependencies=_optional_auth
        )
        router.include_router(
            data_import_router,
            prefix="/data-import",
            tags=["Data Import"],
            dependencies=_optional_auth,
        )
        router.include_router(
            economic_calendar_router,
            prefix="/economic-calendar",
            tags=["Economic Calendar"],
            dependencies=_optional_auth,
        )
        router.include_router(
            news_router, prefix="/news", tags=["News"], dependencies=_optional_auth
        )
        router.include_router(
            jobs_router, prefix="/jobs", tags=["Jobs"], dependencies=_optional_auth
        )
        router.include_router(
            macro_router, prefix="/macro", tags=["Macro"], dependencies=_optional_auth
        )
        router.include_router(
            fundamental_router,
            prefix="/fundamental",
            tags=["Fundamental Analysis"],
            dependencies=_optional_auth,
        )
        router.include_router(
            backtests_router,
            prefix="/backtests",
            tags=["Backtests"],
            dependencies=_optional_auth,
        )
        router.include_router(
            ml_router, prefix="/ml", tags=["ML"], dependencies=_optional_auth
        )
        router.include_router(
            reports_router,
            prefix="/reports",
            tags=["Reports"],
            dependencies=_optional_auth,
        )
        router.include_router(
            smart_money_router,
            prefix="/smart-money",
            tags=["Smart Money"],
            dependencies=_optional_auth,
        )
        router.include_router(
            analysis_router,
            prefix="/analysis",
            tags=["Analysis"],
            dependencies=_optional_auth,
        )
        router.include_router(
            anomalies_router,
            prefix="/anomalies",
            tags=["Anomalies"],
            dependencies=_optional_auth,
        )
        router.include_router(
            alpha_router, prefix="/alpha", tags=["Alpha"], dependencies=_optional_auth
        )
        router.include_router(
            risk_router, prefix="/risk", tags=["Risk"], dependencies=_optional_auth
        )
        router.include_router(
            screener_router,
            prefix="/screener",
            tags=["Screener"],
            dependencies=_optional_auth,
        )
        router.include_router(
            stock_assistant_router,
            prefix="/stock-assistant",
            tags=["Stock Assistant"],
            dependencies=_optional_auth,
        )
        router.include_router(
            tests_router, prefix="/tests", tags=["Tests"], dependencies=_optional_auth
        )
        router.include_router(
            portfolios_router,
            prefix="/portfolios",
            tags=["Portfolios"],
            dependencies=_optional_auth,
        )
        router.include_router(
            watchlist_router,
            prefix="/watchlist",
            tags=["Watchlist"],
            dependencies=_optional_auth,
        )
        router.include_router(
            admin_dashboard_router,
            prefix="/dashboard",
            tags=["Admin Dashboard"],
            dependencies=_optional_auth,
        )
        router.include_router(
            market_info_router, tags=["Market Info"], dependencies=_optional_auth
        )
        # BrsApi endpoints (commodities, crypto, global data)
        router.include_router(
            brsapi_router,
            prefix="/brsapi",
            tags=["BrsApi"],
            dependencies=_optional_auth,
        )
        # Table browser
        router.include_router(
            tables_router,
            prefix="/tables",
            tags=["Tables"],
            dependencies=_optional_auth,
        )
        return router
