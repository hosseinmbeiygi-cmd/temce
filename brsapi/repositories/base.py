"""
Generic BrsApi repository with bulk-insert / upsert support and sync logging.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta
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


def _sha256(payload: str) -> str:
    """Return the SHA-256 hex digest of a payload string (سند §2.3)."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _redact_params(params: dict[str, str] | None) -> dict[str, str] | None:
    """Remove credentials before params reach logs or audit storage."""
    if not params:
        return params
    return {name: "[REDACTED]" if name.lower() in _SENSITIVE_PARAM_NAMES else value for name, value in params.items()}


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


class BulkInsertRowCountUnavailable(RuntimeError):
    """The driver did not report how many rows the batch affected.

    Raised instead of guessing: reporting ``len(records)`` after
    ``ON CONFLICT DO NOTHING`` would claim rows were written when they were
    skipped.
    """


def _affected_row_count(
    result: Any,
    *,
    attempted: int,
    on_conflict_update: bool,
    table_name: str,
) -> int:
    """Return the number of rows the batch actually inserted or updated.

    ``ON CONFLICT DO UPDATE`` touches every (deduplicated) row, so the
    attempted count is exact there.  For ``DO NOTHING`` an unknown count is
    genuinely unknowable without extra queries, so it fails loudly.
    """
    try:
        rowcount = result.rowcount
    except (AttributeError, NotImplementedError):
        rowcount = None

    if isinstance(rowcount, int) and rowcount >= 0:
        return rowcount

    if on_conflict_update:
        logger.debug(
            "bulk_insert: no rowcount for %s; DO UPDATE affects all %d rows",
            table_name,
            attempted,
        )
        return attempted

    raise BulkInsertRowCountUnavailable(
        f"Driver did not report rowcount for {table_name}; the number of "
        f"rows inserted by ON CONFLICT DO NOTHING is unknown"
    )

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
        outcome: str = "unknown",
    ) -> SyncLogModel:
        entry = SyncLogModel(
            endpoint=endpoint,
            category=category,
            status=status,
            outcome=outcome,
            items_count=items_count,
            error_message=error_message,
            duration_ms=duration_ms,
            params_snapshot=json.dumps(_redact_params(params)) if params else None,
            completed_at=utc_now_naive(),
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def last_sync(
        self,
        endpoint: str,
        max_age_seconds: int = 120,
        params: dict[str, str] | None = None,
    ) -> SyncLogModel | None:
        """Return the most recent successful sync for *endpoint*.

        When *params* is supplied the lookup is scoped to that exact
        (redacted) parameter snapshot.  Without this, syncing one symbol
        would suppress the next symbol's sync of the same endpoint.
        """
        stmt = select(SyncLogModel).where(
            SyncLogModel.endpoint == endpoint, SyncLogModel.status == "success"
        )
        if params is not None:
            stmt = stmt.where(
                SyncLogModel.params_snapshot == json.dumps(_redact_params(params))
            )
        stmt = stmt.order_by(SyncLogModel.completed_at.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def needs_sync(
        self,
        endpoint: str,
        interval_seconds: int = 60,
        params: dict[str, str] | None = None,
    ) -> bool:
        """
        Return ``True`` if enough time has passed since the last
        successful sync for *endpoint* (and *params*, when given).
        """
        last = await self.last_sync(endpoint, params=params)
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
        stmt = select(sa_func.count(SyncLogModel.id)).where(
            SyncLogModel.endpoint == endpoint, SyncLogModel.started_at >= cutoff
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
        success_count = sa_func.sum(sa_case((SyncLogModel.status == "success", 1), else_=0)).label("success_count")
        error_count = sa_func.sum(sa_case((SyncLogModel.status == "error", 1), else_=0)).label("error_count")
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
    """Stores raw JSON payloads for audit (سند v5.0 §2.3 Raw_Tick contract)."""

    DEFAULT_SCHEMA_VERSION = "raw_payload.v1"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def store(
        self,
        endpoint: str,
        payload: str,
        status_code: int = 200,
        params: dict[str, str] | None = None,
        *,
        receive_time: datetime | None = None,
        market_time: datetime | None = None,
        response_latency_ms: float | None = None,
        schema_version: str | None = None,
        checksum_sha256: str | None = None,
    ) -> RawPayloadModel:
        entry = RawPayloadModel(
            endpoint=endpoint,
            params=json.dumps(_redact_params(params)) if params else None,
            status_code=status_code,
            payload=payload,
            size_bytes=len(payload),
            # Always store an explicit naive-UTC timestamp: the retention job
            # compares this column against ``utc_now_naive()``.
            fetched_at=receive_time or utc_now_naive(),
            receive_time=receive_time or utc_now_naive(),
            market_time=market_time,
            response_latency_ms=response_latency_ms,
            schema_version=schema_version or self.DEFAULT_SCHEMA_VERSION,
            checksum_sha256=checksum_sha256 or _sha256(payload),
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
            update_clause = (
                ", ".join(
                    f"{_quote_model_identifier(self.model_class, c)} = EXCLUDED.{_quote_model_identifier(self.model_class, c)}"
                    for c in update_cols
                )
                or ""
            )
            target_sql = ", ".join(_quote_model_identifier(self.model_class, c) for c in conflict_target)
            conflict_sql = (
                f"ON CONFLICT ({target_sql}) DO UPDATE SET {update_clause}"
                if update_clause
                else "ON CONFLICT DO NOTHING"
            )
        else:
            conflict_sql = "ON CONFLICT DO NOTHING"

        # PostgreSQL rejects a batch that touches the same conflict key twice
        # ("ON CONFLICT DO UPDATE command cannot affect row a second time").
        # Keep the last row per key; rows with NULL keys are left untouched
        # because NULLs are distinct in a unique index.
        if on_conflict_update and conflict_target:
            keys = [tuple(rec.get(c) for c in conflict_target) for rec in records]
            if all(value is not None for key in keys for value in key):
                deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
                for key, rec in zip(keys, records, strict=False):
                    deduped[key] = rec
                if len(deduped) != len(records):
                    logger.warning(
                        "bulk_insert: collapsed %d duplicate conflict keys for %s",
                        len(records) - len(deduped),
                        table_name,
                    )
                records = list(deduped.values())

        result = await self.session.execute(
            text(f'INSERT INTO "{table_name}" ({cols_str}) VALUES ({placeholders}) {conflict_sql}'),
            records,
        )
        await self.session.flush()
        # ``rowcount`` is the number of rows actually inserted/updated. It is
        # not guessed when the driver omits it — see _affected_row_count.
        return _affected_row_count(
            result,
            attempted=len(records),
            on_conflict_update=on_conflict_update,
            table_name=table_name,
        )

    async def delete_where(self, column: str, value: Any) -> int:
        """Delete rows whose *column* equals *value* (scoped replace).

        Used instead of :meth:`truncate` when only one logical slice of a
        table (e.g. one symbol, or one ``section``) may be refreshed. The
        delete participates in the caller's transaction, so a later insert
        failure rolls the deletion back.
        """
        table_name = self.model_class.__table__.name
        if not _SAFE_IDENTIFIER.fullmatch(table_name):
            raise ValueError(f"Invalid model table identifier: {table_name!r}")
        quoted_column = _quote_model_identifier(self.model_class, column)
        result = await self.session.execute(
            text(f'DELETE FROM "{table_name}" WHERE {quoted_column} = :value'),
            {"value": value},
        )
        await self.session.flush()
        try:
            rc = result.rowcount  # type: ignore[attr-defined]  # CursorResult only; Result protocol omits it
        except (AttributeError, NotImplementedError) as exc:
            logger.debug("delete_where: driver did not report rowcount for %s: %s", table_name, exc)
            return 0
        return rc if isinstance(rc, int) and rc >= 0 else 0

    async def truncate(self) -> None:
        """Truncate the table (use with caution — for full-refresh endpoints).

        Destructive refreshes require an explicit environment opt-in so a
        mis-scoped caller cannot wipe a table by accident.
        """
        if os.environ.get("ALLOW_TABLE_TRUNCATE") != "1":
            raise RuntimeError(
                "TRUNCATE is disabled; set ALLOW_TABLE_TRUNCATE=1 only for an "
                "intentional full-refresh run"
            )
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
        stmt = select(self.model_class).where(self.model_class.symbol == symbol).order_by(col.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
