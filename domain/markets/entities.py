from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class MarketSession(BaseEntity):
    market_code: str
    session_date: date | None = None
    open_time: str = ""
    close_time: str = ""
    pre_open_time: str = ""
    status: str = "closed"
    is_trading_day: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        market_code: str,
        session_date: date | None = None,
        open_time: str = "",
        close_time: str = "",
        pre_open_time: str = "",
        status: str = "closed",
        is_trading_day: bool = True,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.market_code = market_code
        self.session_date = session_date
        self.open_time = open_time
        self.close_time = close_time
        self.pre_open_time = pre_open_time
        self.status = status
        self.is_trading_day = is_trading_day
        self.extra = extra or {}

    def open_market(self) -> None:
        self.status = "open"
        self.mark_updated()

    def close_market(self) -> None:
        self.status = "closed"
        self.mark_updated()


@dataclass
class MarketHoliday(BaseEntity):
    market_code: str
    holiday_date: date | None = None
    name: str = ""
    description: str = ""
    is_recurring: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        market_code: str,
        holiday_date: date | None = None,
        name: str = "",
        description: str = "",
        is_recurring: bool = False,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.market_code = market_code
        self.holiday_date = holiday_date
        self.name = name
        self.description = description
        self.is_recurring = is_recurring
        self.extra = extra or {}
