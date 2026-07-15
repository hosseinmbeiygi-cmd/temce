"""
Generic BrsApi repository with bulk-insert / upsert support and sync logging.
"""

from __future__ import annotations

import json
from logging import getLogger
from typing import Any, Generic, TypeVar

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.models.base import RawPayloadModel, SyncLogModel

logger = getLogger(__name__)

T = TypeVar("T")

# ──────────────────────────────────────────────
#  Sync Log Repository
# ──────────────────────────────────────────────


class SyncLogRepository:
    """Logs sync operations for observability and dedup."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        endpoint: str,
        category: str,
        status: str = "success",
        items_count: int = 0,
        error_message: str | None = None,
        duration_ms: float = 0.0,
        params: dict[str, str] | None = None,
    ) -> SyncLogModel:
        entry = SyncLogModel(
            endpoint=endpoint,
            category=category,
            status=status,
            items_count=items_count,
            error_message=error_message,
            duration_ms=duration_ms,
            params_snapshot=json.dumps(params) if params else None,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def last_sync(self, endpoint: str, max_age_seconds: int = 120) -> SyncLogModel | None:
        """Return the most recent successful sync for *endpoint*."""
        stmt = (
            select(SyncLogModel)
            .where(SyncLogModel.endpoint == endpoint, SyncLogModel.status == "success")
            .order_by(SyncLogModel.completed_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def needs_sync(self, endpoint: str, interval_seconds: int = 60) -> bool:
        """
        Return ``True`` if enough time has passed since the last
        successful sync for *endpoint*.
        """
        from datetime import UTC, datetime

        last = await self.last_sync(endpoint)
        if last is None:
            return True
        if last.completed_at is None:
            return True
        elapsed = (datetime.now(UTC) - last.completed_at).total_seconds()
        return elapsed >= interval_seconds

    async def count_since(self, endpoint: str, since_minutes: int = 60) -> int:
        """How many syncs for *endpoint* in the last N minutes."""
        from datetime import UTC, datetime, timedelta

        cutoff = datetime.now(UTC) - timedelta(minutes=since_minutes)
        stmt = (
            select(SyncLogModel)
            .where(SyncLogModel.endpoint == endpoint, SyncLogModel.started_at >= cutoff)
        )
        result = await self.session.execute(stmt)
        return len(result.scalars().all())


# ──────────────────────────────────────────────
#  Raw Payload Repository
# ──────────────────────────────────────────────


class RawPayloadRepository:
    """Stores raw JSON payloads for audit."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def store(
        self,
        endpoint: str,
        payload: str,
        status_code: int = 200,
        params: dict[str, str] | None = None,
    ) -> RawPayloadModel:
        entry = RawPayloadModel(
            endpoint=endpoint,
            params=json.dumps(params) if params else None,
            status_code=status_code,
            payload=payload,
            size_bytes=len(payload),
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def purge_older_than(self, days: int = 30) -> int:
        """Delete raw payloads older than *days*."""
        from datetime import UTC, datetime, timedelta

        cutoff = datetime.now(UTC) - timedelta(days=days)
        stmt = select(RawPayloadModel).where(RawPayloadModel.fetched_at < cutoff)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        count = len(rows)
        for row in rows:
            await self.session.delete(row)
        await self.session.flush()
        logger.info("Purged %d raw payloads older than %d days", count, days)
        return count


# ──────────────────────────────────────────────
#  Bulk Upsert Repository
# ──────────────────────────────────────────────


class BulkUpsertRepository(Generic[T]):
    """
    Generic repository for bulk upsert of BrsApi data.

    Handles inserting new rows efficiently and provides a
    ``truncate_before`` option for full-refresh endpoints.
    """

    def __init__(self, session: AsyncSession, model_class: type[T]) -> None:
        self.session = session
        self.model_class = model_class

    async def bulk_insert(self, records: list[dict[str, Any]]) -> int:
        """
        Insert multiple records in one round-trip.
        Skips duplicates based on the table's unique constraints.
        """
        if not records:
            return 0
        table_name = self.model_class.__tablename__
        cols = list(records[0].keys())
        cols_str = ", ".join([f'"{c}"' for c in cols])
        placeholders = ", ".join([f":{c}" for c in cols])

        await self.session.execute(
            text(f'INSERT INTO "{table_name}" ({cols_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'),
            records,
        )
        await self.session.flush()
        return len(records)

    async def truncate(self) -> None:
        """Truncate the table (use with caution — for full-refresh endpoints)."""
        table_name = self.model_class.__tablename__
        await self.session.execute(text(f"TRUNCATE TABLE {table_name}"))
        await self.session.flush()
        logger.info("Truncated %s", table_name)

    async def count(self) -> int:
        """Return total row count."""
        from sqlalchemy import func as sa_func

        stmt = select(sa_func.count()).select_from(self.model_class)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_latest_by_symbol(
        self,
        symbol: str,
        limit: int = 1,
        order_column: str = "fetched_at",
    ) -> list[T]:
        """Get the most recent rows for a given symbol."""
        col = getattr(self.model_class, order_column, None)
        if col is None:
            col = self.model_class.created_at
        stmt = (
            select(self.model_class)
            .where(self.model_class.symbol == symbol)
            .order_by(col.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
