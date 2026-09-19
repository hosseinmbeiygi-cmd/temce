"""🏛 Regulator Portal — دسترسی خواندنی نظارتی با ثبت کامل رخداد (فاز ۱۰).

مسیرها زیر ``/funds/v2/regulator``:

  GET /funds/v2/regulator/{fund_id}/evidence   — بسته کامل مدارک (NAV + تطبیق + دفتر + انطباق)
  GET /funds/v2/regulator/{fund_id}/audit-pack — خروجی CSV برای حسابرسی
  GET /funds/v2/regulator/access-logs          — سابقه دسترسی‌ها

هر دسترسی در ``fund_regulator_access_logs`` ثبت می‌شود (append-only).
"""

from __future__ import annotations

import io
import os
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_current_user, get_db_session
from core.logging import get_logger
from services.fund_compliance import FundComplianceService
from services.fund_ledger import FundLedgerService
from services.fund_nav_engine import FundNavEngine, build_evidence_hash
from services.fund_nav_reconciliation import FundNavReconciliationService

logger = get_logger(__name__)
router = APIRouter()


def require_regulator_key(
    x_regulator_key: str | None = Header(default=None),
) -> None:
    """احراز هویت درگاه نظارتی با API Key (در صورت تنظیم ``REGULATOR_API_KEY``).

    اگر متغیر محیطی تنظیم نشده باشد، مسیر باز می‌ماند (سازگاری با استقرار فعلی)
    ولی هر دسترسی در ``fund_regulator_access_logs`` ثبت می‌شود.
    """
    expected = os.getenv("REGULATOR_API_KEY")
    if expected and x_regulator_key != expected:
        raise HTTPException(status_code=401, detail="کلید نظارتی نامعتبر است")


def require_regulator_admin(
    current_user: dict = Depends(get_current_user),
    x_regulator_key: str | None = Header(default=None),
) -> dict:
    """دسترسی نظارتی: JWT معتبر با نقش admin + کلید API (در صورت پیکربندی)."""
    from core.enums.rbac import has_any_role

    expected = os.getenv("REGULATOR_API_KEY")
    if expected and x_regulator_key != expected:
        raise HTTPException(status_code=401, detail="کلید نظارتی نامعتبر است")
    user_roles = current_user.get("roles", [])
    if not has_any_role(user_roles, ["admin"]):
        raise HTTPException(
            status_code=403, detail="دسترسی نظارتی نیازمند نقش admin است"
        )
    return current_user


def _canonical_fund_id(raw: str) -> str:
    if ":" in raw:
        return raw
    return f"tse:{raw}"


def _get_engine(session: AsyncSession = Depends(get_db_session)) -> FundNavEngine:
    return FundNavEngine(session=session)


def _get_recon(
    session: AsyncSession = Depends(get_db_session),
) -> FundNavReconciliationService:
    return FundNavReconciliationService(session=session)


def _get_ledger(session: AsyncSession = Depends(get_db_session)) -> FundLedgerService:
    return FundLedgerService(session=session)


def _get_compliance(
    session: AsyncSession = Depends(get_db_session),
) -> FundComplianceService:
    return FundComplianceService(session=session)


async def _collect_evidence(
    fid: str,
    engine: FundNavEngine,
    recon: FundNavReconciliationService,
    ledger: FundLedgerService,
    compliance: FundComplianceService,
) -> dict[str, Any]:
    latest_run = await engine.get_latest(fid)
    runs = await engine.list_runs(fid, limit=5)
    history = await recon.list_reconciliations(fid, limit=5)
    breaks = await recon.list_breaks(fund_id=fid, limit=50)
    trial = await ledger.trial_balance(fid)
    alerts = await compliance.list_aml_alerts(fid, limit=50)
    strs = await compliance.list_str_reports(fid, limit=50)
    committees = await compliance.list_committees(fid)
    audits = await compliance.list_internal_audits(fid, limit=10)
    csdi_breaks = await compliance.list_csdi_breaks(fid, limit=50)
    latest_recon = history[0] if history else None
    return {
        "fund_id": fid,
        "latest_run": latest_run,
        "recent_runs": runs,
        "latest_reconciliation": latest_recon,
        "reconciliation_history": history,
        "breaks": breaks,
        "trial_balance": trial,
        "aml_alerts": alerts,
        "str_reports": strs,
        "governance_committees": committees,
        "internal_audits": audits,
        "csdi_breaks": csdi_breaks,
        "integrity_hash": build_evidence_hash(latest_run, latest_recon),
    }


@router.get("/{fund_id}/evidence", summary="بسته کامل مدارک نظارتی")
async def get_regulator_evidence(
    fund_id: str,
    actor: str | None = Query(default=None, description="شناسه بازرس/سازمان"),
    purpose: str | None = Query(default=None),
    x_actor: str | None = Header(default=None),
    engine: FundNavEngine = Depends(_get_engine),
    recon: FundNavReconciliationService = Depends(_get_recon),
    ledger: FundLedgerService = Depends(_get_ledger),
    compliance: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await _collect_evidence(fid, engine, recon, ledger, compliance)
    await compliance.log_regulator_access(
        endpoint=f"/funds/v2/regulator/{fid}/evidence",
        fund_id=fid,
        actor=actor or x_actor,
        purpose=purpose,
    )
    return {"success": True, "data": data}


@router.get("/{fund_id}/audit-pack", summary="خروجی CSV بسته حسابرسی")
async def get_audit_pack(
    fund_id: str,
    actor: str | None = Query(default=None),
    x_actor: str | None = Header(default=None),
    engine: FundNavEngine = Depends(_get_engine),
    recon: FundNavReconciliationService = Depends(_get_recon),
    ledger: FundLedgerService = Depends(_get_ledger),
    compliance: FundComplianceService = Depends(_get_compliance),
) -> PlainTextResponse:
    fid = _canonical_fund_id(fund_id)
    data = await _collect_evidence(fid, engine, recon, ledger, compliance)
    await compliance.log_regulator_access(
        endpoint=f"/funds/v2/regulator/{fid}/audit-pack",
        fund_id=fid,
        actor=actor or x_actor,
        purpose="audit-pack",
    )
    run = data.get("latest_run") or {}
    rec = data.get("latest_reconciliation") or {}
    trial = data.get("trial_balance") or {}
    buffer = io.StringIO()
    buffer.write("section,key,value\n")
    rows = [
        ("run", "run_id", run.get("run_id")),
        ("run", "valuation_date", run.get("valuation_date")),
        ("run", "nav_per_unit", run.get("nav_per_unit")),
        ("run", "net_assets", run.get("net_assets")),
        ("run", "quality_status", run.get("quality_status")),
        ("run", "input_hash", run.get("input_hash")),
        ("reconciliation", "comparability_status", rec.get("comparability_status")),
        ("reconciliation", "reference_status", rec.get("reference_status")),
        ("reconciliation", "diff_status", rec.get("diff_status")),
        ("reconciliation", "bps_diff", rec.get("bps_diff")),
        ("ledger", "total_debit", trial.get("total_debit")),
        ("ledger", "total_credit", trial.get("total_credit")),
        ("ledger", "balanced", trial.get("balanced")),
        ("breaks", "open_breaks", len(data.get("breaks") or [])),
        ("aml", "alerts", len(data.get("aml_alerts") or [])),
        ("integrity", "evidence_hash", data.get("integrity_hash")),
    ]
    for section, key, value in rows:
        buffer.write(f"{section},{key},{value}\n")
    safe_name = "".join(ch if (ch.isascii() and ch.isalnum()) else "_" for ch in fid)
    return PlainTextResponse(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="audit-pack-{safe_name}.csv"'},
    )


@router.get("/access-logs", summary="سابقه دسترسی‌های نظارتی")
async def list_access_logs(
    fund_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    compliance: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id) if fund_id else None
    logs = await compliance.list_regulator_access_logs(fund_id=fid, limit=limit)
    return {"success": True, "data": {"logs": logs, "total": len(logs)}}
