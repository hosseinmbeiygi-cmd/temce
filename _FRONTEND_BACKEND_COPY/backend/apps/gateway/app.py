from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class GatewayApp:
    def __init__(self) -> None:
        self.app = FastAPI(title="API Gateway", version=settings.api_version)

        origins = settings.cors_origins
        # Wildcard + credentials is a CORS spec violation; only allow creds with specific origins
        allow_creds = origins != ["*"]

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=allow_creds,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        logger.info("Gateway created with CORS origins=%s allow_credentials=%s", origins, allow_creds)

    def get_app(self) -> FastAPI:
        return self.app
