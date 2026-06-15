from __future__ import annotations


class AuthHandler:
    def __init__(self, token: str = "", api_key: str = "", username: str = "", password: str = "") -> None:
        self.token = token
        self.api_key = api_key
        self.username = username
        self.password = password

    def get_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get_auth(self) -> tuple[str, str] | None:
        if self.username and self.password:
            return (self.username, self.password)
        return None
