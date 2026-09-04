"""Router composition. Mounts all sub-routers under /currency."""

from __future__ import annotations

from fastapi import APIRouter

from apps.currency_service.endpoints.health import router as health_router
from apps.currency_service.endpoints.overview import router as overview_router
from apps.currency_service.endpoints.positions import router as positions_router
from apps.currency_service.endpoints.signals import router as signals_router


class CurrencyRouter:
    def setup(self) -> APIRouter:
        router = APIRouter()
        # Sub-routers expose endpoint paths directly (e.g. /health, /overview).
        # The outer prefix `/api/v1/currency` is applied where this router mounts.
        router.include_router(health_router, tags=["Currency Health"])
        router.include_router(overview_router, tags=["Currency Overview"])
        router.include_router(signals_router, tags=["Currency Signals"])
        router.include_router(positions_router, tags=["Currency Positions"])
        return router
