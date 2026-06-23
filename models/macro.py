from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class MacroIndicatorModel(TimestampMixin, Base):
    __tablename__ = "macro_indicators"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    indicator: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String(50), server_default="iran", index=True)
    value: Mapped[float | None] = mapped_column(Float)
    previous_value: Mapped[float | None] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)
    date: Mapped[str | None] = mapped_column(String(20), index=True)
    source: Mapped[str | None] = mapped_column(String(100))
    unit: Mapped[str | None] = mapped_column(String(50))
    frequency: Mapped[str | None] = mapped_column(String(20), server_default="monthly")
    data_source: Mapped[str | None] = mapped_column(String(20), server_default="rss")
