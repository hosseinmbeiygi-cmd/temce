from __future__ import annotations

from core.logging import get_logger

logger = get_logger(__name__)


class AuthManager:
    def __init__(self) -> None:
        self._tokens: dict[str, str] = {}

    def set_token(self, service: str, token: str) -> None:
        self._tokens[service] = token

    def get_token(self, service: str) -> str | None:
        return self._tokens.get(service)

    def get_auth_header(self, service: str) -> dict[str, str]:
        token = self.get_token(service)
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}
