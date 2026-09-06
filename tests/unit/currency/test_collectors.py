"""Live-collector parsing + per-venue fallback. No network (fake httpx client)."""
from __future__ import annotations

import pytest

from apps.currency_service.infra.collectors import (
    fetch_nobitex_usdt,
    fetch_tgju_dollar,
    parse_tgju_row,
)

# Real observed shape: [open, low, high, close, change, change%, greg, jalali]
TGJU_ROW_OK = [
    "6,145,000",
    "6,140,000",
    "6,180,000",
    "6,150,000",
    '<span class="high" dir="ltr">15000</span>',
    '<span class="high" dir="ltr">0.24%</span>',
    "2026-09-05",
    "1405-06-14",
]


class TestParseTgjuRow:
    def test_real_shape(self) -> None:
        close, open_, chg = parse_tgju_row(TGJU_ROW_OK)
        assert close == 615_000  # RIAL /10 -> Toman
        assert open_ == 614_500
        assert chg == 0.24

    def test_too_short_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_tgju_row(["1", "2"])

    def test_out_of_band_raises(self) -> None:
        bad = list(TGJU_ROW_OK)
        bad[3] = "999,999,999,999"  # absurd
        with pytest.raises(ValueError, match="sanity"):
            parse_tgju_row(bad)


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, payload=None, error=None, status=200):
        self._payload = payload
        self._error = error
        self._status = status

    async def get(self, url, **kw):
        if self._error:
            raise self._error
        return _FakeResp(self._payload, self._status)


class TestTgjuFetch:
    async def test_success(self) -> None:
        client = _FakeClient({"data": [TGJU_ROW_OK]})
        pair = await fetch_tgju_dollar(client)
        assert pair is not None
        assert pair.sell_price == 615_000
        assert pair.buy_price == 614_500
        assert "tgju" in pair.source

    async def test_http_error_returns_none(self) -> None:
        assert await fetch_tgju_dollar(_FakeClient(error=RuntimeError("boom"))) is None

    async def test_empty_data_returns_none(self) -> None:
        assert await fetch_tgju_dollar(_FakeClient({"data": []})) is None


class TestNobitexFetch:
    async def test_success(self) -> None:
        payload = {
            "stats": {
                "USDT-IRT": {
                    "buy": "619000",
                    "sell": "620000",
                    "last": "619500",
                    "dayOpenPrice": "615000",
                }
            }
        }
        pair = await fetch_nobitex_usdt(_FakeClient(payload))
        assert pair is not None
        assert pair.buy_price == 619_000
        assert pair.sell_price == 620_000
        assert pair.daily_change_pct == pytest.approx(0.73, abs=0.01)

    async def test_missing_pair_returns_none(self) -> None:
        assert await fetch_nobitex_usdt(_FakeClient({"stats": {}})) is None

    async def test_out_of_band_returns_none(self) -> None:
        payload = {"stats": {"USDT-IRT": {"buy": "1", "sell": "2", "last": "5", "dayOpenPrice": "5"}}}
        assert await fetch_nobitex_usdt(_FakeClient(payload)) is None
