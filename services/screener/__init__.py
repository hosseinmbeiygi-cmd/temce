"""D7: Unified Screener package — single entry point for all screeners.

Re-exports the three screener engines under a common interface so callers
no longer import three separate modules.

Usage:
    from services.screener import get_screener, ScreenerType

    svc = get_screener(ScreenerType.SMART_V2, session)
    results = await svc.screen(filters)

Old imports (still work, now thin wrappers):
    from services.screener_service import ScreenerService
    from services.smart_screener_v2 import SmartScreenerV2
    from services.screener110_service import Screener110Service
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class ScreenerType(str, Enum):  # noqa: UP042
    CLASSIC = "classic"
    SMART_V2 = "smart_v2"
    SCREENER110 = "screener110"


def get_screener(screener_type: ScreenerType | str, session: AsyncSession, **kwargs: Any):
    """Factory — returns the appropriate screener service."""
    st = ScreenerType(screener_type) if isinstance(screener_type, str) else screener_type
    if st == ScreenerType.CLASSIC:
        from services.screener_service import ScreenerService

        return ScreenerService(session=session, **kwargs)
    if st == ScreenerType.SMART_V2:
        from services.smart_screener_v2 import SmartScreenerV2

        return SmartScreenerV2(session=session, **kwargs)
    if st == ScreenerType.SCREENER110:
        from services.screener110_service import Screener110Service

        return Screener110Service(session=session, **kwargs)
    raise ValueError(f"Unknown screener type: {screener_type}")


__all__ = ["ScreenerType", "get_screener"]
