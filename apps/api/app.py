from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from apps.api.error_handlers import register_error_handlers
from apps.api.middleware import LoggingMiddleware, RateLimitMiddleware, TimingMiddleware
from apps.api.router import Router
from core.cache import get_cache
from core.config import settings
from core.database import close_database, get_session, init_database
from core.event_bus import event_bus
from core.logging import get_logger, setup_logging
from ml.models import register_all_models

logger = get_logger(__name__)


async def _fetch_news_on_startup() -> None:
    """Background task: fetch news from RSS feeds on API startup."""
    try:
        from services.news_ingestion import NewsIngestionService

        logger.info("Auto-fetching news on startup...")
        session_obtained = False
        async for session in get_session():
            session_obtained = True
            service = NewsIngestionService(session=session)
            stats = await service.ingest(
                sources=None,
                limit_per_source=30,
                save=True,
                verbose=False,
                skip_sentiment=False,
            )
            logger.info(
                "Startup news fetch complete: fetched=%d saved=%d",
                stats.get("fetched", 0),
                stats.get("saved", 0),
            )
        if not session_obtained:
            logger.warning("Could not obtain DB session for startup news fetch")
    except Exception:
        logger.exception("Startup news fetch failed")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    try:
        settings.validate_production()
    except Exception:
        logger.warning("Production validation skipped (development mode)")

    # Database: resilient init
    try:
        await init_database()
    except Exception:
        logger.exception("Database init failed, continuing without DB")

    # ML models: optional
    try:
        register_all_models()
    except Exception:
        logger.warning("ML model registration failed (optional)")

    # Cache: resilient init
    cache = get_cache()
    try:
        await cache.initialize()
    except Exception:
        logger.warning("Cache init failed, using null cache")

    # Auto-fetch news in background (non-blocking)
    asyncio.create_task(_fetch_news_on_startup())

    logger.info("Starting %s", settings.app_name)
    yield
    try:
        await cache.close()
    except Exception:
        pass
    try:
        await close_database()
    except Exception:
        pass
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TimingMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)

    register_error_handlers(app)

    @app.get("/")
    async def root():
        return RedirectResponse(url="/docs")

    router = Router()
    app.include_router(router.setup(), prefix=settings.api_prefix)

    return app


app = create_app()
