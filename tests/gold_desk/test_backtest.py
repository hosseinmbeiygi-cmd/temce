"""تست Backtest — حباب تکنیکال باید فقط گذشته را ببیند (C2)."""

from __future__ import annotations

import asyncio

import numpy as np
import pytest

from src.gold_desk.backtest import _daily_bubble_pct


class _Res:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _Session:
    def __init__(self, rows):
        self._rows = rows

    async def execute(self, _stmt):
        return _Res(self._rows)


def _rows(n: int = 70, start: float = 100.0):
    """n ردیف با تاریخ صعودی شمسی‌نما و قیمت‌های پله‌ای."""
    return [(f"1405-01-{i:02d}", start + i) for i in range(n)]


def test_daily_bubble_is_trailing_not_centered():
    """میانگین پنجره باید prices[i-29:i+1] باشد، نه پنجرهٔ centered حول i."""
    rows = _rows(70)  # قیمت‌ها 100..169
    out = asyncio.run(_daily_bubble_pct(_Session(rows), "IR_COIN_EMAMI", 90))
    assert out, "برای ۷۰ ردیف باید نمونهٔ معتبر تولید شود"

    prices = np.array([p for _, p in rows], dtype=float)
    # اولین ایندکس مجاز i=30 است (i<30 رد می‌شود)
    i = 30
    mean_trailing = prices[i - 29 : i + 1].mean()
    expected = (prices[i] - mean_trailing) / mean_trailing * 100.0
    assert out[0][1] == pytest.approx(expected)


def test_daily_bubble_rejects_lookahead_shape():
    """با قیمت صعودی خطی، حباب trailing کوچک‌تر از پنجرهٔ centered است."""
    rows = _rows(70)
    out = asyncio.run(_daily_bubble_pct(_Session(rows), "IR_COIN_EMAMI", 90))
    assert out[0][1] < 15.0


def test_daily_bubble_returns_empty_for_short_history():
    assert asyncio.run(_daily_bubble_pct(_Session(_rows(10)), "IR_COIN_EMAMI", 90)) == []
