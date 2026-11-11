from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.alert_hub.assessment import AssessmentOrchestrator
from app.alert_hub.repository import (
    cleanup_inactive_snapshots_for_user,
    deactivate_alert,
    list_user_alerts,
    save_snapshot,
    upsert_alert,
)
from app.alert_hub.schemas import (
    SymbolAlertCreate,
    SymbolAlertResponse,
    SymbolDecisionHubResponse,
    SymbolListEntry,
)
from apps.api.dependencies import get_current_user, get_db_session
from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)

router = APIRouter()


@router.get("/")
async def list_symbol_alerts(
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    items = await list_user_alerts(session, current_user["sub"])
    return ApiResponse(success=True, data={"items": [SymbolListEntry(**it).model_dump() for it in items]})


@router.post("/")
async def add_symbol_to_alerts(
    req: SymbolAlertCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    user_id = current_user["sub"]
    alert = await upsert_alert(
        session,
        user_id=user_id,
        symbol=req.symbol,
        market=req.market,
        base_price=req.base_price,
        trigger_rules=req.trigger_rules,
    )

    task = _make_task(req.symbol, req.market, user_id)
    try:
        orchestrator = AssessmentOrchestrator()
        assessment = await orchestrator.assess(task)
        snapshot = await save_snapshot(session, task, assessment, user_id)
    except Exception as e:
        logger.warning("assessment failed for %s: %s", req.symbol, e)
        snapshot = None

    return ApiResponse(
        success=True,
        data={
            "alert": SymbolAlertResponse(
                id=alert["id"],
                user_id=alert["user_id"],
                symbol=alert["symbol"],
                market=alert["market"] or "",
                base_price=alert["base_price"],
                trigger_rules=alert["trigger_rules"],
                is_active=alert["is_active"],
                created_at=alert["created_at"],
            ).model_dump(),
            "assessment": snapshot,
        },
    )


def _make_task(symbol: str, market: str, user_id: str) -> Any:
    # lightweight task DTO
    return type("SymbolAssessmentTask", (), {"symbol": symbol, "market": market, "user_id": user_id})()


@router.delete("/{alert_id}")
async def remove_symbol_alert(
    alert_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    user_id = current_user["sub"]
    ok = await deactivate_alert(session, alert_id, user_id)
    if not ok:
        return ApiResponse(success=False, error={"message": "Alert not found or not owned"})
    await cleanup_inactive_snapshots_for_user(session, user_id)
    return ApiResponse(success=True, message="Symbol removed from alerts")


@router.get("/{symbol}/decision-hub")
async def get_symbol_decision_hub(
    symbol: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    from app.alert_hub.repository import _find_latest_snapshot

    snap = await _find_latest_snapshot(session, symbol)
    if not snap:
        return ApiResponse(success=True, data=SymbolDecisionHubResponse(
            symbol=symbol,
            user_id=current_user["sub"],
            assessment={},
            generated_at=None,
            status="pending",
        ).model_dump())

    return ApiResponse(success=True, data=SymbolDecisionHubResponse(
        symbol=symbol,
        user_id=current_user["sub"],
        assessment={
            "market_metrics": snap.get("market_metrics"),
            "ml_prediction": snap.get("ml_prediction"),
            "backtest_summary": snap.get("backtest_summary"),
            "codal_signals": snap.get("codal_signals"),
            "decision_summary": snap.get("decision_summary"),
            "last_evaluated_at": snap.get("last_evaluated_at"),
        },
        generated_at=snap.get("last_evaluated_at"),
        status="ready",
    ).model_dump())
