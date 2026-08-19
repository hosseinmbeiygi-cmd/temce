"""SQLAlchemy ORM models for the 110-column CANSLIM-inspired screener system.

Three tables:
  1. screener_profiles  — one row per symbol; static/fundamental data (weekly updates)
  2. screener_snapshots — time-series of intraday snapshots (every ~2 minutes)
  3. screener_signals   — final scores, decisions and risk management output
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin

# ══════════════════════════════════════════════════════════════════
# TABLE 1: ScreenerProfile — داده‌های ایستا و بنیادی (هر سهم یک ردیف)
# ══════════════════════════════════════════════════════════════════

class ScreenerProfile(TimestampMixin, Base):
    """📋 پروفایل ایستای هر سهم برای مدل ۱۱۰ ستونی.

    یک ردیف برای هر نماد. داده‌های بنیادی، فیلترهای رویدادی و متغیرهای
    کلان در این جدول ذخیره می‌شوند و روزانه/هفتگی به‌روز می‌شوند.
    """
    __tablename__ = "screener_profiles"

    # ── PK ──
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)

    # ── بخش اول: اطلاعات پایه (ستون‌های ۱-۵) ──
    industry: Mapped[str | None] = mapped_column(String(100))
    sub_industry: Mapped[str | None] = mapped_column(String(100))
    free_float_shares: Mapped[float | None] = mapped_column(BigInteger)

    # ── بخش دوم: داده‌های بنیادی از صورت‌های مالی (ستون‌های ۶-۲۵) ──
    eps_current: Mapped[float | None] = mapped_column(Float, comment="EPS فصل جاری (ریال) — ستون ۶")
    eps_prev_year: Mapped[float | None] = mapped_column(Float, comment="EPS فصل مشابه سال قبل (ریال) — ستون ۷")
    exchange_rate_base: Mapped[float | None] = mapped_column(Float, comment="نرخ ارز مبنا — ستون ۸")
    inflation_rate: Mapped[float | None] = mapped_column(Float, comment="نرخ تورم نقطه‌به‌نقطه (درصد) — ستون ۱۲")
    net_operating_profit: Mapped[float | None] = mapped_column(Float, comment="سود خالص عملیاتی (میلیارد) — ستون ۱۴")
    accumulated_loss: Mapped[float | None] = mapped_column(Float, comment="زیان انباشته (میلیارد) — ستون ۱۵")
    registered_capital: Mapped[float | None] = mapped_column(Float, comment="سرمایه ثبت‌شده (میلیارد) — ستون ۱۶")
    legal_reserve: Mapped[float | None] = mapped_column(Float, comment="ذخیره هزینه‌های حقوقی (میلیارد) — ستون ۱۸")
    gross_margin: Mapped[float | None] = mapped_column(Float, comment="حاشیه سود ناخالص (درصد) — ستون ۲۰")
    feedstock_price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="نرخ خوراک مصرفی — ستون ۲۱")
    feedstock_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="تغییرات نرخ خوراک در ۳ ماه آینده — ستون ۲۲")
    capital_increase_type: Mapped[str | None] = mapped_column(String(30), comment="نوع افزایش سرمایه: نقدی/تجدید ارزیابی/ندارد — ستون ۲۴")
    capital_increase_pct: Mapped[float | None] = mapped_column(Float, comment="مبلغ افزایش سرمایه (درصد سرمایه فعلی) — ستون ۲۵")

    # ── بخش سوم: داده‌های ارزش‌گذاری (ستون‌های ۲۶-۳۵) ──
    current_price: Mapped[float | None] = mapped_column(Float, comment="قیمت روز سهم — ستون ۲۶")
    industry_pe: Mapped[float | None] = mapped_column(Float, comment="میانگین P/E صنعت — ستون ۲۸")
    bank_interest_rate: Mapped[float | None] = mapped_column(Float, comment="نرخ سود سپرده بانکی (درصد) — ستون ۳۱")
    bond_rate: Mapped[float | None] = mapped_column(Float, comment="نرخ اوراق بدهی دولتی (درصد) — ستون ۳۲")
    nima_rate: Mapped[float | None] = mapped_column(Float, comment="نرخ دلار نیما — ستون ۳۳")
    free_market_rate: Mapped[float | None] = mapped_column(Float, comment="نرخ دلار آزاد — ستون ۳۴")

    # ── بخش چهارم: داده‌های رفتاری و معاملاتی (ستون‌های ۳۶-۵۵) ──
    price_change_pct: Mapped[float | None] = mapped_column(Float, comment="تغییر قیمت امروز (درصد) — ستون ۴۱")
    today_volume: Mapped[int | None] = mapped_column(BigInteger, comment="حجم معاملات امروز — ستون ۳۶")
    avg_50d_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="میانگین حجم ۵۰ روزه — ستون ۳۷")
    avg_daily_value: Mapped[float | None] = mapped_column(Float, comment="میانگین ارزش معاملات روزانه (تومان) — ستون ۳۹")
    institutional_buy: Mapped[int | None] = mapped_column(BigInteger, comment="خرید حقوقی ۳۰ روز — ستون ۴۷")
    institutional_sell: Mapped[int | None] = mapped_column(BigInteger, comment="فروش حقوقی ۳۰ روز — ستون ۴۸")
    farabourse_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="حجم معاملات فرابورس (هفته) — ستون ۴۳")
    farabourse_price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="قیمت سهم در فرابورس — ستون ۴۵")

    # ── بخش پنجم: فیلترهای رویدادی و کیفی (ستون‌های ۵۶-۷۴) — مقدار ۰ یا ۱ ──
    ceo_change_success: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="تغییر مدیرعامل موفق در ۶ ماه اخیر؟ — ستون ۵۶")
    ceo_change_fail: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="تغییر مدیرعامل ناموفق — ستون ۵۷")
    annual_meeting_near: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="مجمع سالیانه نزدیکتر از ۴۵ روز — ستون ۵۸")
    annual_meeting_passed: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="مجمع گذشته و ریسک ریزش — ستون ۵۹")
    capital_increase_cash: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="افزایش سرمایه نقدی اعلام شده — ستون ۶۰")
    capital_increase_reval: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="افزایش سرمایه تجدید ارزیابی — ستون ۶۱")
    price_liberation_news: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="اخبار گشایش قیمتی در صنعت — ستون ۶۲")
    gov_support_news: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="حمایت دولتی اعلام‌شده — ستون ۶۳")
    heavy_legal_case: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="پرونده حقوقی سنگین (>۱۰٪ سود) — ستون ۶۴")
    telegram_pump: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="پیشنهاد خرید در >۳ کانال تلگرامی — ستون ۶۵")
    end_of_month: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="روز پایانی ماه — ستون ۶۶")
    pre_holiday: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="روز قبل از تعطیلات طولانی — ستون ۶۷")
    political_tension: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="رویداد سیاسی تنش‌زا در ۳ ماه آینده — ستون ۶۸")
    political_relief: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="رویداد سیاسی گشایش‌زا — ستون ۶۹")
    feedstock_meeting: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="جلسه تعیین نرخ خوراک در ۳ ماه آینده — ستون ۷۰")
    big_ipo: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="IPO بزرگ در ۳۰ روز آینده — ستون ۷۱")
    new_shareholder_capital: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="افزایش سرمایه از محل سهامداران جدید — ستون ۷۲")
    positive_mgmt_news: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="اخبار مثبت مدیریتی — ستون ۷۳")
    negative_mgmt_news: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="اخبار منفی مدیریتی — ستون ۷۴")

    # ── بخش ششم: فیلترهای محاسباتی خودکار (ستون‌های ۷۷-۸۴) — با فرمول از داده‌های موجود محاسبه می‌شوند ──
    f77_dollar_eps_growth: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="نرخ رشد دلاری EPS > ۱۵٪ — ستون ۷۷")
    f78_real_eps_growth: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="نرخ رشد واقعی EPS > ۱۵٪ — ستون ۷۸")
    f79_pe_ratio_ok: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="ضریب P/E < ۱.۲ — ستون ۷۹")
    f80_yield_gt_bank: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="بازده سهام > نرخ سود بانکی — ستون ۸۰")
    f81_inst_ratio_ok: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="نسبت خرید خالص حقوقی > ۵٪ شناور — ستون ۸۱")
    f82_volume_spike: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="جهش حجمی > ۳ برابر میانگین — ستون ۸۲")
    f83_liquidity_ok: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="نقدشوندگی > ۰.۵٪ شناور در روز — ستون ۸۳")
    f84_loss_ratio_ok: Mapped[int | None] = mapped_column(Integer, server_default="0", comment="نسبت زیان انباشته به سرمایه < ۵۰٪ — ستون ۸۴")

    # ── Timestamps ──
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ══════════════════════════════════════════════════════════════════
# TABLE 2: ScreenerSnapshot — داده‌های لحظه‌ای (هر ۲ دقیقه یک ردیف)
# ══════════════════════════════════════════════════════════════════

class ScreenerSnapshot(TimestampMixin, Base):
    """📊 اسنپ‌شات‌های لحظه‌ای از وضعیت سهم.

    این جدول به صورت time-series ذخیره می‌شود (هر ~۲ دقیقه یک ردیف).
    شامل OHLC, حجم, قیمت, داده‌های حقوقی لحظه‌ای و اندیکاتورهای تکنیکال.
    """
    __tablename__ = "screener_snapshots"
    # ── PK (composite — PostgreSQL creates a unique B-tree index automatically) ──
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, primary_key=True, index=True)

    # ── OHLC ──
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(BigInteger)

    # ── قیمت و تغییرات ──
    current_price: Mapped[float | None] = mapped_column(Float, comment="قیمت روز سهم — ستون ۲۶")
    price_change_pct: Mapped[float | None] = mapped_column(Float, comment="تغییر قیمت امروز (درصد) — ستون ۴۱")

    # ── حجم و ارزش ──
    today_volume: Mapped[int | None] = mapped_column(BigInteger, comment="حجم معاملات امروز — ستون ۳۶")
    avg_daily_value: Mapped[float | None] = mapped_column(Float, comment="میانگین ارزش معاملات روزانه (تومان) — ستون ۳۹")

    # ── داده‌های حقوقی لحظه‌ای ──
    institutional_buy: Mapped[int | None] = mapped_column(BigInteger, comment="خرید حقوقی امروز")
    institutional_sell: Mapped[int | None] = mapped_column(BigInteger, comment="فروش حقوقی امروز")

    # ── داده‌های فرابورس ──
    farabourse_price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="قیمت سهم در فرابورس — ستون ۴۵")
    farabourse_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="حجم معاملات فرابورس (هفته) — ستون ۴۳")

    # ── بافرهای محاسباتی (اختیاری — برای دیباگ) ──
    atr_14: Mapped[float | None] = mapped_column(Float, nullable=True, comment="میانگین محدوده واقعی ۱۴ دوره")
    volume_ma_50: Mapped[float | None] = mapped_column(Float, nullable=True, comment="میانگین حجم ۵۰ دوره")


# ══════════════════════════════════════════════════════════════════
# TABLE 3: ScreenerSignal — سیگنال‌ها و تصمیمات نهایی
# ══════════════════════════════════════════════════════════════════

class ScreenerSignal(TimestampMixin, Base):
    """🚨 سیگنال‌های خروجی مدل ۱۱۰ ستونی.

    هر ردیف = یک بار اجرای کامل مدل برای یک سهم.
    شامل تمام نمرات میانی و نهایی، حد ضرر و تصمیم خرید/نخرید.
    """
    __tablename__ = "screener_signals"
    __table_args__ = (
        Index("ix_screener_signals_symbol_time", "symbol", "generated_at"),
        Index("ix_screener_signals_decision", "decision"),
        Index("ix_screener_signals_final_score", "final_score"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    # ── قیمت‌ها ──
    current_price: Mapped[float | None] = mapped_column(Float, comment="قیمت لحظه‌ای هنگام سیگنال")
    live_pe: Mapped[float | None] = mapped_column(Float, comment="P/E لحظه‌ای")
    pe_ratio: Mapped[float | None] = mapped_column(Float, comment="ضریب P/E به صنعت")

    # ── داده‌های حقوقی و حجم ──
    institutional_ratio: Mapped[float | None] = mapped_column(Float, comment="نسبت خرید خالص حقوقی به شناور")
    volume_spike: Mapped[float | None] = mapped_column(Float, comment="نسبت جهش حجمی")
    liquidity_pct: Mapped[float | None] = mapped_column(Float, comment="نقدشوندگی (درصد شناور)")
    nima_free_spread: Mapped[float | None] = mapped_column(Float, comment="شکاف دلار نیما و آزاد")

    # ── نمرات میانی (ستون‌های ۸۶-۹۴) ──
    score_fundamental: Mapped[float | None] = mapped_column(Float, comment="نمره بنیادی — ستون ۸۶")
    score_valuation: Mapped[float | None] = mapped_column(Float, comment="نمره ارزش‌گذاری — ستون ۸۷")
    score_institutional: Mapped[float | None] = mapped_column(Float, comment="نمره نهادی — ستون ۸۸")
    score_technical: Mapped[float | None] = mapped_column(Float, comment="نمره تکنیکال — ستون ۸۹")
    score_macro: Mapped[float | None] = mapped_column(Float, comment="نمره کلان — ستون ۹۰")
    score_gov_support: Mapped[float | None] = mapped_column(Float, comment="نمره حمایت دولتی — ستون ۹۱")
    score_liquidity: Mapped[float | None] = mapped_column(Float, comment="نمره نقدشوندگی — ستون ۹۲")
    score_farabourse: Mapped[float | None] = mapped_column(Float, comment="نمره فرابورس — ستون ۹۳")
    score_feedstock: Mapped[float | None] = mapped_column(Float, comment="نمره خوراک و انرژی — ستون ۹۴")

    # ── نمرات نهایی (ستون‌های ۹۵-۱۰۷) ──
    risk_ok: Mapped[bool | None] = mapped_column(Boolean, comment="نمره مدیریت ریسک — ستون ۹۵")
    raw_score: Mapped[float | None] = mapped_column(Float, comment="مجموع نمره خام — ستون ۹۶")
    final_score: Mapped[float | None] = mapped_column(Float, comment="نمره نهایی ۰-۱۰۰ — ستون ۹۷")
    adjusted_score: Mapped[float | None] = mapped_column(Float, comment="نمره تعدیل‌شده — ستون ۱۰۴-۱۰۶")
    negative_filters_count: Mapped[int | None] = mapped_column(Integer, comment="تعداد فیلترهای منفی فعال — ستون ۹۹")
    rule_50_30: Mapped[str | None] = mapped_column(String(10), comment="قانون ۵۰/۳۰: قبول/رد — ستون ۱۰۰")

    # ── مدیریت ریسک (ستون‌های ۱۰۱-۱۰۷) ──
    stop_loss_price: Mapped[float | None] = mapped_column(Float, comment="حد ضرر (ریال) — ستون ۱۰۱")
    position_size: Mapped[int | None] = mapped_column(Integer, comment="تعداد سهام مجاز — ستون ۱۰۲")
    decision: Mapped[str | None] = mapped_column(String(20), comment="تصمیم نهایی: خرید/نخرید/رد_ریسک — ستون ۱۰۷")

    # ── رهگیری نتیجه ──
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="قیمت ورود واقعی")
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="قیمت خروج")
    exit_reason: Mapped[str | None] = mapped_column(String(30), nullable=True, comment="دلیل خروج: stop_loss/target/manual")
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="درصد سود/ضرر نهایی")
    outcome_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True, comment="آیا سیگنال درست بود؟")
    outcome_set_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="زمان ثبت نتیجه")
