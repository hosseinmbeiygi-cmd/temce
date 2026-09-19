"""⚖️ Fund NAV Reconciliation — تطبیق NAV مستقل با NAV مرجع (فاز ۵ معماری).

دو مرحله:
  ۱. گیت‌های قابلیت مقایسه (صندوق/طبقه/نوع NAV/تاریخ/اعتبار مرجع/کیفیت داخلی).
  ۲. محاسبه اختلاف مطلق و bps + دسته‌بندی با آستانه دوگانه نسخه‌دار.

سه بُعد وضعیت هرگز در یک enum تخت نمی‌شوند:
  - comparability_status : COMPARABLE | NOT_COMPARABLE | INCOMPLETE
  - reference_status     : VALID | STALE | INVALID
  - diff_status          : MATCHED | WARNING | BREACH | (None)

پرونده مغایرت با چرخه عمر ``OPEN → TRIAGED → INVESTIGATING → RESOLVED/ACCEPTED/ESCALATED``
در ``fund_nav_reconciliation_breaks`` ثبت می‌شود.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.time import now_tehran
from services.fund_nav_engine import DEFAULT_NAV_TYPE, NAV_TYPES, FundNavEngine
from services.fund_read_through import StaleResult

logger = get_logger(__name__)

RECON_ENGINE_VERSION = "nav-recon-1.0.0"
STALE_REFERENCE_DAYS = 5

DEFAULT_THRESHOLDS: dict[str, Any] = {
    "abs_warn": 1_000_000.0,
    "abs_breach": 10_000_000.0,
    "bps_warn": 10.0,
    "bps_breach": 50.0,
    "version": "v1",
}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "OPEN": {"TRIAGED", "INVESTIGATING", "RESOLVED", "ACCEPTED", "ESCALATED"},
    "TRIAGED": {"INVESTIGATING", "RESOLVED", "ACCEPTED", "ESCALATED"},
    "INVESTIGATING": {"RESOLVED", "ACCEPTED", "ESCALATED"},
    "ESCALATED": {"INVESTIGATING", "RESOLVED", "ACCEPTED"},
    "RESOLVED": {"OPEN"},
    "ACCEPTED": set(),
}

# ── Pure helpers (قابل تست بدون DB) ─────────────────────────────────────────


def compute_diff(
    internal_nav: float | None, reference_nav: float | None
) -> tuple[float | None, float | None]:
    """ΔNAV = internal − reference و bps فقط وقتی مرجع > ۰ باشد."""
    if internal_nav is None or reference_nav is None:
        return None, None
    delta = float(internal_nav) - float(reference_nav)
    bps = (delta / float(reference_nav) * 10000.0) if reference_nav > 0 else None
    return delta, bps


def classify_diff(
    abs_diff: float | None, bps_diff: float | None, thresholds: dict[str, Any]
) -> str | None:
    """آستانه دوگانه: عبور از هر یک از دو معیار کافی است."""
    if abs_diff is None:
        return None
    if abs(abs_diff) >= float(thresholds["abs_breach"]) or (
        bps_diff is not None and abs(bps_diff) >= float(thresholds["bps_breach"])
    ):
        return "BREACH"
    if abs(abs_diff) >= float(thresholds["abs_warn"]) or (
        bps_diff is not None and abs(bps_diff) >= float(thresholds["bps_warn"])
    ):
        return "WARNING"
    return "MATCHED"


def evaluate_reference_status(
    reference_nav: float | None,
    reference_date: date | None,
    as_of: date,
    stale_days: int = STALE_REFERENCE_DAYS,
) -> str:
    """VALID | STALE | INVALID — اعتبار مرجع مستقل از اختلاف."""
    if reference_nav is None or reference_nav <= 0 or reference_date is None:
        return "INVALID"
    if (as_of - reference_date).days > stale_days:
        return "STALE"
    return "VALID"


def evaluate_comparability(
    internal_quality: str | None,
    same_date: bool,
    reference_status: str,
) -> str:
    """COMPARABLE | NOT_COMPARABLE | INCOMPLETE — گیت پیش از تفریق."""
    if internal_quality == "BLOCKED":
        return "INCOMPLETE"
    if reference_status != "VALID":
        return "NOT_COMPARABLE"
    if not same_date:
        return "NOT_COMPARABLE"
    return "COMPARABLE"


def next_lifecycle(current: str, target: str) -> str:
    """اعتبارسنجی گذار چرخه عمر پرونده مغایرت."""
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"گذار نامعتبر: {current} → {target}")
    return target


def summarize_shadow_acceptance(
    rows: list[dict[str, Any]],
    min_days: int = 20,
    min_match_rate: float = 0.95,
) -> dict[str, Any]:
    """جمع‌بندی پذیرش اجرای سایه از ردیف‌های روزانه (اجرا + تطبیق)."""
    runs = len(rows)
    days = len({r.get("valuation_date") for r in rows if r.get("valuation_date")})
    comparable = sum(1 for r in rows if r.get("comparability_status") == "COMPARABLE")
    matched = sum(1 for r in rows if r.get("diff_status") == "MATCHED")
    warnings = sum(1 for r in rows if r.get("diff_status") == "WARNING")
    breaches = sum(1 for r in rows if r.get("diff_status") == "BREACH")
    blocked = sum(1 for r in rows if r.get("quality_status") == "BLOCKED")
    coverages = [float(r["coverage_pct"]) for r in rows if r.get("coverage_pct") is not None]
    match_rate = (matched / comparable) if comparable else None
    ready = bool(
        days >= min_days
        and comparable >= min_days
        and blocked == 0
        and breaches == 0
        and match_rate is not None
        and match_rate >= min_match_rate
    )
    return {
        "runs": runs,
        "days": days,
        "comparable": comparable,
        "matched": matched,
        "warnings": warnings,
        "breaches": breaches,
        "blocked": blocked,
        "match_rate": match_rate,
        "avg_coverage_pct": (sum(coverages) / len(coverages)) if coverages else None,
        "min_days": min_days,
        "min_match_rate": min_match_rate,
        "acceptance_ready": ready,
    }


class FundNavReconciliationService:
    """تطبیق NAV داخلی با NAV مرجع (آماری/صدور/ابطال) + مدیریت پرونده مغایرت."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.engine = FundNavEngine(session)

    # ── Loaders ─────────────────────────────────────────────────────────────

    async def _load_reference(
        self, fund_id: str, nav_type: str
    ) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT nav_date, nav_statistical, nav_redemption, nav_issue,
                           units_outstanding, data_source, payload_version
                    FROM fund_nav_history
                    WHERE fund_id = :fid
                    ORDER BY nav_date DESC
                    LIMIT 1
                    """
                ),
                {"fid": fund_id},
            )
        ).first()
        if row is None:
            return None
        value = {
            "STATISTICAL": row[1] if row[1] is not None else (row[2] or row[3]),
            "ISSUANCE": row[3],
            "REDEMPTION": row[2],
        }.get(nav_type)
        return {
            "nav_date": row[0],
            "nav_value": float(value) if value else None,
            "units_outstanding": row[4],
            "source": f"fund_nav_history:{row[5] or 'api'}",
            "payload_version": row[6],
        }

    async def _persist_reference(
        self, fund_id: str, nav_type: str, reference: dict[str, Any]
    ) -> int | None:
        if not reference.get("nav_value") or not reference.get("nav_date"):
            return None
        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_nav_reference_reports
                        (fund_id, nav_date, nav_type, nav_value, units_outstanding,
                         source, source_ref, raw_json)
                    VALUES (:fid, :nd, :nt, :nv, :units, :src, :ref, :raw)
                    ON CONFLICT (fund_id, nav_date, nav_type, source) DO NOTHING
                    RETURNING id
                    """
                ),
                {
                    "fid": fund_id,
                    "nd": reference["nav_date"],
                    "nt": nav_type,
                    "nv": reference["nav_value"],
                    "units": reference.get("units_outstanding"),
                    "src": reference.get("source") or "fund_nav_history",
                    "ref": f"payload:{reference.get('payload_version')}",
                    "raw": json.dumps(reference, ensure_ascii=False, default=str),
                },
            )
        ).first()
        if row is not None:
            return int(row[0])
        row2 = (
            await self.session.execute(
                text(
                    """
                    SELECT id FROM fund_nav_reference_reports
                    WHERE fund_id = :fid AND nav_date = :nd AND nav_type = :nt
                      AND source = :src
                    """
                ),
                {
                    "fid": fund_id,
                    "nd": reference["nav_date"],
                    "nt": nav_type,
                    "src": reference.get("source") or "fund_nav_history",
                },
            )
        ).first()
        return int(row2[0]) if row2 else None

    async def _load_thresholds(self, fund_id: str, nav_type: str) -> dict[str, Any]:
        for fid in (fund_id, "*"):
            row = (
                await self.session.execute(
                    text(
                        """
                        SELECT abs_warn, abs_breach, bps_warn, bps_breach, version
                        FROM fund_nav_thresholds
                        WHERE fund_id = :fid AND nav_type = :nt
                        ORDER BY effective_from DESC LIMIT 1
                        """
                    ),
                    {"fid": fid, "nt": nav_type},
                )
            ).first()
            if row is not None:
                return {
                    "abs_warn": float(row[0]),
                    "abs_breach": float(row[1]),
                    "bps_warn": float(row[2]),
                    "bps_breach": float(row[3]),
                    "version": row[4],
                }
        return dict(DEFAULT_THRESHOLDS)

    # ── Calibration ─────────────────────────────────────────────────────────

    async def calibrate_thresholds(
        self,
        fund_id: str,
        nav_type: str = DEFAULT_NAV_TYPE,
        min_samples: int = 10,
    ) -> dict[str, Any]:
        """کالیبراسیون آستانه دوگانه از توزیع تاریخی اختلاف‌ها (p95/p99)."""
        from services.fund_class_nav import percentile

        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT abs_diff, bps_diff
                    FROM fund_nav_reconciliation_runs
                    WHERE fund_id = :fid AND nav_type = :nt
                      AND comparability_status = 'COMPARABLE'
                      AND abs_diff IS NOT NULL
                    ORDER BY id DESC
                    LIMIT 500
                    """
                ),
                {"fid": fund_id, "nt": nav_type},
            )
        ).fetchall()
        abs_values = [abs(float(r[0])) for r in rows if r[0] is not None]
        bps_values = [abs(float(r[1])) for r in rows if r[1] is not None]
        if len(abs_values) < min_samples:
            raise ValueError(
                f"نمونه کافی برای کالیبراسیون نیست ({len(abs_values)} < {min_samples})"
            )
        p95_abs = percentile(abs_values, 95.0) or DEFAULT_THRESHOLDS["abs_warn"]
        p99_abs = percentile(abs_values, 99.0) or DEFAULT_THRESHOLDS["abs_breach"]
        p95_bps = percentile(bps_values, 95.0) if bps_values else DEFAULT_THRESHOLDS["bps_warn"]
        p99_bps = percentile(bps_values, 99.0) if bps_values else DEFAULT_THRESHOLDS["bps_breach"]
        version = f"cal-{datetime.utcnow():%Y%m%d%H%M%S}"

        await self.session.execute(
            text(
                """
                INSERT INTO fund_nav_thresholds
                    (fund_id, nav_type, abs_warn, abs_breach, bps_warn, bps_breach,
                     version, source_document_id)
                VALUES (:fid, :nt, :aw, :ab, :bw, :bb, :ver, 'calibration')
                ON CONFLICT (fund_id, nav_type, version) DO NOTHING
                """
            ),
            {
                "fid": fund_id,
                "nt": nav_type,
                "aw": p95_abs,
                "ab": p99_abs,
                "bw": p95_bps,
                "bb": p99_bps,
                "ver": version,
            },
        )
        await self.session.execute(
            text(
                """
                INSERT INTO fund_nav_threshold_calibrations
                    (fund_id, nav_type, sample_size, p95_abs, p99_abs, p95_bps,
                     p99_bps, applied_version)
                VALUES (:fid, :nt, :n, :p95a, :p99a, :p95b, :p99b, :ver)
                """
            ),
            {
                "fid": fund_id,
                "nt": nav_type,
                "n": len(abs_values),
                "p95a": p95_abs,
                "p99a": p99_abs,
                "p95b": p95_bps,
                "p99b": p99_bps,
                "ver": version,
            },
        )
        await self.session.commit()
        return {
            "fund_id": fund_id,
            "nav_type": nav_type,
            "sample_size": len(abs_values),
            "abs_warn": p95_abs,
            "abs_breach": p99_abs,
            "bps_warn": p95_bps,
            "bps_breach": p99_bps,
            "version": version,
        }

    # ── Shadow Acceptance (فاز ۱۱) ──────────────────────────────────────────

    async def shadow_acceptance(self, fund_id: str, days: int = 30) -> dict[str, Any]:
        """گزارش پذیرش اجرای سایه: نرخ تطبیق، پوشش، مغایرت‌ها و آمادگی."""
        run_rows = (
            await self.session.execute(
                text(
                    """
                    SELECT valuation_date, quality_status, coverage_pct
                    FROM fund_nav_runs
                    WHERE fund_id = :fid
                    ORDER BY valuation_date DESC
                    LIMIT :lim
                    """
                ),
                {"fid": fund_id, "lim": days},
            )
        ).fetchall()
        recon_rows = (
            await self.session.execute(
                text(
                    """
                    SELECT valuation_date, comparability_status, diff_status
                    FROM fund_nav_reconciliation_runs
                    WHERE fund_id = :fid
                    ORDER BY valuation_date DESC
                    LIMIT :lim
                    """
                ),
                {"fid": fund_id, "lim": days},
            )
        ).fetchall()
        recon_by_date = {
            str(r[0]): {"comparability_status": r[1], "diff_status": r[2]} for r in recon_rows
        }
        rows = [
            {
                "valuation_date": str(r[0]),
                "quality_status": r[1],
                "coverage_pct": r[2],
                **recon_by_date.get(str(r[0]), {}),
            }
            for r in run_rows
        ]
        return {
            "fund_id": fund_id,
            "summary": summarize_shadow_acceptance(rows),
            "rows": rows,
            "engine_version": RECON_ENGINE_VERSION,
        }

    # ── Core ────────────────────────────────────────────────────────────────

    async def reconcile(
        self,
        fund_id: str,
        nav_type: str = DEFAULT_NAV_TYPE,
        as_of: date | None = None,
        run_id: int | None = None,
        mode: str = "SHADOW",
    ) -> StaleResult:
        """اجرای تطبیق؛ در نبود اجرای داخلی، ابتدا محاسبه انجام می‌شود."""
        if nav_type not in NAV_TYPES:
            raise ValueError(f"nav_type نامعتبر: {nav_type}")
        as_of = as_of or now_tehran().date()

        internal = None
        if run_id is not None:
            internal = await self.engine.get_run(fund_id, run_id)
        if internal is None:
            calc = await self.engine.calculate(fund_id, nav_type=nav_type, as_of=as_of, mode=mode)
            internal = await self.engine.get_run(fund_id, int(calc.data["run_id"]))

        internal_nav = (internal or {}).get("nav_per_unit")
        internal_quality = (internal or {}).get("quality_status")
        valuation_date = (
            date.fromisoformat(str(internal["valuation_date"])) if internal else as_of
        )

        reference = await self._load_reference(fund_id, nav_type)
        reference_nav = reference.get("nav_value") if reference else None
        reference_date = reference.get("nav_date") if reference else None

        reference_status = evaluate_reference_status(reference_nav, reference_date, valuation_date)
        same_date = reference_date == valuation_date
        comparability = evaluate_comparability(internal_quality, same_date, reference_status)

        abs_diff, bps_diff = compute_diff(internal_nav, reference_nav)
        thresholds = await self._load_thresholds(fund_id, nav_type)
        diff_status = (
            classify_diff(abs_diff, bps_diff, thresholds)
            if comparability == "COMPARABLE"
            else None
        )

        reference_report_id = (
            await self._persist_reference(fund_id, nav_type, reference) if reference else None
        )

        probable_cause = json.dumps(
            {
                "internal_quality": internal_quality,
                "internal_coverage_pct": (internal or {}).get("coverage_pct"),
                "holdings_period": (internal or {}).get("holdings_period"),
                "units_outstanding": (internal or {}).get("units_outstanding"),
                "reference_date": str(reference_date) if reference_date else None,
                "reference_source": (reference or {}).get("source"),
                "same_date": same_date,
                "note": "با تک‌عدد مرجع، علت قطعی قابل انتساب نیست؛ ردیف‌های مرجع لازم است.",
            },
            ensure_ascii=False,
        )

        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_nav_reconciliation_runs
                        (fund_id, run_id, reference_report_id, nav_type, valuation_date,
                         comparability_status, reference_status, diff_status,
                         internal_nav, reference_nav, abs_diff, bps_diff,
                         abs_threshold, bps_threshold, threshold_version,
                         probable_cause, residual_unexplained)
                    VALUES
                        (:fid, :rid, :refid, :nt, :vd, :comp, :refst, :diff,
                         :inav, :rnav, :adiff, :bdiff, :ath, :bth, :tver,
                         :cause, :residual)
                    RETURNING id
                    """
                ),
                {
                    "fid": fund_id,
                    "rid": (internal or {}).get("run_id"),
                    "refid": reference_report_id,
                    "nt": nav_type,
                    "vd": valuation_date,
                    "comp": comparability,
                    "refst": reference_status,
                    "diff": diff_status,
                    "inav": internal_nav,
                    "rnav": reference_nav,
                    "adiff": abs_diff,
                    "bdiff": bps_diff,
                    "ath": thresholds["abs_breach"],
                    "bth": thresholds["bps_breach"],
                    "tver": thresholds["version"],
                    "cause": probable_cause,
                    "residual": abs_diff if diff_status in ("WARNING", "BREACH") else None,
                },
            )
        ).first()
        recon_id = int(row[0]) if row else None

        break_id = None
        if recon_id is not None and diff_status in ("WARNING", "BREACH"):
            break_id = await self._open_break(
                recon_id=recon_id,
                fund_id=fund_id,
                severity=diff_status,
                evidence=probable_cause,
            )
        await self.session.commit()

        return StaleResult(
            data={
                "recon_run_id": recon_id,
                "fund_id": fund_id,
                "nav_type": nav_type,
                "valuation_date": str(valuation_date),
                "comparability_status": comparability,
                "reference_status": reference_status,
                "diff_status": diff_status,
                "internal_nav": internal_nav,
                "reference_nav": reference_nav,
                "abs_diff": abs_diff,
                "bps_diff": bps_diff,
                "thresholds": thresholds,
                "break_id": break_id,
                "probable_cause": json.loads(probable_cause),
                "residual_unexplained": abs_diff if diff_status in ("WARNING", "BREACH") else None,
                "engine_version": RECON_ENGINE_VERSION,
            },
            freshness="live" if comparability == "COMPARABLE" else "estimated",
            fetched_from="db",
        )

    async def _open_break(
        self, recon_id: int, fund_id: str, severity: str, evidence: str
    ) -> int:
        sla_days = 1 if severity == "BREACH" else 3
        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_nav_reconciliation_breaks
                        (recon_run_id, fund_id, lifecycle, severity, sla_due_at, evidence)
                    VALUES (:rid, :fid, 'OPEN', :sev, :sla, :ev)
                    RETURNING id
                    """
                ),
                {
                    "rid": recon_id,
                    "fid": fund_id,
                    "sev": severity,
                    "sla": datetime.utcnow() + timedelta(days=sla_days),
                    "ev": evidence,
                },
            )
        ).first()
        return int(row[0]) if row else -1

    # ── Read APIs ───────────────────────────────────────────────────────────

    async def list_reconciliations(self, fund_id: str, limit: int = 30) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, nav_type, valuation_date, comparability_status,
                           reference_status, diff_status, internal_nav, reference_nav,
                           abs_diff, bps_diff, threshold_version, created_at
                    FROM fund_nav_reconciliation_runs
                    WHERE fund_id = :fid
                    ORDER BY valuation_date DESC, id DESC
                    LIMIT :lim
                    """
                ),
                {"fid": fund_id, "lim": limit},
            )
        ).fetchall()
        return [
            {
                "recon_run_id": int(r[0]),
                "nav_type": r[1],
                "valuation_date": str(r[2]),
                "comparability_status": r[3],
                "reference_status": r[4],
                "diff_status": r[5],
                "internal_nav": r[6],
                "reference_nav": r[7],
                "abs_diff": r[8],
                "bps_diff": r[9],
                "threshold_version": r[10],
                "created_at": str(r[11]) if r[11] else None,
            }
            for r in rows
        ]

    async def list_breaks(
        self, fund_id: str | None = None, lifecycle: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        clauses = []
        params: dict[str, Any] = {"lim": limit}
        if fund_id:
            clauses.append("fund_id = :fid")
            params["fid"] = fund_id
        if lifecycle:
            clauses.append("lifecycle = :lc")
            params["lc"] = lifecycle
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = (
            await self.session.execute(
                text(
                    f"""
                    SELECT id, fund_id, recon_run_id, lifecycle, severity, owner,
                           opened_at, resolved_at, sla_due_at, notes
                    FROM fund_nav_reconciliation_breaks
                    {where}
                    ORDER BY opened_at DESC
                    LIMIT :lim
                    """
                ),
                params,
            )
        ).fetchall()
        return [
            {
                "break_id": int(r[0]),
                "fund_id": r[1],
                "recon_run_id": r[2],
                "lifecycle": r[3],
                "severity": r[4],
                "owner": r[5],
                "opened_at": str(r[6]) if r[6] else None,
                "resolved_at": str(r[7]) if r[7] else None,
                "sla_due_at": str(r[8]) if r[8] else None,
                "notes": r[9],
            }
            for r in rows
        ]

    async def update_break(
        self,
        break_id: int,
        lifecycle: str,
        notes: str | None = None,
        owner: str | None = None,
    ) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT id, fund_id, lifecycle, notes, owner
                    FROM fund_nav_reconciliation_breaks WHERE id = :bid
                    """
                ),
                {"bid": break_id},
            )
        ).first()
        if row is None:
            raise LookupError("پرونده مغایرت یافت نشد")
        current = row[2]
        next_lifecycle(current, lifecycle)
        resolved = datetime.utcnow() if lifecycle in ("RESOLVED", "ACCEPTED") else None
        await self.session.execute(
            text(
                """
                UPDATE fund_nav_reconciliation_breaks
                SET lifecycle = :lc,
                    notes = COALESCE(:notes, notes),
                    owner = COALESCE(:owner, owner),
                    resolved_at = :resolved,
                    updated_at = now()
                WHERE id = :bid
                """
            ),
            {
                "lc": lifecycle,
                "notes": notes,
                "owner": owner,
                "resolved": resolved,
                "bid": break_id,
            },
        )
        await self.session.commit()
        return {
            "break_id": break_id,
            "fund_id": row[1],
            "previous_lifecycle": current,
            "lifecycle": lifecycle,
            "resolved_at": str(resolved) if resolved else None,
        }


__all__ = [
    "ALLOWED_TRANSITIONS",
    "DEFAULT_THRESHOLDS",
    "RECON_ENGINE_VERSION",
    "STALE_REFERENCE_DAYS",
    "FundNavReconciliationService",
    "classify_diff",
    "compute_diff",
    "evaluate_comparability",
    "evaluate_reference_status",
    "next_lifecycle",
    "summarize_shadow_acceptance",
]
