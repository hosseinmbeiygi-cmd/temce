from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alert_hub.models import SymbolAssessmentSnapshotOut
from core.ids import new_id
from core.logging import get_logger

logger = get_logger(__name__)

ALERT_TABLE = "symbol_alerts"
SNAP_TABLE = "symbol_assessment_snapshots"


async def upsert_alert(session: AsyncSession, user_id: str, symbol: str, market: str, base_price: float, trigger_rules: dict[str, Any]) -> dict[str, Any]:
    from models.alert_hub import SymbolAlertModel

    row = await session.execute(select(SymbolAlertModel).where(SymbolAlertModel.symbol == symbol, SymbolAlertModel.user_id == user_id))
    existing = row.scalar_one_or_none()
    if existing:
        existing.market = market
        existing.base_price = base_price
        existing.trigger_rules = json.dumps(trigger_rules)
        existing.is_active = True
        existing.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await session.flush()
        obj = existing
    else:
        obj = SymbolAlertModel(
            id=new_id("sal"),
            user_id=user_id,
            symbol=symbol,
            market=market,
            base_price=base_price,
            trigger_rules=json.dumps(trigger_rules),
            is_active=True,
        )
        session.add(obj)
        await session.flush()

    return {
        "id": obj.id,
        "user_id": obj.user_id,
        "symbol": obj.symbol,
        "market": obj.market,
        "base_price": float(obj.base_price),
        "trigger_rules": json.loads(obj.trigger_rules) if obj.trigger_rules else {},
        "is_active": bool(obj.is_active),
        "created_at": obj.created_at,
    }


async def deactivate_alert(session: AsyncSession, alert_id: str, user_id: str) -> bool:
    from models.alert_hub import SymbolAlertModel

    row = await session.execute(select(SymbolAlertModel).where(SymbolAlertModel.id == alert_id, SymbolAlertModel.user_id == user_id))
    alert = row.scalar_one_or_none()
    if not alert:
        return False
    alert.is_active = False
    alert.updated_at = datetime.now(UTC).replace(tzinfo=None)
    await session.flush()
    return True


async def list_user_alerts(session: AsyncSession, user_id: str) -> list[dict[str, Any]]:
    from models.alert_hub import SymbolAlertModel

    result = await session.execute(select(SymbolAlertModel).where(SymbolAlertModel.user_id == user_id).order_by(SymbolAlertModel.created_at.desc()))
    alerts = result.scalars().all()
    out: list[dict[str, Any]] = []
    for a in alerts:
        snap = await _find_latest_snapshot(session, a.symbol)
        out.append({
            "id": a.id,
            "symbol": a.symbol,
            "market": a.market or "",
            "base_price": float(a.base_price or 0),
            "is_active": bool(a.is_active),
            "created_at": a.created_at,
            "last_evaluated_at": snap.get("last_evaluated_at") if snap else None,
            "assessment_status": "ready" if snap else "pending",
        })
    return out


async def _find_latest_snapshot(session: AsyncSession, symbol: str) -> dict[str, Any] | None:
    from models.alert_hub import SymbolAssessmentSnapshotModel

    result = await session.execute(
        select(SymbolAssessmentSnapshotModel)
        .where(SymbolAssessmentSnapshotModel.symbol == symbol)
        .order_by(SymbolAssessmentSnapshotModel.last_evaluated_at.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()
    if not snap:
        return None
    return {
        "id": snap.id,
        "symbol": snap.symbol,
        "user_id": snap.user_id,
        "market_metrics": json.loads(snap.market_metrics) if snap.market_metrics else {},
        "ml_prediction": json.loads(snap.ml_prediction) if snap.ml_prediction else {},
        "backtest_summary": json.loads(snap.backtest_summary) if snap.backtest_summary else {},
        "codal_signals": json.loads(snap.codal_signals) if snap.codal_signals else {},
        "decision_summary": json.loads(snap.decision_summary) if snap.decision_summary else {},
        "last_evaluated_at": snap.last_evaluated_at,
    }


async def save_snapshot(session: AsyncSession, task: Any, assessment: SymbolAssessmentSnapshotOut, user_id: str) -> dict[str, Any]:
    from models.alert_hub import SymbolAssessmentSnapshotModel

    obj = SymbolAssessmentSnapshotModel(
        id=new_id("sas"),
        user_id=user_id,
        symbol=assessment.symbol,
        market=assessment.market_metrics.get("market", ""),
        market_metrics=json.dumps(assessment.market_metrics),
        ml_prediction=json.dumps(assessment.ml_prediction),
        backtest_summary=json.dumps(assessment.backtest_summary),
        codal_signals=json.dumps(assessment.codal_signals),
        decision_summary=json.dumps(assessment.decision_summary),
        last_evaluated_at=assessment.last_evaluated_at,
    )
    session.add(obj)
    await session.flush()
    return {
        "id": obj.id,
        "symbol": obj.symbol,
        "user_id": obj.user_id,
        "last_evaluated_at": obj.last_evaluated_at,
    }


async def cleanup_inactive_snapshots_for_user(session: AsyncSession, user_id: str) -> None:
    from models.alert_hub import SymbolAlertModel, SymbolAssessmentSnapshotModel

    active_symbols = await session.execute(
        select(SymbolAlertModel.symbol).where(SymbolAlertModel.user_id == user_id, SymbolAlertModel.is_active.is_(True))
    )
    keep = {row[0] for row in active_symbols.fetchall()}
    if not keep:
        return
    result = await session.execute(select(SymbolAssessmentSnapshotModel).where(SymbolAssessmentSnapshotModel.user_id == user_id))
    for snap in result.scalars().all():
        if snap.symbol not in keep:
            await session.delete(snap)
    await session.flush()
