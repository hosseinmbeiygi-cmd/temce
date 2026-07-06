from __future__ import annotations

from fastapi import APIRouter

from apps.admin.audit import router as audit_router
from apps.admin.backtests import router as backtests_router
from apps.admin.dashboard import router as dashboard_router
from apps.admin.health import router as health_router
from apps.admin.jobs import router as jobs_router
from apps.admin.models import router as models_router
from apps.admin.providers import router as providers_router


class AdminRouter:
    def setup(self) -> APIRouter:
        router = APIRouter()
        router.include_router(dashboard_router, prefix="/dashboard", tags=["Admin Dashboard"])
        router.include_router(health_router, prefix="/dashboard/health", tags=["Admin Health"])
        router.include_router(jobs_router, prefix="/jobs", tags=["Admin Jobs"])
        router.include_router(providers_router, prefix="/providers", tags=["Admin Providers"])
        router.include_router(models_router, prefix="/models", tags=["Admin Models"])
        router.include_router(backtests_router, prefix="/backtests", tags=["Admin Backtests"])
        router.include_router(audit_router, prefix="/audit", tags=["Admin Audit"])
        return router
