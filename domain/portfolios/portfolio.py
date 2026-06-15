from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class Portfolio(BaseEntity):
    name: str
    owner_id: str = ""
    description: str = ""
    initial_capital: float = 0.0
    current_capital: float = 0.0
    cash: float = 0.0
    nav: float = 0.0
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    positions: list[Any] = field(default_factory=list)
    currency: str = "IRR"
    tags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        owner_id: str = "",
        description: str = "",
        initial_capital: float = 0.0,
        current_capital: float = 0.0,
        cash: float = 0.0,
        nav: float = 0.0,
        total_pnl: float = 0.0,
        total_return_pct: float = 0.0,
        positions: list[Any] | None = None,
        currency: str = "IRR",
        tags: list[str] | None = None,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.owner_id = owner_id
        self.description = description
        self.initial_capital = initial_capital
        self.current_capital = current_capital
        self.cash = cash
        self.nav = nav
        self.total_pnl = total_pnl
        self.total_return_pct = total_return_pct
        self.positions = positions or []
        self.currency = currency
        self.tags = tags or []
        self.extra = extra or {}
