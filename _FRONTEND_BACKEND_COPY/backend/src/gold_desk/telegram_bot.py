"""Telegram Bot — ارسال پیام بدون کتابخانه اضافی (httpx مستقیم).

Rate limit: 1 msg/sec با asyncio.Semaphore.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}/{method}"


@dataclass
class TelegramConfig:
    bot_token: str | None
    default_chat_id: str | None
    enabled: bool

    @classmethod
    def from_env(cls) -> TelegramConfig:
        return cls(
            bot_token=os.getenv("GOLD_TELEGRAM_BOT_TOKEN"),
            default_chat_id=os.getenv("GOLD_TELEGRAM_CHAT_ID"),
            enabled=os.getenv("GOLD_TELEGRAM_ENABLED", "false").lower() == "true",
        )

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.default_chat_id and self.enabled)


_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(1)
    return _semaphore


async def send_message(
    text: str,
    chat_id: str | None = None,
    config: TelegramConfig | None = None,
    parse_mode: str = "HTML",
) -> bool:
    """ارسال پیام. بازمی‌گرداند True/False."""
    cfg = config or TelegramConfig.from_env()
    if not cfg.is_configured():
        logger.debug("Telegram not configured; skipping send")
        return False

    target = chat_id or cfg.default_chat_id
    if not target:
        return False

    sem = _get_semaphore()
    async with sem:
        url = API_BASE.format(token=cfg.bot_token, method="sendMessage")
        payload = {"chat_id": target, "text": text, "parse_mode": parse_mode}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(url, json=payload)
                if r.status_code == 200:
                    return True
                if r.status_code == 429:
                    # rate limited — wait & retry once
                    await asyncio.sleep(2.0)
                    r = await client.post(url, json=payload)
                    return r.status_code == 200
                logger.warning("Telegram send failed: %s %s", r.status_code, r.text[:200])
                return False
        except Exception as exc:
            logger.error("Telegram send exception: %s", exc)
            return False


def format_alert_message(
    rule_name: str,
    symbol: str,
    trigger_value: float,
    threshold: float,
    extra: str = "",
) -> str:
    """فرمت پیام تلگرام."""
    return (
        f"🔔 <b>{rule_name}</b>\n"
        f"Symbol: <code>{symbol or 'global'}</code>\n"
        f"Trigger: <b>{trigger_value:.2f}</b>\n"
        f"Threshold: {threshold:.2f}\n"
        f"{extra}\n"
    )
