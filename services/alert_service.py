from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import Result
from models.alert import AlertHistoryModel, AlertModel

logger = get_logger(__name__)


class AlertService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_alerts(self, page: int = 1, page_size: int = 50) -> Result[dict[str, Any]]:
        try:
            offset = (page - 1) * page_size
            result = await self.session.execute(
                select(AlertModel).order_by(AlertModel.created_at.desc()).offset(offset).limit(page_size)
            )
            total = await self.session.scalar(select(text("COUNT(*)")).select_from(AlertModel.__tablename__))
            items = result.scalars().all()
            return Result.ok({
                "items": [self._alert_to_dict(a) for a in items],
                "total": total or 0,
                "page": page,
                "page_size": page_size,
            })
        except Exception as e:
            logger.error("List alerts failed: %s", e)
            return Result.fail(str(e))

    async def create_alert(self, user_id: str, instrument_id: str, symbol: str, alert_type: str, condition: dict, channels: list[str], description: str) -> Result[dict[str, Any]]:
        try:
            alert = AlertModel(
                id=new_id("alr"),
                instrument_id=instrument_id,
                symbol=symbol,
                alert_type=alert_type,
                condition=json.dumps(condition),
                channels=json.dumps(channels),
                enabled=True,
                description=description,
            )
            self.session.add(alert)
            await self.session.flush()
            return Result.ok(self._alert_to_dict(alert))
        except Exception as e:
            logger.error("Create alert failed: %s", e)
            return Result.fail(str(e))

    async def update_alert(self, alert_id: str, user_id: str, **kwargs: Any) -> Result[dict[str, Any]]:
        try:
            result = await self.session.execute(select(AlertModel).where(AlertModel.id == alert_id))
            alert = result.scalar_one_or_none()
            if not alert:
                return Result.fail("Alert not found")
            if "condition" in kwargs and kwargs["condition"] is not None:
                alert.condition = json.dumps(kwargs["condition"])
            if "channels" in kwargs and kwargs["channels"] is not None:
                alert.channels = json.dumps(kwargs["channels"])
            if "enabled" in kwargs and kwargs["enabled"] is not None:
                alert.enabled = kwargs["enabled"]
            if "description" in kwargs and kwargs["description"] is not None:
                alert.description = kwargs["description"]
            if "alert_type" in kwargs and kwargs["alert_type"] is not None:
                alert.alert_type = kwargs["alert_type"]
            alert.updated_at = datetime.now(UTC)
            await self.session.flush()
            return Result.ok(self._alert_to_dict(alert))
        except Exception as e:
            logger.error("Update alert failed: %s", e)
            return Result.fail(str(e))

    async def delete_alert(self, alert_id: str, user_id: str) -> Result[None]:
        try:
            result = await self.session.execute(select(AlertModel).where(AlertModel.id == alert_id))
            alert = result.scalar_one_or_none()
            if not alert:
                return Result.fail("Alert not found")
            await self.session.delete(alert)
            await self.session.flush()
            return Result.ok(None)
        except Exception as e:
            logger.error("Delete alert failed: %s", e)
            return Result.fail(str(e))

    async def get_alert_history(self, alert_id: str, page: int = 1, page_size: int = 50) -> Result[dict[str, Any]]:
        try:
            offset = (page - 1) * page_size
            result = await self.session.execute(
                select(AlertHistoryModel)
                .where(AlertHistoryModel.alert_id == alert_id)
                .order_by(AlertHistoryModel.triggered_at.desc())
                .offset(offset).limit(page_size)
            )
            items = result.scalars().all()
            return Result.ok({
                "items": [
                    {
                        "id": h.id,
                        "alert_id": h.alert_id,
                        "triggered_at": h.triggered_at,
                        "trigger_value": h.trigger_value,
                        "message": h.message,
                        "delivered": h.delivered,
                    }
                    for h in items
                ],
                "total": len(items),
            })
        except Exception as e:
            logger.error("Get alert history failed: %s", e)
            return Result.fail(str(e))

    async def evaluate_and_trigger(self, instrument_id: str, symbol: str, field: str, value: float) -> list[dict[str, Any]]:
        triggered: list[dict[str, Any]] = []
        try:
            result = await self.session.execute(
                select(AlertModel).where(
                    AlertModel.instrument_id == instrument_id,
                    AlertModel.enabled == True,
                )
            )
            alerts = result.scalars().all()
            for alert in alerts:
                try:
                    cond = json.loads(alert.condition) if isinstance(alert.condition, str) else alert.condition or {}
                    threshold = float(cond.get("threshold", 0))
                    operator = cond.get("operator", "gte")
                    trigger_field = cond.get("field", field)

                    if trigger_field != field:
                        continue

                    triggered_flag = False
                    if operator == "gte" and value >= threshold:
                        triggered_flag = True
                    elif operator == "gt" and value > threshold:
                        triggered_flag = True
                    elif operator == "lte" and value <= threshold:
                        triggered_flag = True
                    elif operator == "lt" and value < threshold:
                        triggered_flag = True
                    elif operator == "eq" and abs(value - threshold) < 0.001:
                        triggered_flag = True

                    if triggered_flag:
                        history = AlertHistoryModel(
                            id=new_id("alh"),
                            alert_id=alert.id,
                            trigger_value=value,
                            message=f"{symbol} {field} reached {value} (threshold: {threshold})",
                            delivered=False,
                        )
                        self.session.add(history)
                        alert.triggered_count = (alert.triggered_count or 0) + 1
                        alert.last_triggered = datetime.now(UTC)
                        triggered.append({
                            "alert_id": alert.id,
                            "symbol": symbol,
                            "value": value,
                            "threshold": threshold,
                            "message": history.message,
                        })
                except Exception:
                    continue
            if triggered:
                await self.session.flush()
        except Exception as e:
            logger.error("Evaluate alerts failed: %s", e)
        return triggered

    def _alert_to_dict(self, alert: AlertModel) -> dict[str, Any]:
        return {
            "id": alert.id,
            "instrument_id": alert.instrument_id or "",
            "symbol": alert.symbol or "",
            "alert_type": alert.alert_type or "",
            "condition": json.loads(alert.condition) if isinstance(alert.condition, str) and alert.condition else {},
            "channels": json.loads(alert.channels) if isinstance(alert.channels, str) and alert.channels else [],
            "enabled": alert.enabled if alert.enabled is not None else True,
            "triggered_count": alert.triggered_count or 0,
            "last_triggered": alert.last_triggered,
            "description": alert.description or "",
            "created_at": alert.created_at,
            "updated_at": alert.updated_at,
        }
