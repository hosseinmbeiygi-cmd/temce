"""🧾 Fund Ledger — دفتر مالی دوطرفه + ثبت واحدها + Outbox (فاز ۲ و ۶).

قواعد:
  - هر سند باید متوازن باشد (هم در پایتون و هم با Constraint Trigger در DB).
  - ثبت دوباره با ``idempotency_key`` ردیف تکراری نمی‌سازد.
  - رویداد Outbox در همان تراکنش سند نوشته می‌شود (at-least-once).
  - اصلاح فقط با «سند برگشتی» انجام می‌شود، نه حذف/ویرایش.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from services.fund_read_through import StaleResult

logger = get_logger(__name__)

LEDGER_ENGINE_VERSION = "ledger-1.0.0"

UNIT_MOVEMENT_ACCOUNTS: dict[str, tuple[str, str]] = {
    # movement_type → (account_debit, account_credit)
    "ISSUE": ("CASH", "UNITS_LIABILITY"),
    "REDEEM": ("UNITS_LIABILITY", "CASH"),
    "DISTRIBUTION": ("RETAINED_EARNINGS", "DISTRIBUTION_PAYABLE"),
    "TRANSFER": ("UNITS_LIABILITY", "UNITS_LIABILITY"),
    "PLEDGE": ("UNITS_LIABILITY", "UNITS_LIABILITY"),
    "RELEASE": ("UNITS_LIABILITY", "UNITS_LIABILITY"),
}

# ── Pure helpers (قابل تست بدون DB) ─────────────────────────────────────────


def validate_balanced(lines: list[dict[str, Any]]) -> tuple[float, float]:
    """کنترل توازن سند در پایتون (دفاع دوم پس از تریگر DB)."""
    if not lines:
        raise ValueError("سند بدون خط معتبر نیست")
    debit = round(sum(float(line.get("debit_amount") or 0) for line in lines), 2)
    credit = round(sum(float(line.get("credit_amount") or 0) for line in lines), 2)
    if debit != credit:
        raise ValueError(f"سند متوازن نیست: بدهکار={debit} بستانکار={credit}")
    for line in lines:
        d = float(line.get("debit_amount") or 0)
        c = float(line.get("credit_amount") or 0)
        if d < 0 or c < 0 or (d > 0 and c > 0):
            raise ValueError("خط سند باید فقط یک طرف (بدهکار یا بستانکار) داشته باشد")
    return debit, credit


def build_unit_movement_lines(
    movement_type: str, amount: float, unit_delta: float = 0.0
) -> list[dict[str, Any]]:
    """ساخت خطوط سند صدور/ابطال/توزیع بر اساس مبلغ ریالی."""
    accounts = UNIT_MOVEMENT_ACCOUNTS.get(movement_type)
    if accounts is None:
        raise ValueError(f"نوع حرکت واحد نامعتبر: {movement_type}")
    if amount < 0:
        raise ValueError("مبلغ حرکت واحد نمی‌تواند منفی باشد")
    debit_account, credit_account = accounts
    if debit_account == credit_account:
        # انتقال/توثیق: بدون اثر ریالی، فقط مقدار
        return [
            {
                "account_code": debit_account,
                "debit_amount": 0,
                "credit_amount": 0,
                "quantity_delta": unit_delta,
                "memo": movement_type,
            }
        ]
    return [
        {
            "account_code": debit_account,
            "debit_amount": amount,
            "credit_amount": 0,
            "quantity_delta": unit_delta,
            "memo": movement_type,
        },
        {
            "account_code": credit_account,
            "debit_amount": 0,
            "credit_amount": amount,
            "quantity_delta": -unit_delta if debit_account == "UNITS_LIABILITY" else unit_delta,
            "memo": movement_type,
        },
    ]


def build_fee_accrual_lines(amount: float) -> list[dict[str, Any]]:
    """سند تعهد کارمزد: هزینه کارمزد / کارمزد پرداختنی."""
    if amount < 0:
        raise ValueError("مبلغ کارمزد نمی‌تواند منفی باشد")
    return [
        {"account_code": "FEE_EXPENSE", "debit_amount": amount, "credit_amount": 0},
        {"account_code": "FEE_PAYABLE", "debit_amount": 0, "credit_amount": amount},
    ]


def trial_balance_from_rows(rows: list[Any]) -> dict[str, Any]:
    """محاسبه تراز از ردیف‌های خام (account_code, name, type, side, debit, credit)."""
    accounts: list[dict[str, Any]] = []
    total_debit = 0.0
    total_credit = 0.0
    for row in rows:
        code, name, acc_type, side = row[0], row[1], row[2], row[3]
        debit = float(row[4] or 0)
        credit = float(row[5] or 0)
        balance = (debit - credit) if side == "DEBIT" else (credit - debit)
        accounts.append(
            {
                "account_code": code,
                "account_name": name,
                "account_type": acc_type,
                "normal_side": side,
                "debit": debit,
                "credit": credit,
                "balance": balance,
            }
        )
        total_debit += debit
        total_credit += credit
    return {
        "accounts": accounts,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "balanced": round(total_debit, 2) == round(total_credit, 2),
    }


# ── Service ─────────────────────────────────────────────────────────────────


class FundLedgerService:
    """ثبت اسناد دوطرفه، حرکت واحدها و تراز — با Outbox هم‌تراکنش."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def post_entry(
        self,
        fund_id: str,
        event_type: str,
        lines: list[dict[str, Any]],
        effective_at: datetime | None = None,
        idempotency_key: str | None = None,
        source_system: str | None = "internal",
        source_ref_id: str | None = None,
        memo: str | None = None,
        outbox_event: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """ثبت سند متوازن (idempotent) + Outbox در همان تراکنش."""
        validate_balanced(lines)
        effective_at = effective_at or datetime.utcnow()
        idem = idempotency_key or f"{fund_id}:{event_type}:{source_ref_id or uuid.uuid4().hex}"

        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO journal_entries
                        (fund_id, event_type, status, effective_at, source_system,
                         source_ref_id, idempotency_key, memo)
                    VALUES (:fid, :et, 'POSTED', :ea, :src, :sref, :idem, :memo)
                    ON CONFLICT (idempotency_key) DO NOTHING
                    RETURNING id
                    """
                ),
                {
                    "fid": fund_id,
                    "et": event_type,
                    "ea": effective_at,
                    "src": source_system,
                    "sref": source_ref_id,
                    "idem": idem,
                    "memo": memo,
                },
            )
        ).first()

        if row is None:
            existing = (
                await self.session.execute(
                    text("SELECT id FROM journal_entries WHERE idempotency_key = :idem"),
                    {"idem": idem},
                )
            ).first()
            return {
                "entry_id": int(existing[0]) if existing else None,
                "created": False,
                "idempotency_key": idem,
            }

        entry_id = int(row[0])
        for line in lines:
            await self.session.execute(
                text(
                    """
                    INSERT INTO journal_lines
                        (entry_id, fund_id, account_code, instrument_symbol,
                         debit_amount, credit_amount, quantity_delta, memo)
                    VALUES (:eid, :fid, :acc, :sym, :d, :c, :q, :memo)
                    """
                ),
                {
                    "eid": entry_id,
                    "fid": fund_id,
                    "acc": line["account_code"],
                    "sym": line.get("instrument_symbol"),
                    "d": line.get("debit_amount") or 0,
                    "c": line.get("credit_amount") or 0,
                    "q": line.get("quantity_delta") or 0,
                    "memo": line.get("memo") or memo,
                },
            )

        if outbox_event:
            await self._enqueue(
                event_type=outbox_event.get("event_type") or event_type,
                fund_id=fund_id,
                payload=outbox_event.get("payload") or {},
            )

        await self.session.commit()
        return {
            "entry_id": entry_id,
            "created": True,
            "idempotency_key": idem,
            "event_type": event_type,
        }

    async def record_unit_movement(
        self,
        fund_id: str,
        movement_type: str,
        movement_date: date,
        units: float,
        price_per_unit: float | None = None,
        reference: str | None = None,
        nav_type: str | None = None,
    ) -> StaleResult:
        """ثبت حرکت واحد + سند دوطرفه آن (اتمیک و idempotent)."""
        if movement_type not in UNIT_MOVEMENT_ACCOUNTS:
            raise ValueError(f"نوع حرکت واحد نامعتبر: {movement_type}")
        if units <= 0:
            raise ValueError("تعداد واحد باید مثبت باشد")
        amount = float(units) * float(price_per_unit) if price_per_unit else 0.0
        if movement_type in ("ISSUE", "REDEEM") and amount <= 0:
            raise ValueError("برای صدور/ابطال، قیمت هر واحد لازم است")
        ref = reference or f"{movement_type}-{movement_date}-{units}"

        inserted = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_unit_movements
                        (fund_id, movement_date, movement_type, units,
                         price_per_unit, amount, nav_type, reference)
                    VALUES (:fid, :md, :mt, :u, :p, :amt, :nt, :ref)
                    ON CONFLICT (fund_id, movement_date, movement_type, reference) DO NOTHING
                    RETURNING id
                    """
                ),
                {
                    "fid": fund_id,
                    "md": movement_date,
                    "mt": movement_type,
                    "u": units,
                    "p": price_per_unit,
                    "amt": amount,
                    "nt": nav_type,
                    "ref": ref,
                },
            )
        ).first()

        if inserted is None:
            return StaleResult(
                data={"created": False, "reference": ref, "fund_id": fund_id},
                freshness="stale",
                fetched_from="db",
            )

        lines = build_unit_movement_lines(movement_type, amount, units)
        entry = await self.post_entry(
            fund_id=fund_id,
            event_type=f"UNIT_{movement_type}",
            lines=lines,
            effective_at=datetime.combine(movement_date, datetime.min.time()),
            idempotency_key=f"{fund_id}:UNIT_{movement_type}:{ref}",
            source_system="unit_registry",
            source_ref_id=ref,
            memo=f"حرکت واحد {movement_type} — {ref}",
            outbox_event={
                "event_type": f"UNIT_{movement_type}",
                "payload": {
                    "fund_id": fund_id,
                    "units": units,
                    "price_per_unit": price_per_unit,
                    "amount": amount,
                    "movement_date": str(movement_date),
                },
            },
        )
        return StaleResult(
            data={
                "created": True,
                "movement_id": int(inserted[0]),
                "reference": ref,
                "fund_id": fund_id,
                "movement_type": movement_type,
                "units": units,
                "amount": amount,
                "entry_id": entry.get("entry_id"),
            },
            freshness="live",
            fetched_from="db",
        )

    async def reverse_entry(
        self, entry_id: int, memo: str | None = None
    ) -> dict[str, Any]:
        """سند برگشتی — بدون حذف تاریخچه."""
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT fund_id, event_type, idempotency_key FROM journal_entries
                    WHERE id = :eid
                    """
                ),
                {"eid": entry_id},
            )
        ).first()
        if row is None:
            raise LookupError("سند یافت نشد")
        fund_id, event_type, idem = row[0], row[1], row[2]
        line_rows = (
            await self.session.execute(
                text(
                    """
                    SELECT account_code, instrument_symbol, debit_amount, credit_amount,
                           quantity_delta
                    FROM journal_lines WHERE entry_id = :eid
                    """
                ),
                {"eid": entry_id},
            )
        ).fetchall()
        reversed_lines = [
            {
                "account_code": lr[0],
                "instrument_symbol": lr[1],
                "debit_amount": float(lr[3] or 0),
                "credit_amount": float(lr[2] or 0),
                "quantity_delta": -float(lr[4] or 0),
            }
            for lr in line_rows
        ]
        result = await self.post_entry(
            fund_id=fund_id,
            event_type=f"{event_type}_REVERSAL",
            lines=reversed_lines,
            idempotency_key=f"{idem}:reversal",
            source_system="internal",
            source_ref_id=f"reversal:{entry_id}",
            memo=memo or f"برگشت سند {entry_id}",
        )
        await self.session.execute(
            text("UPDATE journal_entries SET status = 'REVERSED' WHERE id = :eid"),
            {"eid": entry_id},
        )
        await self.session.commit()
        return result

    async def list_entries(self, fund_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, event_type, status, effective_at, source_system,
                           source_ref_id, idempotency_key, memo
                    FROM journal_entries
                    WHERE fund_id = :fid
                    ORDER BY effective_at DESC, id DESC
                    LIMIT :lim
                    """
                ),
                {"fid": fund_id, "lim": limit},
            )
        ).fetchall()
        entries = [
            {
                "entry_id": int(r[0]),
                "event_type": r[1],
                "status": r[2],
                "effective_at": str(r[3]) if r[3] else None,
                "source_system": r[4],
                "source_ref_id": r[5],
                "idempotency_key": r[6],
                "memo": r[7],
                "lines": [],
            }
            for r in rows
        ]
        if entries:
            ids = [e["entry_id"] for e in entries]
            line_rows = (
                await self.session.execute(
                    text(
                        """
                        SELECT entry_id, account_code, instrument_symbol,
                               debit_amount, credit_amount, quantity_delta
                        FROM journal_lines WHERE entry_id = ANY(:ids)
                        ORDER BY id
                        """
                    ),
                    {"ids": ids},
                )
            ).fetchall()
            by_entry: dict[int, list[dict[str, Any]]] = {}
            for lr in line_rows:
                by_entry.setdefault(int(lr[0]), []).append(
                    {
                        "account_code": lr[1],
                        "instrument_symbol": lr[2],
                        "debit_amount": float(lr[3] or 0),
                        "credit_amount": float(lr[4] or 0),
                        "quantity_delta": float(lr[5] or 0),
                    }
                )
            for e in entries:
                e["lines"] = by_entry.get(e["entry_id"], [])
        return entries

    async def trial_balance(self, fund_id: str) -> dict[str, Any]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT c.account_code, c.account_name, c.account_type, c.normal_side,
                           COALESCE(SUM(l.debit_amount), 0) AS total_debit,
                           COALESCE(SUM(l.credit_amount), 0) AS total_credit
                    FROM chart_of_accounts c
                    LEFT JOIN journal_lines l
                        ON l.account_code = c.account_code AND l.fund_id = :fid
                    WHERE c.is_active = TRUE
                    GROUP BY c.account_code, c.account_name, c.account_type, c.normal_side
                    ORDER BY c.account_code
                    """
                ),
                {"fid": fund_id},
            )
        ).fetchall()
        return trial_balance_from_rows(list(rows))

    async def list_unit_movements(self, fund_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, movement_date, movement_type, units, price_per_unit,
                           amount, nav_type, reference
                    FROM fund_unit_movements
                    WHERE fund_id = :fid
                    ORDER BY movement_date DESC, id DESC
                    LIMIT :lim
                    """
                ),
                {"fid": fund_id, "lim": limit},
            )
        ).fetchall()
        return [
            {
                "movement_id": int(r[0]),
                "movement_date": str(r[1]),
                "movement_type": r[2],
                "units": r[3],
                "price_per_unit": r[4],
                "amount": r[5],
                "nav_type": r[6],
                "reference": r[7],
            }
            for r in rows
        ]

    async def _enqueue(self, event_type: str, fund_id: str | None, payload: dict[str, Any]) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO fund_nav_outbox (event_type, fund_id, payload_json)
                VALUES (:et, :fid, :payload)
                """
            ),
            {
                "et": event_type,
                "fid": fund_id,
                "payload": json.dumps(payload, ensure_ascii=False, default=str),
            },
        )

    async def pending_outbox(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, event_type, fund_id, payload_json, attempts
                    FROM fund_nav_outbox
                    WHERE status = 'PENDING'
                    ORDER BY id
                    LIMIT :lim
                    """
                ),
                {"lim": limit},
            )
        ).fetchall()
        return [
            {
                "id": int(r[0]),
                "event_type": r[1],
                "fund_id": r[2],
                "payload": json.loads(r[3]) if r[3] else {},
                "attempts": r[4],
            }
            for r in rows
        ]

    async def mark_published(self, outbox_id: int) -> None:
        await self.session.execute(
            text(
                """
                UPDATE fund_nav_outbox
                SET status = 'PUBLISHED', published_at = now(), attempts = attempts + 1
                WHERE id = :oid
                """
            ),
            {"oid": outbox_id},
        )
        await self.session.commit()

    async def mark_failed(self, outbox_id: int, error: str) -> None:
        await self.session.execute(
            text(
                """
                UPDATE fund_nav_outbox
                SET status = CASE WHEN attempts >= 4 THEN 'FAILED' ELSE 'PENDING' END,
                    attempts = attempts + 1,
                    last_error = :err
                WHERE id = :oid
                """
            ),
            {"oid": outbox_id, "err": error[:500]},
        )
        await self.session.commit()


__all__ = [
    "LEDGER_ENGINE_VERSION",
    "UNIT_MOVEMENT_ACCOUNTS",
    "FundLedgerService",
    "build_fee_accrual_lines",
    "build_unit_movement_lines",
    "trial_balance_from_rows",
    "validate_balanced",
]
