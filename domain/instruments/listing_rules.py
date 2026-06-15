from __future__ import annotations

from domain.common.enum_types import InstrumentStatus


def can_trade(status: InstrumentStatus) -> bool:
    return status == InstrumentStatus.ACTIVE


def is_suspended(status: InstrumentStatus) -> bool:
    return status == InstrumentStatus.SUSPENDED


def is_halted(status: InstrumentStatus) -> bool:
    return status == InstrumentStatus.HALTED


def can_place_order(status: InstrumentStatus, is_market_open: bool) -> bool:
    return status == InstrumentStatus.ACTIVE and is_market_open
