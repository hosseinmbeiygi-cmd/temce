"""Currency service FastAPI app.

Lightweight, mirrors ``apps/admin`` pattern: no middleware stack, single
lifespan that initializes the shared DB engine. Run on port 8002.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.currency_service.config import settings as svc_settings
from apps.currency_service.router import CurrencyRouter
from core.config import settings as core_settings
from core.database import close_database, init_database
from core.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    core_settings.validate_production()
    await init_database()
    logger.info(
        "Starting currency_service on port %d (jitter_pct=%.2f, alerts=%s)",
        svc_settings.port,
        svc_settings.jitter_pct,
        svc_settings.enable_alerts,
    )
    yield
    await close_database()
    logger.info("Shutting down currency_service")


def create_currency_app() -> FastAPI:
    app = FastAPI(
        title="Currency Service",
        version="0.1.0",
        lifespan=lifespan,
        description="Standalone USD/USDT market service — mock data, signals, manual positions.",
    )

    api_prefix = svc_settings.api_prefix  # /api/v1
    currency_router = CurrencyRouter().setup()
    app.include_router(currency_router, prefix=f"{api_prefix}/currency")

    return app


currency_app = create_currency_app()
