"""Approval Gateway MVP — Phase 2-5.

Proposal lifecycle: pending -> approved/rejected/expired
Each decision is logged to an append-only audit table.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class ProposalModel(TimestampMixin, Base):
    """A trading proposal awaiting approval."""

    __tablename__ = "proposals"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    legs: Mapped[str | None] = mapped_column(Text)  # JSON: legs of the strategy
    price: Mapped[float | None] = mapped_column(Float)
    gross_cost: Mapped[float | None] = mapped_column(Float)
    net_cost: Mapped[float | None] = mapped_column(Float)
    max_loss: Mapped[float | None] = mapped_column(Float)
    margin: Mapped[float | None] = mapped_column(Float)
    var_95: Mapped[float | None] = mapped_column(Float)
    scenario_pnl: Mapped[str | None] = mapped_column(Text)  # JSON: 5-point pnl
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    ttl_seconds: Mapped[int | None] = mapped_column(Integer, default=3600)
    approved_by: Mapped[str | None] = mapped_column(String(50))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    reject_reason: Mapped[str | None] = mapped_column(Text)
    broker_order_id: Mapped[str | None] = mapped_column(String(50))
    calc_version: Mapped[str | None] = mapped_column(String(20), default="v1")


class ProposalAuditModel(TimestampMixin, Base):
    """Append-only audit log for every proposal decision."""

    __tablename__ = "proposal_audit"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    proposal_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # approve/reject/expire
    who: Mapped[str] = mapped_column(String(50), nullable=False)
    why: Mapped[str | None] = mapped_column(Text)
    calc_version: Mapped[str | None] = mapped_column(String(20))
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
