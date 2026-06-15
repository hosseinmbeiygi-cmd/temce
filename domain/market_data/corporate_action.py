from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


class ActionType:
    CAPITAL_INCREASE = "capital_increase"
    CASH_DIVIDEND = "cash_dividend"
    STOCK_SPLIT = "stock_split"
    STOCK_REVERSE_SPLIT = "stock_reverse_split"
    RIGHTS_ISSUE = "rights_issue"
    SYMBOL_CHANGE = "symbol_change"
    MERGER = "merger"
    ACQUISITION = "acquisition"
    DELISTING = "delisting"


@dataclass
class CorporateAction(BaseEntity):
    instrument_id: str
    action_type: str
    symbol: str = ""
    date: date | None = None
    record_date: date | None = None
    pay_date: date | None = None
    ratio: float = 0.0
    value: float = 0.0
    description: str = ""
    is_adjusted: bool = False
    data_source: str = "codal"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        action_type: str,
        symbol: str = "",
        date: date | None = None,
        record_date: date | None = None,
        pay_date: date | None = None,
        ratio: float = 0.0,
        value: float = 0.0,
        description: str = "",
        is_adjusted: bool = False,
        data_source: str = "codal",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.action_type = action_type
        self.symbol = symbol
        self.date = date
        self.record_date = record_date
        self.pay_date = pay_date
        self.ratio = ratio
        self.value = value
        self.description = description
        self.is_adjusted = is_adjusted
        self.data_source = data_source
        self.extra = extra or {}

    @property
    def adjustment_factor(self) -> float:
        if self.action_type == ActionType.CAPITAL_INCREASE and self.ratio > 0:
            return 1.0 + self.ratio
        if self.action_type == ActionType.STOCK_SPLIT and self.ratio > 0:
            return 1.0 / self.ratio
        if self.action_type == ActionType.STOCK_REVERSE_SPLIT and self.ratio > 0:
            return self.ratio
        return 1.0
