"""Alert-engine API — mounted under ``/alerts`` next to the threshold alerts.

Adding an instrument here starts identity verification, coverage checks, a baseline
analysis and continuous monitoring (``MonitorAlertInstrumentsJob``). Everything is
owner-scoped by the token's user id. Nothing in this surface places, changes or cancels
an order; positions exist only through entries the user records in the ledger.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import current_user_id, get_current_user, get_db_session
from core.logging import get_logger
from schemas.common.responses import ApiResponse
from services.alert_engine import data as engine_data
from services.alert_engine.engine import AlertEngine, EngineError
from services.alert_engine.risk import LedgerError
from services.alert_engine.settings import SettingsError

logger = get_logger(__name__)

router = APIRouter()


class MonitorCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=60)


class LedgerEntryCreate(BaseModel):
    entry_type: str
    book: str = "actual"
    symbol: str | None = None
    quantity: float | None = None
    price_rial: float | None = None
    fees_toman: float = 0.0
    amount_toman: float | None = None
    executed_at: datetime | None = None
    note: str | None = Field(default=None, max_length=500)
    analysis_id: str | None = None


class SettingsUpdate(BaseModel):
    patch: dict[str, dict[str, Any]]
    confirm_loosening: bool = False
    note: str = Field(default="", max_length=500)


class SettingsRollback(BaseModel):
    version: int


class Acknowledge(BaseModel):
    notification_id: str | None = None


def _fail(exc: Exception) -> ApiResponse:
    return ApiResponse(success=False, error={"message": str(exc)})


@router.get("/monitors")
async def list_monitors(session: AsyncSession = Depends(get_db_session),
                        current_user: dict = Depends(get_current_user)) -> ApiResponse:
    items = await AlertEngine(session).list_monitors(current_user_id(current_user))
    return ApiResponse(success=True, data={"items": items})


@router.post("/monitors")
async def add_monitor(req: MonitorCreate, session: AsyncSession = Depends(get_db_session),
                      current_user: dict = Depends(get_current_user)) -> ApiResponse:
    try:
        result = await AlertEngine(session).activate(current_user_id(current_user), req.symbol)
    except EngineError as exc:
        return _fail(exc)
    return ApiResponse(success=True, data=result)


@router.get("/monitors/{monitor_id}")
async def get_monitor(monitor_id: str, session: AsyncSession = Depends(get_db_session),
                      current_user: dict = Depends(get_current_user)) -> ApiResponse:
    try:
        return ApiResponse(success=True, data=await AlertEngine(session).get_monitor(current_user_id(current_user), monitor_id))
    except EngineError as exc:
        return _fail(exc)


@router.post("/monitors/{monitor_id}/analyze")
async def analyze_monitor(monitor_id: str, session: AsyncSession = Depends(get_db_session),
                          current_user: dict = Depends(get_current_user)) -> ApiResponse:
    engine = AlertEngine(session)
    user_id = current_user_id(current_user)
    try:
        await engine.get_monitor(user_id, monitor_id, history=1)  # ownership check
    except EngineError as exc:
        return _fail(exc)
    result = await engine.analyze(monitor_id, force=True)
    if result is None:
        return ApiResponse(success=False, error={"message": "این پایش هم‌اکنون در حال تحلیل است یا دیگر فعال نیست."})
    return ApiResponse(success=True, data={"result": result, "monitor": await engine.get_monitor(user_id, monitor_id)})


@router.delete("/monitors/{monitor_id}")
async def remove_monitor(monitor_id: str, acknowledge_position: bool = Query(False),
                         session: AsyncSession = Depends(get_db_session),
                         current_user: dict = Depends(get_current_user)) -> ApiResponse:
    try:
        result = await AlertEngine(session).remove(current_user_id(current_user), monitor_id,
                                                   acknowledge_position=acknowledge_position)
    except EngineError as exc:
        return _fail(exc)
    return ApiResponse(success=True, data=result)


@router.get("/engine/portfolio")
async def portfolio(session: AsyncSession = Depends(get_db_session),
                    current_user: dict = Depends(get_current_user)) -> ApiResponse:
    return ApiResponse(success=True, data=await AlertEngine(session).portfolio_overview(current_user_id(current_user)))


@router.get("/engine/ledger")
async def ledger(session: AsyncSession = Depends(get_db_session),
                 current_user: dict = Depends(get_current_user)) -> ApiResponse:
    items = await AlertEngine(session)._ledger(current_user_id(current_user))
    return ApiResponse(success=True, data={"items": list(reversed(items))})


@router.post("/engine/ledger")
async def add_ledger_entry(req: LedgerEntryCreate, session: AsyncSession = Depends(get_db_session),
                           current_user: dict = Depends(get_current_user)) -> ApiResponse:
    """Record a trade the user confirms was executed, or a deposit/withdrawal."""
    try:
        entry = await AlertEngine(session).add_ledger_entry(current_user_id(current_user), req.model_dump())
    except LedgerError as exc:
        return _fail(exc)
    return ApiResponse(success=True, data=entry)


@router.get("/engine/settings")
async def get_settings(session: AsyncSession = Depends(get_db_session),
                       current_user: dict = Depends(get_current_user)) -> ApiResponse:
    engine = AlertEngine(session)
    user_id = current_user_id(current_user)
    settings, version = await engine.get_settings(user_id)
    return ApiResponse(success=True, data={"version": version, "settings": settings.to_dict(),
                                           "history": await engine.settings_history(user_id),
                                           "note": "مقادیر اولیهٔ موقت برای ارزیابی کاغذی‌اند، نه استاندارد و نه تضمینِ سقف زیان."})


@router.put("/engine/settings")
async def update_settings(req: SettingsUpdate, session: AsyncSession = Depends(get_db_session),
                          current_user: dict = Depends(get_current_user)) -> ApiResponse:
    user_id = current_user_id(current_user)
    try:
        result = await AlertEngine(session).update_settings(user_id, req.patch, approved_by=user_id,
                                                            confirm_loosening=req.confirm_loosening, note=req.note)
    except SettingsError as exc:
        return _fail(exc)
    return ApiResponse(success=True, data=result)


@router.post("/engine/settings/rollback")
async def rollback_settings(req: SettingsRollback, session: AsyncSession = Depends(get_db_session),
                            current_user: dict = Depends(get_current_user)) -> ApiResponse:
    user_id = current_user_id(current_user)
    try:
        result = await AlertEngine(session).rollback_settings(user_id, req.version, approved_by=user_id)
    except (EngineError, SettingsError) as exc:
        return _fail(exc)
    return ApiResponse(success=True, data=result)


@router.get("/engine/notifications")
async def notifications(limit: int = Query(50, ge=1, le=200), unacknowledged_only: bool = Query(False),
                        since: datetime | None = Query(None), session: AsyncSession = Depends(get_db_session),
                        current_user: dict = Depends(get_current_user)) -> ApiResponse:
    items = await AlertEngine(session).list_notifications(current_user_id(current_user), limit=limit,
                                                          unacknowledged_only=unacknowledged_only, since=since)
    return ApiResponse(success=True, data={"items": items})


@router.post("/engine/notifications/ack")
async def acknowledge(req: Acknowledge, session: AsyncSession = Depends(get_db_session),
                      current_user: dict = Depends(get_current_user)) -> ApiResponse:
    count = await AlertEngine(session).acknowledge(current_user_id(current_user), req.notification_id)
    return ApiResponse(success=True, data={"acknowledged": count})


@router.post("/engine/notifications/test-telegram")
async def test_telegram(session: AsyncSession = Depends(get_db_session),
                        current_user: dict = Depends(get_current_user)) -> ApiResponse:
    """Send a connection-test message to the chat linked to this account and report the real outcome."""
    from datetime import UTC

    from services.alert_engine import notifier
    from services.alert_engine.settings import NotificationPrefs

    user_id = current_user_id(current_user)
    now = datetime.now(UTC)
    nid = await notifier.notify(session, user_id=user_id, severity="informational", event_type="telegram_test",
                                title="آزمایش اتصال تلگرام", body="اگر این پیام را می‌بینید، اتصال برقرار است.",
                                dedupe_key=f"telegram_test:{now.isoformat()}", now=now,
                                prefs=NotificationPrefs(telegram_enabled=True))
    await notifier.deliver_pending(session, now=now, user_id=user_id, max_attempts=1)
    items = await AlertEngine(session).list_notifications(user_id, limit=20)
    result = next((n for n in items if n["id"] == nid), None)
    state = (result or {}).get("telegram", {}).get("state")
    return ApiResponse(success=state == "accepted", data=result,
                       error=None if state == "accepted" else {"message": (result or {}).get("telegram", {}).get("error") or "ارسال نشد"})


@router.get("/engine/health")
async def health(session: AsyncSession = Depends(get_db_session),
                 current_user: dict = Depends(get_current_user)) -> ApiResponse:
    return ApiResponse(success=True, data=await AlertEngine(session).health(current_user_id(current_user)))


@router.get("/engine/support-matrix")
async def support_matrix(current_user: dict = Depends(get_current_user)) -> ApiResponse:
    items = [{"category": key, "label": engine_data.CATEGORY_LABELS[key], **value}
             for key, value in engine_data.SUPPORT_MATRIX.items()]
    return ApiResponse(success=True, data={"items": items})
