"""In-platform + Telegram notifications for the alert engine.

Delivery states are kept honest: a row existing means it is *stored* in the platform;
``telegram_state == "accepted"`` means the provider accepted it — neither is proof the
user saw it. Only ``acknowledged_at`` records that. Audio is played by the browser from
the stored notification and can never be guaranteed (autoplay policy, background tabs,
closed tabs), so nothing here reports "sound delivered".

Guarantees:
* dedup — ``(user_id, dedupe_key)`` is unique; a repeated event is dropped at insert;
* an opportunity that outlived its validity is never sent as active (``suppressed_stale``);
* quiet hours hold Telegram back, except critical alerts when the user approved that;
* bounded retries; failures stay visible in the notification history;
* Telegram goes only to the chat linked to that user's own account; balances and sizes
  are excluded unless the user opted in.
"""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from models.alert_engine import AlertNotificationModel
from services.alert_engine.settings import NotificationPrefs

logger = get_logger(__name__)

SEVERITIES = ("informational", "opportunity", "material_change", "risk_warning", "critical")
SEVERITY_LABELS = {"informational": "اطلاع", "opportunity": "فرصت مشروط", "material_change": "تغییر مهم تحلیلی",
                   "risk_warning": "هشدار ریسک", "critical": "ریسک بحرانی / قطع داده"}
_TOKEN_RE = re.compile(r"bot\d+:[A-Za-z0-9_-]+")


def redact(message: str) -> str:
    """Strip a bot token from provider error text before it is stored or logged."""
    return _TOKEN_RE.sub("bot<redacted>", message or "")[:500]


def in_quiet_hours(prefs: NotificationPrefs, now: datetime) -> bool:
    if not prefs.quiet_start or not prefs.quiet_end:
        return False
    import pytz

    local = now.astimezone(pytz.timezone("Asia/Tehran"))
    minute = local.hour * 60 + local.minute

    def to_min(hhmm: str) -> int:
        hh, mm = hhmm.split(":")
        return int(hh) * 60 + int(mm)

    start, end = to_min(prefs.quiet_start), to_min(prefs.quiet_end)
    return start <= minute < end if start <= end else (minute >= start or minute < end)


def initial_telegram_state(prefs: NotificationPrefs, severity: str, now: datetime) -> str:
    if not prefs.telegram_enabled:
        return "not_requested"
    if in_quiet_hours(prefs, now) and not (severity == "critical" and prefs.critical_during_quiet):
        return "suppressed_quiet"
    return "queued"


async def notify(session: AsyncSession, *, user_id: str, severity: str, event_type: str, title: str,
                 body: str, dedupe_key: str, prefs: NotificationPrefs, now: datetime,
                 monitor_id: str | None = None, analysis_id: str | None = None, symbol: str | None = None,
                 valid_until: datetime | None = None, revises_id: str | None = None) -> str | None:
    """Store one notification. Returns its id, or ``None`` when it was a duplicate."""
    if severity not in SEVERITIES:
        raise ValueError(f"unknown severity {severity}")
    stmt = (
        pg_insert(AlertNotificationModel)
        .values(id=new_id("ntf"), user_id=user_id, monitor_id=monitor_id, analysis_id=analysis_id, symbol=symbol,
                severity=severity, event_type=event_type, title=title[:300], body=body, dedupe_key=dedupe_key[:200],
                revises_id=revises_id, created_at=now, valid_until=valid_until,
                telegram_state=initial_telegram_state(prefs, severity, now))
        .on_conflict_do_nothing(constraint="uq_alert_notifications_dedupe")
        .returning(AlertNotificationModel.id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def telegram_text(n: AlertNotificationModel, report_url: str = "") -> str:
    """Instrument, event, time, validity, conclusion + reason (title/body), report link."""
    lines = [
        f"<b>{html.escape(SEVERITY_LABELS.get(n.severity, n.severity))}</b> — {html.escape(n.symbol or '')}",
        html.escape(n.title),
    ]
    if n.body:
        lines.append(html.escape(n.body))
    lines.append(f"زمان: {n.created_at.strftime('%Y-%m-%d %H:%M UTC')}")
    if n.valid_until:
        lines.append(f"اعتبار تا: {n.valid_until.strftime('%Y-%m-%d %H:%M UTC')}")
    if report_url:
        lines.append(f"گزارش کامل: {html.escape(report_url)}")
    lines.append("این پیام توصیهٔ پشتیبان تصمیم است، نه دستور معامله.")
    return "\n".join(lines)


async def _chat_id_for(session: AsyncSession, user_id: str) -> str | None:
    try:
        async with session.begin_nested():
            row = (await session.execute(text("SELECT telegram_chat_id FROM users WHERE id = :u"), {"u": user_id})).first()
        return str(row[0]) if row and row[0] else None
    except Exception:  # noqa: BLE001
        return None


async def deliver_pending(session: AsyncSession, *, now: datetime, max_attempts: int = 3,
                          user_id: str | None = None, sender_factory: Any = None, limit: int = 50) -> dict[str, int]:
    """Send queued Telegram messages; bounded retries; stale opportunities are not sent."""
    from core.config import settings

    stmt = (select(AlertNotificationModel)
            .where(AlertNotificationModel.telegram_state.in_(("queued", "failed")),
                   AlertNotificationModel.telegram_attempts < max_attempts)
            .order_by(AlertNotificationModel.created_at).limit(limit).with_for_update(skip_locked=True))
    if user_id:
        stmt = stmt.where(AlertNotificationModel.user_id == user_id)
    stats = {"accepted": 0, "failed": 0, "suppressed_stale": 0, "not_configured": 0}
    token = getattr(settings, "telegram_bot_token", "")
    base_url = getattr(settings, "frontend_base_url", "") or ""
    for n in (await session.execute(stmt)).scalars().all():
        if n.severity == "opportunity" and n.valid_until and now > n.valid_until:
            n.telegram_state, n.telegram_error = "suppressed_stale", "validity expired before delivery"
            stats["suppressed_stale"] += 1
            continue
        chat_id = await _chat_id_for(session, n.user_id)
        if not token or not chat_id:
            n.telegram_state = "not_configured"
            n.telegram_error = "bot token not configured" if not token else "no Telegram chat linked to this account"
            stats["not_configured"] += 1
            continue
        url = f"{base_url.rstrip('/')}/alerts?monitor={n.monitor_id}" if base_url and n.monitor_id else ""
        n.telegram_attempts += 1
        n.telegram_at = now
        try:
            if sender_factory is None:
                from integrations.notifications.telegram_sender import TelegramSender

                sender = TelegramSender(bot_token=token, chat_id=chat_id)
            else:
                sender = sender_factory(token, chat_id)
            result = await sender.send(telegram_text(n, url))
            ok, error = bool(result.success), None if result.success else redact(str(result.error))
        except Exception as exc:  # noqa: BLE001 — one failed send must not stop the batch
            ok, error = False, redact(str(exc))
        if ok:
            n.telegram_state, n.telegram_error = "accepted", None
            stats["accepted"] += 1
        else:
            n.telegram_state, n.telegram_error = "failed", error
            stats["failed"] += 1
    await session.flush()
    return stats


def to_dict(n: AlertNotificationModel) -> dict[str, Any]:
    return {
        "id": n.id, "monitor_id": n.monitor_id, "analysis_id": n.analysis_id, "symbol": n.symbol,
        "severity": n.severity, "severity_label": SEVERITY_LABELS.get(n.severity, n.severity),
        "event_type": n.event_type, "title": n.title, "body": n.body, "revises_id": n.revises_id,
        "created_at": n.created_at, "valid_until": n.valid_until,
        "in_platform_state": "stored",
        "telegram": {"state": n.telegram_state, "attempts": n.telegram_attempts, "error": n.telegram_error, "at": n.telegram_at},
        "acknowledged_at": n.acknowledged_at,
    }
