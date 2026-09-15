"""Router ترکیبی صندوق‌یار — همه endpoint ها در یک نقطه.

برای ادغام با router اصلی پروژه:
    from apps.funds.router import funds_router
    app.include_router(funds_router)
"""

from __future__ import annotations

from fastapi import APIRouter

from .api import router as funds_api_router
from .constants import DISCLAIMER_API, DISCLAIMER_UI

funds_router = APIRouter()
funds_router.include_router(funds_api_router)

__all__ = ["funds_router", "DISCLAIMER_API", "DISCLAIMER_UI"]
