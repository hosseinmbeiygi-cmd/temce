from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_current_user, get_optional_user
from apps.api.dependencies import require_roles as require_any_role
from schemas.common.responses import ApiResponse

# Auth dependency that makes user info available if token is provided (optional)
_optional_auth = [Depends(get_optional_user)]

# Required auth dependency — token is mandatory for sensitive endpoints
_required_auth = [Depends(get_current_user)]

# Role-based dependencies (require_any_role: user must have ANY of the listed roles)
_require_analyst = [Depends(require_any_role("analyst", "admin"))]
_require_admin = [Depends(require_any_role("admin"))]
_require_user = [Depends(require_any_role("user", "analyst", "admin"))]

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
        "path": "/symbols",
        "tag": "Symbols",
        "description": "Static symbol catalog & search (DB-free)",
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
        "path": "/saved-filters",
        "tag": "Saved Filters",
        "description": "User-saved screener filter presets",
    },
    {
        "path": "/screener110",
        "tag": "Screener110",
        "description": "110-column CANSLIM screener — populate profiles & run model",
    },
    {
        "path": "/stock-assistant",
        "tag": "Stock Assistant",
        "description": "Conversational Q&A stock assistant",
    },
    {
        "path": "/assistant",
        "tag": "Unified Assistant",
        "description": "Unified conversational assistant — execute commands across all features",
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
    {
        "path": "/market-insights",
        "tag": "Market Insights",
        "description": "Fake queues, accumulation, manipulation, fear-greed, market health, block trades",
    },
    {
        "path": "/decision-engine",
        "tag": "Decision Engine",
        "description": "Enterprise architecture data & decisions for the Decision Support System",
    },
    {
        "path": "/market-info",
        "tag": "Market Info",
        "description": "Industries & funds list (market-info namespace)",
    },
    {
        "path": "/screener-v2",
        "tag": "Smart Screener V2",
        "description": "Advanced analytics screener, compare & sector analysis",
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

        # ── Lazy imports: all endpoint routers ─────────────────────────
        # These are imported here (not at module level) so that importing
        # the Router class (~300ms) doesn't trigger loading all 45 endpoint
        # files (~45s cumulative).  Each endpoint loads only when setup()
        # is called, which happens once at app creation time.
        from apps.admin.dashboard import router as admin_dashboard_router
        from apps.api.endpoints.alerts import router as alerts_router
        from apps.api.endpoints.alpha import router as alpha_router
        from apps.api.endpoints.analysis import router as analysis_router
        from apps.api.endpoints.anomalies import router as anomalies_router
        from apps.api.endpoints.assistant import router as assistant_router
        from apps.api.endpoints.auth import router as auth_router
        from apps.api.endpoints.backtests import router as backtests_router
        from apps.api.endpoints.brsapi import router as brsapi_router
        from apps.api.endpoints.chat import router as chat_router
        from apps.api.endpoints.codal import router as codal_router
        from apps.api.endpoints.codal_accounting import router as codal_accounting_router
        from apps.api.endpoints.codal_audit import router as codal_audit_router
        from apps.api.endpoints.codal_professional import router as codal_professional_router
        from apps.api.endpoints.compose import router as compose_router
        from apps.api.endpoints.data_import import router as data_import_router
        from apps.api.endpoints.decision_engine import router as decision_engine_router
        from apps.api.endpoints.economic_calendar import router as economic_calendar_router
        from apps.api.endpoints.fundamental import router as fundamental_router
        from apps.api.endpoints.funds import router as funds_router
        from apps.api.endpoints.health import router as health_router
        from apps.api.endpoints.indicators import router as indicators_router
        from apps.api.endpoints.jobs import router as jobs_router
        from apps.api.endpoints.macro import router as macro_router
        from apps.api.endpoints.market import router as market_router
        from apps.api.endpoints.market_dashboard import router as market_dashboard_router
        from apps.api.endpoints.market_info import router as market_info_router
        from apps.api.endpoints.market_insights import router as market_insights_router
        from apps.api.endpoints.market_watch import router as market_watch_router
        from apps.api.endpoints.ml import router as ml_router
        from apps.api.endpoints.multi_market_signals import router as multi_market_signals_router
        from apps.api.endpoints.news import router as news_router
        from apps.api.endpoints.orderbooks import router as orderbooks_router
        from apps.api.endpoints.paper_trading import router as paper_trading_router
        from apps.api.endpoints.portfolios import router as portfolios_router
        from apps.api.endpoints.queue_analysis import router as queue_analysis_router
        from apps.api.endpoints.quotes import router as quotes_router
        from apps.api.endpoints.recommendations import router as recommendations_router
        from apps.api.endpoints.reports import router as reports_router
        from apps.api.endpoints.risk import router as risk_router
        from apps.api.endpoints.saved_filters import router as saved_filters_router
        from apps.api.endpoints.screener import router as screener_router
        from apps.api.endpoints.screener110 import router as screener110_router
        from apps.api.endpoints.screener_v2 import router as screener_v2_router
        from apps.api.endpoints.signal_insights import router as signal_insights_router
        from apps.api.endpoints.signals import router as signals_router
        from apps.api.endpoints.smart_money import router as smart_money_router
        from apps.api.endpoints.stock_assistant import router as stock_assistant_router
        from apps.api.endpoints.symbol_search import router as symbol_search_router
        from apps.api.endpoints.symbols import router as symbols_router
        from apps.api.endpoints.tabdeal import router as tabdeal_router
        from apps.api.endpoints.tables import router as tables_router
        from apps.api.endpoints.tests_runner import router as tests_router
        from apps.api.endpoints.trades import router as trades_router
        from apps.api.endpoints.watchlist import router as watchlist_router
        from apps.api.endpoints.websocket import router as websocket_router

        # Health and auth routers are intentionally unprotected
        router.include_router(health_router, prefix="/health", tags=["Health"])
        router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
        # All data routers have optional auth — token is checked if provided, but not required
        router.include_router(alerts_router, prefix="/alerts", tags=["Alerts"], dependencies=_optional_auth)
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
            market_watch_router,
            prefix="/market-watch",
            tags=["Market Watch"],
            dependencies=_optional_auth,
        )
        router.include_router(
            symbols_router,
            prefix="/instruments",
            tags=["Symbols"],
            dependencies=_optional_auth,
        )
        # DB-free static symbol catalog & search — works without PostgreSQL.
        router.include_router(
            symbol_search_router,
            prefix="/symbols",
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
        router.include_router(signals_router,
            prefix="/signals",
            tags=["Signals"],
            dependencies=_require_user,
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
            codal_accounting_router,
            prefix="/codal-accounting",
            tags=["Codal Accounting"],
            dependencies=_optional_auth,
        )
        router.include_router(
            codal_audit_router,
            prefix="/codal-audit",
            tags=["Codal Audit"],
            dependencies=_optional_auth,
        )
        router.include_router(
            codal_professional_router,
            prefix="/codal-professional",
            tags=["Codal Professional"],
            dependencies=_optional_auth,
        )
        router.include_router(data_import_router,
            prefix="/data-import",
            tags=["Data Import"],
            dependencies=_require_admin,
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
            jobs_router, prefix="/jobs", tags=["Jobs"], dependencies=_require_admin
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
        router.include_router(backtests_router,
            prefix="/backtests",
            tags=["Backtests"],
            dependencies=_optional_auth,
        )
        router.include_router(ml_router, prefix="/ml", tags=["ML"], dependencies=_optional_auth)
        router.include_router(
            multi_market_signals_router,
            prefix="/multi-market-signals",
            tags=["Multi-Market Signals"],
            dependencies=_optional_auth,
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
            funds_router,
            prefix="/funds",
            tags=["Funds"],
            dependencies=_optional_auth,
        )
        router.include_router(
            saved_filters_router,
            prefix="/saved-filters",
            tags=["Saved Filters"],
            dependencies=_optional_auth,
        )
        router.include_router(
            screener_router,
            prefix="/screener",
            tags=["Screener"],
            dependencies=_optional_auth,
        )
        router.include_router(
            screener110_router,
            prefix="/screener110",
            tags=["Screener110"],
            dependencies=_optional_auth,
        )
        router.include_router(
            screener_v2_router,
            prefix="/screener-v2",
            tags=["Smart Screener V2"],
            dependencies=_optional_auth,
        )
        router.include_router(
            stock_assistant_router,
            prefix="/stock-assistant",
            tags=["Stock Assistant"],
            dependencies=_optional_auth,
        )
        router.include_router(
            assistant_router,
            prefix="/assistant",
            tags=["Unified Assistant"],
            dependencies=_optional_auth,
        )
        router.include_router(
            tests_router, prefix="/tests", tags=["Tests"], dependencies=_optional_auth
        )
        router.include_router(portfolios_router,
            prefix="/portfolios",
            tags=["Portfolios"],
            dependencies=_require_user,
        )
        router.include_router(
            paper_trading_router,
            prefix="/paper-trading",
            tags=["Paper Trading"],
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
            dependencies=_require_admin,
        )
        # Mounted under /market-info so its /funds and /industries routes do not
        # collide with the dedicated funds_router (mounted at /funds).
        router.include_router(
            market_info_router,
            prefix="/market-info",
            tags=["Market Info"],
            dependencies=_optional_auth,
        )
        # BrsApi endpoints (commodities, crypto, global data)
        router.include_router(
            brsapi_router,
            prefix="/brsapi",
            tags=["BrsApi"],
            dependencies=_optional_auth,
        )
        # Tabdeal exchange integration
        router.include_router(
            tabdeal_router,
            prefix="/tabdeal",
            tags=["Tabdeal"],
            dependencies=_optional_auth,
        )
        # Table browser exposes arbitrary database metadata/rows; keep it
        # restricted to administrators (never anonymous or optional-auth).
        router.include_router(
            tables_router,
            prefix="/tables",
            tags=["Tables"],
            dependencies=_require_admin,
        )
        # Strategy Composition
        router.include_router(
            compose_router,
            prefix="/compose",
            tags=["Strategy Composition"],
            dependencies=_optional_auth,
        )
        # Market Insights (fake queues, accumulation, manipulation, fear-greed, etc.)
        router.include_router(
            market_insights_router,
            prefix="/market-insights",
            tags=["Market Insights"],
            dependencies=_optional_auth,
        )
        # Signal Insights (accuracy, backtesting, walk-forward, ensemble)
        router.include_router(signal_insights_router,
            prefix="/signal-insights",
            tags=["Signal Insights"],
            dependencies=_require_analyst,
        )
        # Decision Engine Architecture API
        router.include_router(
            decision_engine_router,
            prefix="/decision-engine",
            tags=["Decision Engine"],
            dependencies=_optional_auth,
        )
        # Queue Analysis (Phase 1 — real queue detection from TSETMC data)
        router.include_router(
            queue_analysis_router,
            prefix="/queue-analysis",
            tags=["Queue Analysis"],
            dependencies=_optional_auth,
        )
        # WebSocket for real-time market data
        router.include_router(
            websocket_router,
            prefix="/ws",
            tags=["WebSocket"],
        )
        return router
