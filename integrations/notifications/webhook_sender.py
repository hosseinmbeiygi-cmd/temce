from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class WebhookSender:
    def __init__(self, secret: str = ""):
        self._secret = secret

    async def send(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
        method: str = "POST",
    ) -> Result[bool]:
        req_headers = headers or {}
        req_headers.setdefault("Content-Type", "application/json")
        if self._secret:
            import json

            body = json.dumps(payload, ensure_ascii=False, default=str)
            signature = hmac.new(self._secret.encode(), body.encode(), hashlib.sha256).hexdigest()
            req_headers["X-Signature"] = signature
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                if method.upper() == "POST":
                    resp = await client.post(url, json=payload, headers=req_headers)
                elif method.upper() == "PUT":
                    resp = await client.put(url, json=payload, headers=req_headers)
                else:
                    resp = await client.post(url, json=payload, headers=req_headers)
                resp.raise_for_status()
                logger.info("Webhook sent to %s with status %d", url, resp.status_code)
                return Result.ok(True)
            except httpx.HTTPError as e:
                logger.error("Webhook failed for %s: %s", url, e)
                return Result.fail(str(e))

    async def send_alert(self, url: str, alert_type: str, message: str, **extra: Any) -> Result[bool]:
        payload = {"type": "alert", "alert_type": alert_type, "message": message, **extra}
        return await self.send(url, payload)

    async def send_event(self, url: str, event: str, data: dict[str, Any]) -> Result[bool]:
        payload = {"type": "event", "event": event, "data": data}
        return await self.send(url, payload)
