from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any

from core.database import AsyncSession, or_, select
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


# Operators the evaluator actually understands (_condition_met); anything else fails
# closed silently, so it must never be accepted at write time (audit F1, 2026-11-28).
CONDITION_OPERATORS = frozenset({"gte", "gt", "lte", "lt", "eq", "neq"})
# Canonical fields evaluate_and_trigger can receive — the values of _FIELD_ALIASES.
CONDITION_FIELDS = frozenset(_FIELD_ALIASES.values())
# Server-side anti-spam default. The frontend injects cooldown_minutes=30, but the API
# contract must not depend on UI behaviour: an alert created without the key used to
# re-trigger on every 2-minute EvaluateAlertsJob pass (audit F1, 2026-11-28).
DEFAULT_COOLDOWN_MINUTES = 30.0


def validate_condition(condition: Any) -> str | None:
    """Return an error message for a condition the evaluator could not honour, else None.

    Only the keys the evaluator reads are checked; extra keys (e.g. the entry/TP/SL
    snapshot of a signal alert) are carried as data. Missing keys keep the evaluator's
    defaults, so the free-form ``{}`` condition stays valid. A key *present* with a
    null value is invalid — that is how a NaN threshold reaches the API through
    ``JSON.stringify`` (audit F1/F4, 2026-11-28): it used to pass validation and then
    die silently inside the evaluator.
    """
    if not isinstance(condition, dict):
        return "condition must be an object"
    if "field" in condition:
        field = condition.get("field")
        if field is None or _normalize_field(str(field)) not in CONDITION_FIELDS:
            return f"unknown condition field: {field}"
    if "operator" in condition:
        operator = condition.get("operator")
        if operator is None or operator not in CONDITION_OPERATORS:
            return f"unknown condition operator: {operator}"
    if "threshold" in condition:
        threshold = condition.get("threshold")
        if threshold is None or isinstance(threshold, bool) or not isinstance(threshold, (int, float)) \
                or not math.isfinite(float(threshold)):
            return "condition threshold must be a number"
    if "cooldown_minutes" in condition:
        cooldown = condition.get("cooldown_minutes")
        if cooldown is None or isinstance(cooldown, bool) or not isinstance(cooldown, (int, float)) \
                or cooldown < 0:
            return "cooldown_minutes must be a non-negative number"
    return None


def quarantine_reason(alert: Any) -> str | None:
    """Why a stored alert must not fire. The row itself is never changed."""
    if not getattr(alert, "user_id", None):
        return "no_owner"
    symbol = str(getattr(alert, "symbol", "") or "")
    if symbol and not symbol.strip("?؟ ‌"):
        return "unrecoverable_symbol"
    return None


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

    async def list_alerts(
        self, page: int = 1, page_size: int = 50, *, user_id: str | None = None
    ) -> Result[dict[str, Any]]:
        """List alerts; ``user_id=None`` means "no filter" and is admin-only."""
        try:
            from core.database import func as sa_func

            offset = (page - 1) * page_size
            count_stmt = select(sa_func.count(AlertModel.id))
            items_stmt = select(AlertModel)
            if user_id is not None:
                count_stmt = count_stmt.where(AlertModel.user_id == user_id)
                items_stmt = items_stmt.where(AlertModel.user_id == user_id)
            result = await self.session.execute(
                items_stmt.order_by(AlertModel.created_at.desc()).offset(offset).limit(page_size)
            )
            total = await self.session.scalar(count_stmt)
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

    async def create_alert(self, user_id: str, instrument_id: str, symbol: str, alert_type: str, condition: dict,
                           channels: list[str], description: str, signal_id: str = "", market: str = "",
                           timeframe: str = "", enabled: bool = True) -> Result[dict[str, Any]]:
        try:
            error = validate_condition(condition)
            if error:
                return Result.fail(error)
            alert = AlertModel(
                id=new_id("alr"),
                user_id=user_id or None,
                instrument_id=instrument_id,
                symbol=symbol,
                alert_type=alert_type,
                condition=json.dumps(condition),
                channels=json.dumps(channels),
                enabled=enabled,
                description=description,
                signal_id=signal_id or None,
                market=market or None,
                timeframe=timeframe or None,
            )
            self.session.add(alert)
            await self.session.flush()
            logger.info("Alert created: %s (%s — %s)", alert.id, symbol, alert_type)
            return Result.ok(self._alert_to_dict(alert))
        except Exception as e:
            logger.error("Create alert failed: %s", e)
            return Result.fail(str(e))

    async def update_alert(self, alert_id: str, user_id: str | None, **kwargs: Any) -> Result[dict[str, Any]]:
        try:
            stmt = select(AlertModel).where(AlertModel.id == alert_id)
            if user_id is not None:
                stmt = stmt.where(AlertModel.user_id == user_id)
            result = await self.session.execute(stmt)
            alert = result.scalar_one_or_none()
            if not alert:
                return Result.fail("Alert not found")
            if "condition" in kwargs and kwargs["condition"] is not None:
                error = validate_condition(kwargs["condition"])
                if error:
                    return Result.fail(error)
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

    async def delete_alert(self, alert_id: str, user_id: str | None) -> Result[None]:
        try:
            stmt = select(AlertModel).where(AlertModel.id == alert_id)
            if user_id is not None:
                stmt = stmt.where(AlertModel.user_id == user_id)
            result = await self.session.execute(stmt)
            alert = result.scalar_one_or_none()
            if not alert:
                return Result.fail("Alert not found")
            await self.session.delete(alert)
            await self.session.flush()
            return Result.ok(None)
        except Exception as e:
            logger.error("Delete alert failed: %s", e)
            return Result.fail(str(e))

    async def get_alert_history(
        self, alert_id: str, page: int = 1, page_size: int = 50, *, user_id: str | None = None
    ) -> Result[dict[str, Any]]:
        try:
            from core.database import func as sa_func

            # Ownership is checked against the alert itself before any history
            # row is returned (audit SEC-05). ``user_id=None`` is admin-only.
            if user_id is not None:
                owner = await self.session.scalar(
                    select(AlertModel.id).where(
                        AlertModel.id == alert_id, AlertModel.user_id == user_id
                    )
                )
                if owner is None:
                    return Result.fail("Alert not found")

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

    async def count_alerts(self, user_id: str) -> int:
        """Number of stored alerts for a user; -1 when unreadable (never blocks creation)."""
        try:
            from core.database import func as sa_func

            total = await self.session.scalar(
                select(sa_func.count(AlertModel.id)).where(AlertModel.user_id == user_id)
            )
            return int(total or 0)
        except Exception as e:  # noqa: BLE001 — a failed count must not break creation
            logger.warning("Count alerts failed: %s", e)
            return -1

    async def symbol_known(self, symbol: str) -> bool | None:
        """Best-effort existence check against the synced TSETMC tables (audit F7).

        True/False from stored data; None when the tables are unreadable. An unknown
        symbol is a *warning* for the UI, never a hard blocker — manual entry of a
        brand-new symbol stays possible, and the evaluation job simply skips symbols
        with no live snapshot.
        """
        if not (symbol or "").strip():
            return False
        try:
            from sqlalchemy import text

            from services.alert_engine.data import symbol_variants

            variants = list(dict.fromkeys(symbol_variants(symbol)))[:3]
            placeholders = ", ".join(f":v{i}" for i in range(len(variants)))
            params = {f"v{i}": v for i, v in enumerate(variants)}
            row = (await self.session.execute(text(
                f"SELECT 1 FROM brsapi_symbol_details WHERE symbol IN ({placeholders}) LIMIT 1"
            ), params)).first()
            if row:
                return True
            row = (await self.session.execute(text(
                f"SELECT 1 FROM brsapi_symbol_snapshots WHERE symbol IN ({placeholders}) LIMIT 1"
            ), params)).first()
            return bool(row)
        except Exception as e:  # noqa: BLE001 — unreadable tables must not block creation
            logger.warning("Symbol existence check failed: %s", e)
            return None

    async def _owner_chat_id(self, user_id: str) -> str | None:
        """The Telegram chat linked to the alert's owner — the same resolution the
        alert-engine notifier uses (``users.telegram_chat_id``)."""
        try:
            from sqlalchemy import text

            row = (await self.session.execute(
                text("SELECT telegram_chat_id FROM users WHERE id = :u"), {"u": user_id})).first()
            return str(row[0]) if row and row[0] else None
        except Exception:  # noqa: BLE001 — an unreadable owner must not break evaluation
            return None

    async def _owner_bale_chat_id(self, user_id: str) -> str | None:
        """The Bale chat linked to the alert's owner (``users.bale_chat_id``)."""
        try:
            from sqlalchemy import text

            row = (await self.session.execute(
                text("SELECT bale_chat_id FROM users WHERE id = :u"), {"u": user_id})).first()
            return str(row[0]) if row and row[0] else None
        except Exception:  # noqa: BLE001 — an unreadable owner must not break evaluation
            return None

    async def _deliver_notification(self, message: str, channels: list[str], user_id: str | None = None) -> bool:
        """Deliver an alert across its configured channels.

        Returns True only when a channel with a confirmed transport reported
        success. Console/sound/email have no confirmed transport here — they are
        logged and reported as ``not_configured``, never as delivered.
        """
        statuses = await self._deliver_by_channel(message, channels, user_id=user_id)
        return any(status == "delivered" for status in statuses.values())

    async def _deliver_by_channel(self, message: str, channels: list[str], user_id: str | None = None) -> dict[str, str]:
        """Per-channel outcome: delivered | failed | not_configured | skipped."""
        from integrations.notifications.telegram_sender import redact_token

        statuses: dict[str, str] = {}
        for channel in dict.fromkeys(channels):
            try:
                if channel == "console":
                    logger.info("[ALERT] %s", message)
                    statuses[channel] = "not_configured"
                elif channel in ("sound", "email"):
                    logger.info("[ALERT][%s] no delivery transport configured: %s", channel.upper(), message)
                    statuses[channel] = "not_configured"
                elif channel == "telegram":
                    from integrations.notifications.telegram_sender import TelegramSender

                    chat_id = None
                    if user_id:
                        chat_id = await self._owner_chat_id(user_id)
                        if not chat_id:
                            # Telegram goes only to the chat linked to the alert's own owner
                            # (same rule as the alert-engine notifier); falling back to the
                            # global chat_id would send every user's alert to one shared chat.
                            statuses[channel] = "not_configured"
                            logger.info("[ALERT][TELEGRAM] no chat linked to alert owner: %s", message)
                            continue
                    res = await TelegramSender(chat_id=chat_id).send(message)
                    if res.success:
                        statuses[channel] = "delivered"
                    else:
                        error = redact_token(str(res.error or ""))
                        statuses[channel] = "not_configured" if "not configured" in error else "failed"
                        logger.info("[ALERT][TELEGRAM] Not sent: %s", error)
                elif channel == "bale":
                    from integrations.notifications.bale_sender import BaleSender

                    bale_chat = None
                    if user_id:
                        bale_chat = await self._owner_bale_chat_id(user_id)
                        if not bale_chat:
                            # Same owner-scoping rule as Telegram: Bale goes only
                            # to the chat linked to the alert's own owner.
                            statuses[channel] = "not_configured"
                            logger.info("[ALERT][BALE] no chat linked to alert owner: %s", message)
                            continue
                    res = await BaleSender(chat_id=bale_chat).send(message)
                    if res.success:
                        statuses[channel] = "delivered"
                    else:
                        error = redact_token(str(res.error or ""))
                        statuses[channel] = "not_configured" if "not configured" in error else "failed"
                        logger.info("[ALERT][BALE] Not sent: %s", error)
                else:
                    statuses[channel] = "skipped"
            except Exception as e:
                statuses[channel] = "failed"
                logger.error("Failed to deliver alert via %s: %s", channel, redact_token(str(e)))
        # Audit F10: per-channel delivery outcomes, visible in /metrics.
        try:
            from core.metrics import inc_alert_delivery

            for channel_name, outcome in statuses.items():
                inc_alert_delivery("threshold", channel_name, outcome)
        except Exception:  # noqa: BLE001 — metrics never break delivery
            pass
        return statuses

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
                select(AlertModel).where(or_(*match_clauses), AlertModel.enabled.is_(True))
            )
            alerts = result.scalars().all()
            now = datetime.now(UTC).replace(tzinfo=None)
            for alert in alerts:
                reason = quarantine_reason(alert)
                if reason:
                    logger.warning("Alert %s quarantined (%s); not evaluated", getattr(alert, "id", "?"), reason)
                    continue
                if alert.alert_type == "signal_tp_sl":
                    # Signal outcome alerts are notified by the nightly signal
                    # evaluation, not by this sweep: their condition carries an
                    # entry/TP/SL snapshot without a threshold, and evaluating it
                    # here would compare the live price against a defaulted 0.
                    continue
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
                    # A condition WITHOUT the key gets the server default — the
                    # API contract does not depend on the UI injecting it (F1).
                    raw_cooldown = cond.get("cooldown_minutes")
                    cooldown_minutes = (
                        DEFAULT_COOLDOWN_MINUTES if raw_cooldown is None else float(raw_cooldown)
                    )
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
                    statuses = await self._deliver_by_channel(message, channels, user_id=getattr(alert, "user_id", None))
                    delivered = any(status == "delivered" for status in statuses.values())
                    history = AlertHistoryModel(
                        id=new_id("alh"),
                        alert_id=alert.id,
                        trigger_value=value,
                        message=message,
                        delivered=delivered,
                    )
                    self.session.add(history)
                    alert.triggered_count = (alert.triggered_count or 0) + 1
                    # Cooldown arms only when nothing reported "failed" (audit F3,
                    # 2026-11-28): a failed transport must not suppress the next pass —
                    # the 2-minute job cadence is the only retry this path has.
                    # not_configured/skipped still arm, so a console-only alert is
                    # recorded once per window instead of on every pass.
                    if not any(status == "failed" for status in statuses.values()):
                        alert.last_triggered = now
                    # Audit F10: every processed trigger is observable.
                    try:
                        from core.metrics import inc_alert_trigger

                        inc_alert_trigger(current_field)
                    except Exception:  # noqa: BLE001 — metrics never break evaluation
                        pass
                    triggered.append({
                        "alert_id": alert.id,
                        "symbol": symbol,
                        "value": value,
                        "threshold": threshold,
                        "message": message,
                        "delivered": delivered,
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
                select(AlertModel).where(AlertModel.signal_id == signal_id, AlertModel.enabled.is_(True))
            )
            alerts = result.scalars().all()
            now = datetime.now(UTC).replace(tzinfo=None)
            n = 0
            for alert in alerts:
                reason = quarantine_reason(alert)
                if reason:
                    logger.warning("Alert %s quarantined (%s); signal outcome not sent", alert.id, reason)
                    continue
                message = f"Signal {alert.symbol} [{signal_id[:8]}]: {status} @ {price}"
                channels = json.loads(alert.channels) if isinstance(alert.channels, str) and alert.channels else []
                delivered = await self._deliver_notification(message, channels, user_id=getattr(alert, "user_id", None))
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
