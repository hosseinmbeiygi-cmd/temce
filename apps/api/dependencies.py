from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.security.tokens import decode_access_token, is_token_revoked

logger = get_logger(__name__)

# 🔧 PostgreSQL connection via dependency injection
# This is now using settings.database_url from core.config


async def _reject_if_revoked(payload: dict) -> dict:
    """Reject a decoded token if its jti is in the revocation blacklist."""
    if await is_token_revoked(payload.get("jti")):
        raise HTTPException(status_code=401, detail="Token has been revoked")
    return payload


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    from core.database import get_session
    async for session in get_session():
        yield session


def get_symbol_service(session: AsyncSession = Depends(get_db_session)):
    from services.symbol_service import SymbolService

    return SymbolService(session=session)


def get_instrument_import_service(session: AsyncSession = Depends(get_db_session)):
    from repositories.instrument_repository import InstrumentRepository
    from services.instrument_import_service import InstrumentImportService

    return InstrumentImportService(repo=InstrumentRepository(session=session))


def get_quote_service(session: AsyncSession = Depends(get_db_session)):
    from services.quote_service import QuoteService

    return QuoteService(session=session)


def get_brsapi_query_service(session: AsyncSession = Depends(get_db_session)):
    from brsapi.services.query_service import BrsApiQueryService

    return BrsApiQueryService(session=session)


async def get_brsapi_client():
    """Lazily resolve the BrsApi HTTP client singleton."""
    from brsapi.client import get_client

    return await get_client()


def get_market_service(
    session: AsyncSession = Depends(get_db_session),
    brsapi=Depends(get_brsapi_query_service),
    client=Depends(get_brsapi_client),
):
    from services.market_service import MarketService

    return MarketService(session=session, brsapi_query_service=brsapi, brsapi_client=client)


def get_analytics_service(session: AsyncSession = Depends(get_db_session)):
    from services.analytics_service import AnalyticsService

    return AnalyticsService(session=session)


def get_signal_service(session: AsyncSession = Depends(get_db_session)):
    from services.signal_service import SignalService

    return SignalService(session=session)


def get_recommendation_service(session: AsyncSession = Depends(get_db_session)):
    from services.recommendation_service import RecommendationService

    return RecommendationService(session=session)


def get_codal_service(session: AsyncSession = Depends(get_db_session)):
    from services.codal_service import CodalService

    return CodalService(session=session)


def get_news_service(session: AsyncSession = Depends(get_db_session)):
    from services.news_service import NewsService

    return NewsService(session=session)


def get_backtest_service(session: AsyncSession = Depends(get_db_session)):
    from repositories.backtest_repository import BacktestRepository
    from services.backtest_service import BacktestService

    return BacktestService(repository=BacktestRepository(session=session))


def get_inference_service(session: AsyncSession = Depends(get_db_session)):
    from repositories.ml_repository import MlRepository
    from repositories.quote_repository import QuoteRepository
    from services.inference_service import InferenceService

    return InferenceService(
        quote_repo=QuoteRepository(session=session),
        model_repo=MlRepository(session=session),
    )


def get_smart_money_service(session: AsyncSession = Depends(get_db_session)):
    from services.smart_money_service import SmartMoneyService

    return SmartMoneyService(session=session)


def get_trade_service(
    brsapi=Depends(get_brsapi_query_service),
    client=Depends(get_brsapi_client),
):
    from services.trade_service import TradeService

    return TradeService(brsapi_query_service=brsapi, brsapi_client=client)


def get_orderbook_service(
    session: AsyncSession = Depends(get_db_session),
    brsapi=Depends(get_brsapi_query_service),
    client=Depends(get_brsapi_client),
):
    from services.orderbook_service import OrderBookService

    return OrderBookService(session=session, brsapi_query_service=brsapi, brsapi_client=client)


def get_macro_service(
    brsapi=Depends(get_brsapi_query_service),
    client=Depends(get_brsapi_client),
):
    from services.macro_service import MacroService

    return MacroService(brsapi_query_service=brsapi, brsapi_client=client)


def get_report_service(session: AsyncSession = Depends(get_db_session)):
    from services.report_service import ReportService

    return ReportService(session=session)


async def get_current_user(authorization: str = Header("")) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    try:
        payload = decode_access_token(token)
        return await _reject_if_revoked(payload)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_optional_user(authorization: str = Header("")) -> dict | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    try:
        payload = decode_access_token(token)
        if await is_token_revoked(payload.get("jti")):
            return None
        return payload
    except Exception as e:
        logger.debug("Optional user token invalid: %s", e)
        return None


async def require_role(role: str, current_user: dict = Depends(get_current_user)) -> dict:
    """Require user to have at least the specified role.

    Admin always has access to everything.
    """
    from core.enums.rbac import has_role
    user_roles = current_user.get("roles", [])
    if not has_role(user_roles, role):
        raise HTTPException(status_code=403, detail=f"Insufficient permissions: requires {role} or higher")
    return current_user


def require_roles(*roles: str):
    """Dependency factory: require user to have ANY of the listed roles.

    Usage:
        @router.get("/admin-only")
        async def admin_only(user = Depends(require_roles("admin"))):
            ...

        @router.get("/analyst-or-admin")
        async def analyst_or_admin(user = Depends(require_roles("analyst", "admin"))):
            ...
    """
    from core.enums.rbac import has_any_role

    async def _check(current_user: dict = Depends(get_current_user)) -> dict:
        user_roles = current_user.get("roles", [])
        if not has_any_role(user_roles, list(roles)):
            raise HTTPException(status_code=403, detail=f"Insufficient permissions: requires one of {list(roles)}")
        return current_user

    return _check


def get_portfolio_service(session: AsyncSession = Depends(get_db_session)):
    from services.portfolio_service import PortfolioService

    return PortfolioService(session=session)


def get_watchlist_service(
    brsapi=Depends(get_brsapi_query_service),
):
    from services.watchlist_service import WatchlistService

    return WatchlistService(brsapi=brsapi)


def get_multi_market_signal_service(session: AsyncSession = Depends(get_db_session)):
    from services.multi_market_signal_engine import MultiMarketSignalEngine

    return MultiMarketSignalEngine(session=session)


def get_screener_service(session: AsyncSession = Depends(get_db_session)):
    from services.screener_service import ScreenerService

    return ScreenerService(session=session)


def get_fake_queue_detector_service(session: AsyncSession = Depends(get_db_session)):
    from services.fake_queue_detector import FakeQueueDetector

    return FakeQueueDetector(session=session)


def get_hidden_accumulation_service(session: AsyncSession = Depends(get_db_session)):
    from services.hidden_accumulation import HiddenAccumulationDetector

    return HiddenAccumulationDetector(session=session)


def get_signal_performance_tracker_service(session: AsyncSession = Depends(get_db_session)):
    from services.signal_performance_tracker import SignalPerformanceTracker

    return SignalPerformanceTracker(session=session)


def get_manipulation_detector_service(session: AsyncSession = Depends(get_db_session)):
    from services.manipulation_detector import ManipulationDetector

    return ManipulationDetector(session=session)


def get_real_return_calculator_service(session: AsyncSession = Depends(get_db_session)):
    from services.real_return_calculator import RealReturnCalculator

    return RealReturnCalculator(session=session)


def get_iran_fear_greed_service(session: AsyncSession = Depends(get_db_session)):
    from services.iran_fear_greed_index import IranFearGreedIndex

    return IranFearGreedIndex(session=session)


def get_historical_level_analyzer_service(session: AsyncSession = Depends(get_db_session)):
    from services.historical_level_analyzer import HistoricalLevelAnalyzer

    return HistoricalLevelAnalyzer(session=session)


def get_block_trade_detector_service(session: AsyncSession = Depends(get_db_session)):
    from services.block_trade_detector import BlockTradeDetector

    return BlockTradeDetector(session=session)


def get_market_health_index_service(session: AsyncSession = Depends(get_db_session)):
    from services.market_health_index import MarketHealthIndex

    return MarketHealthIndex(session=session)


def get_gap_prediction_service(session: AsyncSession = Depends(get_db_session)):
    from services.gap_prediction import GapPredictor

    return GapPredictor(session=session)
