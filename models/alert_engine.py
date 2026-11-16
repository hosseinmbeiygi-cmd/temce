"""Persistence for the alert engine (``services.alert_engine``).

Timestamps are timezone-aware UTC. JSON documents are stored as text (repo convention).
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base

_TS = DateTime(timezone=True)


class AlertMonitorModel(Base):
    """One instrument a user actively monitors. Not a position and not an allocation."""

    __tablename__ = "alert_monitors"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(60), nullable=False)
    ins_id: Mapped[str | None] = mapped_column(String(40), index=True)
    isin: Mapped[str | None] = mapped_column(String(20))
    name: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40), nullable=False, server_default="unknown")
    supported: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active", index=True)
    monitoring_state: Mapped[str] = mapped_column(String(30), nullable=False, server_default="pending")
    identity: Mapped[str | None] = mapped_column(Text)
    last_analysis_id: Mapped[str | None] = mapped_column(String(50))
    last_analyzed_at: Mapped[datetime | None] = mapped_column(_TS)
    last_input_hash: Mapped[str | None] = mapped_column(String(64))
    last_error: Mapped[str | None] = mapped_column(Text)
    removed_at: Mapped[datetime | None] = mapped_column(_TS)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(_TS)

    __table_args__ = (
        # one active monitor per (user, symbol): duplicates are impossible, not just unlikely
        sa.Index("uq_alert_monitors_active", "user_id", "symbol", unique=True,
                 postgresql_where=sa.text("status = 'active'")),
    )


class AlertAnalysisModel(Base):
    """Immutable analysis + recommendation record (the auditable history)."""

    __tablename__ = "alert_analyses"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    monitor_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), index=True)
    valid_until: Mapped[datetime | None] = mapped_column(_TS)
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    subject: Mapped[str] = mapped_column(String(30), nullable=False, server_default="new_position")
    regime: Mapped[str | None] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(20), nullable=False, server_default="paper")
    engine_version: Mapped[str | None] = mapped_column(String(40))
    rules_version: Mapped[str | None] = mapped_column(String(40))
    settings_version: Mapped[int | None] = mapped_column(Integer)
    input_hash: Mapped[str | None] = mapped_column(String(64))
    supersedes_id: Mapped[str | None] = mapped_column(String(50))
    report: Mapped[str] = mapped_column(Text, nullable=False)


class AlertNotificationModel(Base):
    """In-platform notification + Telegram delivery state.

    ``telegram_state``: not_requested | queued | accepted | failed | suppressed_stale |
    suppressed_quiet | not_configured. "accepted" means the provider accepted the message —
    it is not proof of delivery or of the user having seen it; ``acknowledged_at`` is.
    """

    __tablename__ = "alert_notifications"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    monitor_id: Mapped[str | None] = mapped_column(String(50), index=True)
    analysis_id: Mapped[str | None] = mapped_column(String(50))
    symbol: Mapped[str | None] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    revises_id: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now(), index=True)
    valid_until: Mapped[datetime | None] = mapped_column(_TS)
    telegram_state: Mapped[str] = mapped_column(String(20), nullable=False, server_default="not_requested")
    telegram_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    telegram_error: Mapped[str | None] = mapped_column(Text)
    telegram_at: Mapped[datetime | None] = mapped_column(_TS)
    acknowledged_at: Mapped[datetime | None] = mapped_column(_TS)

    __table_args__ = (sa.UniqueConstraint("user_id", "dedupe_key", name="uq_alert_notifications_dedupe"),)


class AlertEngineSettingsModel(Base):
    """Append-only settings versions; the highest version per user is current."""

    __tablename__ = "alert_engine_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    settings: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(100))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now())

    __table_args__ = (sa.UniqueConstraint("user_id", "version", name="uq_alert_engine_settings_version"),)


class AlertLedgerEntryModel(Base):
    """User-confirmed trades and cash flows. ``book`` keeps paper and actual apart."""

    __tablename__ = "alert_ledger_entries"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False)
    book: Mapped[str] = mapped_column(String(10), nullable=False, server_default="actual")
    symbol: Mapped[str | None] = mapped_column(String(60), index=True)
    quantity: Mapped[float | None] = mapped_column(Float)
    price_rial: Mapped[float | None] = mapped_column(Float)
    fees_toman: Mapped[float | None] = mapped_column(Float, server_default="0")
    amount_toman: Mapped[float | None] = mapped_column(Float)
    executed_at: Mapped[datetime] = mapped_column(_TS, nullable=False)
    analysis_id: Mapped[str | None] = mapped_column(String(50))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(_TS, server_default=func.now())


class AlertEquityStateModel(Base):
    """Cash-flow-adjusted equity high-water mark per (user, book)."""

    __tablename__ = "alert_equity_state"

    user_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    book: Mapped[str] = mapped_column(String(10), primary_key=True)
    hwm_toman: Mapped[float] = mapped_column(Float, nullable=False)
    hwm_flows_toman: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    last_equity_toman: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime | None] = mapped_column(_TS)
