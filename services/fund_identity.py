"""🆔 Fund Canonical Identity & Alias Resolution (A2 / A8 سوپر-پرامپت).

مسئله: نماد صندوق ممکن است تغییر کند، دو نماد به یک صندوق اشاره کنند، یا
یک نماد میان دو شناسه تکرار شود. تطبیق نباید بر «نماد» بنا شود.

اولویت کلید کانونی (طبق الزام A2):
    ۱) ISIN   ۲) National ID   ۳) Symbol + FundType + Manager

این ماژول کاملاً Side-Effect-Free برای بخش «تصمیم‌گیری» است (قابل تست بدون
DB) و فقط توابع ``resolve_*`` / ``register_alias`` به دیتابیس دست می‌زنند.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger

logger = get_logger(__name__)

# ── نرمال‌سازی نماد (سازگار با brsapi.services.sync_service._normalize_persian) ──


def normalize_symbol(value: Any) -> str:
    """نرمال‌سازی نماد: ی/ک عربی، نیم‌فاصله، فاصله‌های تکراری، ارقام فارسی."""
    if value is None:
        return ""
    s = str(value).strip()
    s = s.replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")
    s = s.replace("\u200c", "").replace("\u200e", "").replace("\u200f", "")
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_isin(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip().upper().replace(" ", "")
    return s or None


def derive_fund_id(
    *,
    symbol: str,
    market: str = "tse",
    existing_fund_id: str | None = None,
) -> str:
    """``fund_id`` کانونی و پایدار ماژول.

    اگر صندوق قبلاً شناسایی شده باشد، همان ``existing_fund_id`` حفظ می‌شود
    (حتی اگر نماد تغییر کرده باشد)؛ در غیر این صورت ``<market>:<symbol>``.
    """
    if existing_fund_id:
        return existing_fund_id
    return f"{(market or 'tse').lower()}:{normalize_symbol(symbol)}"


def identity_fingerprint(
    isin: str | None, national_id: str | None, symbol: str | None
) -> str:
    """اثر انگشت پایدار هویت برای Idempotency و ممیزی."""
    basis = "|".join(
        [
            normalize_isin(isin) or "",
            (national_id or "").strip(),
            normalize_symbol(symbol).lower(),
        ]
    )
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:40]


# ── تصمیم‌یار تطبیق (Pure / Testable) ────────────────────────────────────────


@dataclass
class IdentityDecision:
    """نتیجه تطبیق یک رکورد Universe با هویت موجود."""

    action: str                          # same | new | symbol_added | symbol_changed | conflict
    fund_id: str | None = None
    existing_symbol: str | None = None
    matched_by: str | None = None        # isin | national_id | alias | symbol
    conflict_reason: str | None = None
    aliases_to_add: list[str] = field(default_factory=list)

    @property
    def is_conflict(self) -> bool:
        return self.action == "conflict"


def decide_identity(
    *,
    symbol: str,
    isin: str | None,
    national_id: str | None,
    matches: dict[str, str | None],
) -> IdentityDecision:
    """تصمیم تطبیق بر اساس هویت‌های یافت‌شده در DB.

    ``matches``: دیکشنری نگاشت‌شده‌های موجود:
        - ``by_isin``        : fund_id دارندهٔ همین ISIN
        - ``by_national_id`` : fund_id دارندهٔ همین شناسه ملی
        - ``by_alias``       : fund_id که این نماد در Aliasهایش است
        - ``by_symbol``      : fund_id که خودِ نماد فعلی صندوقش است
        - ``symbol_owner``   : fund_id دیگری که *همین نماد* را در funds دارد
    """
    sym = normalize_symbol(symbol)
    fund_ids = {
        k: v
        for k, v in matches.items()
        if v and k in ("by_isin", "by_national_id", "by_alias", "by_symbol")
    }
    distinct = set(fund_ids.values())

    # تداخل: یک ISIN/شناسه به دو صندوق مختلف اشاره می‌کند → Quarantine
    if len(distinct) > 1:
        return IdentityDecision(
            action="conflict",
            fund_id=None,
            conflict_reason="هویت متناقض: " + "، ".join(f"{k}={v}" for k, v in fund_ids.items()),
        )

    owner = matches.get("symbol_owner")
    if owner and distinct and owner not in distinct:
        # نماد به صندوق دیگری تعلق دارد که هویتش متفاوت است → تغییر نماد یا تداخل
        return IdentityDecision(
            action="conflict",
            fund_id=None,
            existing_symbol=sym,
            conflict_reason=f"نماد {sym} قبلاً برای {owner} ثبت شده و با هویت {sorted(distinct)} هم‌خوان نیست",
        )

    if distinct:
        fid = sorted(distinct)[0]
        matched_by = sorted(
            k for k in ("by_isin", "by_national_id", "by_alias", "by_symbol") if fund_ids.get(k) == fid
        )[0]
        if matched_by in ("by_isin", "by_national_id") and owner is None and matches.get("by_alias") != fid:
            # هویت کانونی قوی‌تر از نماد است؛ نماد جدید باید Alias شود
            return IdentityDecision(
                action="symbol_changed",
                fund_id=fid,
                matched_by=matched_by,
                aliases_to_add=[sym],
            )
        return IdentityDecision(action="same", fund_id=fid, matched_by=matched_by)

    if owner:
        return IdentityDecision(action="new", fund_id=None, conflict_reason=None)

    return IdentityDecision(action="new", fund_id=None)


# ── لایه دیتابیس ─────────────────────────────────────────────────────────────


async def resolve_matches(
    session: AsyncSession,
    *,
    symbol: str,
    isin: str | None,
    national_id: str | None,
) -> dict[str, str | None]:
    """جست‌وجوی هویت‌های موجود در DB (بدون Side-Effect)."""
    sym = normalize_symbol(symbol)
    iso = normalize_isin(isin)
    out: dict[str, str | None] = {
        "by_isin": None,
        "by_national_id": None,
        "by_alias": None,
        "by_symbol": None,
        "symbol_owner": None,
    }
    if iso:
        row = (
            await session.execute(
                text("SELECT id FROM funds WHERE isin = :isin LIMIT 1"), {"isin": iso}
            )
        ).first()
        out["by_isin"] = row[0] if row else None
    if national_id:
        row = (
            await session.execute(
                text("SELECT id FROM funds WHERE national_id = :nid LIMIT 1"),
                {"nid": str(national_id).strip()},
            )
        ).first()
        out["by_national_id"] = row[0] if row else None
    row = (
        await session.execute(
            text(
                """
                SELECT fund_id FROM fund_symbol_aliases
                WHERE symbol = :sym AND is_active = TRUE
                ORDER BY last_seen_at DESC NULLS LAST
                LIMIT 1
                """
            ),
            {"sym": sym},
        )
    ).first()
    out["by_alias"] = row[0] if row else None
    row = (
        await session.execute(
            text("SELECT id FROM funds WHERE symbol = :sym LIMIT 1"), {"sym": sym}
        )
    ).first()
    out["by_symbol"] = row[0] if row else None
    out["symbol_owner"] = out["by_symbol"]
    return out


async def register_alias(
    session: AsyncSession,
    *,
    fund_id: str,
    symbol: str,
    isin: str | None = None,
    national_id: str | None = None,
    source: str = "discovery",
    active: bool = True,
) -> None:
    """ثبت/به‌روزرسانی Alias — Idempotent."""
    sym = normalize_symbol(symbol)
    if not sym or not fund_id:
        return
    now = datetime.utcnow()
    await session.execute(
        text(
            """
            INSERT INTO fund_symbol_aliases
                (fund_id, symbol, isin, national_id, source, is_active,
                 first_seen_at, last_seen_at)
            VALUES (:fid, :sym, :isin, :nid, :src, :active, :now, :now)
            ON CONFLICT (fund_id, symbol) DO UPDATE SET
                isin = COALESCE(EXCLUDED.isin, fund_symbol_aliases.isin),
                national_id = COALESCE(EXCLUDED.national_id, fund_symbol_aliases.national_id),
                source = EXCLUDED.source,
                is_active = EXCLUDED.is_active,
                last_seen_at = EXCLUDED.last_seen_at
            """
        ),
        {
            "fid": fund_id,
            "sym": sym,
            "isin": normalize_isin(isin),
            "nid": (str(national_id).strip() if national_id else None),
            "src": source,
            "active": active,
            "now": now,
        },
    )


async def canonical_fund_id_for_symbol(
    session: AsyncSession, symbol: str
) -> str | None:
    """هر نماد (فعلی یا قدیمی) → ``fund_id`` کانونی؛ در نبود رکورد None."""
    sym = normalize_symbol(symbol)
    if not sym:
        return None
    row = (
        await session.execute(
            text(
                """
                SELECT fund_id FROM fund_symbol_aliases WHERE symbol = :sym
                UNION ALL
                SELECT id FROM funds WHERE symbol = :sym
                LIMIT 1
                """
            ),
            {"sym": sym},
        )
    ).first()
    return row[0] if row else None


def safe_symbol(symbol: str) -> str:
    """نماد امن برای فایل/کلید — فقط برای لاگ."""
    return re.sub(r"[^\w\u0600-\u06FF\-]+", "_", normalize_symbol(symbol))[:60]
