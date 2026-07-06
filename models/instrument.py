"""SQLAlchemy ORM model for trading instruments (stocks, ETFs, bonds, etc.)."""

import json
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class UnicodeJSON(JSON):
    """``JSON`` column variant that preserves non-ASCII text on write.
    """

    cache_ok = True

    def bind_processor(self, dialect):
        string_process = self._str_impl.bind_processor(dialect)
        json_serializer = lambda obj: json.dumps(obj, ensure_ascii=False)
        return self._make_bind_processor(string_process, json_serializer)

    def process_result_value(self, value: Any, dialect: Any) -> Any:  # type: ignore[override]
        if value is None or value == "":
            return None
        return super().process_result_value(value, dialect)


class InstrumentModel(TimestampMixin, Base):
    __tablename__ = "instruments"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    isin: Mapped[str | None] = mapped_column(String(50), unique=True)
    market_type: Mapped[str | None] = mapped_column(String(20), index=True)
    asset_class: Mapped[str | None] = mapped_column(String(20), index=True)
    status: Mapped[str | None] = mapped_column(String(20), server_default="active", index=True)
    sector_code: Mapped[str | None] = mapped_column(String(20), index=True)
    group_code: Mapped[str | None] = mapped_column(String(20), index=True)
    sub_group_code: Mapped[str | None] = mapped_column(String(20))
    tick_size: Mapped[float | None] = mapped_column(Float, server_default="1.0")
    lot_size: Mapped[int | None] = mapped_column(Integer, server_default="1")
    par_value: Mapped[int | None] = mapped_column(Integer, server_default="1000")
    eps: Mapped[float | None] = mapped_column(Float, server_default="0")
    shares_count: Mapped[int | None] = mapped_column(BigInteger, server_default="0")
    base_volume: Mapped[int | None] = mapped_column(BigInteger, server_default="0")
    market_id: Mapped[str | None] = mapped_column(String(50))
    exchange_code: Mapped[str | None] = mapped_column(String(20))
    board_code: Mapped[str | None] = mapped_column(String(20))
    data_source: Mapped[str | None] = mapped_column(String(20), server_default="tsetmc")
    tags: Mapped[list[str] | None] = mapped_column(UnicodeJSON, nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(UnicodeJSON, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
