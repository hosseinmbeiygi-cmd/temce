from __future__ import annotations

from datetime import time


def test_market_session_bours_open():
    from core.time.market_sessions import MarketSession

    session = MarketSession()
    open_time = time(9, 0)
    close_time = time(12, 30)
    assert session.is_open(open_time, close_time, current_time=time(10, 0)) is True


def test_market_session_bours_closed():
    from core.time.market_sessions import MarketSession

    session = MarketSession()
    open_time = time(9, 0)
    close_time = time(12, 30)
    assert session.is_open(open_time, close_time, current_time=time(14, 0)) is False


def test_market_session_before_open():
    from core.time.market_sessions import MarketSession

    session = MarketSession()
    open_time = time(9, 0)
    close_time = time(12, 30)
    assert session.is_open(open_time, close_time, current_time=time(8, 0)) is False


def test_market_session_pre_open():
    from core.time.market_sessions import MarketSession

    session = MarketSession()
    assert session.is_pre_open(current_time=time(8, 30)) is True
    assert session.is_pre_open(current_time=time(9, 30)) is False


def test_market_session_post_close():
    from core.time.market_sessions import MarketSession

    session = MarketSession()
    assert session.is_post_close(current_time=time(13, 0)) is True
    assert session.is_post_close(current_time=time(10, 0)) is False


def test_market_session_weekend():
    from core.time.market_sessions import MarketSession

    session = MarketSession()
    assert session.is_weekend("Friday") is True
    assert session.is_weekend("Saturday") is False

