from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TradingSessionConfig:
    market_code: str = ""
    session_type: str = "regular"
    open_time: str = ""
    close_time: str = ""
    pre_open_time: str = ""
    pre_open_duration_minutes: int = 0
    lunch_break_start: str = ""
    lunch_break_end: str = ""
    max_price_change_pct: float = 0.0
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
