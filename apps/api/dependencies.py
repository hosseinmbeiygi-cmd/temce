from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from core.logging import get_logger
from core.security.tokens import decode_access_token

logger = get_logger(__name__)

# 🔧 PostgreSQL connection via dependency injection
# This is now using settings.database_url from core.config
from core.config import settings


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    from core.database import get_session
    async for session in get_session():
        yield session


def get_symbol_service(session: AsyncSession = Depends(get_db_session)):
    from services.symbol_service import SymbolService

    return SymbolService(session=session)


def get_instrument_import_service(session: AsyncSession = Depends(get_db_session)):
    from services.instrument_import_service import InstrumentImportService
    from repositories.instrument_repository import InstrumentRepository

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


@lru_cache(maxsize=1)
def get_backtest_service():
    from services.backtest_service import BacktestService

    return BacktestService()


def get_inference_service():
    from services.inference_service import InferenceService

    return InferenceService()


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
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_optional_user(authorization: str = Header("")) -> dict | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    try:
        return decode_access_token(token)
    except Exception as e:
        logger.debug("Optional user token invalid: %s", e)
        return None


async def require_role(role: str, current_user: dict = Depends(get_current_user)) -> dict:
    user_roles = current_user.get("roles", [])
    if role not in user_roles and "admin" not in user_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return current_user


def get_portfolio_service(session: AsyncSession = Depends(get_db_session)):
    from services.portfolio_service import PortfolioService

    return PortfolioService(session=session)