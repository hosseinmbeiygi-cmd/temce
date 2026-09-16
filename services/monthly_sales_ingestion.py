"""🏭 Monthly Sales Ingestion Service — واکشی و پارس گزارش ماهانه کدال.

بخش ۴.۱ معماری Enterprise سهام (Monthly Production & Sales Pipeline):
  ۱. یافتن اطلاعیه‌های «گزارش فعالیت ماهانه» از brsapi_codal_announcements
     (عناوین شامل «گزارش فعالیت ماهانه» / «گزارش ماهانه»).
  ۲. دانلود فایل Excel اطلاعیه از excel.codal.ir (با User-Agent فارسی-سازگار).
  ۳. پارس جدول‌های HTML-Table اکسل با اعداد فارسی/عربی → (محصول، مبلغ، تناژ، نرخ).
  ۴. محاسبه MoM/YoY بر اساس دوره جلالی (سال/ماه) و ثبت رکوردهای رکوردشکن.
  ۵. Upsert idempotent به stock_monthly_sales_production (یکتا روی symbol+year+month+product).

پارس فقط از فایل Excel رسمی کدال انجام می‌شود (No Scraping — Excel API رسمی).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from models.stock_enterprise import StockMonthlySalesModel

logger = get_logger(__name__)

# جدول کدال: HTML-table با اعداد فارسی؛ عنوان شمسی در سلول اول/دوم
_MONTH_MAP = {
    "فروردین": 1, "اردیبهشت": 2, "ارديبهشت": 2, "خرداد": 3,
    "تیر": 4, "مرداد": 5, "امرداد": 5, "شهریور": 6,
    "مهر": 7, "آبان": 8, "آذر": 9,
    "دی": 10, "بهمن": 11, "اسفند": 12,
}
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

_MONTHLY_TITLE_RX = re.compile(r"گزارش\s*(فعالیت\s*)?ماهانه")
_PERIOD_RX = re.compile(r"(?:ماه|منتهی\s+به)\s+(\d{4})/(\d{2})|(\d{4})/(\d{2})")
_PRODUCT_ROW_SKIP = re.compile(r"شرح|جمع کل|جمع|کل دوره|توضیحات|^$")


@dataclass
class MonthlySalesRow:
    product_name: str
    jalali_year: int
    jalali_month: int
    sales_amount: float | None = None
    sales_volume: float | None = None
    unit_price: float | None = None


@dataclass
class MonthlySalesSummary:
    processed: int = 0        # اطلاعیه‌های پردازش‌شده
    parsed_rows: int = 0      # ردیف‌های معتبر
    upserted: int = 0         # ردیف‌های ثبت/به‌روز شده
    errors: int = 0
    all_time_highs: int = 0
    skipped: int = 0
    details: list[str] = field(default_factory=list)


def _normalize_number(raw: str | None) -> float | None:
    """تبدیل عدد فارسی/عربی/حاوی کاما به float."""
    if raw is None:
        return None
    txt = str(raw).translate(_ARABIC_DIGITS).translate(_PERSIAN_DIGITS)
    txt = txt.replace(",", "").replace("،", "").strip()
    # پرانتز = عدد منفی حسابداری
    negative = txt.startswith("(") and txt.endswith(")")
    txt = txt.strip("()").strip()
    if not txt or not re.fullmatch(r"-?\d+(\.\d+)?", txt):
        return None
    val = float(txt)
    return -val if negative else val


def _extract_period(title: str) -> tuple[int, int] | None:
    """استخراج (سال، ماه) جلالی از عنوان اطلاعیه: «گزارش ماهانه منتهی به 1404/06»."""
    txt = title.translate(_PERSIAN_DIGITS).translate(_ARABIC_DIGITS)
    m = _PERIOD_RX.search(txt)
    if not m:
        return None
    year = int(m.group(1) or m.group(3))
    month = int(m.group(2) or m.group(4))
    if 1300 <= year <= 1500 and 1 <= month <= 12:
        return year, month
    return None


def _parse_workbook(content: bytes, period: tuple[int, int]) -> list[MonthlySalesRow]:
    """پارس اکسل گزارش ماهانه — جدول‌های HTML-style با اعداد فارسی."""
    try:
        import openpyxl
    except ImportError:  # pragma: no cover
        logger.warning("openpyxl not installed — monthly sales parse skipped")
        return []

    rows_out: list[MonthlySalesRow] = []
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    except Exception:
        logger.warning("codal monthly excel unreadable (probably HTML masquerading as xls)")
        return []

    year, month = period
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            if not row:
                continue
            cells = [str(c).strip() if c is not None else "" for c in row]
            # ستون اول = نام محصول؛ حداقل یک عدد بعد از آن
            name = cells[0].strip("‌ ").strip()
            if not name or _PRODUCT_ROW_SKIP.search(name) or len(cells) < 2:
                continue
            # سلول‌های عددی متوالی: [مبلغ فروش، تناژ/مقدار، نرخ فروش، ...]
            nums: list[float] = []
            for c in cells[1:6]:
                v = _normalize_number(c)
                if v is not None:
                    nums.append(v)
            if not nums:
                continue
            sales_amount = nums[0] if nums else None
            sales_volume = nums[1] if len(nums) > 1 else None
            unit_price = nums[2] if len(nums) > 2 else None
            rows_out.append(
                MonthlySalesRow(
                    product_name=name[:200],
                    jalali_year=year,
                    jalali_month=month,
                    sales_amount=sales_amount,
                    sales_volume=sales_volume,
                    unit_price=unit_price,
                )
            )
    return rows_out


class MonthlySalesIngestionService:
    """سرویس شبانه fill جدول stock_monthly_sales_production از اکسل کدال."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://codal.ir/",
                },
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── منبع اطلاعیه‌ها ──────────────────────────────────────────────────────

    async def _fetch_pending_announcements(self, limit: int) -> list:
        """اطلاعیه‌های ماهانه با لینک اکسل که هنوز import نشده‌اند."""
        m = self._model()
        rows = (
            await self.session.execute(
                select(
                    m.id,
                    m.symbol,
                    m.title,
                    m.link_excel,
                    m.link,
                )
                .where(self._title_filter())
                .where(self._excel_link_filter())
                .order_by(m.date_publish.desc())
                .limit(limit)
            )
        ).fetchall()
        return rows

    def _model(self):
        from brsapi.models.codal import CodalAnnouncementModel
        return CodalAnnouncementModel

    def _title_filter(self):
        from sqlalchemy import or_
        m = self._model()
        return or_(
            m.title.op("~")(r"گزارش\s*(فعالیت\s*)?ماهانه"),
            m.title.ilike("%ماهانه%"),
        )

    def _excel_link_filter(self):
        from sqlalchemy import and_
        m = self._model()
        return and_(
            m.link_excel.isnot(None),
            m.link_excel != "",
        )

    # ── چرخه اصلی ────────────────────────────────────────────────────────────

    async def run(self, *, limit: int = 100, symbol: str | None = None) -> MonthlySalesSummary:
        summary = MonthlySalesSummary()
        try:
            rows = await self._fetch_pending_announcements(limit)
        except Exception as exc:
            logger.error("monthly-sales fetch announcements failed: %s", exc)
            summary.errors += 1
            return summary

        client = await self._get_client()
        for row in rows:
            ann_id, ann_symbol, title, link_excel, link = row
            if symbol and ann_symbol and ann_symbol.upper() != symbol.upper():
                summary.skipped += 1
                continue
            period = _extract_period(title or "")
            if period is None:
                summary.skipped += 1
                continue

            url = link_excel or link
            if not url:
                summary.skipped += 1
                continue
            if not url.startswith("http"):
                url = f"https://codal.ir{url}"

            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    summary.errors += 1
                    continue
                parsed = _parse_workbook(resp.content, period)
            except Exception as exc:
                logger.debug("monthly-sales download failed %s: %s", url, exc)
                summary.errors += 1
                continue

            summary.processed += 1
            if not parsed:
                summary.skipped += 1
                continue

            for pr in parsed:
                upserted = await self._upsert_row(str(ann_symbol or "")[:50], pr, str(ann_id))
                if upserted:
                    summary.upserted += 1
                summary.parsed_rows += 1

        await self.session.flush()
        # رکوردهای تاریخی فروش (ATH) — بعد از همه upsertها
        summary.all_time_highs = await self._mark_all_time_highs()
        await self.session.flush()
        return summary

    async def _upsert_row(self, symbol: str, pr: MonthlySalesRow, codal_letter_id: str) -> bool:
        """Idempotent upsert به stock_monthly_sales_production + محاسبه MoM."""
        if not symbol:
            return False
        stmt = (
            pg_insert(StockMonthlySalesModel)
            .values(
                symbol=symbol,
                isin=None,
                jalali_year=pr.jalali_year,
                jalali_month=pr.jalali_month,
                product_name=pr.product_name,
                sales_amount=pr.sales_amount,
                sales_volume=pr.sales_volume,
                unit_price=pr.unit_price,
                sales_mom_pct=None,
                sales_yoy_pct=None,
                is_all_time_high=False,
                codal_letter_id=codal_letter_id,
            )
            .on_conflict_do_update(
                constraint="uq_stock_monthly_sales",
                set_={
                    "sales_amount": pr.sales_amount,
                    "sales_volume": pr.sales_volume,
                    "unit_price": pr.unit_price,
                    "codal_letter_id": codal_letter_id,
                },
            )
        )
        await self.session.execute(stmt)
        await self._compute_mom(symbol, pr)
        return True

    async def _compute_mom(self, symbol: str, pr: MonthlySalesRow) -> None:
        """محاسبه MoM/YoY برای یک ردیف تازه‌شده."""
        y, m = pr.jalali_year, pr.jalali_month
        prev_y, prev_m = (y - 1, 12) if m == 1 else (y, m - 1)
        base = (
            await self.session.execute(
                select(StockMonthlySalesModel.sales_amount)
                .where(StockMonthlySalesModel.symbol == symbol)
                .where(StockMonthlySalesModel.product_name == pr.product_name)
                .where(StockMonthlySalesModel.jalali_year == prev_y)
                .where(StockMonthlySalesModel.jalali_month == prev_m)
            )
        ).scalar_one_or_none()
        yoy = (
            await self.session.execute(
                select(StockMonthlySalesModel.sales_amount)
                .where(StockMonthlySalesModel.symbol == symbol)
                .where(StockMonthlySalesModel.product_name == pr.product_name)
                .where(StockMonthlySalesModel.jalali_year == y - 1)
                .where(StockMonthlySalesModel.jalali_month == m)
            )
        ).scalar_one_or_none()

        mom_pct = yoy_pct = None
        if base is not None and base != 0 and pr.sales_amount is not None:
            mom_pct = (pr.sales_amount - float(base)) / abs(float(base)) * 100.0
        if yoy is not None and yoy != 0 and pr.sales_amount is not None:
            yoy_pct = (pr.sales_amount - float(yoy)) / abs(float(yoy)) * 100.0

        if mom_pct is not None or yoy_pct is not None:
            await self.session.execute(
                StockMonthlySalesModel.__table__.update()
                .where(StockMonthlySalesModel.symbol == symbol)
                .where(StockMonthlySalesModel.product_name == pr.product_name)
                .where(StockMonthlySalesModel.jalali_year == y)
                .where(StockMonthlySalesModel.jalali_month == m)
                .values(sales_mom_pct=mom_pct, sales_yoy_pct=yoy_pct)
            )

    async def _mark_all_time_highs(self) -> int:
        """رکوردهای تاریخی: مبلغ فروش بالاتر از همه ماه‌های قبلی همان محصول."""
        from sqlalchemy import text as sa_text
        res = await self.session.execute(
            sa_text(
                """
                WITH ranked AS (
                    SELECT id,
                           sales_amount,
                           RANK() OVER (
                               PARTITION BY symbol, product_name
                               ORDER BY sales_amount DESC NULLS LAST,
                                        jalali_year DESC, jalali_month DESC
                           ) AS rnk
                    FROM stock_monthly_sales_production
                    WHERE sales_amount IS NOT NULL
                )
                UPDATE stock_monthly_sales_production m
                SET is_all_time_high = (ranked.rnk = 1)
                FROM ranked
                WHERE ranked.id = m.id AND m.is_all_time_high IS DISTINCT FROM (ranked.rnk = 1)
                """
            )
        )
        return res.rowcount or 0


__all__ = ["MonthlySalesIngestionService", "MonthlySalesSummary"]
