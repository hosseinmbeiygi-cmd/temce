from __future__ import annotations
from apps.api.endpoints import quotes_router
from fastapi import APIRouter, Depends

from apps.api.dependencies import get_optional_user
from apps.api.endpoints import (
    alerts_router,
    analysis_router,
    auth_router,
    backtests_router,
    fundamental_router,
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
    signals_router,
    smart_money_router,
    symbols_router,
    tests_router,
    trades_router,
    portfolios_router,
    market_info_router,
)
from apps.admin.dashboard import router as admin_dashboard_router

# Auth dependency that makes user info available if token is provided (optional)
_optional_auth = [Depends(get_optional_user)]


class Router:
    def setup(self) -> APIRouter:
        router = APIRouter()
        # Health and auth routers are intentionally unprotected
        router.include_router(health_router, prefix="/health", tags=["Health"])
        router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
        # All data routers have optional auth — token is checked if provided, but not required
        # Note: alerts_router has its own endpoint-level Depends(get_current_user), so no router-level dep needed
        router.include_router(alerts_router, prefix="/alerts", tags=["Alerts"])
        router.include_router(market_router, prefix="/market", tags=["Market"], dependencies=_optional_auth)
        router.include_router(symbols_router, prefix="/instruments", tags=["Symbols"], dependencies=_optional_auth)
        router.include_router(quotes_router, prefix="/quotes", tags=["Quotes"], dependencies=_optional_auth)
        router.include_router(orderbooks_router, prefix="/orderbooks", tags=["Orderbooks"], dependencies=_optional_auth)
        router.include_router(trades_router, prefix="/trades", tags=["Trades"], dependencies=_optional_auth)
        router.include_router(signals_router, prefix="/signals", tags=["Signals"], dependencies=_optional_auth)
        router.include_router(recommendations_router, prefix="/recommendations", tags=["Recommendations"], dependencies=_optional_auth)
        router.include_router(indicators_router, prefix="/indicators", tags=["Indicators"], dependencies=_optional_auth)
        router.include_router(codal_router, prefix="/codal", tags=["Codal"], dependencies=_optional_auth)
        router.include_router(news_router, prefix="/news", tags=["News"], dependencies=_optional_auth)
        router.include_router(macro_router, prefix="/macro", tags=["Macro"], dependencies=_optional_auth)
        router.include_router(fundamental_router, prefix="/fundamental", tags=["Fundamental Analysis"], dependencies=_optional_auth)
        router.include_router(backtests_router, prefix="/backtests", tags=["Backtests"], dependencies=_optional_auth)
        router.include_router(ml_router, prefix="/ml", tags=["ML"], dependencies=_optional_auth)
        router.include_router(reports_router, prefix="/reports", tags=["Reports"], dependencies=_optional_auth)
        router.include_router(smart_money_router, prefix="/smart-money", tags=["Smart Money"], dependencies=_optional_auth)
        router.include_router(analysis_router, prefix="/analysis", tags=["Analysis"], dependencies=_optional_auth)
        router.include_router(tests_router, prefix="/tests", tags=["Tests"], dependencies=_optional_auth)
        router.include_router(portfolios_router, prefix="/portfolios", tags=["Portfolios"], dependencies=_optional_auth)
        router.include_router(admin_dashboard_router, prefix="/dashboard", tags=["Admin Dashboard"], dependencies=_optional_auth)
        router.include_router(market_info_router, tags=["Market Info"], dependencies=_optional_auth)
        return router
