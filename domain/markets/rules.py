from __future__ import annotations

from datetime import date

from domain.markets.entities import MarketSession


def is_market_open(session: MarketSession) -> bool:
    return session.status == "open"


def is_trading_day(session: MarketSession) -> bool:
    return session.is_trading_day


def can_trade(session: MarketSession) -> bool:
    return session.status == "open" and session.is_trading_day


def validate_session_times(open_time: str, close_time: str) -> bool:
    return open_time < close_time if open_time and close_time else False


def is_holiday(market_code: str, check_date: date) -> bool:
    return False
