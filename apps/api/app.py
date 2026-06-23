from __future__ import annotations

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
from core.database import close_database, init_database
from core.event_bus import event_bus
from core.logging import get_logger, setup_logging
from ml.models import register_all_models

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    settings.validate_production()
    await init_database()
    register_all_models()
    cache = get_cache()
    await cache.initialize()
    logger.info("Starting %s", settings.app_name)
    yield
    await cache.close()
    await close_database()
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
