from __future__ import annotations

import contextlib
import time
from typing import Any
from urllib.parse import urlparse

from core.logging import get_logger

logger = get_logger(__name__)


class RobotsPolicy:
    def __init__(self, user_agent: str = "IranMarketBot/1.0") -> None:
        self.user_agent = user_agent
        self._rules: dict[str, dict[str, Any]] = {}
        self._crawl_delays: dict[str, float] = {}
        self._last_access: dict[str, float] = {}

    async def parse_robots(self, robots_content: str, domain: str) -> None:
        rules: dict[str, Any] = {"allow": [], "disallow": []}
        current_agent = "*"
        crawl_delay = 0.0

        for line in robots_content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("user-agent:"):
                current_agent = line.split(":", 1)[1].strip().lower()
            if current_agent in (self.user_agent.lower(), "*"):
                if line.lower().startswith("disallow:"):
                    path = line.split(":", 1)[1].strip()
                    rules["disallow"].append(path)
                elif line.lower().startswith("allow:"):
                    path = line.split(":", 1)[1].strip()
                    rules["allow"].append(path)
                elif line.lower().startswith("crawl-delay:"):
                    with contextlib.suppress(ValueError):
                        crawl_delay = float(line.split(":", 1)[1].strip())

        self._rules[domain] = rules
        self._crawl_delays[domain] = crawl_delay
        logger.info(
            "Parsed robots.txt for %s: %d disallow rules, %ds delay", domain, len(rules["disallow"]), crawl_delay
        )

    def is_allowed(self, url: str, domain: str | None = None) -> bool:
        if domain is None:
            domain = urlparse(url).netloc
        rules = self._rules.get(domain, {"allow": [], "disallow": []})
        path = urlparse(url).path or "/"

        if self._is_crawled_recently(domain):
            return False

        for allow_path in rules.get("allow", []):
            if path.startswith(allow_path):
                return True
        for disallow_path in rules.get("disallow", []):
            if disallow_path == "":
                return True
            if path.startswith(disallow_path):
                return False
        return True

    def _is_crawled_recently(self, domain: str) -> bool:
        delay = self._crawl_delays.get(domain, 0)
        if delay <= 0:
            return False
        last = self._last_access.get(domain, 0)
        return (time.time() - last) < delay

    def record_access(self, domain: str) -> None:
        self._last_access[domain] = time.time()

    def get_crawl_delay(self, domain: str) -> float:
        return self._crawl_delays.get(domain, 0)
