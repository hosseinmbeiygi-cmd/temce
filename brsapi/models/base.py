"""
Base BrsApi ORM models and shared utility tables.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class BrsApiBase(DeclarativeBase):
    """Base class for all BrsApi ORM models."""

    __abstract__ = True


class InstrumentRefMixin:
    """
    Mixin that adds ``ins_id`` and ``instrument_id`` columns for
    linking BrsApi records to the main ``instruments`` table.

    - ``ins_id``: TSETMC internal instrument ID (string, from API)
    - ``instrument_id``: ForeignKey to ``instruments.id``
    """

    ins_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True, comment="TSETMC internal instrument ID"
    )
    instrument_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True, comment="FK to instruments.id"
    )


# ──────────────────────────────────────────────
#  Raw Payload Audit
# ──────────────────────────────────────────────


class RawPayloadModel(BrsApiBase):
    """
    Stores raw JSON responses for audit / replay purposes.

    This table is optional (controlled by
    ``BrsApiSettings.raw_payload_sink_enabled``) and has a
    configurable retention period.

    سند v5.0 §2.3: آرشیو تغییرناپذیر با Market_Time, Receive_Time,
    Response_Latency_ms, HTTP_Status, SHA256_Checksum, schema_version.
    """

    __tablename__ = "brsapi_raw_payloads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    params: Mapped[str | None] = mapped_column(Text, nullable=True, comment="URL params as JSON")
    status_code: Mapped[int] = mapped_column(Integer, default=200)
    payload: Mapped[str] = mapped_column(Text, nullable=False, comment="Raw JSON payload")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        index=True,
    )
    # سند §2.3: ستون‌های اضافی برای ردیابی کامل
    receive_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="Wall-clock at client receive"
    )
    market_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="Market timestamp inside the payload"
    )
    response_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Round-trip latency in ms")
    schema_version: Mapped[str | None] = mapped_column(
        String(40), nullable=True, comment="Payload schema version (raw_payload.vN)"
    )
    checksum_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="SHA256 of payload"
    )


# ──────────────────────────────────────────────
#  Sync Log
# ──────────────────────────────────────────────


class SyncLogModel(BrsApiBase):
    """
    Tracks each sync operation for observability and dedup.

    Used by the sync service to avoid re-fetching data that has
    already been fetched recently.
    """

    __tablename__ = "brsapi_sync_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="success", comment="success | partial | error")
    items_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    params_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (Index("idx_sync_log_endpoint_time", "endpoint", "started_at"),)


# ──────────────────────────────────────────────
#  Daily Usage (admin reporting)
# ──────────────────────────────────────────────


class BrsApiDailyUsageModel(BrsApiBase):
    """
    One row per Tehran day aggregating BrsApi request usage.

    Written by :class:`brsapi.usage_recorder.BrsApiUsageRecorder` as an
    incremental, additive upsert (``ON CONFLICT (usage_date) DO UPDATE``) so
    multiple API workers each add their own share without clobbering each
    other. Read by the admin panel via ``GET /api/v1/brsapi/manage/usage``.

    - ``usage_date``    — Tehran calendar date (``YYYY-MM-DD``)
    - ``request_count`` — live requests granted that day
    - ``daily_limit``   — configured daily cap in effect (snapshot)
    - ``blocked_count`` — HTTP 302 over-quota blocks observed
    - ``blocked_at``    — last 302 block timestamp
    - ``last_request_at`` — last granted request timestamp
    """

    __tablename__ = "brsapi_daily_usage"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    usage_date: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Tehran date YYYY-MM-DD",
    )
    request_count: Mapped[int] = mapped_column(Integer, default=0, comment="Granted live requests that day")
    daily_limit: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Configured daily cap in effect")
    blocked_count: Mapped[int] = mapped_column(Integer, default=0, comment="HTTP 302 over-quota blocks observed")
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="Last 302 block timestamp")
    last_request_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="Last granted request timestamp"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )

    __table_args__ = (Index("uq_brsapi_daily_usage_date", "usage_date", unique=True),)
