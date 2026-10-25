"""تست های رگرسیون برای باگ های بحرانی گزارش طلا و صندوق ها.

این تست ها رفتار درست را قفل می کنند (GS-01 تا GS-05 رفع شده اند) و به عنوان
نگهبان رگرسیون اجرا می شوند.

پوشش:
  GS-01  ستون NAV در ORM
  GS-02  سقف امتیاز قابل دسترس در برابر آستانه YELLOW
  GS-03  تقویم تاریخ در بک تست طلا
  GS-04  مسیر holdings_missing در موتور NAV
  GS-05  واحد مثقال برای طلای آب شده

این فایل هیچ فایل موجودی را تغییر نمی دهد و هیچ اتصالی به DB زنده لازم ندارد.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.fund_nav_engine import FundNavEngine  # noqa: E402
from src.gold_desk import nav_checker, pricer  # noqa: E402
from src.gold_desk.backtest import _daily_bubble_pct  # noqa: E402
from src.gold_desk.backtest_real import _fetch_daily_data  # noqa: E402
from src.gold_desk.backtest_runner import _fetch_daily_closes  # noqa: E402
from src.gold_desk.bubbler import calc_bubble  # noqa: E402
from src.gold_desk.constants import (  # noqa: E402
    SCORE_GREEN_MIN,
    SCORE_YELLOW_MIN,
    VALID_BUBBLE_PCT_RANGE,
)
from src.gold_desk.scorer import compute_score  # noqa: E402

ISO_DATE_RE = re.compile(r"^(\d{4})-\d{2}-\d{2}$")

# ── کمک‌تابع‌های بدون DB ────────────────────────────────────────────────────


class _FakeResult:
    """نتیجهٔ جعلی SQLAlchemy برای یک کوئری SELECT."""

    def __init__(self, rows=(), row=None):
        self._rows = list(rows)
        self._row = row

    def all(self):
        return list(self._rows)

    def fetchall(self):
        return list(self._rows)

    def first(self):
        return self._row

    def scalar(self):
        return self._row[0] if self._row else None


class _CapturingSession:
    """session جعلی که statement اجراشده را نگه می‌دارد و ردیف‌های داده‌شده را برمی‌گرداند."""

    def __init__(self, rows=(), row=None):
        self.rows = list(rows)
        self.row = row
        self.statements: list[object] = []

    async def execute(self, stmt, *_args, **_kwargs):
        self.statements.append(stmt)
        return _FakeResult(self.rows, self.row)


class _ScriptedSession:
    """session جعلی که بر اساس متن SQL، پاسخ از پیش تعیین‌شده برمی‌گرداند."""

    def __init__(self, by_table: dict[str, _FakeResult]):
        self._by_table = by_table
        self.queries: list[str] = []

    async def execute(self, stmt, *_args, **_kwargs):
        sql = str(stmt)
        self.queries.append(sql)
        for table, result in self._by_table.items():
            if table in sql:
                return result
        raise AssertionError(f"کوئری پیش‌بینی‌نشده در تست: {sql[:160]}")


def _jalali_rows(n: int = 60) -> list[tuple[str, float]]:
    """ردیف‌های تاریخچه با تاریخ شمسی — همان قالبی که در `brsapi_gold_coin_history` ذخیره می‌شود."""
    rows: list[tuple[str, float]] = []
    for month in (5, 6):
        for day in range(1, 29):
            rows.append((f"1405-{month:02d}-{day:02d}", 100_000_000.0 + len(rows) * 1_000_000.0))
    return rows[:n]


def _cutoff_literal(stmt) -> str:
    """رشتهٔ تاریخ که در WHERE مقایسه می‌شود (پارامتر bind شده)."""
    params = stmt.compile().params
    dated = [v for v in params.values() if isinstance(v, str) and ISO_DATE_RE.match(v)]
    assert len(dated) == 1, f"انتظار یک پارامتر تاریخ در کوئری، دریافت: {params}"
    return dated[0]


# ── GS-01 — ستون NAV در ORM ────────────────────────────────────────────────


async def test_latest_nav_returns_a_value_when_the_source_has_one():
    """`_latest_nav` باید مقدار NAV را برگرداند وقتی منبع داده یک ردیف دارد.

    باگ: ``select(NavRecordModel.nav)`` پیش از هر کوئری ``AttributeError`` می‌دهد،
    خطا در ``except Exception`` بی‌صدا خورده می‌شود و تابع ``None`` برمی‌گرداند —
    در نتیجه هر ۱۰ صندوق طلا از snapshot حذف می‌شوند (اجرای واقعی روی DB: ۰ از ۱۰).
    این تست عمداً «نحوهٔ رفع» را قفل نمی‌کند: خواندن ``nav_issue`` یا هر نگاشت
    درست دیگری آن را سبز می‌کند.
    """
    session = _CapturingSession(row=(1_234_567.0,))
    nav = await nav_checker._latest_nav(session, "عیار")
    assert nav is not None, "_latest_nav مقدار None برگرداند؛ منبع NAV بی‌صدا از دست می‌رود"
    assert nav == pytest.approx(1_234_567.0)


# ── GS-02 — سقف امتیاز قابل‌دسترس ──────────────────────────────────────────


async def test_scorer_can_reach_green_with_a_fully_wired_market_state():
    """دارایی‌های امتیازدهی خودشان سالم‌اند: با داده کامل، GREEN قابل‌دسترس است.

    این تست در وضعیت فعلی **سبز** است و نقش کنترل دارد: ثابت می‌کند مشکل در
    حساب امتیاز نیست، بلکه در وصل‌نبودن منابع داده است.
    """
    result = compute_score(
        bubble_pct=0.0,
        nav_bubble_pct=0.0,
        bpr=10.0,
        net_inflow=1e12,
        xau_rsi=40.0,
        aed_gap_pct=0.0,
        nav_7d_pct=5.0,
    )
    assert result.total >= SCORE_GREEN_MIN
    assert result.decision == "GREEN"


async def test_reachable_score_can_clear_the_yellow_threshold():
    """بالاترین امتیازی که با منابع داده‌ای «وصل‌شدهٔ امروز» قابل تولید است باید از RED عبور کند.

    ورودی‌های این تست همان چیزهایی است که ``build_snapshot`` واقعاً می‌تواند تأمین کند
    (شاهد: اجرای زنده در پیوست گزارش — ``technical``/``nav``/``fund_flow`` همیشه صفر).
    اگر منبعی وصل شود، این تست هم باید به‌روز شود و همین arbitrariness عمدی است:
    تصمیم دربارهٔ «آستانه در برابر منابع» نباید بی‌صدا باقی بماند.
    """
    reachable = compute_score(
        bubble_pct=0.0,  # از coin_emami (وصل)
        nav_bubble_pct=None,  # nav_checker امروز هیچ صندوقی برنمی‌گرداند (GS-01)
        bpr=10.0,  # tsetmc (وصل)
        net_inflow=1e18,
        xau_rsi=None,  # XAUUSD در brsapi_gold_coin_history صفر ردیف دارد (GS-06)
        aed_gap_pct=0.0,  # parity (وصل)
        nav_7d_pct=None,  # همان منبع NAV
    )
    assert reachable.total >= SCORE_YELLOW_MIN, (
        f"سقف امتیاز قابل‌دسترس {reachable.total} است ولی آستانهٔ YELLOW {SCORE_YELLOW_MIN} — "
        "تصمیم هرگز YELLOW/GREEN نمی‌شود"
    )


# ── GS-03 — تقویم تاریخ در بک‌تست طلا ───────────────────────────────────────


@pytest.mark.parametrize(
    ("fetcher", "name"),
    [
        (_daily_bubble_pct, "gold_desk.backtest._daily_bubble_pct"),
        (_fetch_daily_data, "gold_desk.backtest_real._fetch_daily_data"),
        (_fetch_daily_closes, "gold_desk.backtest_runner._fetch_daily_closes"),
    ],
)
async def test_history_cutoff_matches_the_stored_calendar(fetcher, name):
    """مقدار مقایسه‌شده با تاریخچه باید با تقویم دادهٔ ذخیره‌شده بخواند.

    شاهد گزارش: ``brsapi_gold_coin_history.date`` شمسی است (نمونهٔ واقعی
    ``'1405-06-23'``، اسکریپت واردکننده: «OHLC data … with Persian dates») و
    cutoff کد ``'2026-05-14'`` می‌سازد؛ اجرای واقعی همان predicate → ۰ ردیف از ۴۸۶۹.

    این تست «نحوهٔ رفع» را تحمیل نمی‌کند: تبدیل cutoff به تقویم شمسی یا مقایسه با
    ستون میلادی (``gregorian_date``) هر دو آن را سبز می‌کنند.
    """
    session = _CapturingSession(rows=_jalali_rows())
    await fetcher(session, "IR_COIN_EMAMI", 90)

    assert session.statements, f"{name} هیچ کوئری اجرا نکرد"
    cutoff = _cutoff_literal(session.statements[0])
    statement_text = str(session.statements[0])
    uses_gregorian_column = "gregorian_date" in statement_text

    year = int(cutoff[:4])
    assert uses_gregorian_column or 1300 <= year <= 1499, (
        f"{name}: cutoff میلادی {cutoff!r} با ستون تاریخ شمسی مقایسه می‌شود "
        "(ستون شمسی هرگز با رشتهٔ میلادی مطابقت نمی‌کند)"
    )


# ── GS-04 — NAV در مسیر holdings_missing ───────────────────────────────────


async def test_nav_regression_from_report_net_assets_does_not_subtract_liabilities_twice():
    """در نبود ریز موقعیت‌ها، NAV موتور باید همان NAV گزارش دوره باشد.

    اعداد نمونه: دارایی ۱B، بدهی ۱۰۰M، ۱M واحد → NAV درست ۹۰۰ و مسیر باگ‌دار ۸۰۰ (‎−۱۱.۱٪‎).
    """
    total_assets = 1_000_000_000.0
    total_liabilities = 100_000_000.0
    net_asset_value = total_assets - total_liabilities
    units = 1_000_000
    valuation_date = date(2026, 9, 20)

    session = _ScriptedSession(
        {
            "fund_holdings": _FakeResult(rows=[]),  # هیچ ریز موقعیتی موجود نیست
            "fund_portfolio_reports": _FakeResult(
                row=(
                    valuation_date,
                    total_assets,
                    total_liabilities,
                    net_asset_value,
                    units,
                    None,  # cash_and_equivalents
                )
            ),
        }
    )
    engine = FundNavEngine(session)  # type: ignore[arg-type]
    payload = await engine._build_payload("tse:TEST", valuation_date, "STATISTICAL", "SHADOW")

    assert "holdings_missing_used_report_net_assets" in payload.warnings
    assert payload.units == units
    # ۱) NAV باید برابر NAV گزارش دوره باشد، نه «NAV گزارش − بدهی»
    assert payload.net_assets == pytest.approx(net_asset_value), (
        f"net_assets={payload.net_assets} در حالی که NAV گزارش دوره {net_asset_value} است"
    )
    # ۲) و NAV هر واحد باید همان نسبت باشد
    assert payload.nav_per_unit == pytest.approx(net_asset_value / units)


# ── GS-05 — واحد مثقال برای طلای آب‌شده ────────────────────────────────────


XAU_USD = 4346.66
USD_IRT = 265_100.0
MELTED_MARKET_IRT = 114_669_000.0  # قیمت واقعی بازار در اجرای زندهٔ گزارش


def test_melted_gold_fair_value_is_quoted_in_the_same_unit_as_the_market():
    """ارزش ذاتی «طلای آب‌شده» باید هم‌واحد با قیمت بازار باشد (مثقال، نه گرم).

    باگ شاهد: ``MESGHAL_GRAMS = 4.6083`` در ``constants.py`` تعریف شده و هیچ‌جا
    استفاده نمی‌شود؛ برای همین fair یک گرم است و حباب +۳۱۲.۶۵٪ گزارش می‌شود.
    """
    from src.gold_desk.constants import MESGHAL_GRAMS

    fair = pricer.fair_value("IR_GOLD_MELTED", XAU_USD, USD_IRT)
    per_gram_18k = pricer.fair_gold_18k(XAU_USD, USD_IRT)
    assert fair == pytest.approx(MESGHAL_GRAMS * per_gram_18k, rel=1e-9), (
        f"fair={fair:,.0f} در حالی که هر مثقال ۱۸ عیار {MESGHAL_GRAMS * per_gram_18k:,.0f} است"
    )


def test_melted_bubble_with_a_real_market_quote_is_within_the_valid_range():
    """حباب طلای آب‌شده با قیمت واقعی بازار باید داخل بازهٔ اعتبارسنجی داخلی بماند."""
    fair = pricer.fair_value("IR_GOLD_MELTED", XAU_USD, USD_IRT)
    bubble = calc_bubble("IR_GOLD_MELTED", MELTED_MARKET_IRT, fair, XAU_USD)
    low, high = VALID_BUBBLE_PCT_RANGE
    assert low <= bubble.bubble_pct <= high, (
        f"حباب محاسبه‌شده {bubble.bubble_pct:.2f}٪ خارج از بازهٔ معتبر {VALID_BUBBLE_PCT_RANGE} است"
    )
