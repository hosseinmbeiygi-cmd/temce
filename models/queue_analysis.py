"""SQLAlchemy model for Queue Analysis results.

Each row stores the output of a queue analysis run for a single symbol,
including all 5 queue features, adjusted scores, and the final decision.

Table: ``queue_analysis_results``
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class QueueAnalysisResult(TimestampMixin, Base):
    """📊 نتایج تحلیل صف برای یک نماد

    Each row stores the complete output of QueueAnalysisService.analyze_symbol()
    for one symbol at one point in time, enabling historical query, audit, and
    comparison across runs.

    Columns are divided into 5 groups:
      1. Identity — who, what, when
      2. 5 Queue Features — the core output
      3. Metadata — price, limits, volumes
      4. Adjusted Scores — liquidity, technical, orderflow, penalty
      5. Decision — hard rules override
    """

    __tablename__ = "queue_analysis_results"

    # ── Identity ──────────────────────────────────────────────────

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True,
                                         comment="نماد بورسی (مثلاً فولاد)")
    run_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True,
                                         comment="شناسه اجرا (مثلاً auto-20260727-153000)")
    market_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="bours",
                                              comment="نوع بازار: bours / farabours / base_market")

    # ── 5 Queue Features (هسته اصلی) ──────────────────────────────

    queue_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True,
                                               comment="وضعیت صف: BUY_QUEUE / SELL_QUEUE / NONE")
    queue_volume_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0,
                                                       comment="نسبت حجم صف به کل سفارشات (0-1)")
    queue_days_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                    comment="تعداد روزهای متوالی در صف (امروز + تاریخچه)")
    queue_type_change: Mapped[str] = mapped_column(String(20), nullable=False, default="NO_CHANGE",
                                                    comment="نوع تغییر صف: NEW_BUY_QUEUE / NEW_SELL_QUEUE / QUEUE_BROKEN / NO_CHANGE")
    distance_to_limit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0,
                                                      comment="فاصله تا سقف/کف دامنه (درصد)")

    # ── Metadata ──────────────────────────────────────────────────

    last_price: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                      comment="آخرین قیمت معامله‌شده")
    limit_up: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                    comment="سقف مجاز روزانه (tmax)")
    limit_down: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                      comment="کف مجاز روزانه (tmin)")
    queue_buy_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True,
                                                          comment="حجم سفارشات خرید باقی‌مانده در صف")
    queue_sell_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True,
                                                           comment="حجم سفارشات فروش باقی‌مانده در صف")

    # ── Adjusted Scores ──────────────────────────────────────────

    adjusted_liquidity: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                              comment="S_L تعدیل‌شده (نقدشوندگی)")
    adjusted_technical: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                              comment="S_T تعدیل‌شده (تکنیکال)")
    adjusted_orderflow: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                              comment="S_O تعدیل‌شده (جریان پول)")
    adjusted_penalty: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                           comment="Penalty تعدیل‌شده (جریمه)")
    liquidity_delta: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                          comment="تغییر S_L نسبت به پایه")
    technical_delta: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                          comment="تغییر S_T نسبت به پایه")
    orderflow_delta: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                          comment="تغییر S_O نسبت به پایه")
    penalty_delta: Mapped[float | None] = mapped_column(Float, nullable=True,
                                                        comment="تغییر Penalty نسبت به پایه")

    # ── Decision ──────────────────────────────────────────────────

    final_decision: Mapped[str | None] = mapped_column(String(20), nullable=True,
                                                        comment="تصمیم نهایی: BUY / WATCHLIST / HOLD / REDUCE / REJECT / NEUTRAL")
    overridden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                              comment="آیا Hard Rule فعال شده است؟")
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True,
                                                        comment="دلیل override در صورت فعال بودن")

    # ── Interpretation (تفسیر انسانی) ─────────────────────────────

    interpretation: Mapped[dict | None] = mapped_column(JSONB, nullable=True,
                                                         comment="تفسیر انسانی وضعیت صف (status_fa, volume_fa, ...)")

    # ── Timing ────────────────────────────────────────────────────

    analyzed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(),
                                                   comment="زمان انجام تحلیل")
    # created_at is inherited from TimestampMixin

    def __repr__(self) -> str:
        return (
            f"<QueueAnalysisResult {self.symbol}: {self.queue_status} "
            f"(ratio={self.queue_volume_ratio:.2f}, streak={self.queue_days_streak})>"
        )
