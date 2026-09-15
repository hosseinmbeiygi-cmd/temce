"""Materialized view maintenance (Q1 P0).

Provides `refresh_latest_views()` used by the scheduler/worker every 60s
and by the API on-demand after a bulk ingest.

Uses CONCURRENT refresh so readers are never blocked.
Falls back to no-op if the view does not exist yet (pre-migration).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger

logger = get_logger(__name__)


async def refresh_latest_views(session: AsyncSession) -> dict[str, str]:
    """Refresh both mv_* views concurrently. Returns per-view status."""
    results: dict[str, str] = {}
    for view in ("mv_latest_brsapi_symbol_snapshot", "mv_latest_symbol_snapshot"):
        try:
            await session.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"))
            await session.commit()
            results[view] = "refreshed"
            logger.info("Materialized view %s refreshed", view)
        except Exception as exc:
            await session.rollback()
            # View may not exist before migration 0048
            if "does not exist" in str(exc) or "not exist" in str(exc).lower():
                results[view] = "not_exists (pre-migration)"
                logger.debug("MV %s not yet created: %s", view, exc)
            else:
                results[view] = f"error: {exc}"
                logger.warning("MV %s refresh failed: %s", view, exc)
    return results


async def refresh_latest_views_with_new_session() -> dict[str, str]:
    """Helper for background tasks / scheduler that need their own session."""
    from core.database import async_session_factory

    if async_session_factory is None:
        return {"error": "database not initialized"}
    async with async_session_factory() as session:
        return await refresh_latest_views(session)
