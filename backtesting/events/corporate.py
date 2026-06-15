from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    CAPITAL_INCREASE = "capital_increase"
    STOCK_SPLIT = "stock_split"
    REVERSE_SPLIT = "reverse_split"
    CASH_DIVIDEND = "cash_dividend"
    STOCK_DIVIDEND = "stock_dividend"
    IPO = "ipo"
    DELISTING = "delisting"
    SUSPENSION = "suspension"
    RESUMPTION = "resumption"
    TICKER_CHANGE = "ticker_change"
    NAME_CHANGE = "name_change"
    MERGER = "merger"
    ACQUISITION = "acquisition"
    RIGHTS_ISSUE = "rights_issue"
    ASSET_REVALUATION = "asset_revaluation"


@dataclass
class CorporateEvent:
    event_id: str
    instrument_id: str
    event_type: EventType
    event_date: date
    record_date: date | None = None
    pay_date: date | None = None
    ratio: float | None = None
    amount: float | None = None
    old_value: str | None = None
    new_value: str | None = None
    description: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def adjustment_factor(self) -> float:
        if self.event_type == EventType.CAPITAL_INCREASE and self.ratio:
            return self.ratio
        if self.event_type == EventType.STOCK_SPLIT and self.ratio:
            return self.ratio
        if self.event_type == EventType.REVERSE_SPLIT and self.ratio:
            return 1.0 / self.ratio
        if self.event_type == EventType.STOCK_DIVIDEND and self.ratio:
            return 1.0 + self.ratio
        if self.event_type == EventType.RIGHTS_ISSUE and self.ratio:
            return self.ratio
        return 1.0

    def price_adjustment(self, price_before: float) -> float:
        if self.event_type == EventType.CASH_DIVIDEND and self.amount:
            return price_before - self.amount
        factor = self.adjustment_factor()
        if factor != 1.0:
            return price_before / factor
        return price_before


class CorporateEventTracker:
    def __init__(self) -> None:
        self._events: dict[str, list[CorporateEvent]] = {}
        self._instrument_map: dict[str, str] = {}

    def add_event(self, event: CorporateEvent) -> None:
        if event.instrument_id not in self._events:
            self._events[event.instrument_id] = []
        self._events[event.instrument_id].append(event)
        self._events[event.instrument_id].sort(key=lambda e: e.event_date)

    def get_events(
        self,
        instrument_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
        event_type: EventType | None = None,
    ) -> list[CorporateEvent]:
        events = self._events.get(instrument_id, [])
        if start_date:
            events = [e for e in events if e.event_date >= start_date]
        if end_date:
            events = [e for e in events if e.event_date <= end_date]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events

    def get_all_events_between(self, start: date, end: date) -> list[CorporateEvent]:
        result: list[CorporateEvent] = []
        for _inst_id, events in self._events.items():
            for e in events:
                if start <= e.event_date <= end:
                    result.append(e)
        return result

    def get_adjustment_factor(self, instrument_id: str, from_date: date, to_date: date) -> float:
        factor = 1.0
        for event in self.get_events(instrument_id, from_date, to_date):
            factor *= event.adjustment_factor()
        return factor

    async def load_from_db(self, db: Any) -> None:
        rows = await db.fetch("SELECT * FROM corporate_events ORDER BY event_date")
        for row in rows:
            self.add_event(
                CorporateEvent(
                    event_id=str(row["id"]),
                    instrument_id=str(row["instrument_id"]),
                    event_type=EventType(row["event_type"]),
                    event_date=row["event_date"],
                    record_date=row.get("record_date"),
                    pay_date=row.get("pay_date"),
                    ratio=float(row["ratio"]) if row.get("ratio") else None,
                    amount=float(row["amount"]) if row.get("amount") else None,
                    old_value=row.get("old_value"),
                    new_value=row.get("new_value"),
                    description=row.get("description"),
                )
            )
