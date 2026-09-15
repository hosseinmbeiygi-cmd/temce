"""Alert dispatcher — log-only today, real Telegram when CURRENCY_ENABLE_ALERTS=True."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from apps.currency_service.config import settings
from apps.currency_service.domain import KillSwitch, Signal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AlertMessage:
    channel: str  # "log" | "telegram"
    body: str


class AlertDispatcher:
    def __init__(self, enabled: bool | None = None) -> None:
        self._enabled = settings.enable_alerts if enabled is None else enabled

    def dispatch_signal(self, signal: Signal) -> AlertMessage | None:
        if signal.confidence not in ("MEDIUM", "HIGH"):
            return None
        body = (
            f"🔔 سیگنال {signal.signal_type} ({signal.asset_type})\n"
            f"اطمینان: {signal.confidence} | ریسک: {signal.risk_level}\n"
            f"دلیل: {signal.reason}"
        )
        return self._emit(body, tag="signal")

    def dispatch_kill_switch(self, kill: KillSwitch) -> AlertMessage | None:
        if not kill.active:
            return None
        bullets = "\n".join(f"- {r}" for r in kill.reasons)
        body = f"🚨 KILL-SWITCH فعال شد\nدلایل:\n{bullets}\nاقدام: از ورود به پوزیشن جدید خودداری کنید"
        return self._emit(body, tag="kill_switch")

    def _emit(self, body: str, tag: str) -> AlertMessage:
        if self._enabled:
            # TODO: replace with httpx.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage")
            logger.info("ALERT[%s][telegram-stub] %s", tag, body)
            return AlertMessage(channel="telegram", body=body)
        logger.info("ALERT[%s][log] %s", tag, body)
        return AlertMessage(channel="log", body=body)
