from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.auth import AuthHandler

logger = get_logger(__name__)


class BrokerageAuth(AuthHandler):
    def __init__(self, token: str = "", api_key: str = "", username: str = "", password: str = "") -> None:
        super().__init__(token=token, api_key=api_key, username=username, password=password)
        self._access_token: str | None = None
        self._refresh_token: str | None = None

    async def authenticate(self, login_url: str, credentials: dict[str, str]) -> Result[dict[str, Any]]:
        try:
            from providers.base.http_client import HttpClient

            client = HttpClient(base_url=login_url)
            result = await client.post("", json=credentials)
            if result.success and hasattr(result.value, "json"):
                data = result.value.json()
                self._access_token = data.get("access_token") or data.get("token")
                self._refresh_token = data.get("refresh_token")
                return Result.ok(data)
            return Result.fail("Authentication failed")
        except Exception as e:
            logger.error("Brokerage auth failed: %s", e)
            return Result.fail(str(e))

    def get_auth_headers(self) -> dict[str, str]:
        headers = self.get_headers()
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers
