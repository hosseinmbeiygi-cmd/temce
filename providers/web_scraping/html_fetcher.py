from __future__ import annotations

from core.logging import get_logger
from core.result import Result
from providers.base.http_client import HttpClient

logger = get_logger(__name__)


class HTMLFetcher(HttpClient):
    def __init__(self, timeout: int = 30) -> None:
        super().__init__(timeout=timeout)
        self._headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
            }
        )

    async def fetch_page(self, url: str) -> Result[str]:
        result = await self.get(url)
        if result.success and hasattr(result.value, "text"):
            return Result.ok(result.value.text)
        return Result.fail(result.error or "Failed to fetch page")

    async def fetch_page_with_retries(self, url: str, max_retries: int = 3) -> Result[str]:
        for attempt in range(max_retries):
            result = await self.fetch_page(url)
            if result.success:
                return result
            logger.warning("Fetch attempt %d/%d failed for %s", attempt + 1, max_retries, url)
            if attempt < max_retries - 1:
                import asyncio

                await asyncio.sleep(2**attempt)
        return Result.fail(f"Failed to fetch {url} after {max_retries} attempts")

    async def fetch_screenshot(self, url: str) -> Result[bytes]:
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle")
                screenshot = await page.screenshot()
                await browser.close()
                return Result.ok(screenshot)
        except ImportError:
            return Result.fail("Playwright is required for screenshots")
        except Exception as e:
            return Result.fail(f"Screenshot failed: {e}")
