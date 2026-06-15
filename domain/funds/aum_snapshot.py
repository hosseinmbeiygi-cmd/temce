from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class FundAumSnapshot(BaseEntity):
    fund_id: str
    snapshot_date: date | None = None
    aum: float = 0.0
    total_units: int = 0
    unit_price: float = 0.0
    inflow: float = 0.0
    outflow: float = 0.0
    net_flow: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        fund_id: str,
        snapshot_date: date | None = None,
        aum: float = 0.0,
        total_units: int = 0,
        unit_price: float = 0.0,
        inflow: float = 0.0,
        outflow: float = 0.0,
        net_flow: float = 0.0,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.fund_id = fund_id
        self.snapshot_date = snapshot_date
        self.aum = aum
        self.total_units = total_units
        self.unit_price = unit_price
        self.inflow = inflow
        self.outflow = outflow
        self.net_flow = net_flow
        self.extra = extra or {}
