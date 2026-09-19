"""🛡 Fund Compliance — AML/CFT + انطباق شرعی + حاکمیت + چرخه عمر + CSDI.

دامنه (فازهای ۷، ۸، ۹ و اتصال CSDI):
  - AML: تولید هشدار از حرکت‌های نقدی، گزارش STR با مهلت، فهرست/رسیدگی.
  - Sharia: رجیستری تأیید کمیته فقهی برای ابزار/عملیات.
  - Governance: معاملات با اشخاص وابسته، شکایات.
  - Lifecycle: نسخه‌های امیدنامه، رویدادهای چرخه عمر.
  - CSDI: ورود صورت‌وضعیت واحدها و تطبیق با دفتر (تشخیص مغایرت).

هیچ‌کدام جایگزین سامانه رسمی مرکز نیستند؛ رکورد داخلی + مدارک برای ارائه‌اند.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from services.fund_read_through import StaleResult

logger = get_logger(__name__)

COMPLIANCE_ENGINE_VERSION = "compliance-1.0.0"
DEFAULT_CASH_THRESHOLD = 1_000_000_000.0  # ۱ میلیارد ریال (پارامتریک)
STR_DEADLINE_HOURS = 8

# ── Pure helpers (قابل تست بدون DB) ─────────────────────────────────────────


def assess_movement(
    movement: dict[str, Any], cash_threshold: float = DEFAULT_CASH_THRESHOLD
) -> dict[str, Any] | None:
    """قاعده ساده AML: حرکت نقدی بالای آستانه یا ابطال بزرگ پرتکرار."""
    amount = abs(float(movement.get("amount") or 0))
    movement_type = str(movement.get("movement_type") or "")
    if movement_type in ("ISSUE", "REDEEM") and amount >= cash_threshold:
        return {
            "alert_type": f"LARGE_CASH_{movement_type}",
            "risk_level": "HIGH" if amount >= cash_threshold * 10 else "MEDIUM",
            "subject_ref": movement.get("reference"),
            "amount": amount,
            "evidence": {"movement_type": movement_type, "threshold": cash_threshold},
        }
    return None


def str_due_at(created_at: datetime | None = None) -> datetime:
    """مهلت گزارش مشکوک: پایان همان روز کاری (تقریب +۸ ساعت)."""
    base = created_at or datetime.utcnow()
    return base + timedelta(hours=STR_DEADLINE_HOURS)


def reconcile_units(
    internal_units: int | None, csdi_units: int | None, tolerance: int = 0
) -> dict[str, Any]:
    """تطبیق تعداد واحد داخلی با CSDI؛ خارج از تلورانس = مغایرت."""
    if internal_units is None or csdi_units is None:
        return {"status": "INCOMPLETE", "units_diff": None}
    diff = int(csdi_units) - int(internal_units)
    status = "MATCHED" if abs(diff) <= tolerance else "BREACH"
    return {"status": status, "units_diff": diff}


class FundComplianceService:
    """رجیستری انطباق: AML، شرعی، حاکمیت، چرخه عمر و CSDI."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _enqueue(self, event_type: str, fund_id: str | None, payload: dict[str, Any]) -> None:
        """ثبت Outbox در همان تراکنش رکورد (at-least-once)."""
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

    # ── AML ────────────────────────────────────────────────────────────────

    async def generate_aml_alerts(
        self, fund_id: str, cash_threshold: float = DEFAULT_CASH_THRESHOLD
    ) -> StaleResult:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT movement_date, movement_type, units, amount, reference
                    FROM fund_unit_movements
                    WHERE fund_id = :fid
                    ORDER BY movement_date DESC
                    LIMIT 200
                    """
                ),
                {"fid": fund_id},
            )
        ).fetchall()
        created = 0
        for r in rows:
            movement = {
                "movement_date": str(r[0]),
                "movement_type": r[1],
                "units": r[2],
                "amount": r[3],
                "reference": r[4],
            }
            alert = assess_movement(movement, cash_threshold)
            if alert is None:
                continue
            existing = (
                await self.session.execute(
                    text(
                        """
                        SELECT id FROM fund_aml_alerts
                        WHERE fund_id = :fid AND alert_type = :at AND subject_ref = :ref
                        LIMIT 1
                        """
                    ),
                    {"fid": fund_id, "at": alert["alert_type"], "ref": alert["subject_ref"]},
                )
            ).first()
            if existing:
                continue
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_aml_alerts
                        (fund_id, alert_type, risk_level, subject_ref, amount, evidence_json)
                    VALUES (:fid, :at, :risk, :ref, :amt, :ev)
                    """
                ),
                {
                    "fid": fund_id,
                    "at": alert["alert_type"],
                    "risk": alert["risk_level"],
                    "ref": alert["subject_ref"],
                    "amt": alert["amount"],
                    "ev": json.dumps(alert["evidence"], ensure_ascii=False),
                },
            )
            created += 1
        await self.session.commit()
        return StaleResult(
            data={"fund_id": fund_id, "alerts_created": created, "scanned": len(rows)},
            freshness="live",
            fetched_from="db",
        )

    async def list_aml_alerts(
        self, fund_id: str, status: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"fid": fund_id, "lim": limit}
        clause = ""
        if status:
            clause = "AND status = :status"
            params["status"] = status
        rows = (
            await self.session.execute(
                text(
                    f"""
                    SELECT id, alert_type, risk_level, subject_ref, amount, status, created_at
                    FROM fund_aml_alerts
                    WHERE fund_id = :fid {clause}
                    ORDER BY created_at DESC LIMIT :lim
                    """
                ),
                params,
            )
        ).fetchall()
        return [
            {
                "alert_id": int(r[0]),
                "alert_type": r[1],
                "risk_level": r[2],
                "subject_ref": r[3],
                "amount": r[4],
                "status": r[5],
                "created_at": str(r[6]) if r[6] else None,
            }
            for r in rows
        ]

    async def create_str(
        self,
        fund_id: str,
        reason: str,
        alert_id: int | None = None,
        subject_ref: str | None = None,
        amount: float | None = None,
    ) -> dict[str, Any]:
        due = str_due_at()
        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_aml_str_reports
                        (fund_id, alert_id, subject_ref, reason, amount, due_at, payload_json)
                    VALUES (:fid, :aid, :ref, :reason, :amt, :due, :payload)
                    RETURNING id
                    """
                ),
                {
                    "fid": fund_id,
                    "aid": alert_id,
                    "ref": subject_ref,
                    "reason": reason[:300],
                    "amt": amount,
                    "due": due,
                    "payload": json.dumps({"engine": COMPLIANCE_ENGINE_VERSION}, ensure_ascii=False),
                },
            )
        ).first()
        if alert_id:
            await self.session.execute(
                text("UPDATE fund_aml_alerts SET status = 'REPORTED' WHERE id = :aid"),
                {"aid": alert_id},
            )
        await self._enqueue(
            "AML_STR_CREATED",
            fund_id,
            {
                "str_id": int(row[0]) if row else None,
                "reason": reason,
                "amount": amount,
                "due_at": str(due),
            },
        )
        await self.session.commit()
        return {
            "str_id": int(row[0]) if row else None,
            "fund_id": fund_id,
            "status": "DRAFT",
            "due_at": str(due),
        }

    async def list_str_reports(self, fund_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, alert_id, subject_ref, reason, amount, due_at,
                           submitted_at, status, created_at
                    FROM fund_aml_str_reports
                    WHERE fund_id = :fid
                    ORDER BY created_at DESC LIMIT :lim
                    """
                ),
                {"fid": fund_id, "lim": limit},
            )
        ).fetchall()
        return [
            {
                "str_id": int(r[0]),
                "alert_id": r[1],
                "subject_ref": r[2],
                "reason": r[3],
                "amount": r[4],
                "due_at": str(r[5]) if r[5] else None,
                "submitted_at": str(r[6]) if r[6] else None,
                "status": r[7],
                "created_at": str(r[8]) if r[8] else None,
            }
            for r in rows
        ]

    async def submit_str(self, str_id: int) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    UPDATE fund_aml_str_reports
                    SET status = 'SUBMITTED', submitted_at = now()
                    WHERE id = :sid AND status = 'DRAFT'
                    RETURNING id, fund_id
                    """
                ),
                {"sid": str_id},
            )
        ).first()
        if row is None:
            raise LookupError("گزارش مشکوک یافت نشد یا قبلاً ارسال شده است")
        await self._enqueue(
            "AML_STR_SUBMITTED",
            row[1],
            {"str_id": int(row[0]), "submitted_at": str(datetime.utcnow())},
        )
        await self.session.commit()
        return {"str_id": int(row[0]), "fund_id": row[1], "status": "SUBMITTED"}

    # ── Sharia ─────────────────────────────────────────────────────────────

    async def upsert_sharia_approval(
        self,
        approval_ref: str,
        instrument_symbol: str | None = None,
        instrument_type: str | None = None,
        status: str = "APPROVED",
        notes: str | None = None,
    ) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_sharia_approvals
                        (instrument_symbol, instrument_type, approval_ref, status, notes)
                    VALUES (:sym, :itype, :ref, :status, :notes)
                    ON CONFLICT (instrument_symbol, instrument_type, approval_ref)
                    DO UPDATE SET status = EXCLUDED.status, notes = EXCLUDED.notes
                    RETURNING id
                    """
                ),
                {
                    "sym": instrument_symbol,
                    "itype": instrument_type,
                    "ref": approval_ref,
                    "status": status,
                    "notes": notes,
                },
            )
        ).first()
        await self.session.commit()
        return {
            "approval_id": int(row[0]) if row else None,
            "approval_ref": approval_ref,
            "status": status,
        }

    async def list_sharia_approvals(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, instrument_symbol, instrument_type, approval_ref, status,
                           notes, effective_from
                    FROM fund_sharia_approvals
                    ORDER BY effective_from DESC LIMIT :lim
                    """
                ),
                {"lim": limit},
            )
        ).fetchall()
        return [
            {
                "approval_id": int(r[0]),
                "instrument_symbol": r[1],
                "instrument_type": r[2],
                "approval_ref": r[3],
                "status": r[4],
                "notes": r[5],
                "effective_from": str(r[6]) if r[6] else None,
            }
            for r in rows
        ]

    # ── Governance ─────────────────────────────────────────────────────────

    async def record_rpt(
        self,
        fund_id: str,
        counterparty: str,
        transaction_date: date,
        amount: float | None = None,
        relation_type: str | None = None,
        approved_by: str | None = None,
        disclosed: bool = False,
        notes: str | None = None,
    ) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_related_party_transactions
                        (fund_id, counterparty, relation_type, amount, transaction_date,
                         approved_by, disclosed, notes)
                    VALUES (:fid, :cp, :rel, :amt, :td, :appr, :disc, :notes)
                    RETURNING id
                    """
                ),
                {
                    "fid": fund_id,
                    "cp": counterparty,
                    "rel": relation_type,
                    "amt": amount,
                    "td": transaction_date,
                    "appr": approved_by,
                    "disc": disclosed,
                    "notes": notes,
                },
            )
        ).first()
        await self.session.commit()
        return {"rpt_id": int(row[0]) if row else None, "fund_id": fund_id}

    async def list_rpt(self, fund_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, counterparty, relation_type, amount, transaction_date,
                           approved_by, disclosed, notes
                    FROM fund_related_party_transactions
                    WHERE fund_id = :fid
                    ORDER BY transaction_date DESC LIMIT :lim
                    """
                ),
                {"fid": fund_id, "lim": limit},
            )
        ).fetchall()
        return [
            {
                "rpt_id": int(r[0]),
                "counterparty": r[1],
                "relation_type": r[2],
                "amount": r[3],
                "transaction_date": str(r[4]),
                "approved_by": r[5],
                "disclosed": r[6],
                "notes": r[7],
            }
            for r in rows
        ]

    async def record_complaint(
        self,
        fund_id: str,
        subject: str,
        channel: str = "SETA",
        tracking_code: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_complaints
                        (fund_id, channel, subject, tracking_code, notes)
                    VALUES (:fid, :ch, :sub, :code, :notes)
                    RETURNING id
                    """
                ),
                {
                    "fid": fund_id,
                    "ch": channel,
                    "sub": subject[:300],
                    "code": tracking_code,
                    "notes": notes,
                },
            )
        ).first()
        await self.session.commit()
        return {"complaint_id": int(row[0]) if row else None, "fund_id": fund_id}

    async def list_complaints(self, fund_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, channel, subject, tracking_code, lifecycle, opened_at,
                           resolved_at, notes
                    FROM fund_complaints
                    WHERE fund_id = :fid
                    ORDER BY opened_at DESC LIMIT :lim
                    """
                ),
                {"fid": fund_id, "lim": limit},
            )
        ).fetchall()
        return [
            {
                "complaint_id": int(r[0]),
                "channel": r[1],
                "subject": r[2],
                "tracking_code": r[3],
                "lifecycle": r[4],
                "opened_at": str(r[5]) if r[5] else None,
                "resolved_at": str(r[6]) if r[6] else None,
                "notes": r[7],
            }
            for r in rows
        ]

    # ── Lifecycle / Prospectus ─────────────────────────────────────────────

    async def record_prospectus_version(
        self,
        fund_id: str,
        version: str,
        change_type: str,
        changes: dict[str, Any] | None = None,
        assembly_date: date | None = None,
        source_ref: str | None = None,
    ) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_prospectus_versions
                        (fund_id, version, change_type, changes_json, assembly_date, source_ref)
                    VALUES (:fid, :ver, :ctype, :changes, :adate, :src)
                    ON CONFLICT (fund_id, version) DO UPDATE SET
                        change_type = EXCLUDED.change_type,
                        changes_json = EXCLUDED.changes_json,
                        assembly_date = EXCLUDED.assembly_date,
                        source_ref = EXCLUDED.source_ref
                    RETURNING id
                    """
                ),
                {
                    "fid": fund_id,
                    "ver": version,
                    "ctype": change_type,
                    "changes": json.dumps(changes or {}, ensure_ascii=False),
                    "adate": assembly_date,
                    "src": source_ref,
                },
            )
        ).first()
        await self.session.commit()
        return {"prospectus_id": int(row[0]) if row else None, "fund_id": fund_id, "version": version}

    async def list_prospectus_versions(self, fund_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, version, change_type, changes_json, assembly_date, source_ref
                    FROM fund_prospectus_versions
                    WHERE fund_id = :fid
                    ORDER BY created_at DESC LIMIT :lim
                    """
                ),
                {"fid": fund_id, "lim": limit},
            )
        ).fetchall()
        return [
            {
                "prospectus_id": int(r[0]),
                "version": r[1],
                "change_type": r[2],
                "changes": json.loads(r[3]) if r[3] else {},
                "assembly_date": str(r[4]) if r[4] else None,
                "source_ref": r[5],
            }
            for r in rows
        ]

    async def record_lifecycle_event(
        self,
        fund_id: str,
        event_type: str,
        event_date: date,
        details: dict[str, Any] | None = None,
        source_ref: str | None = None,
    ) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_lifecycle_events
                        (fund_id, event_type, event_date, details_json, source_ref)
                    VALUES (:fid, :et, :ed, :det, :src)
                    RETURNING id
                    """
                ),
                {
                    "fid": fund_id,
                    "et": event_type,
                    "ed": event_date,
                    "det": json.dumps(details or {}, ensure_ascii=False),
                    "src": source_ref,
                },
            )
        ).first()
        await self.session.commit()
        return {"event_id": int(row[0]) if row else None, "fund_id": fund_id}

    async def list_lifecycle_events(self, fund_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, event_type, event_date, details_json, source_ref
                    FROM fund_lifecycle_events
                    WHERE fund_id = :fid
                    ORDER BY event_date DESC LIMIT :lim
                    """
                ),
                {"fid": fund_id, "lim": limit},
            )
        ).fetchall()
        return [
            {
                "event_id": int(r[0]),
                "event_type": r[1],
                "event_date": str(r[2]),
                "details": json.loads(r[3]) if r[3] else {},
                "source_ref": r[4],
            }
            for r in rows
        ]

    # ── Governance (تکمیل فاز ۸) ───────────────────────────────────────────

    async def record_committee(
        self,
        fund_id: str,
        committee_type: str,
        members: list[dict[str, Any]] | None = None,
        charter_ref: str | None = None,
        formed_at: date | None = None,
    ) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_governance_committees
                        (fund_id, committee_type, members_json, charter_ref, formed_at)
                    VALUES (:fid, :ctype, :members, :charter, :formed)
                    RETURNING id
                    """
                ),
                {
                    "fid": fund_id,
                    "ctype": committee_type.upper(),
                    "members": json.dumps(members or [], ensure_ascii=False),
                    "charter": charter_ref,
                    "formed": formed_at,
                },
            )
        ).first()
        await self.session.commit()
        return {"committee_id": int(row[0]) if row else None, "fund_id": fund_id}

    async def list_committees(self, fund_id: str) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, committee_type, members_json, charter_ref, is_active, formed_at
                    FROM fund_governance_committees
                    WHERE fund_id = :fid
                    ORDER BY committee_type
                    """
                ),
                {"fid": fund_id},
            )
        ).fetchall()
        return [
            {
                "committee_id": int(r[0]),
                "committee_type": r[1],
                "members": json.loads(r[2]) if r[2] else [],
                "charter_ref": r[3],
                "is_active": r[4],
                "formed_at": str(r[5]) if r[5] else None,
            }
            for r in rows
        ]

    async def record_internal_audit(
        self,
        fund_id: str,
        period_label: str,
        report_date: date | None = None,
        findings: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_internal_audit_reports
                        (fund_id, period_label, report_date, findings_json)
                    VALUES (:fid, :period, :rdate, :findings)
                    RETURNING id
                    """
                ),
                {
                    "fid": fund_id,
                    "period": period_label,
                    "rdate": report_date,
                    "findings": json.dumps(findings or [], ensure_ascii=False),
                },
            )
        ).first()
        await self.session.commit()
        return {"audit_id": int(row[0]) if row else None, "fund_id": fund_id}

    async def list_internal_audits(self, fund_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, period_label, report_date, findings_json, status, created_at
                    FROM fund_internal_audit_reports
                    WHERE fund_id = :fid
                    ORDER BY created_at DESC LIMIT :lim
                    """
                ),
                {"fid": fund_id, "lim": limit},
            )
        ).fetchall()
        return [
            {
                "audit_id": int(r[0]),
                "period_label": r[1],
                "report_date": str(r[2]) if r[2] else None,
                "findings": json.loads(r[3]) if r[3] else [],
                "status": r[4],
                "created_at": str(r[5]) if r[5] else None,
            }
            for r in rows
        ]

    async def record_disciplinary_case(
        self,
        fund_id: str,
        subject_role: str,
        case_type: str,
        subject_name: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_disciplinary_cases
                        (fund_id, subject_role, subject_name, case_type, notes)
                    VALUES (:fid, :role, :name, :ctype, :notes)
                    RETURNING id
                    """
                ),
                {
                    "fid": fund_id,
                    "role": subject_role,
                    "name": subject_name,
                    "ctype": case_type,
                    "notes": notes,
                },
            )
        ).first()
        await self.session.commit()
        return {"case_id": int(row[0]) if row else None, "fund_id": fund_id}

    async def list_disciplinary_cases(self, fund_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, subject_role, subject_name, case_type, status,
                           opened_at, closed_at, notes
                    FROM fund_disciplinary_cases
                    WHERE fund_id = :fid
                    ORDER BY opened_at DESC LIMIT :lim
                    """
                ),
                {"fid": fund_id, "lim": limit},
            )
        ).fetchall()
        return [
            {
                "case_id": int(r[0]),
                "subject_role": r[1],
                "subject_name": r[2],
                "case_type": r[3],
                "status": r[4],
                "opened_at": str(r[5]) if r[5] else None,
                "closed_at": str(r[6]) if r[6] else None,
                "notes": r[7],
            }
            for r in rows
        ]

    async def record_insurance_policy(
        self,
        fund_id: str,
        policy_type: str = "D_AND_O",
        insurer: str | None = None,
        coverage_amount: float | None = None,
        valid_from: date | None = None,
        valid_to: date | None = None,
        policy_ref: str | None = None,
    ) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_insurance_policies
                        (fund_id, policy_type, insurer, coverage_amount, valid_from,
                         valid_to, policy_ref)
                    VALUES (:fid, :ptype, :insurer, :amount, :vfrom, :vto, :ref)
                    RETURNING id
                    """
                ),
                {
                    "fid": fund_id,
                    "ptype": policy_type,
                    "insurer": insurer,
                    "amount": coverage_amount,
                    "vfrom": valid_from,
                    "vto": valid_to,
                    "ref": policy_ref,
                },
            )
        ).first()
        await self.session.commit()
        return {"policy_id": int(row[0]) if row else None, "fund_id": fund_id}

    async def list_insurance_policies(self, fund_id: str) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, policy_type, insurer, coverage_amount, valid_from,
                           valid_to, policy_ref
                    FROM fund_insurance_policies
                    WHERE fund_id = :fid
                    ORDER BY created_at DESC
                    """
                ),
                {"fid": fund_id},
            )
        ).fetchall()
        return [
            {
                "policy_id": int(r[0]),
                "policy_type": r[1],
                "insurer": r[2],
                "coverage_amount": r[3],
                "valid_from": str(r[4]) if r[4] else None,
                "valid_to": str(r[5]) if r[5] else None,
                "policy_ref": r[6],
            }
            for r in rows
        ]

    # ── Regulator Portal (فاز ۱۰) ──────────────────────────────────────────

    async def log_regulator_access(
        self,
        endpoint: str,
        fund_id: str | None = None,
        actor: str | None = None,
        purpose: str | None = None,
    ) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO fund_regulator_access_logs (fund_id, endpoint, actor, purpose)
                VALUES (:fid, :endpoint, :actor, :purpose)
                """
            ),
            {"fid": fund_id, "endpoint": endpoint, "actor": actor, "purpose": purpose},
        )
        await self.session.commit()

    async def list_regulator_access_logs(
        self, fund_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"lim": limit}
        clause = ""
        if fund_id:
            clause = "WHERE fund_id = :fid"
            params["fid"] = fund_id
        rows = (
            await self.session.execute(
                text(
                    f"""
                    SELECT id, fund_id, endpoint, actor, purpose, created_at
                    FROM fund_regulator_access_logs
                    {clause}
                    ORDER BY created_at DESC LIMIT :lim
                    """
                ),
                params,
            )
        ).fetchall()
        return [
            {
                "log_id": int(r[0]),
                "fund_id": r[1],
                "endpoint": r[2],
                "actor": r[3],
                "purpose": r[4],
                "created_at": str(r[5]) if r[5] else None,
            }
            for r in rows
        ]

    async def export_str_payload(self, str_id: int) -> dict[str, Any]:
        """خروجی STR در قالب قابل ارائه به مرکز (JSON نسخه‌دار)."""
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT id, fund_id, subject_ref, reason, amount, due_at,
                           submitted_at, status
                    FROM fund_aml_str_reports WHERE id = :sid
                    """
                ),
                {"sid": str_id},
            )
        ).first()
        if row is None:
            raise LookupError("گزارش مشکوک یافت نشد")
        return {
            "format": "FIU-STR-JSON",
            "format_version": "1.0",
            "engine_version": COMPLIANCE_ENGINE_VERSION,
            "report": {
                "internal_id": int(row[0]),
                "fund_id": row[1],
                "subject_ref": row[2],
                "reason": row[3],
                "amount": row[4],
                "due_at": str(row[5]) if row[5] else None,
                "submitted_at": str(row[6]) if row[6] else None,
                "status": row[7],
            },
            "note": "قالب داخلی؛ ارسال رسمی فقط از سامانه مرکز مجاز است.",
        }

    # ── CSDI ───────────────────────────────────────────────────────────────

    async def import_csdi_statement(
        self,
        fund_id: str,
        as_of_date: date,
        units_outstanding: int,
        source_ref: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_csdi_statements
                        (fund_id, as_of_date, units_outstanding, source_ref, payload_json)
                    VALUES (:fid, :d, :u, :ref, :payload)
                    ON CONFLICT (fund_id, as_of_date, source_ref) DO UPDATE SET
                        units_outstanding = EXCLUDED.units_outstanding,
                        payload_json = EXCLUDED.payload_json
                    RETURNING id
                    """
                ),
                {
                    "fid": fund_id,
                    "d": as_of_date,
                    "u": units_outstanding,
                    "ref": source_ref,
                    "payload": json.dumps(payload or {}, ensure_ascii=False),
                },
            )
        ).first()
        await self._enqueue(
            "CSDI_STATEMENT_IMPORTED",
            fund_id,
            {
                "statement_id": int(row[0]) if row else None,
                "as_of_date": str(as_of_date),
                "units_outstanding": units_outstanding,
                "source_ref": source_ref,
            },
        )
        await self.session.commit()
        return {"statement_id": int(row[0]) if row else None, "fund_id": fund_id}

    async def reconcile_csdi(
        self, fund_id: str, as_of_date: date | None = None, tolerance: int = 0
    ) -> StaleResult:
        statement = (
            await self.session.execute(
                text(
                    """
                    SELECT as_of_date, units_outstanding
                    FROM fund_csdi_statements
                    WHERE fund_id = :fid AND (:d IS NULL OR as_of_date = :d)
                    ORDER BY as_of_date DESC LIMIT 1
                    """
                ),
                {"fid": fund_id, "d": as_of_date},
            )
        ).first()
        if statement is None:
            raise LookupError("صورت‌وضعیت CSDI یافت نشد")
        internal = (
            await self.session.execute(
                text(
                    """
                    SELECT units_outstanding FROM fund_nav_history
                    WHERE fund_id = :fid AND units_outstanding IS NOT NULL
                    ORDER BY nav_date DESC LIMIT 1
                    """
                ),
                {"fid": fund_id},
            )
        ).first()
        internal_units = int(internal[0]) if internal and internal[0] else None
        result = reconcile_units(internal_units, int(statement[1]) if statement[1] else None, tolerance)
        break_id = None
        if result["status"] == "BREACH":
            row = (
                await self.session.execute(
                    text(
                        """
                        INSERT INTO fund_csdi_reconciliation_breaks
                            (fund_id, as_of_date, internal_units, csdi_units, units_diff)
                        VALUES (:fid, :d, :iu, :cu, :diff)
                        RETURNING id
                        """
                    ),
                    {
                        "fid": fund_id,
                        "d": statement[0],
                        "iu": internal_units,
                        "cu": int(statement[1]) if statement[1] else None,
                        "diff": result["units_diff"],
                    },
                )
            ).first()
            break_id = int(row[0]) if row else None
            await self.session.commit()
        return StaleResult(
            data={
                "fund_id": fund_id,
                "as_of_date": str(statement[0]),
                "internal_units": internal_units,
                "csdi_units": int(statement[1]) if statement[1] else None,
                "status": result["status"],
                "units_diff": result["units_diff"],
                "break_id": break_id,
            },
            freshness="live",
            fetched_from="db",
        )

    async def list_csdi_breaks(self, fund_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, as_of_date, internal_units, csdi_units, units_diff, status, notes
                    FROM fund_csdi_reconciliation_breaks
                    WHERE fund_id = :fid
                    ORDER BY created_at DESC LIMIT :lim
                    """
                ),
                {"fid": fund_id, "lim": limit},
            )
        ).fetchall()
        return [
            {
                "break_id": int(r[0]),
                "as_of_date": str(r[1]),
                "internal_units": r[2],
                "csdi_units": r[3],
                "units_diff": r[4],
                "status": r[5],
                "notes": r[6],
            }
            for r in rows
        ]


__all__ = [
    "COMPLIANCE_ENGINE_VERSION",
    "DEFAULT_CASH_THRESHOLD",
    "FundComplianceService",
    "assess_movement",
    "reconcile_units",
    "str_due_at",
]
