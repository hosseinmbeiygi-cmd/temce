from __future__ import annotations

import asyncio

import httpx

from core.config import settings
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class SmsSender:
    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        sender_number: str = "",
        provider_url: str = "",
    ):
        self._api_key = api_key or getattr(settings, "sms_api_key", "")
        self._api_secret = api_secret or getattr(settings, "sms_api_secret", "")
        self._sender = sender_number or getattr(settings, "sms_sender", "")
        self._url = provider_url or getattr(settings, "sms_provider_url", "https://api.sms-provider.com/v1/send")
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(timeout=15.0)
            return self._client

    async def close(self) -> None:
        async with self._client_lock:
            if self._client is not None and not self._client.is_closed:
                await self._client.aclose()

    async def __aenter__(self) -> SmsSender:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def send(self, to: str | list[str], message: str) -> Result[bool]:
        recipients = [to] if isinstance(to, str) else to
        payload = {
            "sender": self._sender,
            "recipients": recipients,
            "message": message,
            "api_key": self._api_key,
        }
        client = await self._get_client()
        try:
            resp = await client.post(self._url, json=payload)
            resp.raise_for_status()
            logger.info("SMS sent to %s", ", ".join(recipients))
            return Result.ok(True)
        except httpx.HTTPError as e:
            logger.error("Failed to send SMS: %s", e)
            return Result.fail(str(e))

    async def send_alert(self, to: str | list[str], alert_type: str, message: str) -> Result[bool]:
        prefix = f"[{alert_type}] "
        return await self.send(to, prefix + message)
