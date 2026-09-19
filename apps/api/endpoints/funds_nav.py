"""🧮 Funds NAV API — محاسبه NAV مستقل و تطبیق با مرجع (فاز ۶ معماری).

مسیرها زیر ``/funds/v2/nav`` ارائه می‌شوند تا قرارداد موجود ``/funds`` و
``/funds/v2`` دست‌نخورده بماند (Zero Breaking Changes):

  POST /funds/v2/nav/{fund_id}/calculate      — اجرای محاسبه NAV مستقل
  GET  /funds/v2/nav/{fund_id}/latest         — آخرین اجرا + ردیف‌های ارزش‌گذاری
  GET  /funds/v2/nav/{fund_id}/runs           — تاریخچه اجراها
  GET  /funds/v2/nav/{fund_id}/runs/{run_id}  — جزئیات یک اجرا
  POST /funds/v2/nav/{fund_id}/reconcile      — تطبیق با NAV مرجع
  GET  /funds/v2/nav/{fund_id}/reconciliation — تاریخچه تطبیق + پرونده‌های باز
  GET  /funds/v2/nav/{fund_id}/dashboard      — بسته یکپارچه برای صفحه صندوق
  GET  /funds/v2/nav/breaks                   — فهرست پرونده‌های مغایرت
  PATCH /funds/v2/nav/breaks/{break_id}       — به‌روزرسانی چرخه عمر پرونده
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session
from core.logging import get_logger
from services.fund_class_nav import ALLOCATION_TYPES, FundClassNavService
from services.fund_fof import FundFofService
from services.fund_nav_engine import NAV_TYPES, FundNavEngine, build_evidence_hash
from services.fund_nav_reconciliation import FundNavReconciliationService

logger = get_logger(__name__)
router = APIRouter()

ENGINE_VERSION = "nav-api-1.0.0"


def _canonical_fund_id(raw: str) -> str:
    """``آگاس`` → ``tse:آگاس``؛ ``ime:X`` دست‌نخورده."""
    if ":" in raw:
        return raw
    return f"tse:{raw}"


def _get_engine(session: AsyncSession = Depends(get_db_session)) -> FundNavEngine:
    return FundNavEngine(session=session)


def _get_recon(
    session: AsyncSession = Depends(get_db_session),
) -> FundNavReconciliationService:
    return FundNavReconciliationService(session=session)


def _get_class_nav(
    session: AsyncSession = Depends(get_db_session),
) -> FundClassNavService:
    return FundClassNavService(session=session)


def _get_fof(session: AsyncSession = Depends(get_db_session)) -> FundFofService:
    return FundFofService(session=session)


class CalculateRequest(BaseModel):
    nav_type: str = Field(default="STATISTICAL", description="STATISTICAL|ISSUANCE|REDEMPTION")
    as_of: date | None = None
    mode: str = Field(default="SHADOW", description="SHADOW|LIVE")


class ReconcileRequest(BaseModel):
    nav_type: str = Field(default="STATISTICAL")
    as_of: date | None = None
    run_id: int | None = None
    mode: str = Field(default="SHADOW")


class BreakUpdateRequest(BaseModel):
    lifecycle: str = Field(description="TRIAGED|INVESTIGATING|RESOLVED|ACCEPTED|ESCALATED|OPEN")
    notes: str | None = None
    owner: str | None = None


class ClassConfigRequest(BaseModel):
    version: str = Field(description="نسخه پیکربندی از امیدنامه")
    classes: list[dict[str, Any]] = Field(min_length=1)
    source_document_id: str | None = None


class ClassCalculateRequest(BaseModel):
    valuation_date: date | None = None


class BackfillRequest(BaseModel):
    days: int = Field(default=90, ge=1, le=1000)
    nav_type: str = "STATISTICAL"


class CalibrateRequest(BaseModel):
    nav_type: str = "STATISTICAL"
    min_samples: int = Field(default=10, ge=3, le=500)


class FofCalculateRequest(BaseModel):
    valuation_date: date | None = None


def _validate_nav_type(nav_type: str) -> str:
    if nav_type not in NAV_TYPES:
        raise HTTPException(status_code=400, detail=f"nav_type نامعتبر: {nav_type}")
    return nav_type


# ── Calculation ──────────────────────────────────────────────────────────────


@router.post("/{fund_id}/calculate", summary="اجرای محاسبه NAV مستقل و نسخه‌دار")
async def calculate_nav(
    fund_id: str,
    body: CalculateRequest | None = None,
    engine: FundNavEngine = Depends(_get_engine),
) -> dict[str, Any]:
    body = body or CalculateRequest()
    _validate_nav_type(body.nav_type)
    fid = _canonical_fund_id(fund_id)
    try:
        result = await engine.calculate(
            fid, nav_type=body.nav_type, as_of=body.as_of, mode=body.mode
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "success": True,
        "data": result.data,
        "freshness": result.freshness,
        "fetched_from": result.fetched_from,
    }


@router.get("/{fund_id}/latest", summary="آخرین اجرای NAV مستقل")
async def get_latest_nav(
    fund_id: str,
    engine: FundNavEngine = Depends(_get_engine),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await engine.get_latest(fid)
    if data is None:
        return {"success": True, "data": None, "freshness": "stale", "fetched_from": "db"}
    return {"success": True, "data": data, "freshness": "live", "fetched_from": "db"}


@router.get("/{fund_id}/runs", summary="تاریخچه اجراهای NAV")
async def list_nav_runs(
    fund_id: str,
    limit: int = Query(default=30, ge=1, le=200),
    engine: FundNavEngine = Depends(_get_engine),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    runs = await engine.list_runs(fid, limit=limit)
    return {"success": True, "data": {"runs": runs, "total": len(runs)}}


@router.get("/{fund_id}/runs/{run_id}", summary="جزئیات یک اجرای NAV")
async def get_nav_run(
    fund_id: str,
    run_id: int,
    engine: FundNavEngine = Depends(_get_engine),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await engine.get_run(fid, run_id)
    if data is None:
        raise HTTPException(status_code=404, detail="اجرای NAV یافت نشد")
    return {"success": True, "data": data}


# ── Reconciliation ───────────────────────────────────────────────────────────


@router.post("/{fund_id}/reconcile", summary="تطبیق NAV مستقل با NAV مرجع")
async def reconcile_nav(
    fund_id: str,
    body: ReconcileRequest | None = None,
    recon: FundNavReconciliationService = Depends(_get_recon),
) -> dict[str, Any]:
    body = body or ReconcileRequest()
    _validate_nav_type(body.nav_type)
    fid = _canonical_fund_id(fund_id)
    try:
        result = await recon.reconcile(
            fid,
            nav_type=body.nav_type,
            as_of=body.as_of,
            run_id=body.run_id,
            mode=body.mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "success": True,
        "data": result.data,
        "freshness": result.freshness,
        "fetched_from": result.fetched_from,
    }


@router.get("/{fund_id}/reconciliation", summary="تاریخچه تطبیق + پرونده‌های باز")
async def get_reconciliation(
    fund_id: str,
    limit: int = Query(default=30, ge=1, le=200),
    recon: FundNavReconciliationService = Depends(_get_recon),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    history = await recon.list_reconciliations(fid, limit=limit)
    open_breaks = await recon.list_breaks(fund_id=fid, lifecycle="OPEN", limit=50)
    return {
        "success": True,
        "data": {
            "history": history,
            "latest": history[0] if history else None,
            "open_breaks": open_breaks,
        },
    }


@router.get("/{fund_id}/dashboard", summary="بسته یکپارچه NAV/تطبیق برای صفحه صندوق")
async def get_nav_dashboard(
    fund_id: str,
    engine: FundNavEngine = Depends(_get_engine),
    recon: FundNavReconciliationService = Depends(_get_recon),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    latest = await engine.get_latest(fid)
    runs = await engine.list_runs(fid, limit=10)
    history = await recon.list_reconciliations(fid, limit=10)
    open_breaks = await recon.list_breaks(fund_id=fid, lifecycle="OPEN", limit=50)
    return {
        "success": True,
        "data": {
            "fund_id": fid,
            "latest_run": latest,
            "recent_runs": runs,
            "latest_reconciliation": history[0] if history else None,
            "reconciliation_history": history,
            "open_breaks": open_breaks,
            "engine_version": ENGINE_VERSION,
        },
    }


# ── Tiered NAV (فاز ۴) ───────────────────────────────────────────────────────


@router.get("/{fund_id}/class-nav", summary="آخرین تخصیص NAV طبقاتی")
async def get_class_nav(
    fund_id: str,
    class_nav: FundClassNavService = Depends(_get_class_nav),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await class_nav.get_latest(fid)
    return {"success": True, "data": data}


@router.put("/{fund_id}/class-nav/config", summary="ثبت پیکربندی نسخه‌دار طبقات")
async def set_class_nav_config(
    fund_id: str,
    body: ClassConfigRequest,
    class_nav: FundClassNavService = Depends(_get_class_nav),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    for cls in body.classes:
        atype = str(cls.get("allocation_type") or "SIMPLE").upper()
        if atype not in ALLOCATION_TYPES:
            raise HTTPException(status_code=400, detail=f"allocation_type نامعتبر: {atype}")
    try:
        saved = await class_nav.set_class_config(
            fid, classes=body.classes, version=body.version, source_document_id=body.source_document_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": {"fund_id": fid, "saved": saved}}


@router.post("/{fund_id}/class-nav/calculate", summary="محاسبه تخصیص NAV طبقاتی")
async def calculate_class_nav(
    fund_id: str,
    body: ClassCalculateRequest | None = None,
    class_nav: FundClassNavService = Depends(_get_class_nav),
) -> dict[str, Any]:
    body = body or ClassCalculateRequest()
    fid = _canonical_fund_id(fund_id)
    try:
        result = await class_nav.calculate(fid, valuation_date=body.valuation_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": result.data, "freshness": result.freshness}


# ── FOF (فاز ۴) ──────────────────────────────────────────────────────────────


@router.get("/{fund_id}/fof", summary="آخرین ارزش‌گذاری فراصندوق + حلقه‌ها")
async def get_fof(
    fund_id: str,
    fof: FundFofService = Depends(_get_fof),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await fof.get_latest(fid)
    return {"success": True, "data": data}


@router.post("/{fund_id}/fof/calculate", summary="محاسبه ارزش فراصندوق از NAV زیرصندوق‌ها")
async def calculate_fof(
    fund_id: str,
    body: FofCalculateRequest | None = None,
    fof: FundFofService = Depends(_get_fof),
) -> dict[str, Any]:
    body = body or FofCalculateRequest()
    fid = _canonical_fund_id(fund_id)
    try:
        result = await fof.calculate(fid, valuation_date=body.valuation_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": result.data, "freshness": result.freshness}


# ── Backfill (فاز ۱۲) ────────────────────────────────────────────────────────


@router.post("/{fund_id}/backfill", summary="بازسازی NAV تاریخی از گزارش‌های دوره")
async def backfill_nav(
    fund_id: str,
    body: BackfillRequest | None = None,
    engine: FundNavEngine = Depends(_get_engine),
) -> dict[str, Any]:
    body = body or BackfillRequest()
    _validate_nav_type(body.nav_type)
    fid = _canonical_fund_id(fund_id)
    try:
        result = await engine.backfill(fid, days=body.days, nav_type=body.nav_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": result.data, "freshness": result.freshness}


# ── Calibration ──────────────────────────────────────────────────────────────


@router.post("/{fund_id}/thresholds/calibrate", summary="کالیبراسیون آستانه تطبیق از تاریخ")
async def calibrate_thresholds(
    fund_id: str,
    body: CalibrateRequest | None = None,
    recon: FundNavReconciliationService = Depends(_get_recon),
) -> dict[str, Any]:
    body = body or CalibrateRequest()
    _validate_nav_type(body.nav_type)
    fid = _canonical_fund_id(fund_id)
    try:
        data = await recon.calibrate_thresholds(
            fid, nav_type=body.nav_type, min_samples=body.min_samples
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


# ── Shadow Acceptance (فاز ۱۱) ───────────────────────────────────────────────


@router.get("/{fund_id}/shadow-acceptance", summary="گزارش پذیرش اجرای سایه")
async def get_shadow_acceptance(
    fund_id: str,
    days: int = Query(default=30, ge=1, le=365),
    recon: FundNavReconciliationService = Depends(_get_recon),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await recon.shadow_acceptance(fid, days=days)
    return {"success": True, "data": data}


# ── Evidence ─────────────────────────────────────────────────────────────────


@router.get("/{fund_id}/evidence", summary="بسته مدارک حسابرسی NAV + تطبیق")
async def get_evidence_pack(
    fund_id: str,
    engine: FundNavEngine = Depends(_get_engine),
    recon: FundNavReconciliationService = Depends(_get_recon),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    latest = await engine.get_latest(fid)
    runs = await engine.list_runs(fid, limit=5)
    history = await recon.list_reconciliations(fid, limit=5)
    breaks = await recon.list_breaks(fund_id=fid, limit=50)
    latest_recon = history[0] if history else None
    return {
        "success": True,
        "data": {
            "fund_id": fid,
            "latest_run": latest,
            "recent_runs": runs,
            "latest_reconciliation": latest_recon,
            "reconciliation_history": history,
            "breaks": breaks,
            "integrity_hash": build_evidence_hash(latest, latest_recon),
            "engine_version": ENGINE_VERSION,
        },
    }


# ── Breaks ───────────────────────────────────────────────────────────────────


@router.get("/breaks", summary="فهرست پرونده‌های مغایرت")
async def list_breaks(
    fund_id: str | None = Query(default=None),
    lifecycle: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    recon: FundNavReconciliationService = Depends(_get_recon),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id) if fund_id else None
    breaks = await recon.list_breaks(fund_id=fid, lifecycle=lifecycle, limit=limit)
    return {"success": True, "data": {"breaks": breaks, "total": len(breaks)}}


@router.patch("/breaks/{break_id}", summary="به‌روزرسانی چرخه عمر پرونده مغایرت")
async def update_break(
    break_id: int,
    body: BreakUpdateRequest,
    x_operator: str | None = Header(default=None, description="شناسه عملگر (SoD/ممیزی)"),
    recon: FundNavReconciliationService = Depends(_get_recon),
) -> dict[str, Any]:
    try:
        data = await recon.update_break(
            break_id,
            lifecycle=body.lifecycle,
            notes=body.notes,
            owner=body.owner or x_operator,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}
