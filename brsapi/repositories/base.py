"""
Generic BrsApi repository with bulk-insert / upsert support and sync logging.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from logging import getLogger
from typing import Any, Generic, TypeVar

from sqlalchemy import case as sa_case
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.models.base import RawPayloadModel, SyncLogModel
from core.time import utc_now_naive

logger = getLogger(__name__)

_SAFE_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
_SENSITIVE_PARAM_NAMES = frozenset({"key", "api_key", "token", "secret", "password"})


def _redact_params(params: dict[str, str] | None) -> dict[str, str] | None:
    """Remove credentials before params reach logs or audit storage."""
    if not params:
        return params
    return {
        name: "[REDACTED]" if name.lower() in _SENSITIVE_PARAM_NAMES else value
        for name, value in params.items()
    }


def _quote_model_identifier(model_class: type[Any], name: str) -> str:
    """Quote an identifier only when it is a real column of ``model_class``.

    Record keys can originate from provider payloads.  They must never be
    interpolated into SQL before being checked against the ORM table schema.
    """
    table = model_class.__table__
    if not isinstance(name, str) or not _SAFE_IDENTIFIER.fullmatch(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    if name not in table.c:
        raise ValueError(f"Unknown column for {table.name}: {name!r}")
    return f'"{name}"'


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
            params_snapshot=json.dumps(_redact_params(params)) if params else None,
            completed_at=utc_now_naive(),
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
        last = await self.last_sync(endpoint)
        if last is None:
            return True
        if last.completed_at is None:
            return True
        elapsed = (utc_now_naive() - last.completed_at).total_seconds()
        return elapsed >= interval_seconds

    async def count_since(self, endpoint: str, since_minutes: int = 60) -> int:
        """How many syncs for *endpoint* in the last N minutes."""
        from datetime import timedelta

        from sqlalchemy import func as sa_func

        cutoff = utc_now_naive() - timedelta(minutes=since_minutes)
        stmt = (
            select(sa_func.count(SyncLogModel.id))
            .where(SyncLogModel.endpoint == endpoint, SyncLogModel.started_at >= cutoff)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_sync_stats(
        self,
        endpoint: str | None = None,
        window_days: int = 7,
    ) -> list[dict[str, Any]]:
        """
        Return per-endpoint sync statistics for the last *window_days* days.

        Metrics returned for each endpoint:
        - last_success_at: datetime of the most recent successful sync
        - last_run_at: datetime of the most recent sync attempt
        - error_rate: percentage of error syncs (0-100)
        - avg_duration_ms: average duration of syncs in the window
        - total_runs: total number of sync attempts in the window
        - success_count: number of successful syncs
        - error_count: number of failed syncs
        """
        from datetime import timedelta

        from sqlalchemy import func as sa_func

        cutoff = utc_now_naive() - timedelta(days=window_days)
        filters = [SyncLogModel.started_at >= cutoff]
        if endpoint:
            filters.append(SyncLogModel.endpoint == endpoint)

        total_runs = sa_func.count(SyncLogModel.id).label("total_runs")
        success_count = sa_func.sum(
            sa_case((SyncLogModel.status == "success", 1), else_=0)
        ).label("success_count")
        error_count = sa_func.sum(
            sa_case((SyncLogModel.status == "error", 1), else_=0)
        ).label("error_count")
        error_rate = (error_count * 100.0 / sa_func.nullif(total_runs, 0)).label("error_rate")
        avg_duration = sa_func.avg(SyncLogModel.duration_ms).label("avg_duration_ms")
        last_success = sa_func.max(
            sa_case(
                (SyncLogModel.status == "success", SyncLogModel.completed_at),
                else_=None,
            )
        ).label("last_success_at")
        last_run = sa_func.max(SyncLogModel.completed_at).label("last_run_at")

        stmt = (
            select(
                SyncLogModel.endpoint,
                last_success,
                last_run,
                error_rate,
                avg_duration,
                total_runs,
                success_count,
                error_count,
            )
            .where(*filters)
            .group_by(SyncLogModel.endpoint)
            .order_by(sa_func.max(SyncLogModel.completed_at).desc().nullslast())
        )

        result = await self.session.execute(stmt)
        rows = result.mappings().all()
        return [dict(row) for row in rows]


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
            params=json.dumps(_redact_params(params)) if params else None,
            status_code=status_code,
            payload=payload,
            size_bytes=len(payload),
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def purge_older_than(self, days: int = 30) -> int:
        """Delete raw payloads older than *days*.

        ``fetched_at`` is stored as a naive ``utc_now_naive()`` (see
        ``RawPayloadModel``), so the cutoff must use the same clock/zone to
        compare correctly — mixing aware UTC with naive DB timestamps would
        silently miss or over-delete rows.
        """
        from sqlalchemy import delete as sa_delete

        cutoff = utc_now_naive() - timedelta(days=days)
        stmt = sa_delete(RawPayloadModel).where(RawPayloadModel.fetched_at < cutoff)
        result = await self.session.execute(stmt)
        await self.session.flush()
        count = result.rowcount or 0
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

    async def bulk_insert(
        self,
        records: list[dict[str, Any]],
        on_conflict_update: bool = False,
        conflict_target: list[str] | tuple[str, ...] | None = None,
    ) -> int:
        """
        Insert multiple records in one round-trip.

        By default this is a plain insert (``ON CONFLICT DO NOTHING`` so a
        primary-key collision won't abort the batch). Pass
        ``on_conflict_update=True`` (used by ``SymbolSnapshotModel``, which
        has the ``(symbol, fetched_at)`` unique constraint) to refresh the
        conflicting row with the latest values via ``DO UPDATE`` instead of
        silently skipping it.

        ``on_conflict_update=True`` **requires** ``conflict_target`` — the
        **column name(s)** PostgreSQL uses to infer the conflict, e.g.
        ``["symbol", "fetched_at"]``. ``ON CONFLICT DO UPDATE`` without a
        target is a syntax error in PostgreSQL (``DO NOTHING`` is the only
        form allowed to omit it). A unique index must exist on exactly those
        columns; constraint names are not supported here.
        """
        if not records:
            return 0
        table_name = self.model_class.__table__.name
        if not _SAFE_IDENTIFIER.fullmatch(table_name):
            raise ValueError(f"Invalid model table identifier: {table_name!r}")
        cols = list(records[0].keys())
        if not cols:
            raise ValueError("bulk_insert requires at least one column")
        expected_keys = frozenset(cols)
        if any(frozenset(record.keys()) != expected_keys for record in records[1:]):
            raise ValueError("All bulk_insert records must contain the same columns")
        quoted_cols = [_quote_model_identifier(self.model_class, col) for col in cols]
        cols_str = ", ".join(quoted_cols)
        placeholders = ", ".join([f":{c}" for c in cols])

        if on_conflict_update:
            if not conflict_target:
                raise ValueError(
                    "bulk_insert(on_conflict_update=True) requires conflict_target "
                    "(e.g. ['symbol', 'fetched_at']) — PostgreSQL requires a "
                    "conflict-inference target for ON CONFLICT DO UPDATE"
                )
            # ``id`` is the PK — never overwrite it on conflict.
            update_cols = [c for c in cols if c != "id"]
            update_clause = ", ".join(
                f"{_quote_model_identifier(self.model_class, c)} = EXCLUDED.{_quote_model_identifier(self.model_class, c)}"
                for c in update_cols
            ) or ""
            target_sql = ", ".join(
                _quote_model_identifier(self.model_class, c) for c in conflict_target
            )
            conflict_sql = (
                f"ON CONFLICT ({target_sql}) DO UPDATE SET {update_clause}"
                if update_clause
                else "ON CONFLICT DO NOTHING"
            )
        else:
            conflict_sql = "ON CONFLICT DO NOTHING"

        result = await self.session.execute(
            text(f'INSERT INTO "{table_name}" ({cols_str}) VALUES ({placeholders}) {conflict_sql}'),
            records,
        )
        await self.session.flush()
        # rowcount is driver-dependent (psycopg may return None); fall back to len(records) only if unavailable
        try:
            rc = result.rowcount  # type: ignore[attr-defined]
            if rc is not None and rc >= 0:
                return int(rc)
        except Exception:
            pass
        return len(records)

    async def truncate(self) -> None:
        """Truncate the table (use with caution — for full-refresh endpoints)."""
        table_name = self.model_class.__table__.name
        if not _SAFE_IDENTIFIER.fullmatch(table_name):
            raise ValueError(f"Invalid model table identifier: {table_name!r}")
        await self.session.execute(text(f'TRUNCATE TABLE "{table_name}"'))
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
