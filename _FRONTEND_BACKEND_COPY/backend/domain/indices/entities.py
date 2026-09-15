from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class Index(BaseEntity):
    name: str
    symbol: str = ""
    index_type: str = ""
    currency: str = "IRR"
    base_value: float = 100.0
    base_date: str = ""
    current_value: float = 0.0
    change_pct: float = 0.0
    member_count: int = 0
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        symbol: str = "",
        index_type: str = "",
        currency: str = "IRR",
        base_value: float = 100.0,
        base_date: str = "",
        current_value: float = 0.0,
        change_pct: float = 0.0,
        member_count: int = 0,
        is_active: bool = True,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.symbol = symbol
        self.index_type = index_type
        self.currency = currency
        self.base_value = base_value
        self.base_date = base_date
        self.current_value = current_value
        self.change_pct = change_pct
        self.member_count = member_count
        self.is_active = is_active
        self.extra = extra or {}


@dataclass
class IndexMember(BaseEntity):
    index_id: str
    instrument_id: str
    symbol: str = ""
    weight: float = 0.0
    sector: str = ""
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        index_id: str,
        instrument_id: str,
        symbol: str = "",
        weight: float = 0.0,
        sector: str = "",
        is_active: bool = True,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.index_id = index_id
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.weight = weight
        self.sector = sector
        self.is_active = is_active
        self.extra = extra or {}


@dataclass
class IndexValue(BaseEntity):
    index_id: str
    value: float = 0.0
    open_value: float = 0.0
    high_value: float = 0.0
    low_value: float = 0.0
    volume: int = 0
    date: str = ""
    time: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        index_id: str,
        value: float = 0.0,
        open_value: float = 0.0,
        high_value: float = 0.0,
        low_value: float = 0.0,
        volume: int = 0,
        date: str = "",
        time: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.index_id = index_id
        self.value = value
        self.open_value = open_value
        self.high_value = high_value
        self.low_value = low_value
        self.volume = volume
        self.date = date
        self.time = time
        self.extra = extra or {}
