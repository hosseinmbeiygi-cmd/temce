from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CommodityClassification:
    category: str = ""
    sub_category: str = ""
    sector: str = ""
    industry: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
