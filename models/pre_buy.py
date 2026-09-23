"""📝 Persistence for the pre-buy decision sheet (برگهٔ تصمیم پیش از خرید).

Two tables, deliberately split by mutability:

``pre_buy_sheets`` is the working draft — one open draft per user per symbol, rewritten
on every keystroke. ``pre_buy_reviews`` is append-only: each submission freezes the
answers, the evidence that was visible at the time, the verdict the engine produced and
an ``input_hash`` over all three, so a sheet defended a year later is exactly the sheet
that was signed («اگر امروز تحلیل را پنهان کنم و یک سال بعد ببینم»).

Nothing here recomputes judgement — the verdict column is a cache of
:func:`core.question_bank.engine.evaluate`, and is always derived server-side.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin

#: Draft = being filled. Submitted = frozen into a review row. Abandoned = user closed it
#: without a decision, kept so the gap shows up in the review history.
SHEET_STATUSES = ("DRAFT", "SUBMITTED", "ABANDONED")


class PreBuySheet(TimestampMixin, Base):
    """یک برگهٔ در حال تکمیل برای یک نماد."""

    __tablename__ = "pre_buy_sheets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    #: Broker symbol as typed by the user (Persian or Latin); no instruments FK because a
    #: sheet may be opened for a symbol that is not in the local table yet.
    symbol: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    instrument_name: Mapped[str | None] = mapped_column(String(150), comment="نام شرکت از داده زنده")
    #: Which question bank this sheet is judged against — see ``core.question_bank.registry``.
    #: Defaults to 'equity' so sheets written before the instrument axis stay valid.
    instrument_type: Mapped[str] = mapped_column(
        String(24), nullable=False, default="equity", server_default=sa.text("'equity'"), index=True,
        comment="equity | etf | fund | leveraged_fund | fixed_income | commodity_fund | "
                "commodity_certificate | future | option",
    )
    #: How the type was decided: the table and column that matched, or «انتخاب کاربر».
    #: Kept on the row because a silently wrong classification is worse than no data.
    instrument_basis: Mapped[str | None] = mapped_column(String(240))
    bank_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=sa.text("'DRAFT'"),
        comment="DRAFT | SUBMITTED | ABANDONED",
    )

    #: {question_code: {"value": str|null, "numbers": {...}, "note": str|null, "answered_at": iso}}
    answers: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    #: {evidence_key: {"value", "unit", "source", "as_of", "status", "note"}} — the last
    #: snapshot the user actually saw, kept so the verdict can be audited later.
    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    #: Frozen evaluation: verdict, stage states, derived maths, blocking reasons.
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    verdict: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=sa.text("'not_started'"),
        comment="خروجی موتور: vetoed | hold | blocked_unknown | in_progress | cleared | not_started",
    )
    completion_pct: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("0"))
    #: sha256 over (bank_version, answers, evidence) — the auditability anchor.
    input_hash: Mapped[str | None] = mapped_column(String(64))

    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    #: Stage 9 asks for a review date; it is stored so a sweep can flag stale sheets.
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime)


class PreBuyReview(TimestampMixin, Base):
    """نسخهٔ ثبت‌شده و غیرقابل‌تغییر یک برگهٔ تصمیم."""

    __tablename__ = "pre_buy_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sheet_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pre_buy_sheets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    #: Frozen with the submission: the same answer codes mean different stages under a
    #: different bank, so a review is only re-computable with the type it was judged as.
    instrument_type: Mapped[str] = mapped_column(
        String(24), nullable=False, default="equity", server_default=sa.text("'equity'")
    )
    bank_version: Mapped[str] = mapped_column(String(20), nullable=False)
    answers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    completion_pct: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("0"))
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Free-text sign-off written at submission — the user's own two-sentence reason.
    statement: Mapped[str | None] = mapped_column(Text)


__all__ = ["SHEET_STATUSES", "PreBuyReview", "PreBuySheet"]
