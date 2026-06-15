from __future__ import annotations

from datetime import datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.manual import ManualDataProvider

logger = get_logger(__name__)


class ManualNewsProvider(ManualDataProvider):
    def __init__(self) -> None:
        super().__init__(name="manual_news")
        self._articles: list[dict[str, Any]] = []

    async def fetch(self, **kwargs: Any) -> Result[Any]:
        return Result.ok(self._articles)

    async def submit(self, data: dict[str, Any], **kwargs: Any) -> Result[dict[str, Any]]:
        validation = await self.validate(data)
        if not validation.success:
            return Result.fail(validation.error or "Validation failed")
        article = {
            **data,
            "submitted_at": datetime.utcnow().isoformat(),
            "status": "pending",
            "id": len(self._articles) + 1,
        }
        self._articles.append(article)
        logger.info("Manual news article submitted: %s", article.get("title", ""))
        return Result.ok(article)

    async def validate(self, data: dict[str, Any]) -> Result[bool]:
        if "title" not in data:
            return Result.fail("title is required")
        if "content" not in data:
            return Result.fail("content is required")
        return Result.ok(True)

    async def get_pending(self) -> Result[list[dict[str, Any]]]:
        return Result.ok([a for a in self._articles if a.get("status") == "pending"])

    async def health(self) -> dict[str, Any]:
        return {"healthy": True, "message": f"{len(self._articles)} articles"}
