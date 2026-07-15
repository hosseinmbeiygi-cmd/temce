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
from core.logging import get_logger, setup_logging
from ml.models import register_all_models

logger = get_logger(__name__)


# ── Notification callback for rate limit alerts ──

async def _rate_limit_notify(message: str) -> None:
    """Send rate limit alerts via Telegram if configured, always log."""
    logger.warning("RATE LIMIT ALERT: %s", message)
    try:
        from integrations.notifications.telegram_sender import TelegramSender
        sender = TelegramSender()
        result = await sender.send(f"⚠️ <b>BrsApi Rate Limit</b>\n\n{message}")
        if not result.success:
            logger.debug("Telegram notification not sent (not configured?): %s", result.error)
    except Exception:
        pass


# ── Startup background tasks ──

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


async def _brsapi_startup_sync() -> None:
    """
    Startup sync: fetch ALL BrsApi endpoints in order.
    Respects rate limits automatically (the rate limiter enforces 10K/day, 500/5min).
    """
    try:
        from brsapi.client import get_client
        from brsapi.services.sync_service import BrsApiSyncService

        logger.info("=" * 60)
        logger.info("BrsApi STARTUP SYNC — fetching ALL endpoints in order")
        logger.info("=" * 60)

        client = await get_client()
        session_obtained = False

        async for session in get_session():
            session_obtained = True
            service = BrsApiSyncService(client=client, session=session)

            # sync_all runs every endpoint in sequence, respecting rate limits
            reports = await service.sync_all(session)

            # Log summary
            ok = sum(1 for r in reports if r.success)
            fail = sum(1 for r in reports if not r.success)
            skipped = sum(1 for r in reports if r.skipped)
            total_items = sum(r.items_count for r in reports)
            total_ms = sum(r.duration_ms for r in reports)

            logger.info("=" * 60)
            logger.info("STARTUP SYNC COMPLETE: %d ok, %d failed, %d skipped", ok, fail, skipped)
            logger.info("Total items synced: %d | Total time: %.1fs", total_items, total_ms / 1000)
            logger.info("=" * 60)

            for r in reports:
                status = "OK" if r.success else ("SKIP" if r.skipped else "FAIL")
                logger.info(
                    "  [%s] %s — %d items, %.0fms%s",
                    status, r.endpoint, r.items_count, r.duration_ms,
                    f" — {r.error}" if r.error else "",
                )

            # Log rate limiter status
            from brsapi.rate_limiter import get_rate_limiter
            rl_status = get_rate_limiter().status()
            g = rl_status["global"]
            logger.info(
                "Rate limits: daily %d/%d (%.0f%%) | 5min %d/%d (%.0f%%)",
                g["daily_count"], g["daily_limit"], g["daily_used_pct"],
                g["5min_count"], g["5min_limit"], g["5min_used_pct"],
            )

            break

        if not session_obtained:
            logger.warning("Could not obtain DB session for BrsApi startup sync")

    except Exception:
        logger.exception("BrsApi startup sync failed")


# ── Lifespan ──

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

    # ── Register rate limit notification callback ──
    try:
        from brsapi.rate_limiter import get_rate_limiter
        rl = get_rate_limiter()
        rl.on_threshold(_rate_limit_notify)
        logger.info(
            "Rate limiter initialized: daily=%d, 5min=%d",
            rl._daily_limit, rl._five_min_limit,
        )
    except Exception:
        logger.warning("Rate limiter notification setup failed")

    # ── Start BrsApi scheduler (periodic sync jobs) ──
    try:
        from apps.scheduler.app import SchedulerApp
        _scheduler_app = SchedulerApp()
        _scheduler_app.start()
        job_count = len(_scheduler_app.scheduler.get_jobs())
        logger.info("BrsApi scheduler started with %d periodic jobs", job_count)
    except Exception:
        logger.exception("BrsApi scheduler startup failed — periodic syncs disabled")

    # ── Initial full sync (ALL endpoints, ordered) ──
    asyncio.create_task(_brsapi_startup_sync())

    # Auto-fetch news in background
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

    # ── Rate limit status endpoint ──
    @app.get("/api/v1/rate-limits")
    async def rate_limit_status():
        """Check BrsApi rate limit status (daily, 5min, per-endpoint)."""
        from brsapi.rate_limiter import get_rate_limiter
        from schemas.common.responses import ApiResponse
        return ApiResponse(success=True, data=get_rate_limiter().status())

    router = Router()
    app.include_router(router.setup(), prefix=settings.api_prefix)

    return app


app = create_app()
