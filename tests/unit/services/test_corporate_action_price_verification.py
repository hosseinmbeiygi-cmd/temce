"""اثبات «تأیید فاکتور رویداد شرکتی با شاهد قیمت» (فاز A، گام ۴).

قاعدهٔ جدید در `services/corporate_action_service.resolve_event_factor`: نسبت/مالیاتِ
ثبت‌شده در `corporate_action_events` یک *ادعا*ست؛ سری قیمت خام *شاهد*. سه حکم:

  * `confirmed`      — حرکت خام با ادعا می‌خواند (یا شاهدی برای رد آن نیست) → فاکتور ثبت‌شده؛
  * `invisible`      — رویداد در پنجرهٔ ±۳ روز هیچ اثری روی قیمت نگذاشته → فاکتور ۱٫۰
                       (همین حالت بود که پرش‌های مصنوعی +۴۰٪ می‌ساخت)؛
  * `price_override` — اثر دیده می‌شود ولی ضریب روز `ex` با ادعا نمی‌خواند → ضریب دیده‌شدهٔ
                       قیمت، تا سری پیوسته بماند.

لایهٔ دوم (نیازمند DB، read-only) همان بازه‌های مشکل‌دار پنج نماد طلایی را *شبیه‌سازی*
می‌کند و می‌سنجد که پس از تأیید، دیگر پرش مصنوعی باقی نمی‌ماند — بدون هیچ نوشتنی در DB.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import settings
from services.corporate_action_service import (
    ObservedPriceMove,
    compute_cumulative_factors,
    load_observed_price_moves,
    resolve_event_factor,
)

GOLDEN_SYMBOLS = ("وساخت", "خودرو", "وسپه", "خبهمن", "خساپا")


def _app_db_reachable() -> bool:
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


needs_app_db = pytest.mark.skipif(not _app_db_reachable(), reason="پایگاه‌دادهٔ اپلیکیشن در دسترس نیست")

# نمونهٔ واقعی خودرو: نسبت ثبت‌شدهٔ ۷٫۵۰۱ (فاکتور ۰٫۱۱۷۶) در برابر افت واقعی ۰٫۱۶۵۲
RECORDED_RATIO = 7.501099
RAW_MULTIPLIER = 0.165237
RECORDED_FACTOR = 1.0 / (1.0 + RECORDED_RATIO)


# ════════════════════════════════════════════════════════════════════════════
# ۱) قاعدهٔ تأیید — خالص
# ════════════════════════════════════════════════════════════════════════════
EX = date(2025, 4, 22)


def test_event_is_confirmed_when_the_raw_move_matches_the_recorded_action():
    observed = ObservedPriceMove(
        ex_close=500.0,
        prev_close=1000.0,
        max_drop_in_window=0.50,
        max_drop_date=EX,
        max_drop_multiplier=0.5,
    )
    factor, verdict, apply_on = resolve_event_factor(
        "capital_increase", ratio=1.0, dps=0.0, close_at_ex=500.0, ex_date=EX, observed=observed
    )

    assert verdict == "confirmed"
    assert factor == pytest.approx(0.5)
    assert apply_on == EX


def test_event_without_price_footprint_is_dropped_instead_of_double_adjusting():
    """ادعای افزایش سرمایهٔ ۴۰٪ بدون هیچ افتی در قیمت → فاکتور ۱٫۰ (نه ۰٫۷۱۴)."""
    observed = ObservedPriceMove(ex_close=3065.0, prev_close=3065.0, max_drop_in_window=0.0)
    factor, verdict, _ = resolve_event_factor(
        "capital_increase", ratio=0.400457, dps=0.0, close_at_ex=3065.0, ex_date=EX, observed=observed
    )

    assert verdict == "invisible"
    assert factor == 1.0, "رویداد نامرئی نباید سری را جابه‌جا کند"


def test_visible_event_disagreeing_with_the_feed_follows_the_price():
    """خودرو ۱۴۰۴-۰۲-۰۲: ادعا ۷٫۵۰۱ ولی ضریب واقعی ۰٫۱۶۵۲ → ضریب قیمت، تا پرش نماند."""
    observed = ObservedPriceMove(
        ex_close=638.0,
        prev_close=3862.0,
        max_drop_in_window=0.8348,
        max_drop_date=EX,
        max_drop_multiplier=RAW_MULTIPLIER,
    )
    factor, verdict, apply_on = resolve_event_factor(
        "capital_increase", ratio=RECORDED_RATIO, dps=0.0, close_at_ex=638.0, ex_date=EX, observed=observed
    )

    assert verdict == "price_override"
    assert factor == pytest.approx(RAW_MULTIPLIER, rel=1e-3)
    assert apply_on == EX
    assert factor > RECORDED_FACTOR, "جبران بیش از حد در ادعا، باعث بازاردهی مصنوعی می‌شد"


def test_event_whose_drop_landed_on_another_day_snaps_to_that_day():
    """تاریخ فید یک روز عقب/جلو باشد: فاکتور باید روی روزی بنشیند که تیپ واقعاً حرکت کرده."""
    drop_day = EX + timedelta(days=1)
    observed = ObservedPriceMove(
        ex_close=1000.0,
        prev_close=1000.0,
        max_drop_in_window=0.50,
        max_drop_date=drop_day,
        max_drop_multiplier=0.5,
    )
    factor, verdict, apply_on = resolve_event_factor(
        "capital_increase", ratio=1.0, dps=0.0, close_at_ex=1000.0, ex_date=EX, observed=observed
    )

    assert verdict == "ex_date_snapped"
    assert factor == pytest.approx(0.5)
    assert apply_on == drop_day


def test_event_without_observation_stays_on_the_recorded_factor():
    factor, verdict, apply_on = resolve_event_factor(
        "capital_increase", ratio=1.0, dps=0.0, close_at_ex=500.0, ex_date=EX, observed=None
    )

    assert verdict == "unverified"
    assert factor == pytest.approx(0.5)
    assert apply_on == EX


def test_tiny_claim_stays_on_the_recorded_factor():
    """ادعای کوچک‌تر از نوفهٔ یک روز قابل تأیید/رد نیست → فاکتور ثبت‌شده حفظ می‌شود."""
    observed = ObservedPriceMove(ex_close=993.3, prev_close=1000.0, max_drop_in_window=0.0067)
    factor, verdict, _ = resolve_event_factor(
        "capital_increase", ratio=0.00675, dps=0.0, close_at_ex=993.3, ex_date=EX, observed=observed
    )

    assert verdict == "confirmed"
    assert factor == pytest.approx(0.99329, rel=1e-4)


def test_dividend_is_verified_against_the_same_rule():
    observed = ObservedPriceMove(
        ex_close=950.0,
        prev_close=1000.0,
        max_drop_in_window=0.05,
        max_drop_date=EX,
        max_drop_multiplier=0.95,
    )
    factor, verdict, _ = resolve_event_factor(
        "dividend", ratio=0.0, dps=50.0, close_at_ex=950.0, ex_date=EX, observed=observed
    )

    assert verdict == "confirmed"
    assert factor == pytest.approx((950.0 - 50.0) / 950.0)


def test_cumulative_series_stays_continuous_with_verified_factors():
    """دو رویداد: یکی نامرئی (باید بی‌اثر شود) و یکی دیده‌شده با ادعای غلط."""
    d = [date(2025, 4, 20), date(2025, 4, 21), date(2025, 4, 22), date(2025, 4, 23)]
    actions = [
        {"ex_date": date(2025, 4, 21), "action_type": "capital_increase", "ratio": 0.40, "dps": 0.0},
        {"ex_date": date(2025, 4, 22), "action_type": "capital_increase", "ratio": 7.50, "dps": 0.0},
    ]
    closes = {
        date(2025, 4, 21): 1000.0,
        date(2025, 4, 22): 165.0,
    }
    observed = {
        date(2025, 4, 21): ObservedPriceMove(ex_close=1000.0, prev_close=1000.0, max_drop_in_window=0.0),
        date(2025, 4, 22): ObservedPriceMove(
            ex_close=165.0,
            prev_close=1000.0,
            max_drop_in_window=0.835,
            max_drop_date=date(2025, 4, 22),
            max_drop_multiplier=0.165,
        ),
    }
    raw = [1000.0, 1000.0, 165.0, 160.0]

    factors = compute_cumulative_factors(actions, d, closes, observed)
    adjusted = [price * factors[day] for price, day in zip(raw, d, strict=True)]

    without_invisible = compute_cumulative_factors([actions[1]], d, closes, observed)
    assert factors == without_invisible, "رویداد نامرئی نباید هیچ فاکتوری به سری اضافه کند"
    assert factors[date(2025, 4, 22)] == 1.0, "از روز رویداد به بعد، سری خام است"
    for i in range(1, len(d)):
        raw_ret = raw[i] / raw[i - 1] - 1
        adj_ret = adjusted[i] / adjusted[i - 1] - 1
        if abs(raw_ret) > 0.5:  # پرش بزرگ خام
            assert abs(adj_ret) < 0.05, f"پرش در {d[i]} جبران نشد: خام {raw_ret:.2%} / تعدیل {adj_ret:.2%}"


# ════════════════════════════════════════════════════════════════════════════
# ۲) شبیه‌سازی روی داده‌ی واقعی پنج نماد طلایی — read-only
# ════════════════════════════════════════════════════════════════════════════
# ``price_close`` (پایانی) — همان ستونی که خود `recompute_factors` و
# `load_observed_price_moves` می‌خوانند. ستون ``price_last`` در این پایگاه‌داده
# روی روزهای رویداد ثابت می‌ماند (خودرو، ۱۳۹۰-۰۸-۰۹: price_last=۳۰۶۵ در برابر
# price_close=۲۱۹۰)، پس سنجش «پرش» با آن نه رویداد را می‌بیند و نه تعدیل را.
SIMULATION_SQL = text(
    """
    SELECT h.date AS shamsi,
           jalali_to_gregorian(h.date) AS trade_date,
           h.price_close AS raw_close
    FROM brsapi_historical_daily h
    WHERE h.symbol = :sym AND h.price_close IS NOT NULL AND h.price_close > 0
    ORDER BY trade_date
    """
)

EVENTS_SQL = text(
    """
    SELECT e.symbol_id, e.ex_date, e.action_type, e.ratio, e.dps
    FROM corporate_action_events e
    JOIN symbols s ON s.id = e.symbol_id
    WHERE s.symbol = :sym
    ORDER BY e.ex_date
    """
)


async def _simulate(symbol: str) -> dict[str, object]:
    """فاکتورها را با قاعدهٔ جدید در حافظه بازمحاسبه می‌کند (هیچ نوشتن/به‌روزرسانی در DB)."""
    engine = create_async_engine(settings.database_url_async)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SET statement_timeout = '60s'"))
            bars = (await conn.execute(SIMULATION_SQL, {"sym": symbol})).fetchall()
            events = (await conn.execute(EVENTS_SQL, {"sym": symbol})).fetchall()
            if not bars or not events:
                return {"symbol": symbol, "skipped": True}

            symbol_id = int(events[0].symbol_id)
            ex_dates = [e.ex_date for e in events]
            actions = [
                {
                    "ex_date": e.ex_date,
                    "action_type": e.action_type,
                    "ratio": float(e.ratio or 0),
                    "dps": float(e.dps or 0),
                }
                for e in events
            ]
            closes = {d: float(c) for d, c in ((r.trade_date, r.raw_close) for r in bars)}
            observed = await load_observed_price_moves(conn, symbol_id, ex_dates)
            factors = compute_cumulative_factors(actions, [r.trade_date for r in bars], closes, observed)

            raw = [float(r.raw_close) for r in bars]
            dates = [r.trade_date for r in bars]
            adjusted = [p * factors[d] for p, d in zip(raw, dates, strict=True)]

            boundaries = []
            for i in range(1, len(dates)):
                if factors[dates[i]] == factors[dates[i - 1]]:
                    continue
                boundaries.append(
                    {
                        "date": dates[i],
                        "shamsi": bars[i].shamsi,
                        "raw_ret": raw[i] / raw[i - 1] - 1,
                        "adj_ret": adjusted[i] / adjusted[i - 1] - 1,
                    }
                )
            return {"symbol": symbol, "boundaries": boundaries, "events": len(actions), "observed": len(observed)}
    finally:
        await engine.dispose()


@pytest.fixture(scope="module")
def simulations() -> dict[str, dict[str, object]]:
    return {sym: asyncio.run(_simulate(sym)) for sym in GOLDEN_SYMBOLS}


@needs_app_db
@pytest.mark.parametrize("symbol", GOLDEN_SYMBOLS)
def test_no_artificial_jump_survives_verification(simulations, symbol):
    """پس از تأیید با قیمت، هیچ مرز رویدادی نباید حرکت مصنوعی بزرگ بسازد."""
    result = simulations[symbol]
    assert not result.get("skipped"), f"{symbol}: داده/رویداد کافی نیست"
    offenders = [
        (str(b["shamsi"]), float(b["raw_ret"]), float(b["adj_ret"]))
        for b in result["boundaries"]
        if abs(float(b["adj_ret"])) > 0.05
    ]
    assert not offenders, f"{symbol}: پرش مصنوعی باقی‌مانده: {offenders}"


@needs_app_db
@pytest.mark.parametrize("symbol", GOLDEN_SYMBOLS)
def test_visible_raw_drops_are_still_compensated(simulations, symbol):
    """افت واقعی قیمت در روز رویداد باید در سری تعدیل‌شده خنثی شود (نه نادیده بماند)."""
    big = [
        (str(b["shamsi"]), float(b["raw_ret"]), float(b["adj_ret"]))
        for b in simulations[symbol]["boundaries"]
        if b["raw_ret"] <= -0.05
    ]
    for shamsi, raw_ret, adj_ret in big:
        assert abs(adj_ret) < 0.05, f"{symbol} {shamsi}: افت {raw_ret:.2%} پس از تعدیل {adj_ret:.2%} ماند"
