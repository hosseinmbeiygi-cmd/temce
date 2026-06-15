from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import PaginatedResult, Result
from domain.analytics.recommendation import Recommendation
from domain.common.enum_types import RecommendationAction
from repositories.recommendation_repository import RecommendationRepository

logger = get_logger(__name__)


class RecommendationService:
    def __init__(self, repo: RecommendationRepository | None = None, session: AsyncSession | None = None) -> None:
        self.repo = repo or RecommendationRepository(session=session)

    async def create(self, instrument_id: str, action: RecommendationAction, **kwargs: Any) -> Result[Recommendation]:
        if not isinstance(action, RecommendationAction):
            action = RecommendationAction(action)
        rec = Recommendation(id=new_id("rec"), instrument_id=instrument_id, action=action, **kwargs)
        return await self.repo.save(rec)

    async def get_active(self, instrument_id: str) -> Result[list[Recommendation]]:
        return await self.repo.get_active(instrument_id)

    async def list(self, page: int = 1, page_size: int = 50) -> Result[PaginatedResult[Recommendation]]:
        return await self.repo.list(page, page_size)

    async def generate(self, symbols: list[str], strategy: str = "value") -> Result[list[dict[str, Any]]]:
        return Result.ok([])

    async def list_recommendations(self) -> Result[dict[str, Any]]:
        return Result.ok({"items": [], "total": 0})

    async def get_recommendation(self, recommendation_id: str) -> Result[dict[str, Any] | None]:
        return Result.ok(None)

    async def get_by_symbol(self, symbol: str) -> Result[list[dict[str, Any]]]:
        return Result.ok([])

    def list_strategies(self) -> list[str]:
        return ["value", "growth", "momentum", "income"]
