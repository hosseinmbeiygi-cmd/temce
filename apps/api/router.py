from __future__ import annotations

from fastapi import APIRouter

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
)


class Router:
    def setup(self) -> APIRouter:
        router = APIRouter()
        router.include_router(alerts_router, prefix="/alerts", tags=["Alerts"])
        router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
        router.include_router(health_router, prefix="/health", tags=["Health"])
        router.include_router(market_router, prefix="/market", tags=["Market"])
        router.include_router(symbols_router, prefix="/symbols", tags=["Symbols"])
        router.include_router(quotes_router, prefix="/quotes", tags=["Quotes"])
        router.include_router(orderbooks_router, prefix="/orderbooks", tags=["Orderbooks"])
        router.include_router(trades_router, prefix="/trades", tags=["Trades"])
        router.include_router(signals_router, prefix="/signals", tags=["Signals"])
        router.include_router(recommendations_router, prefix="/recommendations", tags=["Recommendations"])
        router.include_router(indicators_router, prefix="/indicators", tags=["Indicators"])
        router.include_router(codal_router, prefix="/codal", tags=["Codal"])
        router.include_router(news_router, prefix="/news", tags=["News"])
        router.include_router(macro_router, prefix="/macro", tags=["Macro"])
        router.include_router(fundamental_router, prefix="/fundamental", tags=["Fundamental Analysis"])
        router.include_router(backtests_router, prefix="/backtests", tags=["Backtests"])
        router.include_router(ml_router, prefix="/ml", tags=["ML"])
        router.include_router(reports_router, prefix="/reports", tags=["Reports"])
        router.include_router(smart_money_router, prefix="/smart-money", tags=["Smart Money"])
        router.include_router(analysis_router, prefix="/analysis", tags=["Analysis"])
        router.include_router(tests_router, prefix="/tests", tags=["Tests"])
        router.include_router(portfolios_router, prefix="/portfolios", tags=["Portfolios"])
        return router
