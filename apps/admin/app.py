from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.admin.router import AdminRouter
from core.config import settings
from core.database import close_database, init_database
from core.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    settings.validate_production()
    await init_database()
    logger.info("Starting admin panel")
    yield
    await close_database()
    logger.info("Shutting down admin panel")


def create_admin_app() -> FastAPI:
    app = FastAPI(title="Admin Panel", version=settings.api_version, lifespan=lifespan)

    admin_router = AdminRouter()
    app.include_router(admin_router.setup(), prefix="/admin")

    return app


admin_app = create_admin_app()
