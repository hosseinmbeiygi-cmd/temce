from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import Result
from models.alert import AlertHistoryModel, AlertModel

logger = get_logger(__name__)

# Normalize equivalent field names so conditions created from the frontend
# (e.g. field="price") match the data pipeline field (e.g. "price_last").
_FIELD_ALIASES: dict[str, str] = {
    "price": "price",
    "price_last": "price",
    "last_price": "price",
    "close": "price",
    "price_close": "price",
    "volume": "volume",
    "trade_volume": "volume",
    "rsi": "rsi",
    "rsi_14": "rsi",
    "sma_cross_above": "sma_cross_above",
    "sma_cross_below": "sma_cross_below",
}


def _normalize_field(field: str) -> str:
    key = (field or "").strip().lower()
    return _FIELD_ALIASES.get(key, key)


def _condition_met(operator: str, value: float, threshold: float) -> bool:
    if operator == "gte":
        return value >= threshold
    if operator == "gt":
        return value > threshold
    if operator == "lte":
        return value <= threshold
    if operator == "lt":
        return value < threshold
    if operator == "eq":
        return abs(value - threshold) < 0.001
    if operator == "neq":
        return abs(value - threshold) >= 0.001
    return False


class AlertService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_alerts(self, page: int = 1, page_size: int = 50) -> Result[dict[str, Any]]:
        try:
            from sqlalchemy import func as sa_func

            offset = (page - 1) * page_size
            result = await self.session.execute(
                select(AlertModel).order_by(AlertModel.created_at.desc()).offset(offset).limit(page_size)
            )
            total = await self.session.scalar(select(sa_func.count(AlertModel.id)))
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

    async def create_alert(self, user_id: str, instrument_id: str, symbol: str, alert_type: str, condition: dict, channels: list[str], description: str, signal_id: str = "", market: str = "", timeframe: str = "") -> Result[dict[str, Any]]:
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
                signal_id=signal_id or None,
                market=market or None,
                timeframe=timeframe or None,
            )
            self.session.add(alert)
            await self.session.flush()
            await self.session.commit()
            logger.info("Alert created: %s (%s — %s)", alert.id, symbol, alert_type)
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
            alert.updated_at = datetime.now(UTC).replace(tzinfo=None)
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
            from sqlalchemy import func as sa_func

            offset = (page - 1) * page_size
            result = await self.session.execute(
                select(AlertHistoryModel)
                .where(AlertHistoryModel.alert_id == alert_id)
                .order_by(AlertHistoryModel.triggered_at.desc())
                .offset(offset).limit(page_size)
            )
            total = await self.session.scalar(
                select(sa_func.count(AlertHistoryModel.id)).where(AlertHistoryModel.alert_id == alert_id)
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
                "total": total or 0,
                "page": page,
                "page_size": page_size,
            })
        except Exception as e:
            logger.error("Get alert history failed: %s", e)
            return Result.fail(str(e))

    async def _deliver_notification(self, message: str, channels: list[str]) -> bool:
        """Deliver an alert across its configured channels.

        Returns True if at least one channel delivered successfully.
        """
        delivered = False
        for channel in channels:
            try:
                if channel == "console":
                    logger.info("[ALERT] %s", message)
                    delivered = True
                elif channel == "sound":
                    logger.info("[ALERT][SOUND] Notification sound would play: %s", message)
                    delivered = True
                elif channel == "telegram":
                    from integrations.notifications.telegram_sender import TelegramSender

                    res = await TelegramSender().send(message)
                    if res.success:
                        delivered = True
                    else:
                        logger.debug("[ALERT][TELEGRAM] Not sent: %s", res.error)
                elif channel == "email":
                    logger.info("[ALERT][EMAIL] Email would be sent: %s", message)
                    delivered = True
            except Exception as e:
                logger.error("Failed to deliver alert via %s: %s", channel, e)
        return delivered

    async def evaluate_and_trigger(self, instrument_id: str, symbol: str, field: str, value: float) -> list[dict[str, Any]]:
        """Evaluate all enabled alerts for a symbol/instrument and trigger matches.

        Alerts are matched by instrument_id OR symbol — the frontend form only
        stores a symbol (instrument_id stays empty until resolved), so matching
        on symbol alone must work. Field names are normalized so a condition
        stored with field="price" matches pipeline data under "price_last".

        Top-level failures (e.g. the alerts table missing or the query itself
        failing) are logged and re-raised so callers — like EvaluateAlertsJob —
        can surface the failure instead of silently reporting zero triggers.
        Per-alert errors are isolated and logged individually.
        """
        triggered: list[dict[str, Any]] = []
        try:
            # Match by instrument_id OR symbol — but only include the branches
            # that actually have a value. The frontend stores alerts with an
            # empty instrument_id, so matching on instrument_id == "" alone
            # would pull EVERY symbol's alerts into every evaluation.
            match_clauses: list[Any] = []
            if instrument_id:
                match_clauses.append(AlertModel.instrument_id == instrument_id)
            if symbol:
                match_clauses.append(AlertModel.symbol == symbol)
            if not match_clauses:
                return []
            result = await self.session.execute(
                select(AlertModel).where(or_(*match_clauses), AlertModel.enabled)
            )
            alerts = result.scalars().all()
            now = datetime.now(UTC).replace(tzinfo=None)
            for alert in alerts:
                try:
                    cond = json.loads(alert.condition) if isinstance(alert.condition, str) else alert.condition or {}
                    threshold = float(cond.get("threshold", 0))
                    operator = cond.get("operator", "gte")
                    trigger_field = _normalize_field(str(cond.get("field", field)))
                    current_field = _normalize_field(field)

                    if trigger_field != current_field:
                        continue

                    # Cooldown: skip if triggered recently (anti-spam).
                    # Compare both timestamps as naive datetimes so a
                    # timezone-aware last_triggered from the DB can't raise.
                    cooldown_minutes = float(cond.get("cooldown_minutes", 0) or 0)
                    if cooldown_minutes > 0 and alert.last_triggered:
                        from datetime import timedelta

                        last = alert.last_triggered
                        if getattr(last, "tzinfo", None) is not None:
                            last = last.replace(tzinfo=None)
                        if now - last < timedelta(minutes=cooldown_minutes):
                            continue

                    if not _condition_met(operator, value, threshold):
                        continue

                    channels = json.loads(alert.channels) if isinstance(alert.channels, str) and alert.channels else []
                    message = f"{symbol} {current_field} reached {value} (threshold: {threshold})"
                    delivered = await self._deliver_notification(message, channels)
                    history = AlertHistoryModel(
                        id=new_id("alh"),
                        alert_id=alert.id,
                        trigger_value=value,
                        message=message,
                        delivered=delivered,
                    )
                    self.session.add(history)
                    alert.triggered_count = (alert.triggered_count or 0) + 1
                    alert.last_triggered = now
                    triggered.append({
                        "alert_id": alert.id,
                        "symbol": symbol,
                        "value": value,
                        "threshold": threshold,
                        "message": message,
                    })
                except Exception as e:
                    logger.warning("Alert %s evaluation skipped: %s", getattr(alert, "id", "?"), e)
            if triggered:
                await self.session.flush()
        except Exception as e:
            logger.error("Evaluate alerts failed: %s", e)
            raise
        return triggered

    async def create_signal_alert(self, user_id: str, signal_id: str, channels: list[str] | None = None, description: str = "") -> Result[dict[str, Any]]:
        """One-click subscribe to an owned/bought signal: snapshots entry/TP/SL
        so the nightly evaluation can notify on hit_target/hit_stop."""
        try:
            from models.signal import SignalModel
            result = await self.session.execute(select(SignalModel).where(SignalModel.id == signal_id))
            sig = result.scalar_one_or_none()
            if not sig:
                return Result.fail("Signal not found")
            condition = {
                "signal_id": signal_id,
                "direction": sig.direction,
                "entry": sig.entry,
                "take_profit": sig.take_profit,
                "stop_loss": sig.stop_loss,
            }
            return await self.create_alert(
                user_id=user_id, instrument_id=sig.instrument_id or "",
                symbol=sig.symbol, alert_type="signal_tp_sl", condition=condition,
                channels=channels or ["console"],
                description=description or f"Signal {sig.symbol} {sig.direction} TP={sig.take_profit} SL={sig.stop_loss}",
                signal_id=signal_id, market=sig.market or "", timeframe=sig.timeframe or "",
            )
        except Exception as e:
            logger.error("Create signal alert failed: %s", e)
            return Result.fail(str(e))

    async def notify_signal_outcome(self, signal_id: str, status: str, price: float) -> int:
        """Called by the nightly signal-eval job: notify all enabled subscribers
        of this signal about hit_target/hit_stop/expired_neutral."""
        try:
            result = await self.session.execute(
                select(AlertModel).where(AlertModel.signal_id == signal_id, AlertModel.enabled)
            )
            alerts = result.scalars().all()
            now = datetime.now(UTC).replace(tzinfo=None)
            n = 0
            for alert in alerts:
                message = f"Signal {alert.symbol} [{signal_id[:8]}]: {status} @ {price}"
                channels = json.loads(alert.channels) if isinstance(alert.channels, str) and alert.channels else []
                delivered = await self._deliver_notification(message, channels)
                self.session.add(AlertHistoryModel(
                    id=new_id("alh"), alert_id=alert.id,
                    trigger_value=price, message=message, delivered=delivered))
                alert.triggered_count = (alert.triggered_count or 0) + 1
                alert.last_triggered = now
                n += 1
            if n:
                await self.session.flush()
            return n
        except Exception as e:
            logger.error("Notify signal outcome failed: %s", e)
            return 0

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
            "signal_id": alert.signal_id or "",
            "market": alert.market or "",
            "timeframe": alert.timeframe or "",
        }
