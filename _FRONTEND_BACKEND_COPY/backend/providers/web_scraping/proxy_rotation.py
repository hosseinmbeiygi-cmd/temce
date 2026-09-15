from __future__ import annotations

import random
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class Proxy:
    def __init__(self, url: str, username: str = "", password: str = "") -> None:
        self.url = url
        self.username = username
        self.password = password
        self.failures: int = 0
        self.last_used: float = 0.0
        self.enabled: bool = True

    def auth_string(self) -> str:
        if self.username and self.password:
            return f"http://{self.username}:{self.password}@{self.url}"
        return self.url

    def mark_failure(self) -> None:
        self.failures += 1
        if self.failures >= 5:
            self.enabled = False
            logger.warning("Proxy disabled after %d failures: %s", self.failures, self.url)

    def mark_success(self) -> None:
        self.failures = 0


class ProxyRotation:
    def __init__(self, proxies: list[Proxy] | None = None) -> None:
        self._proxies = proxies or []
        self._current_index: int = 0

    def add_proxy(self, proxy: Proxy) -> None:
        self._proxies.append(proxy)

    def remove_proxy(self, url: str) -> None:
        self._proxies = [p for p in self._proxies if p.url != url]

    def get_next(self) -> Proxy | None:
        enabled = [p for p in self._proxies if p.enabled]
        if not enabled:
            logger.warning("No enabled proxies available")
            return None
        proxy = random.choice(enabled)
        proxy.last_used = __import__("time").time()
        return proxy

    def get_round_robin(self) -> Proxy | None:
        enabled = [p for p in self._proxies if p.enabled]
        if not enabled:
            return None
        proxy = enabled[self._current_index % len(enabled)]
        self._current_index = (self._current_index + 1) % len(enabled)
        return proxy

    def mark_failure(self, proxy: Proxy) -> None:
        proxy.mark_failure()

    def mark_success(self, proxy: Proxy) -> None:
        proxy.mark_success()

    def health(self) -> dict[str, Any]:
        return {
            "total": len(self._proxies),
            "enabled": len([p for p in self._proxies if p.enabled]),
            "disabled": len([p for p in self._proxies if not p.enabled]),
        }
