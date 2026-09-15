from __future__ import annotations

from dataclasses import dataclass

from domain.common.events import DomainEvent


@dataclass
class InstrumentCreated(DomainEvent):
    instrument_id: str = ""
    symbol: str = ""
    name: str = ""


@dataclass
class InstrumentUpdated(DomainEvent):
    instrument_id: str = ""
    changes: list[str] = None


@dataclass
class InstrumentSuspended(DomainEvent):
    instrument_id: str = ""
    reason: str = ""


@dataclass
class InstrumentActivated(DomainEvent):
    instrument_id: str = ""


@dataclass
class InstrumentDelisted(DomainEvent):
    instrument_id: str = ""
    reason: str = ""


@dataclass
class InstrumentStatusChanged(DomainEvent):
    instrument_id: str = ""
    old_status: str = ""
    new_status: str = ""
