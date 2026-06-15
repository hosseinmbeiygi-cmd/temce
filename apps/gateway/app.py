from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class GatewayApp:
    def __init__(self) -> None:
        self.app = FastAPI(title="API Gateway", version=settings.api_version)
        self.app.add_middleware(
            CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
        )
        logger.info("Gateway created")

    def get_app(self) -> FastAPI:
        return self.app
