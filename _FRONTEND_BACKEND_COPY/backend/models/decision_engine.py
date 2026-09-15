"""SQLAlchemy model for Decision Engine architecture data.

This model stores the complete enterprise architecture blueprint
(layers, features, services, database schema, APIs) as JSONB columns,
allowing flexible storage without requiring 30+ separate tables.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class DecisionArchitecture(TimestampMixin, Base):
    """🏛️ معماری سامانه تصمیم‌یار بورس تهران

    Each row stores a complete snapshot of the architecture blueprint
    at a given version. The data field is a JSONB blob containing:
      - system metadata (name, version, principles, objectives)
      - 12-layer architecture
      - 110 features in 8 blocks
      - 22 services
      - 30+ database tables
      - 31 API endpoints
    """

    __tablename__ = "decision_architectures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True, comment="نسخه معماری (مثلاً Enterprise-Final-1.0)"
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="عنوان نسخه معماری")
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, comment="داده کامل معماری به صورت JSON")
    is_active: Mapped[bool] = mapped_column(default=True, comment="آیا این نسخه فعال است؟")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=func.now())

    def __repr__(self) -> str:
        return f"<DecisionArchitecture v{self.version}: {self.title}>"


class DecisionResult(TimestampMixin, Base):
    """📊 نتایج تصمیم‌گیری برای نمادها

    Stores the actual decision output for each symbol after running
    the 3-stage pipeline (BaseScore → MicroAdjustment → Penalty → FinalDecision).
    """

    __tablename__ = "decision_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="نماد بورسی")
    run_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="شناسه اجرا")
    model_version: Mapped[str] = mapped_column(String(50), nullable=False, comment="نسخه مدل")
    rulebook_version: Mapped[str] = mapped_column(String(50), nullable=False, comment="نسخه Rulebook")

    # Scores
    score_fundamental: Mapped[float | None] = mapped_column(comment="S_F: امتیاز بنیادی (0-100)")
    score_valuation: Mapped[float | None] = mapped_column(comment="S_V: امتیاز ارزش‌گذاری (0-100)")
    score_technical: Mapped[float | None] = mapped_column(comment="S_T: امتیاز تکنیکال (0-100)")
    score_liquidity: Mapped[float | None] = mapped_column(comment="S_L: امتیاز نقدشوندگی (0-100)")
    score_orderflow: Mapped[float | None] = mapped_column(comment="S_O: امتیاز جریان پول (0-100)")
    score_micro: Mapped[float | None] = mapped_column(comment="S_M: امتیاز ریزساختار (0-100)")
    score_macro: Mapped[float | None] = mapped_column(comment="S_K: امتیاز کلان (0-100)")
    score_event: Mapped[float | None] = mapped_column(comment="S_E: امتیاز رویدادی (0-100)")

    # Base score
    base_score: Mapped[float | None] = mapped_column(comment="BaseScore: مجموع وزنی 8 سوبرسکور")
    micro_adjustment: Mapped[float | None] = mapped_column(comment="MicroAdjustment: اصلاح ناشی از ریزمعاملات")
    penalty: Mapped[float | None] = mapped_column(comment="Penalty: ضریب جریمه ریسک (0-0.35)")

    # Final
    final_score: Mapped[float | None] = mapped_column(comment="FinalScore: امتیاز نهایی (0-100)")
    decision: Mapped[str] = mapped_column(
        String(20), comment="تصمیم نهایی: BUY / WATCHLIST / HOLD / REDUCE / REJECT / NEUTRAL"
    )
    confidence: Mapped[float | None] = mapped_column(comment="اطمینان تصمیم (0-1)")
    neg_events_count: Mapped[int | None] = mapped_column(comment="تعداد رویدادهای منفی فعال")

    # Metadata
    details: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="جزئیات کامل (دلایل، reason_codes, report)"
    )
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="زمان ارزیابی")

    def __repr__(self) -> str:
        return f"<DecisionResult {self.symbol}: {self.decision} ({self.final_score})>"
