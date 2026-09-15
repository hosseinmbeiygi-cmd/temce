"""تست‌های integration: Adapterها + Circuit Breaker.

Adapterها با mock HTTP (بدون شبکه واقعی) تست می‌شوند.
"""

from __future__ import annotations

import asyncio

import pytest

from apps.funds.adapters.base import AdapterParseError
from apps.funds.adapters.fipiran import FipiranAdapter
from apps.funds.adapters.tsetmc import TSETMCAdapter
from apps.funds.resilience import (
    CircuitOpenError,
    get_circuit_breaker,
    reset_circuit_breakers,
)


class FakeResponse:
    def __init__(self, text: str = "", json_data: object | None = None):
        self.text = text
        self._json = json_data

    def json(self):
        if isinstance(self._json, dict) and "_raise" in self._json:
            raise ValueError("boom")
        return self._json


class FakeHTTP:
    """mock HTTP client — پاسخ قابل برنامه‌ریزی."""

    def __init__(self, market_watch_text: str = "", json_payload: object | None = None):
        self.market_watch_text = market_watch_text
        self.json_payload = json_payload
        self.calls = 0
        self.fail_next = 0  # چند درخواست اول باید fail شوند

    async def get(self, url: str, **kwargs):
        self.calls += 1
        if self.fail_next > 0:
            self.fail_next -= 1
            raise ConnectionError("network down")
        if "MarketWatch" in url:
            return FakeResponse(text=self.market_watch_text)
        if "clienttype" in url:
            return FakeResponse(text="100,50;60,40;10,20;30,40;")
        return FakeResponse(json_data=self.json_payload)


def _market_watch_row(symbol: str, last: int, vol: int) -> str:
    fields = ["0"] * 19
    fields[2] = f"صندوق {symbol}"
    fields[3] = symbol
    fields[6] = str(last)
    fields[7] = str(last)
    fields[9] = str(vol)
    fields[10] = str(last * vol)
    fields[18] = "68"
    return ",".join(fields)


def test_tsetmc_parse_market_watch():
    row = _market_watch_row("اهرم", 21000, 1000)
    http = FakeHTTP(market_watch_text="header;" + row + ";")
    adapter = TSETMCAdapter(http_client=http)

    result = asyncio.run(adapter.get("اهرم"))
    assert result.source == "tsetmc"
    assert result.data["last_price"] == 21000
    assert result.data["volume"] == 1000
    assert result.data["group_id"] == "68"


def test_tsetmc_symbol_not_found_raises():
    http = FakeHTTP(market_watch_text=";".join([_market_watch_row("اهرم", 1, 1)]))
    adapter = TSETMCAdapter(http_client=http)
    with pytest.raises(AdapterParseError):
        asyncio.run(adapter.get("طلا"))


def test_fipiran_parse_json():
    payload = {
        "symbol": "کارین",
        "name": "صندوق کارین",
        "navRedempt": 10230.5,
        "netAsset": 48000.0,
    }
    adapter = FipiranAdapter(http_client=FakeHTTP(json_payload=payload))
    result = asyncio.run(adapter.get("کارین"))
    assert result.data["nav_redeem"] == 10230.5
    assert result.data["aum_btoman"] == 48000.0


def test_fipiran_parse_error():
    adapter = FipiranAdapter(http_client=FakeHTTP(json_payload={"_raise": True}))
    with pytest.raises(AdapterParseError):
        asyncio.run(adapter.get("کارین"))


def test_circuit_breaker_opens_after_5_failures():
    reset_circuit_breakers()
    cb = get_circuit_breaker("test-source")

    async def failing():
        raise ConnectionError("boom")

    async def run():
        # ۵ خطای متوالی → OPEN
        for _ in range(5):
            with pytest.raises(ConnectionError):
                await cb.call(failing)
        assert (await cb.state()).value == "open"
        # درخواست بعدی → CircuitOpenError بدون تماس با func
        with pytest.raises(CircuitOpenError):
            await cb.call(failing)
        assert (await cb.state()).value == "open"

    asyncio.run(run())


def test_circuit_breaker_recovers_after_open_duration():
    reset_circuit_breakers()
    cb = get_circuit_breaker("test-source2")

    async def failing():
        raise ConnectionError("boom")

    async def success():
        return "ok"

    async def run():
        for _ in range(5):
            with pytest.raises(ConnectionError):
                await cb.call(failing)
        # شبیه‌سازی گذر زمان ۵ دقیقه (باز شدن در گذشته)
        import time as _time

        cb._stats.opened_at = _time.monotonic() - 301
        # half-open → یک درخواست آزمایشی
        result = await cb.call(success)
        assert result == "ok"
        assert (await cb.state()).value == "closed"

    asyncio.run(run())


def test_adapter_stale_flag():
    adapter = FipiranAdapter(http_client=FakeHTTP(json_payload={"symbol": "X"}))
    adapter.last_success = None  # هرگز sync نشده
    assert adapter._check_stale() is True

    from datetime import datetime, timedelta

    adapter.last_success = datetime.utcnow() - timedelta(hours=30)
    assert adapter._check_stale() is True

    adapter.last_success = datetime.utcnow() - timedelta(hours=1)
    assert adapter._check_stale() is False


def test_retry_backoff():
    from apps.funds.resilience import retry

    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("boom")
        return "done"

    result = asyncio.run(retry(flaky, max_attempts=3, base_delay=0.001)())
    assert result == "done"
    assert calls["n"] == 3
