"""تست golden مسیر قیمت تعدیل‌شده (فاز A، گام ۳ نقشهٔ راه بک‌تست).

مسیر داده: `brsapi_historical_daily` (قیمت خام) + `daily_adjust_factors` (فاکتور تجمعی رویداد شرکتی)
→ نمای `vw_daily_history_adjusted` با قاعدهٔ
`price_*_adj = price_* × COALESCE(adj_factor, 1)` (مهاجرت 0109).

دو لایهٔ تست:

۱) **قرارداد خالص (بدون DB، همیشه اجرا می‌شود):** شکل‌دهی شمع‌ها، ترتیب زمانی، انتخاب SQL
   بر اساس حالت تعدیل، و **ناوردای تعدیل** روی یک افزایش سرمایهٔ ساختگی (۲:۱): سری خام پرش
   مصنوعی −۵۰٪ را نشان می‌دهد و سری تعدیل‌شده نه.

۲) **پنج نماد طلایی (نیازمند DB؛ در نبود PostgreSQL خودکار skip می‌شود):** نمادها با پوشش کامل
   و دارای حداقل یک رویداد شرکتی انتخاب شدند (اسکن read-only روی `daily_adjust_factors` و
   `brsapi_historical_daily`؛ فهرست و اعداد اندازه‌گیری‌شده در بخش ثابت‌های زیر).

نسخهٔ نمادها و پوشش (اندازه‌گیری ۱۴۰۵/۰۷/۲۰ روی DB توسعه، ‎~8.6M سطر):

    وساخت  bars=5894  bad_close=0  ۱ رویداد
    خودرو  bars=5878  bad_close=0  ۸ رویداد
    وسپه   bars=5859  bad_close=0  ۷ رویداد
    خبهمن  bars=5853  bad_close=0  ۲ رویداد
    خساپا  bars=5798  bad_close=0  ۴ رویداد

**یافتهٔ باز (باگ ثبت‌شده، رفع نشده):** روی همین پنج نماد، در چند مرز رویداد شرکتی سری
تعدیل‌شده **پیوسته نیست** — یا قیمت خام حرکت نمی‌کند ولی فاکتور می‌پرد (سود مصنوعی تا
+۶۲٪) یا پرش خام بزرگ با ضریب جبران نمی‌شود. تست‌های `*_boundary_*` این رفتار را با
`xfail` قفل می‌کنند تا روزی که `daily_adjust_factors` درست شود (الگوی GS-01…GS-05 در همین مخزن).
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings
from services.adjusted_price_reader import (
    ADJUSTED_VIEW,
    RAW_SOURCE,
    build_candle_query,
    build_candles,
    build_range_query,
    reset_adjusted_source_cache,
    resolve_price_source,
)

# ── نمادهای طلایی (پوشش کامل + حداقل یک رویداد شرکتی) ──────────────────────────
GOLDEN_SYMBOLS = ("وساخت", "خودرو", "وسپه", "خبهمن", "خساپا")
MIN_BARS = 250


def _app_db_reachable() -> bool:
    """آیا پایگاه‌دادهٔ خود اپلیکیشن (همان URLی که fixture می‌سازد) پاسخ می‌دهد؟

    عمداً به `@pytest.mark.needs_db` تکیه نمی‌کنیم: پروب آن نشانگر فقط متغیر محیطی
    `DATABASE_URL` را می‌بیند (پیش‌فرض `market_test`) و با تنظیمات `.env` کار ندارد،
    پس این تست‌ها روی ماشین توسعه بی‌صدا skip می‌شدند. اینجا همان URLی که تست واقعاً
    استفاده می‌کند بررسی می‌شود.
    """

    async def _ping() -> bool:
        engine = create_async_engine(settings.database_url_async)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_ping())
    except Exception:
        return False


APP_DB_AVAILABLE = _app_db_reachable()
needs_app_db = pytest.mark.skipif(
    not APP_DB_AVAILABLE, reason="پایگاه‌دادهٔ اپلیکیشن در دسترس نیست (localhost/تنطیمات .env)"
)

# آستانه‌های ناورا: حرکت خام بزرگ در برابر حرکت تعدیل‌شده
BIG_RAW_MOVE = 0.20  # پرش خام ≥ ۲۰٪ = رویداد شرکتی
SMALL_ADJ_MOVE = 0.20  # پس از تعدیل نباید حرکت بزرگ بماند
FLAT_RAW_MOVE = 0.05  # حرکت خام عملاً صفر
SPURIOUS_ADJ_MOVE = 0.05  # پس تعدیل هم باید عملاً صفر بماند

BOUNDARY_SQL = text(
    """
    WITH bars AS (
        SELECT h.date AS shamsi,
               jalali_to_gregorian(h.date) AS trade_date,
               h.price_last AS raw_close,
               COALESCE(f.adj_factor, 1) AS factor
        FROM brsapi_historical_daily h
        JOIN symbols s ON s.symbol = h.symbol
        LEFT JOIN daily_adjust_factors f
               ON f.symbol_id = s.id
              AND f.trade_date = jalali_to_gregorian(h.date)
        WHERE h.symbol = :sym AND h.price_last IS NOT NULL AND h.price_last > 0
    ),
    ordered AS (
        SELECT shamsi, trade_date, raw_close, factor,
               LAG(raw_close) OVER (ORDER BY trade_date) AS prev_close,
               LAG(factor)    OVER (ORDER BY trade_date) AS prev_factor
        FROM bars
    )
    SELECT shamsi, trade_date, prev_close, raw_close, prev_factor, factor,
           raw_close / prev_close - 1                             AS raw_ret,
           (raw_close * factor) / (prev_close * prev_factor) - 1  AS adj_ret
    FROM ordered
    WHERE prev_close IS NOT NULL AND factor <> prev_factor
    ORDER BY trade_date
    """
)

VIEW_IDENTITY_SQL = text(
    """
    SELECT trade_date, trade_date_shamsi, price_last, adj_factor, price_last_adj
    FROM vw_daily_history_adjusted
    WHERE symbol = :sym
    ORDER BY trade_date_shamsi DESC
    LIMIT :lim
    """
)


async def _load_boundaries() -> dict[str, list]:
    """مرزهای رویداد شرکتی هر پنج نماد را یک‌بار می‌خواند (پنج کوئری، نه پانزده)."""
    engine = create_async_engine(settings.database_url_async)
    try:
        out: dict[str, list] = {}
        async with engine.connect() as conn:
            await conn.execute(text("SET statement_timeout = '60s'"))
            for symbol in GOLDEN_SYMBOLS:
                out[symbol] = (await conn.execute(BOUNDARY_SQL, {"sym": symbol})).fetchall()
        return out
    finally:
        await engine.dispose()


@pytest.fixture(scope="module")
def boundaries() -> dict[str, list]:
    """نتیجهٔ `BOUNDARY_SQL` برای هر نماد، یک‌بار در کل ماژول."""
    return asyncio.run(_load_boundaries())


@pytest.fixture
async def session():
    """AsyncSession روی همان DBی که اپلیکیشن استفاده می‌کند (تنظیمات `.env`)."""
    engine = create_async_engine(settings.database_url_async)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as sess:
            await sess.execute(text("SET statement_timeout = '60s'"))
            yield sess
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
def _clear_source_cache():
    """کش process-level وضعیت نمای تعدیل بین تست‌ها پاک شود."""
    reset_adjusted_source_cache()
    yield
    reset_adjusted_source_cache()


# ════════════════════════════════════════════════════════════════════════════
# ۱) قرارداد خالص — بدون DB
# ════════════════════════════════════════════════════════════════════════════
def test_build_candles_returns_oldest_first_with_raw_and_shamsi_dates():
    # ورودی نمای تعدیل‌شده: (trade_date, trade_date_shamsi, first, max, min, last, volume, value)، جدیدترین اول
    rows = [
        ("2026-02-25", "1404-12-06", 5100.0, 5200.0, 5000.0, 5080.0, 10, 100),
        ("2026-02-24", "1404-12-05", 6720.0, 6740.0, 6700.0, 6730.0, 20, 200),
    ]
    candles = build_candles(rows)

    assert [c["date"] for c in candles] == ["2026-02-24", "2026-02-25"], "باید از قدیم به جدید مرتب شود"
    assert [c["date_shamsi"] for c in candles] == ["1404-12-05", "1404-12-06"]
    assert candles[0]["close"] == 6730.0 and candles[1]["close"] == 5080.0


def test_build_candles_falls_back_to_close_for_missing_ohlc_legs():
    candles = build_candles([("2026-02-25", "1404-12-06", None, None, None, 5080.0, None, None)])

    assert candles[0]["open"] == candles[0]["high"] == candles[0]["low"] == 5080.0
    assert candles[0]["volume"] == 0.0 and candles[0]["value"] == 0.0


def test_build_candles_drops_rows_without_a_derivable_gregorian_date():
    """شمسی نامعتبر → تاریخ میلادی NULL → سطر باید حذف شود (نه اختراع تاریخ)."""
    candles = build_candles(
        [("2026-02-25", "1404-12-06", 1.0, 1.0, 1.0, 1.0, 0, 0), (None, "1404-13-99", 1.0, 1.0, 1.0, 1.0, 0, 0)]
    )

    assert len(candles) == 1 and candles[0]["date"] == "2026-02-25"


def test_query_selection_follows_the_adjusted_mode():
    """حالت تعدیل‌شده از نما می‌خواند و حالت خام از جدول؛ هر دو همان ۸ ستون را برمی‌گردانند."""
    adjusted = build_candle_query(ADJUSTED_VIEW, True)
    raw = build_candle_query(RAW_SOURCE, False)

    assert "vw_daily_history_adjusted" in adjusted and "price_last_adj" in adjusted
    assert "price_last_adj" not in raw and "daily_history" in raw
    assert "trade_date_shamsi" in adjusted and "NULL AS trade_date_shamsi" in raw
    assert "trade_date >= :start" in build_range_query(ADJUSTED_VIEW, True)


def test_unknown_source_and_mode_combination_raises():
    with pytest.raises(ValueError):
        build_candle_query(ADJUSTED_VIEW, False)
    with pytest.raises(ValueError):
        build_range_query(RAW_SOURCE, True)


async def test_resolve_price_source_falls_back_to_raw_when_view_is_missing(monkeypatch):
    """نمای تعدیل‌شده نباشد → خواندن خام (بدون خطا)، و با بودن نما → تعدیل‌شده."""
    import services.adjusted_price_reader as reader

    async def _missing(_session):  # noqa: ANN001 - امضای همان تابع
        return False

    monkeypatch.setattr(reader, "adjusted_view_available", _missing)
    assert await resolve_price_source(session=None) == (RAW_SOURCE, False)

    async def _present(_session):  # noqa: ANN001
        return True

    monkeypatch.setattr(reader, "adjusted_view_available", _present)
    assert await resolve_price_source(session=None) == (ADJUSTED_VIEW, True)


def test_adjustment_invariant_removes_the_capital_increase_jump():
    """ناوردای اصلی: پرش قیمت در رویداد شرکتی نباید به بازده تعدیل‌شده نشت کند.

    افزایش سرمایهٔ ۲:۱ → قیمت خام نصف می‌شود و فاکتور تجمعی دو برابر می‌شود
    (`adj = raw × factor`), پس سری تعدیل‌شده پیوسته است در حالی که خام −۵۰٪ نشان می‌دهد.
    """
    raw = [1000.0, 500.0]
    factor = [0.5, 1.0]
    adjusted = [p * f for p, f in zip(raw, factor, strict=True)]

    raw_return = raw[1] / raw[0] - 1
    adj_return = adjusted[1] / adjusted[0] - 1

    assert raw_return == pytest.approx(-0.50), "سری خام باید پرش رویداد را نشان دهد"
    assert abs(adj_return) < 1e-12, "سری تعدیل‌شده نباید پرش مصنوعی داشته باشد"
    assert adjusted == [500.0, 500.0]


# ════════════════════════════════════════════════════════════════════════════
# ۲) پنج نماد طلایی — نیازمند DB
# ════════════════════════════════════════════════════════════════════════════
@needs_app_db
@pytest.mark.parametrize("symbol", GOLDEN_SYMBOLS)
async def test_view_identity_adjusted_price_is_raw_times_factor(session, symbol):
    """هر سطر نما باید دقیقاً `price_last_adj = price_last × adj_factor` باشد و تاریخ معاملاتی داشته باشد."""
    rows = (await session.execute(VIEW_IDENTITY_SQL, {"sym": symbol, "lim": 300})).fetchall()
    assert len(rows) >= MIN_BARS, f"{symbol}: فقط {len(rows)} سطر برگشت"

    checked = 0
    for r in rows:
        assert r.trade_date is not None, f"{symbol}: trade_date خالی"
        assert r.trade_date_shamsi is not None, f"{symbol}: date شمسی خالی"
        assert r.adj_factor is not None and float(r.adj_factor) > 0
        if r.price_last is None:
            continue
        expected = float(r.price_last) * float(r.adj_factor)
        assert float(r.price_last_adj) == pytest.approx(expected, rel=1e-9), (
            f"{symbol} {r.trade_date}: price_last_adj={r.price_last_adj} در برابر raw×factor={expected}"
        )
        checked += 1
    assert checked >= MIN_BARS


@needs_app_db
@pytest.mark.parametrize("symbol", GOLDEN_SYMBOLS)
async def test_golden_symbols_have_a_corporate_action_in_range(boundaries, symbol):
    """هر نماد طلایی باید حداقل یک مرز رویداد شرکتی با قیمت موجود داشته باشد (وگرنه تست تعدیل بی‌معنا است)."""
    rows = boundaries[symbol]
    assert rows, f"{symbol}: هیچ مرز رویداد شرکتی پیدا نشد"


def _uncompensated_drops(rows: list) -> list[tuple[str, float, float]]:
    """مرزهایی که پرش خام بزرگ دارند ولی سری تعدیل‌شده هم بزرگ می‌ماند (پرش جبران‌نشده)."""
    return [
        (str(r.shamsi), float(r.raw_ret), float(r.adj_ret))
        for r in rows
        if abs(float(r.raw_ret)) >= BIG_RAW_MOVE and abs(float(r.adj_ret)) > SMALL_ADJ_MOVE
    ]


def _spurious_moves(rows: list) -> list[tuple[str, float, float]]:
    """مرزهایی که قیمت خام تکان نخورده ولی فاکتور پرش ساخته (بازده مصنوعی)."""
    return [
        (str(r.shamsi), float(r.raw_ret), float(r.adj_ret))
        for r in rows
        if abs(float(r.raw_ret)) <= FLAT_RAW_MOVE and abs(float(r.adj_ret)) > SPURIOUS_ADJ_MOVE
    ]


# نمادهایی که ناوردا روی آن‌ها برقرار است (اندازه‌گیری ۱۴۰۵/۰۷/۲۰) در برابر نمادهایی
# که دادهٔ فاکتورشان ناسازگار است. تست «سالم» سخت‌گیر است و «ناسازگار» با xfail قفل می‌شود.
DROPS_COMPENSATED = ("وساخت", "وسپه", "خبهمن")
DROPS_UNCOMPENSATED = ("خودرو", "خساپا")
NO_SPURIOUS_MOVE = ("وساخت", "خساپا")
SPURIOUS_MOVE_PRESENT = ("خودرو", "وسپه", "خبهمن")


@needs_app_db
@pytest.mark.parametrize("symbol", DROPS_COMPENSATED)
async def test_big_corporate_action_drop_is_compensated_by_the_factor(boundaries, symbol):
    """پرش خام ≥ ۲۰٪ باید پس از تعدیل به حرکت کوچک تبدیل شود (ناوردای پیوستگی)."""
    offenders = _uncompensated_drops(boundaries[symbol])
    assert not offenders, f"{symbol}: پرش خام جبران‌نشده: {offenders}"


@needs_app_db
@pytest.mark.parametrize("symbol", NO_SPURIOUS_MOVE)
async def test_no_spurious_adjusted_move_when_the_raw_price_was_flat(boundaries, symbol):
    """قیمت خام بی‌حرکت ⇒ سری تعدیل‌شده هم نباید حرکت مصنوعی بسازد."""
    offenders = _spurious_moves(boundaries[symbol])
    assert not offenders, f"{symbol}: بازده مصنوعی تعدیل: {offenders}"


@needs_app_db
@pytest.mark.parametrize("symbol", DROPS_UNCOMPENSATED)
async def test_known_uncompensated_drop_is_locked(boundaries, symbol):
    """قفل وضعیت شناخته‌شده (باگ رفع‌نشدهٔ فاز A گام ۴): پرش خام بزرگ با فاکتور جبران نمی‌شود.

    این تست عمداً وجود باگ را تثبیت می‌کند. روزی که `daily_adjust_factors` درست شد، تست
    قرمز می‌شود تا نماد را به گروه `DROPS_COMPENSATED` منتقل کنند — یعنی رفع باگ، خاموشی
    نمی‌گیرد.
    """
    assert _uncompensated_drops(boundaries[symbol]), (
        f"{symbol}: پرش جبران‌نشده‌ای دیگر دیده نمی‌شود — به DROPS_COMPENSATED منتقلش کن"
    )


@needs_app_db
@pytest.mark.parametrize("symbol", SPURIOUS_MOVE_PRESENT)
async def test_known_spurious_move_is_locked(boundaries, symbol):
    """قفل وضعیت شناخته‌شده (باگ رفع‌نشدهٔ فاز A گام ۴): فاکتور تعدیل در روزهای بی‌حرکت می‌پرد.

    مثال شاهد: خساپا ۱۳۹۴-۱۲-۲۶ بار خام −۲۷٫۷٪ در برابر تعدیل +۶۲٫۸٪؛ خودرو ۱۳۹۰-۰۸-۰۹ بار
    خام ۰٪ در برابر تعدیل +۴۰٪. روزی که داده درست شد، این تست قرمز می‌شود تا نماد جابه‌جا شود.
    """
    assert _spurious_moves(boundaries[symbol]), (
        f"{symbol}: بازده مصنوعی‌ای دیگر دیده نمی‌شود — به NO_SPURIOUS_MOVE منتقلش کن"
    )
