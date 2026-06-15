from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.error_handlers import register_error_handlers
from apps.api.middleware import TimingMiddleware
from apps.api.router import Router
from core.config import settings
from core.database import close_database, init_database
from core.logging import get_logger, setup_logging
from ml.models import register_all_models

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    settings.validate_production()
    await init_database()
    register_all_models()
    logger.info("Starting %s", settings.app_name)
    yield
    await close_database()
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
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

    register_error_handlers(app)

    router = Router()
    app.include_router(router.setup(), prefix=settings.api_prefix)

    return app


app = create_app()
