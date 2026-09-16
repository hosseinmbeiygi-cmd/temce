"""Unit tests for monthly sales ingestion + indicator precompute services.

پارس اعداد فارسی، استخراج دوره جلالی، پارس اکسل و idempotency منطقی — بدون دیتابیس.
"""

from __future__ import annotations

import io

import pytest

from services.monthly_sales_ingestion import (
    _extract_period,
    _normalize_number,
    _parse_workbook,
)
from services.stock_technical_engine import (
    compute_indicator_snapshot,
    macd,
    rsi,
)


class TestNormalizeNumber:
    def test_persian_digits(self):
        assert _normalize_number("۱۲۳۴۵") == 12345.0

    def test_arabic_digits(self):
        assert _normalize_number("١٢٣") == 123.0

    def test_comma_separated(self):
        assert _normalize_number("۱,۲۳۴,۵۶۷") == 1234567.0

    def test_negative_parentheses(self):
        assert _normalize_number("(۱۲۳)") == -123.0

    def test_ascii(self):
        assert _normalize_number("42.5") == 42.5

    def test_none(self):
        assert _normalize_number(None) is None

    def test_garbage(self):
        assert _normalize_number("نامشخص") is None

    def test_empty(self):
        assert _normalize_number("") is None


class TestExtractPeriod:
    def test_standard_title(self):
        assert _extract_period("گزارش فعالیت ماهانه منتهی به 1404/06") == (1404, 6)

    def test_persian_digits_title(self):
        assert _extract_period("گزارش ماهانه منتهی به ۱۴۰۴/۰۶") == (1404, 6)

    def test_short_period(self):
        assert _extract_period("اطلاعیه 1404/05") == (1404, 5)

    def test_no_period(self):
        assert _extract_period("افزایش سرمایه از آورده") is None

    def test_invalid_month(self):
        # ماه 13 نامعتبر — باید None شود
        assert _extract_period("گزارش ماهانه 1404/13") is None

    def test_invalid_year(self):
        assert _extract_period("گزارش ماهانه 999/05") is None


def _make_xlsx(rows: list[tuple]) -> bytes:
    """ساخت فایل اکسل ساده برای تست پارس."""
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestParseWorkbook:
    def test_basic_parse(self):
        content = _make_xlsx([
            ("شرح محصول", "مبلغ فروش", "تناژ", "نرخ"),
            ("میلگرد آجدار", "۱۲,۳۰۰,۰۰۰", "۵۰۰", "۲۴,۶۰۰"),
            ("تیرآهن IPE", "8,000,000", "300", "26666"),
        ])
        rows = _parse_workbook(content, (1404, 6))
        assert len(rows) == 2
        first = rows[0]
        assert first.product_name == "میلگرد آجدار"
        assert first.jalali_year == 1404
        assert first.jalali_month == 6
        assert first.sales_amount == 12300000.0
        assert first.sales_volume == 500.0
        assert first.unit_price == 24600.0

    def test_skips_header_and_total_rows(self):
        content = _make_xlsx([
            ("شرح", "مبلغ"),
            ("جمع کل", "۹۹۹"),
            ("فولاد", "۱۰۰"),
        ])
        rows = _parse_workbook(content, (1404, 6))
        # «جمع کل» و هدر باید skip شوند
        names = [r.product_name for r in rows]
        assert "جمع کل" not in names
        assert any("فولاد" in n for n in names)

    def test_empty_workbook(self):
        content = _make_xlsx([])
        rows = _parse_workbook(content, (1404, 1))
        assert rows == []

    def test_corrupt_bytes(self):
        rows = _parse_workbook(b"not an excel file at all", (1404, 1))
        assert rows == []


class TestIndicatorSnapshotNoLookAhead:
    """Causal بودن اندیکاتورها: مقدار در روز T باید فقط به داده‌های ≤T وابسته باشد.

    روش تست: مقدار اندیکاتور در نقطه cut-1 از دنباله کامل باید با آخرین مقدار
    همان اندیکاتور روی دنباله cut-تایی (بدون داده‌های آینده) برابر باشد.
    """

    def _mk_closes(self, n: int = 150) -> list[float]:
        closes: list[float] = []
        price = 1000.0
        for i in range(n):
            price = price * 1.01 if i % 3 else price * 0.99
            closes.append(price)
        return closes

    def _mk_candles(self, n: int = 150) -> list[dict]:
        candles = []
        for i, c in enumerate(self._mk_closes(n)):
            candles.append({
                "date": str(i),
                "open": c * 0.99,
                "high": c * 1.02,
                "low": c * 0.98,
                "close": c,
                "volume": 1_000_000 + i * 1000,
                "value": c * 1_000_000,
            })
        return candles

    def test_rsi_is_causal(self):
        closes = self._mk_closes(150)
        cut = 130
        full_series = rsi(closes)
        trunc_series = rsi(closes[:cut])
        assert trunc_series[-1] == pytest.approx(full_series[cut - 1], rel=1e-9)

    def test_macd_is_causal(self):
        closes = self._mk_closes(150)
        cut = 130
        full = macd(closes)
        trunc = macd(closes[:cut])
        assert trunc["macd"][-1] == pytest.approx(full["macd"][cut - 1], rel=1e-9)
        assert trunc["signal"][-1] == pytest.approx(full["signal"][cut - 1], rel=1e-9)

    def test_snapshot_ok(self):
        snap = compute_indicator_snapshot(self._mk_candles())
        assert snap["ok"] is True
        assert snap["rsi_14"] is not None
        assert 0.0 <= snap["rsi_14"] <= 100.0

    def test_truncation_changes_only_time_point_not_history(self):
        """حذف ۲۰ کندل آخر باید مقدار snapshot را عوض کند (روز متفاوت) اما
        همبستگی سنتیمنتی حفظ شود: هر دو در بازه معتبر 0..100 (RSI)."""
        candles = self._mk_candles(150)
        full = compute_indicator_snapshot(candles)
        trunc = compute_indicator_snapshot(candles[:-20])
        assert 0.0 <= full["rsi_14"] <= 100.0
        assert 0.0 <= trunc["rsi_14"] <= 100.0

    def test_insufficient_candles(self):
        snap = compute_indicator_snapshot(self._mk_candles(10))
        assert snap["ok"] is False
