from __future__ import annotations

from typing import Any

from core.logging import get_logger
from integrations.http_client import HttpClient

logger = get_logger(__name__)


class WebhookClient:
    def __init__(self) -> None:
        self.http = HttpClient()

    async def send(self, url: str, payload: dict[str, Any]) -> bool:
        try:
            resp = await self.http.post(url, json=payload)
            logger.info("Webhook sent to %s: %d", url, resp.status_code)
            return resp.is_success
        except Exception as e:
            logger.error("Webhook failed to %s: %s", url, e)
            return False
