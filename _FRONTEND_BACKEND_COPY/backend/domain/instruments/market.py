from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.common.base_entity import BaseEntity
from domain.common.enum_types import MarketType


@dataclass
class Market(BaseEntity):
    code: str
    name: str
    market_type: MarketType = MarketType.BOURS
    exchange_code: str = ""
    board_code: str = ""
    is_active: bool = True
    timezone: str = "Asia/Tehran"
    open_time: str = "09:00"
    close_time: str = "12:30"
    lunch_break_start: str | None = None
    lunch_break_end: str | None = None

    def __init__(
        self,
        id: str,
        code: str,
        name: str,
        market_type: MarketType = MarketType.BOURS,
        exchange_code: str = "",
        board_code: str = "",
        is_active: bool = True,
        timezone: str = "Asia/Tehran",
        open_time: str = "09:00",
        close_time: str = "12:30",
        lunch_break_start: str | None = None,
        lunch_break_end: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.code = code
        self.name = name
        self.market_type = market_type
        self.exchange_code = exchange_code
        self.board_code = board_code
        self.is_active = is_active
        self.timezone = timezone
        self.open_time = open_time
        self.close_time = close_time
        self.lunch_break_start = lunch_break_start
        self.lunch_break_end = lunch_break_end
