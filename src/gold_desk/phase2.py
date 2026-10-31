"""ماژول فاز ۲ طلا (ت پوشش بازار: تابلوی تهران، پلتفرم‌ها، بازدهی، نقشه صندوق) — است CB transición.

فقط برای حل import در api.py؛ توابع trả về پاسخ خالی معتبر Pydantic.
منطق واقعی بعداً تکمیل می‌شود.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TehranBoardResponse(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    source_status: Literal["not_connected", "partial", "live"] = "not_connected"
    data_gaps: list[dict[str, Any]] = Field(default_factory=list)
    as_of: datetime | None = None


class PlatformsResponse(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    source_status: Literal["not_connected", "partial", "live"] = "not_connected"
    capabilities: dict[str, Any] = Field(default_factory=dict)
    as_of: datetime | None = None


class ReturnsMatrixResponse(BaseModel):
    base_currency: Literal["IRR", "USD"] = "IRR"
    matrix: dict[str, Any] = Field(default_factory=dict)
    as_of: datetime | None = None


class FundMapResponse(BaseModel):
    size_metric: Literal["trade_value", "market_value"] = "trade_value"
    top_n: int = 10
    cells: list[dict[str, Any]] = Field(default_factory=list)
    as_of: datetime | None = None


async def load_tehran_board(session) -> TehranBoardResponse:
    """تابلو تهران — الردپ placeholder."""
    return TehranBoardResponse()


async def load_platforms(session) -> PlatformsResponse:
    """پلتفرم‌های آنلاین — الردپ placeholder."""
    return PlatformsResponse()


async def build_returns_matrix(session, base_currency: Literal["IRR", "USD"] = "IRR") -> ReturnsMatrixResponse:
    """ماتریس بازدهی — الردپ placeholder."""
    return ReturnsMatrixResponse(base_currency=base_currency)


async def build_fund_map(
    session, size_metric: Literal["trade_value", "market_value"] = "trade_value", top_n: int = 10
) -> FundMapResponse:
    """نقشه صندوق‌ها — الردپ placeholder."""
    return FundMapResponse(size_metric=size_metric, top_n=top_n)
