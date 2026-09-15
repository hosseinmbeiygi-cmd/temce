from __future__ import annotations

import asyncio
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


try:
    from playwright.async_api import async_playwright

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


class BrowserPool:
    def __init__(self, max_browsers: int = 3, headless: bool = True) -> None:
        self.max_browsers = max_browsers
        self.headless = headless
        self._browsers: list[Any] = []
        self._available: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        if not HAS_PLAYWRIGHT:
            logger.warning("Playwright not installed; browser pool unavailable")
            return
        if self._initialized:
            return
        self._playwright = await async_playwright().start()
        for _ in range(self.max_browsers):
            browser = await self._playwright.chromium.launch(headless=self.headless)
            self._browsers.append(browser)
            await self._available.put(browser)
        self._initialized = True
        logger.info("Browser pool initialized with %d browsers", self.max_browsers)

    async def acquire(self) -> Any:
        if not HAS_PLAYWRIGHT or not self._initialized:
            return None
        return await self._available.get()

    async def release(self, browser: Any) -> None:
        if HAS_PLAYWRIGHT and self._initialized:
            await self._available.put(browser)

    async def close_all(self) -> None:
        if not HAS_PLAYWRIGHT:
            return
        for browser in self._browsers:
            await browser.close()
        self._browsers.clear()
        if hasattr(self, "_playwright"):
            await self._playwright.stop()
        self._initialized = False
        logger.info("Browser pool closed")

    async def health(self) -> dict[str, Any]:
        return {
            "available": self._available.qsize() if self._initialized else 0,
            "total": self.max_browsers,
            "initialized": self._initialized,
            "playwright_installed": HAS_PLAYWRIGHT,
        }
