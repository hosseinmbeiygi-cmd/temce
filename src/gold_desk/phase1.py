"""ماژول فاز ۱ طلا (جداول تیکر، طلا، سکه، صندوق، گواهی) — است CB transición.

فقط برای حل import در api.py؛ توابع trả về پاسخ خالی معتبر Pydantic.
منطق واقعی बादاً تکمیل می‌شود.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TerminalCapabilities(BaseModel):
    orders: bool = False


class TerminalResponse(BaseModel):
    capabilities: TerminalCapabilities = Field(default_factory=TerminalCapabilities)
    data_gaps: list[dict[str, Any]] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    as_of: datetime | None = None


class WhatIfResponse(BaseModel):
    xau_usd: float
    usd_irt_rial: float
    intrinsic_value: float
    bubble_pct: float
    implied_usd: float | None = None
    label: str = "SAMPLE"
    as_of: datetime | None = None


async def build_terminal(session) -> TerminalResponse:
    """جدول فاز ۱ — الردپ placeholder (بدون منبع قیمت reais)."""
    return TerminalResponse()


async def build_what_if(session, xau_usd: float, usd_irt_rial: float) -> WhatIfResponse:
    """ماشین‌حساب سناریو — الردپ placeholder."""
    return WhatIfResponse(
        xau_usd=xau_usd,
        usd_irt_rial=usd_irt_rial,
        intrinsic_value=xau_usd * usd_irt_rial,
        bubble_pct=0.0,
    )
