# گزارش آدیت کامل پروژه — ۱۴۰۳/۰۸/۱۹

**تاریخ:** 2026-11-10  
**شاخه:** main  
**وضعیت نهایی:** ✅ همه ایرادهای شناسایی‌شده رفع و کامیت شدند

---

## خلاصه اجرایی

در این آدیت، فایل‌های اصلی ماژول `gold_desk` و `brsapi` بررسی شدند. در مجموع **۱۲ ایراد** شناسایی و رفع شد که در ۴ کامیت تجمیع شده‌اند.

---

## کامیت‌های رفع ایراد

| کامیت | توضیح |
|-------|--------|
| `86e60589` | `UniqueConstraint` روی `GoldCurrencyProDailyHistoryModel` + بهبود circuit breaker |
| `76200c1f` | Iran market optimizations + `result.error_code` در brsapi + asyncpg rowcount fix |
| `213e5192` | 5 ایراد بحرانی (gold_adapter، asyncio→inspect، redis setex→set، ...) |
| `4c07cc52` | مشکلات باقی‌مانده (lint، deps، deprecations) |

---

## ایرادهای رفع‌شده

### 🔴 بحرانی (Critical)

#### 1. `brsapi/client.py` — اسم اشتباه attribute در circuit breaker
- **قبل:** `result.code not in _CB_IGNORE_CODES`
- **بعد:** `result.error_code not in _CB_IGNORE_CODES`
- **اثر:** circuit breaker برای هر کد وضعیت trigger می‌شد (attribute وجود نداشت)

#### 2. `brsapi/repositories/base.py` — asyncpg rowcount=-1 برای ON CONFLICT DO NOTHING
- **قبل:** `raise BulkInsertRowCountUnavailable(...)` در صورت rowcount=-1
- **بعد:** log هشدار + بازگشت `attempted` به عنوان تقریب
- **اثر:** هر sync run با exception crash می‌کرد

#### 3. `brsapi/models/commodity.py` — نبود `UniqueConstraint` روی `GoldCurrencyProDailyHistoryModel`
- **قبل:** `ON CONFLICT DO NOTHING` بدون unique constraint → درج تکراری
- **بعد:** `UniqueConstraint("symbol", "date", name="uq_pro_daily_sym_date")`
  *(گزارش اولیه نام ستون `currency_pair` و نام constraint `uq_gold_currency_pro_daily` ذکر کرده بود — هر دو در کد نهایی تغییر کردند)*

---

### 🟠 مهم (High)

#### 4. `src/gold_desk/antigravity/calculations.py` — maintenance margin اشتباه
- **قبل:** `maintenance_margin_ratio = 0.05` (5%)
- **بعد:** `maintenance_margin_ratio = 0.07` (7%)
- **دلیل:** حداقل وجه تضمین بورس کالای ایران (IME) 7% است؛ مقدار قدیمی قیمت لیکوئید را امن‌تر از واقع نشان می‌داد

#### 5. `src/gold_desk/backtest_runner.py` — روزهای معاملاتی NYSE به‌جای TSE
- **قبل:** `TRADING_DAYS_PER_YEAR = 252`
- **بعد:** `TRADING_DAYS_PER_YEAR = 250`
- **دلیل:** بورس تهران ~250 روز معاملاتی دارد، نه 252 مانند NYSE

#### 6. `src/gold_desk/performance.py` — همین مشکل در محاسبه Sharpe/Sortino/Vol
- **قبل:** `DEFAULT_PERIODS_PER_YEAR = 252`
- **بعد:** `DEFAULT_PERIODS_PER_YEAR = 250`

#### 7. `src/gold_desk/antigravity/signal_engine.py` — SL/TP خیلی تنگ برای بازار ایران
- **قبل:** BUY: SL 3%, TP1 3%, TP2 6%
- **بعد:** BUY: SL 5%, TP1 5%, TP2 10%
- **دلیل:** ATR روزانه طلای ایران 2-5% است؛ مقادیر قبلی در اولین نوسان عادی trigger می‌شدند

#### 8. `src/gold_desk/dca_planner.py` — SL/TP خیلی کم برای بازاری با بازده 50-100%/سال
- **قبل:** conservative SL/TP: 5%/20%، balanced: 8%/25%، aggressive: 12%/35%
- **بعد:** conservative: 8%/40%، balanced: 12%/60%، aggressive: 20%/100%

---

### 🟡 متوسط (Medium)

#### 9. `src/gold_desk/forecaster.py` — drift clip خیلی محافظه‌کارانه
- **قبل:** `max(-0.02, min(0.02, drift))`
- **بعد:** `max(-0.05, min(0.05, drift))`
- **دلیل:** طلای ایران 3-5% حرکت روزانه دارد

#### 10. `src/gold_desk/forecaster.py` — confidence band cap خیلی پایین
- **قبل:** `min(1.96 * vol * sqrt(h), 1.0)`
- **بعد:** `min(..., 2.0)`
- **دلیل:** نوسان سالانه ایران اغلب >100% است

#### 11. `src/gold_desk/forecaster.py` — تاریخ UTC Gregorian به‌جای تاریخ شمسی
- **قبل:** `last_date = utc_now_naive().strftime("%Y-%m-%d")`
- **بعد:** `last_date = _tehran_jalali_today()` (با `jdatetime + now_tehran()`)

#### 12. `src/gold_desk/pattern_detector.py` — آستانه spike خیلی پایین
- **قبل:** `SPIKE_3D_THRESHOLD_PCT = 5.0`
- **بعد:** `SPIKE_3D_THRESHOLD_PCT = 10.0`
- **دلیل:** 5% در 3 روز در بازار ایران رایج است؛ 10% واقعاً غیرعادی است

---

## فایل‌های بررسی‌شده و بدون ایراد

`signal_engine.py`، `live_signals.py`، `auto_trade.py`، `antigravity/engine.py`، `antigravity/kill_switch.py`، `pricer.py`، `bubbler.py`، `hard_stops.py`، `indicators.py`، `scorer.py`، `entry_rules.py`، `black76.py`، `dates.py`، `returns.py`، `snapshot_service.py`

---

## فایل‌های خارج از محدوده این آدیت

`phase1.py` (کامل)، `phase2.py`، `portfolio.py`، `portfolio_history.py`، `nav_checker.py`، `parity.py`، `freshness.py`، `hotpath.py`، `metrics.py`، `goldapi_client.py`، `secondary_source.py`، `event_calendar.py`، `fund_registry.py`، `crypto.py`، `chat.py`، `macro_news.py`، `push.py`، `ws_hub.py`، `api.py`، `api_token.py`، `telegram_bot.py`، `alert_engine.py`، `backtest_real.py`

---

*گزارش توسط Claude Sonnet 4.6 در تاریخ 2026-11-12 تهیه شد.*
