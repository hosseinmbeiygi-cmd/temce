"""Schemas برای مراحل ۱ و ۲ طلا (فیلدهای درخواست/پاسخ ماژول‌های phase1/phase2).

این فایل فقط برای حل import در ``src.gold_desk.api`` ساخته شده است؛ منطق واقعی
بعداً در ماژول‌های phase1/phase2 تکمیل می‌شود.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WhatIfRequest(BaseModel):
    """درخواست سناریو what-if: XAU/USD و دلار آزاد به ریال."""
    xau_usd: float = Field(..., gt=0)
    usd_irt_rial: float = Field(..., gt=0)


class WhatIfResponse(BaseModel):
    xau_usd: float
    usd_irt_rial: float
    intrinsic_value: float
    bubble_pct: float
    implied_usd: Optional[float] = None
    label: str = "SAMPLE"
    as_of: Optional[datetime] = None
