"""SQLAlchemy ORM model for investment funds (صندوق‌های سرمایه‌گذاری).

Each row stores a daily snapshot of a fund's market data, matching the
Fund interface used by the frontend analysis engine (fund-analysis.ts).

Table: ``funds``
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class FundModel(TimestampMixin, Base):
    """📊 داده‌های روزانه صندوق‌های سرمایه‌گذاری

    Each row represents one fund at one point in time (daily snapshot),
    with all fields needed for the 6-dimension analysis engine.
    """

    __tablename__ = "funds"

    # ── Identity ──────────────────────────────────────────────────

    id: Mapped[str] = mapped_column(String(50), primary_key=True,
                                   comment="شناسه یکتای داخلی (مثلاً fund_abc123)")
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True,
                                        comment="نماد صندوق (مثلاً آگاس)")
    name: Mapped[str] = mapped_column(String(200), nullable=False,
                                      comment="نام کامل صندوق")
    isin: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True,
                                              comment="کد ISIN (شناسه بین‌المللی)")
    fund_type: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True,
                                                   comment="نوع صندوق: سهامی / درآمد ثابت / اهرمی / مختلط / بخشی / اختصاصی")

    # ── Pricing ───────────────────────────────────────────────────

    nav: Mapped[float | None] = mapped_column(Float, nullable=True,
                                              comment="ارزش خالص دارایی‌ها (NAV)")
    nav_change: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                     comment="تغییر NAV نسبت به روز قبل")
    nav_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                         comment="درصد تغییر NAV")
    price_last: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                     comment="آخرین قیمت معامله")
    price_close: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                      comment="قیمت پایانی")
    price_yesterday: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                          comment="قیمت پایانی روز قبل")
    price_max: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                    comment="بیشترین قیمت روز")
    price_min: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                    comment="کمترین قیمت روز")

    # ── Trading ───────────────────────────────────────────────────

    trade_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True,
                                                     comment="حجم معاملات (تعداد)")
    trade_value: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                      comment="ارزش معاملات (تومان)")
    trade_count: Mapped[int | None] = mapped_column(Integer, nullable=True,
                                                    comment="تعداد معاملات")
    shares_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True,
                                                     comment="تعداد واحدهای صندوق")
    base_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True,
                                                    comment="حجم پایه")
    market_value: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                       comment="ارزش بازار (تومان)")

    # ── Real/Legal ────────────────────────────────────────────────

    buy_real_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True,
                                                        comment="حجم خرید حقیقی")
    buy_legal_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True,
                                                         comment="حجم خرید حقوقی")
    sell_real_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True,
                                                         comment="حجم فروش حقیقی")
    sell_legal_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True,
                                                          comment="حجم فروش حقوقی")

    # ── Metadata ──────────────────────────────────────────────────

    time: Mapped[str | None] = mapped_column(String(10), nullable=True,
                                             comment="زمان ثبت (HH:MM:SS)")
    data_source: Mapped[str | None] = mapped_column(String(30), nullable=True,
                                                    comment="منبع داده (tsetmc, brsapi, fundbase)")
    snapshot_date: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True,
                                                      comment="تاریخ اسنپ‌شات (YYYY-MM-DD)")
    # NOTE: stored as a JSON **string** in the TEXT column (never a raw dict).
    # The repository serializes/deserializes it; keep the annotation honest
    # so SQLAlchemy does not try to bind a dict to a Text column.
    extra: Mapped[str | None] = mapped_column(Text, nullable=True,
                                              comment="داده‌های اضافی (JSON string)")

    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True,
                                                     comment="زمان آخرین بروزرسانی")

    def __repr__(self) -> str:
        return (
            f"<FundModel {self.symbol}: NAV={self.nav}, "
            f"change={self.nav_change_pct}%, "
            f"volume={self.trade_volume}>"
        )
