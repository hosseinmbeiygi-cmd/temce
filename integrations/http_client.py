from __future__ import annotations

import time
from typing import Any

import httpx

from core.logging import get_logger

logger = get_logger(__name__)


class HttpClient:
    def __init__(self, base_url: str = "", timeout: float = 30.0, max_retries: int = 3) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    async def get(self, path: str, params: dict[str, Any] | None = None, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(url, params=params, **kwargs)
                    resp.raise_for_status()
                    return resp
            except Exception as e:
                logger.warning("GET %s failed (attempt %d/%d): %s", url, attempt + 1, self.max_retries, e)
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2**attempt)
        raise Exception(f"Request failed after {self.max_retries} retries")

    async def post(self, path: str, json: dict[str, Any] | None = None, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, json=json, **kwargs)
                    resp.raise_for_status()
                    return resp
            except Exception as e:
                logger.warning("POST %s failed (attempt %d/%d): %s", url, attempt + 1, self.max_retries, e)
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2**attempt)
        raise Exception(f"Request failed after {self.max_retries} retries")
