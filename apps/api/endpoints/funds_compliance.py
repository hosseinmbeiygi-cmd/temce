"""🛡 Funds Compliance API — AML/شرعی/حاکمیت/چرخه عمر/CSDI (فازهای ۷–۹).

مسیرها زیر ``/funds/v2/compliance``:

  AML        : GET/POST alerts، POST alerts/generate، POST/GET str، POST str/{id}/submit
  Sharia     : GET/POST sharia/approvals
  Governance : GET/POST {fund_id}/rpt، GET/POST {fund_id}/complaints
  Lifecycle  : GET/POST {fund_id}/prospectus، GET/POST {fund_id}/lifecycle
  CSDI       : POST {fund_id}/csdi/statements، POST {fund_id}/csdi/reconcile، GET {fund_id}/csdi/breaks
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session
from core.logging import get_logger
from services.fund_compliance import DEFAULT_CASH_THRESHOLD, FundComplianceService
from services.fund_tax import TAX_TYPES, FundTaxService

logger = get_logger(__name__)
router = APIRouter()


def _canonical_fund_id(raw: str) -> str:
    if ":" in raw:
        return raw
    return f"tse:{raw}"


def _get_compliance(
    session: AsyncSession = Depends(get_db_session),
) -> FundComplianceService:
    return FundComplianceService(session=session)


def _get_tax(session: AsyncSession = Depends(get_db_session)) -> FundTaxService:
    return FundTaxService(session=session)


# ── Bodies ───────────────────────────────────────────────────────────────────


class GenerateAlertsRequest(BaseModel):
    cash_threshold: float = Field(default=DEFAULT_CASH_THRESHOLD, gt=0)


class CreateStrRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=300)
    alert_id: int | None = None
    subject_ref: str | None = None
    amount: float | None = None


class ShariaApprovalRequest(BaseModel):
    approval_ref: str
    instrument_symbol: str | None = None
    instrument_type: str | None = None
    status: str = "APPROVED"
    notes: str | None = None


class RptRequest(BaseModel):
    counterparty: str
    transaction_date: date
    amount: float | None = None
    relation_type: str | None = None
    approved_by: str | None = None
    disclosed: bool = False
    notes: str | None = None


class ComplaintRequest(BaseModel):
    subject: str
    channel: str = "SETA"
    tracking_code: str | None = None
    notes: str | None = None


class ProspectusRequest(BaseModel):
    version: str
    change_type: str
    changes: dict[str, Any] | None = None
    assembly_date: date | None = None
    source_ref: str | None = None


class LifecycleRequest(BaseModel):
    event_type: str
    event_date: date
    details: dict[str, Any] | None = None
    source_ref: str | None = None


class CsdiStatementRequest(BaseModel):
    as_of_date: date
    units_outstanding: int = Field(ge=0)
    source_ref: str
    payload: dict[str, Any] | None = None


class TaxCalculateRequest(BaseModel):
    tax_type: str = Field(description="|".join(TAX_TYPES))
    base_amount: float = Field(ge=0)
    period_label: str


class TaxFromTradesRequest(BaseModel):
    period_label: str
    trades: list[dict[str, Any]] = Field(min_length=1)


class CommitteeRequest(BaseModel):
    committee_type: str
    members: list[dict[str, Any]] | None = None
    charter_ref: str | None = None
    formed_at: date | None = None


class InternalAuditRequest(BaseModel):
    period_label: str
    report_date: date | None = None
    findings: list[dict[str, Any]] | None = None


class DisciplinaryRequest(BaseModel):
    subject_role: str
    case_type: str
    subject_name: str | None = None
    notes: str | None = None


class InsuranceRequest(BaseModel):
    policy_type: str = "D_AND_O"
    insurer: str | None = None
    coverage_amount: float | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    policy_ref: str | None = None


# ── AML ──────────────────────────────────────────────────────────────────────


@router.get("/{fund_id}/aml/alerts", summary="فهرست هشدارهای AML")
async def list_aml_alerts(
    fund_id: str,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    alerts = await svc.list_aml_alerts(fid, status=status, limit=limit)
    return {"success": True, "data": {"alerts": alerts, "total": len(alerts)}}


@router.post("/{fund_id}/aml/alerts/generate", summary="تولید هشدار AML از حرکت‌های نقدی")
async def generate_aml_alerts(
    fund_id: str,
    body: GenerateAlertsRequest | None = None,
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    body = body or GenerateAlertsRequest()
    fid = _canonical_fund_id(fund_id)
    result = await svc.generate_aml_alerts(fid, cash_threshold=body.cash_threshold)
    return {"success": True, "data": result.data, "freshness": result.freshness}


@router.post("/{fund_id}/aml/str", summary="ایجاد گزارش معاملات مشکوک (STR)")
async def create_str(
    fund_id: str,
    body: CreateStrRequest,
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await svc.create_str(
        fid,
        reason=body.reason,
        alert_id=body.alert_id,
        subject_ref=body.subject_ref,
        amount=body.amount,
    )
    return {"success": True, "data": data}


@router.get("/{fund_id}/aml/str", summary="فهرست گزارش‌های مشکوک")
async def list_str_reports(
    fund_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    reports = await svc.list_str_reports(fid, limit=limit)
    return {"success": True, "data": {"reports": reports, "total": len(reports)}}


@router.post("/aml/str/{str_id}/submit", summary="ارسال گزارش مشکوک")
async def submit_str(
    str_id: int,
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    try:
        data = await svc.submit_str(str_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


# ── Sharia ───────────────────────────────────────────────────────────────────


@router.get("/sharia/approvals", summary="فهرست تأییدهای شرعی")
async def list_sharia_approvals(
    limit: int = Query(default=100, ge=1, le=500),
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    approvals = await svc.list_sharia_approvals(limit=limit)
    return {"success": True, "data": {"approvals": approvals, "total": len(approvals)}}


@router.post("/sharia/approvals", summary="ثبت تأیید شرعی ابزار")
async def upsert_sharia_approval(
    body: ShariaApprovalRequest,
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    data = await svc.upsert_sharia_approval(
        approval_ref=body.approval_ref,
        instrument_symbol=body.instrument_symbol,
        instrument_type=body.instrument_type,
        status=body.status,
        notes=body.notes,
    )
    return {"success": True, "data": data}


# ── Governance ───────────────────────────────────────────────────────────────


@router.get("/{fund_id}/rpt", summary="معاملات با اشخاص وابسته")
async def list_rpt(
    fund_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    items = await svc.list_rpt(fid, limit=limit)
    return {"success": True, "data": {"transactions": items, "total": len(items)}}


@router.post("/{fund_id}/rpt", summary="ثبت معامله با شخص وابسته")
async def record_rpt(
    fund_id: str,
    body: RptRequest,
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await svc.record_rpt(
        fid,
        counterparty=body.counterparty,
        transaction_date=body.transaction_date,
        amount=body.amount,
        relation_type=body.relation_type,
        approved_by=body.approved_by,
        disclosed=body.disclosed,
        notes=body.notes,
    )
    return {"success": True, "data": data}


@router.get("/{fund_id}/complaints", summary="شکایات صندوق")
async def list_complaints(
    fund_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    items = await svc.list_complaints(fid, limit=limit)
    return {"success": True, "data": {"complaints": items, "total": len(items)}}


@router.post("/{fund_id}/complaints", summary="ثبت شکایت")
async def record_complaint(
    fund_id: str,
    body: ComplaintRequest,
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await svc.record_complaint(
        fid,
        subject=body.subject,
        channel=body.channel,
        tracking_code=body.tracking_code,
        notes=body.notes,
    )
    return {"success": True, "data": data}


# ── Lifecycle / Prospectus ───────────────────────────────────────────────────


@router.get("/{fund_id}/prospectus", summary="نسخه‌های امیدنامه")
async def list_prospectus(
    fund_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    items = await svc.list_prospectus_versions(fid, limit=limit)
    return {"success": True, "data": {"versions": items, "total": len(items)}}


@router.post("/{fund_id}/prospectus", summary="ثبت نسخه امیدنامه (مجمع امیدنامه‌ای)")
async def record_prospectus(
    fund_id: str,
    body: ProspectusRequest,
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await svc.record_prospectus_version(
        fid,
        version=body.version,
        change_type=body.change_type,
        changes=body.changes,
        assembly_date=body.assembly_date,
        source_ref=body.source_ref,
    )
    return {"success": True, "data": data}


@router.get("/{fund_id}/lifecycle", summary="رویدادهای چرخه عمر")
async def list_lifecycle(
    fund_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    items = await svc.list_lifecycle_events(fid, limit=limit)
    return {"success": True, "data": {"events": items, "total": len(items)}}


@router.post("/{fund_id}/lifecycle", summary="ثبت رویداد چرخه عمر")
async def record_lifecycle(
    fund_id: str,
    body: LifecycleRequest,
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await svc.record_lifecycle_event(
        fid,
        event_type=body.event_type,
        event_date=body.event_date,
        details=body.details,
        source_ref=body.source_ref,
    )
    return {"success": True, "data": data}


# ── CSDI ─────────────────────────────────────────────────────────────────────


@router.post("/{fund_id}/csdi/statements", summary="ورود صورت‌وضعیت واحدها از CSDI")
async def import_csdi_statement(
    fund_id: str,
    body: CsdiStatementRequest,
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await svc.import_csdi_statement(
        fid,
        as_of_date=body.as_of_date,
        units_outstanding=body.units_outstanding,
        source_ref=body.source_ref,
        payload=body.payload,
    )
    return {"success": True, "data": data}


@router.post("/{fund_id}/csdi/reconcile", summary="تطبیق واحدها با CSDI")
async def reconcile_csdi(
    fund_id: str,
    as_of_date: date | None = Query(default=None),
    tolerance: int = Query(default=0, ge=0),
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    try:
        result = await svc.reconcile_csdi(fid, as_of_date=as_of_date, tolerance=tolerance)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": result.data, "freshness": result.freshness}


@router.get("/{fund_id}/csdi/breaks", summary="مغایرت‌های واحد با CSDI")
async def list_csdi_breaks(
    fund_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    items = await svc.list_csdi_breaks(fid, limit=limit)
    return {"success": True, "data": {"breaks": items, "total": len(items)}}


# ── Tax (فاز ۹) ──────────────────────────────────────────────────────────────


@router.get("/tax/rules", summary="قواعد مالیاتی نسخه‌دار")
async def list_tax_rules(
    tax: FundTaxService = Depends(_get_tax),
) -> dict[str, Any]:
    rules = await tax.list_rules()
    return {"success": True, "data": {"rules": rules, "total": len(rules)}}


@router.post("/{fund_id}/tax/calculate", summary="محاسبه و ثبت مالیات")
async def calculate_tax(
    fund_id: str,
    body: TaxCalculateRequest,
    tax: FundTaxService = Depends(_get_tax),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    try:
        data = await tax.calculate(
            fid, tax_type=body.tax_type, base_amount=body.base_amount, period_label=body.period_label
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/{fund_id}/tax/summary", summary="خلاصه مالیات‌های ثبت‌شده")
async def get_tax_summary(
    fund_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    tax: FundTaxService = Depends(_get_tax),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await tax.summary(fid, limit=limit)
    return {"success": True, "data": data}


@router.post("/{fund_id}/tax/from-trades", summary="محاسبه مالیات مقطوع از جریان معاملات")
async def calculate_tax_from_trades(
    fund_id: str,
    body: TaxFromTradesRequest,
    tax: FundTaxService = Depends(_get_tax),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    try:
        data = await tax.calculate_from_trades(
            fid, trades=body.trades, period_label=body.period_label
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


# ── Governance (تکمیل فاز ۸) ─────────────────────────────────────────────────


@router.get("/{fund_id}/committees", summary="کمیته‌های حاکمیتی")
async def list_committees(
    fund_id: str,
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    items = await svc.list_committees(fid)
    return {"success": True, "data": {"committees": items, "total": len(items)}}


@router.post("/{fund_id}/committees", summary="ثبت کمیته حاکمیتی")
async def record_committee(
    fund_id: str,
    body: CommitteeRequest,
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await svc.record_committee(
        fid,
        committee_type=body.committee_type,
        members=body.members,
        charter_ref=body.charter_ref,
        formed_at=body.formed_at,
    )
    return {"success": True, "data": data}


@router.get("/{fund_id}/internal-audits", summary="گزارش‌های حسابرسی داخلی")
async def list_internal_audits(
    fund_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    items = await svc.list_internal_audits(fid, limit=limit)
    return {"success": True, "data": {"audits": items, "total": len(items)}}


@router.post("/{fund_id}/internal-audits", summary="ثبت گزارش حسابرسی داخلی")
async def record_internal_audit(
    fund_id: str,
    body: InternalAuditRequest,
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await svc.record_internal_audit(
        fid, period_label=body.period_label, report_date=body.report_date, findings=body.findings
    )
    return {"success": True, "data": data}


@router.get("/{fund_id}/disciplinary", summary="پرونده‌های انتظامی")
async def list_disciplinary(
    fund_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    items = await svc.list_disciplinary_cases(fid, limit=limit)
    return {"success": True, "data": {"cases": items, "total": len(items)}}


@router.post("/{fund_id}/disciplinary", summary="ثبت پرونده انتظامی")
async def record_disciplinary(
    fund_id: str,
    body: DisciplinaryRequest,
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await svc.record_disciplinary_case(
        fid,
        subject_role=body.subject_role,
        case_type=body.case_type,
        subject_name=body.subject_name,
        notes=body.notes,
    )
    return {"success": True, "data": data}


@router.get("/{fund_id}/insurance", summary="بیمه‌نامه‌های مسئولیت (D&O)")
async def list_insurance(
    fund_id: str,
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    items = await svc.list_insurance_policies(fid)
    return {"success": True, "data": {"policies": items, "total": len(items)}}


@router.post("/{fund_id}/insurance", summary="ثبت بیمه‌نامه مسئولیت")
async def record_insurance(
    fund_id: str,
    body: InsuranceRequest,
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await svc.record_insurance_policy(
        fid,
        policy_type=body.policy_type,
        insurer=body.insurer,
        coverage_amount=body.coverage_amount,
        valid_from=body.valid_from,
        valid_to=body.valid_to,
        policy_ref=body.policy_ref,
    )
    return {"success": True, "data": data}


@router.get("/{fund_id}/aml/str/{str_id}/export", summary="خروجی STR در قالب قابل ارائه")
async def export_str(
    fund_id: str,
    str_id: int,
    svc: FundComplianceService = Depends(_get_compliance),
) -> dict[str, Any]:
    try:
        data = await svc.export_str_payload(str_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}
