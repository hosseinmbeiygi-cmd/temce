from __future__ import annotations

from domain.common.enum_types import InstrumentStatus


def calculate_base_volume(shares_count: int, avg_turnover: float, price: float) -> int:
    if price <= 0:
        return 0
    return int((shares_count * avg_turnover) / price)


def calculate_price_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100.0


def can_place_order(status: InstrumentStatus, has_sufficient_balance: bool) -> bool:
    return status == InstrumentStatus.ACTIVE and has_sufficient_balance


def suggest_reference_price(price_yesterday: float, tick_size: float) -> float:
    if tick_size <= 0:
        return price_yesterday
    return round(price_yesterday / tick_size) * tick_size
