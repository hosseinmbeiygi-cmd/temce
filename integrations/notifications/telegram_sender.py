from __future__ import annotations

import httpx

from core.config import settings
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class TelegramSender:
    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self._token = bot_token or getattr(settings, "telegram_bot_token", "")
        self._chat_id = chat_id or getattr(settings, "telegram_chat_id", "")

    async def send(self, message: str, parse_mode: str = "HTML") -> Result[bool]:
        if not self._token or not self._chat_id:
            return Result.fail("Telegram bot token or chat ID not configured")
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = {"chat_id": self._chat_id, "text": message, "parse_mode": parse_mode}
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                logger.info("Telegram message sent")
                return Result.ok(True)
            except httpx.HTTPError as e:
                logger.error("Failed to send Telegram message: %s", e)
                return Result.fail(str(e))

    async def send_photo(self, photo_url: str, caption: str = "") -> Result[bool]:
        if not self._token or not self._chat_id:
            return Result.fail("Telegram bot token or chat ID not configured")
        url = f"https://api.telegram.org/bot{self._token}/sendPhoto"
        payload = {"chat_id": self._chat_id, "photo": photo_url, "caption": caption}
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return Result.ok(True)
            except httpx.HTTPError as e:
                return Result.fail(str(e))

    async def send_document(self, document_path: str, caption: str = "") -> Result[bool]:
        if not self._token or not self._chat_id:
            return Result.fail("Telegram bot token or chat ID not configured")
        from core.paths import validate_safe_path
        safe_path = validate_safe_path(document_path)
        url = f"https://api.telegram.org/bot{self._token}/sendDocument"
        data = {"chat_id": self._chat_id, "caption": caption}
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                with open(str(safe_path), "rb") as f:
                    files = {"document": f}
                    resp = await client.post(url, data=data, files=files)
                resp.raise_for_status()
                return Result.ok(True)
            except httpx.HTTPError as e:
                return Result.fail(str(e))
