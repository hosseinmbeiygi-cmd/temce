"""Bale messenger (bale.ai) sender — Telegram-compatible Bot API.

Bale's Bot API mirrors Telegram's with minor changes (docs.bale.ai):
endpoint ``https://tapi.bale.ai/bot<token>/METHOD``. Two differences shape
this class:

* ``sendMessage`` has **no** ``parse_mode`` — formatting is Markdown only
  (``*bold*``, ``_italic_``), so callers must pass pre-formatted text and
  never HTML.
* Bot tokens look like Telegram's (``123456789:abcd…``) and end up embedded
  in the request URL, so every error string is redacted the same way.
"""

from __future__ import annotations

import re

import httpx

from core.config import settings
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)

_BALE_TOKEN_RE = re.compile(r"(?:bot)?\d{5,}(?::|%3A)[A-Za-z0-9_-]+", re.IGNORECASE)

_BALE_API_BASE = "https://tapi.bale.ai"


def redact_token(message: str, token: str = "") -> str:
    """Strip a bot token from provider error text before it is stored or logged."""
    if token:
        message = message.replace(token, "<redacted>").replace(token.replace(":", "%3A"), "<redacted>")
    return _BALE_TOKEN_RE.sub("<redacted>", message)


def _redact_token(message: str) -> str:
    return redact_token(message, getattr(settings, "bale_bot_token", "") or "")


class BaleSender:
    """Send messages through the Bale Bot API (per-user chat, no global fallback
    decision here — callers resolve the chat like the Telegram path does)."""

    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self._token = bot_token or getattr(settings, "bale_bot_token", "")
        self._chat_id = chat_id

    async def send(self, message: str) -> Result[bool]:
        """Send a text message (Markdown formatting, 1–4096 chars)."""
        if not self._token or not self._chat_id:
            return Result.fail("Bale bot token or chat ID not configured")
        url = f"{_BALE_API_BASE}/bot{self._token}/sendMessage"
        payload = {"chat_id": self._chat_id, "text": message[:4096]}
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                logger.info("Bale message sent")
                return Result.ok(True)
            except Exception as e:
                # httpx embeds the request URL — which contains the bot token —
                # in error text; never log or return it verbatim.
                safe = redact_token(str(e), self._token)
                logger.error("Failed to send Bale message: %s", safe)
                return Result.fail(safe)

    async def send_photo(self, photo_url: str, caption: str = "") -> Result[bool]:
        if not self._token or not self._chat_id:
            return Result.fail("Bale bot token or chat ID not configured")
        url = f"{_BALE_API_BASE}/bot{self._token}/sendPhoto"
        payload = {"chat_id": self._chat_id, "photo": photo_url, "caption": caption[:1024]}
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return Result.ok(True)
            except Exception as e:
                return Result.fail(redact_token(str(e), self._token))
