from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity
from domain.common.enum_types import AssetClass, InstrumentStatus, MarketType


@dataclass
class Instrument(BaseEntity):
    symbol: str
    name: str = ""
    isin: str = ""
    ins_code: str = ""
    industry_code: str = ""
    market_type: MarketType = MarketType.BOURS
    asset_class: AssetClass = AssetClass.EQUITY
    status: InstrumentStatus = InstrumentStatus.ACTIVE
    sector_code: str = ""
    group_code: str = ""
    sub_group_code: str = ""
    tick_size: float = 1.0
    lot_size: int = 1
    par_value: int = 1000
    eps: float = 0.0
    shares_count: int = 0
    base_volume: int = 0
    market_id: str = ""
    exchange_code: str = ""
    board_code: str = ""
    data_source: str = "tsetmc"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        symbol: str,
        name: str = "",
        isin: str = "",
        ins_code: str = "",
        industry_code: str = "",
        market_type: MarketType = MarketType.BOURS,
        asset_class: AssetClass = AssetClass.EQUITY,
        status: InstrumentStatus = InstrumentStatus.ACTIVE,
        sector_code: str = "",
        group_code: str = "",
        sub_group_code: str = "",
        tick_size: float = 1.0,
        lot_size: int = 1,
        par_value: int = 1000,
        eps: float = 0.0,
        shares_count: int = 0,
        base_volume: int = 0,
        market_id: str = "",
        exchange_code: str = "",
        board_code: str = "",
        data_source: str = "tsetmc",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.symbol = symbol
        self.name = name
        self.isin = isin
        self.ins_code = ins_code
        self.industry_code = industry_code
        self.market_type = market_type
        self.asset_class = asset_class
        self.status = status
        self.sector_code = sector_code
        self.group_code = group_code
        self.sub_group_code = sub_group_code
        self.tick_size = tick_size
        self.lot_size = lot_size
        self.par_value = par_value
        self.eps = eps
        self.shares_count = shares_count
        self.base_volume = base_volume
        self.market_id = market_id
        self.exchange_code = exchange_code
        self.board_code = board_code
        self.data_source = data_source
        self.tags = tags or []
        self.metadata = metadata or {}

    def suspend(self) -> None:
        self.status = InstrumentStatus.SUSPENDED
        self.mark_updated()

    def activate(self) -> None:
        self.status = InstrumentStatus.ACTIVE
        self.mark_updated()

    def delist(self) -> None:
        self.status = InstrumentStatus.DELISTED
        self.mark_updated()

    def update_eps(self, eps: float) -> None:
        self.eps = eps
        self.mark_updated()

    @property
    def p_e_ratio(self) -> float | None:
        return None

    def __repr__(self) -> str:
        return f"Instrument(symbol={self.symbol}, isin={self.isin})"
