from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    # Both defaults come from the DB clock (``now()``) so Python-side inserts
    # and server-side defaults are guaranteed consistent — no naive/aware or
    # UTC/local mismatch depending on who writes the row.  Column stays naive
    # ``timestamp`` to match the existing migration history.
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        server_default=func.now(),
    )
