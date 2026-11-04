# SPEC_DATA_SCHEMAS — پیش‌نویس اسکیماها (بخش‌های ۰ و ۱ لازم برای مراحل ۱ و ۲)

> **وضعیت: پیشنهادی.** طبق `CLAUDE.md`، قبل از اتکا با نمونه‌ی واقعی و `information_schema` تطبیق شود. ستون‌های «مشاهده‌شده» در بخش ۲ از خروجی واقعی ممیزی (`audit/REPORT_FULL.md` بخش C3 و G1) است؛ بخش ۱ طراحی هدف است، نه واقعیت فعلی.

## ۰. قراردادهای عمومی
1. **واحد قیمت:** ریال؛ `decimal` (نه float) در لایه‌ی `adjusted`/`curated`.
2. **زمان:** UTC + `Asia/Tehran`؛ هرگز offset ثابت. تاریخ‌ها هم میلادی (`trade_date: date`) و هم جلالی (`jalali_date: varchar 'YYYY-MM-DD'`)؛ تبدیل فقط با کتابخانه‌ی تست‌شده.
3. **bitemporal:** هر رکورد `event_time` (رویداد) و `knowledge_time` (زمان در دسترس‌شدن برای ما) دارد؛ `ingested_at` زمان درج؛ **اصلاحیه = نسخه‌ی جدید، نه بازنویسی**. بک‌تست در T فقط `knowledge_time ≤ T` را می‌بیند. اگر منبع فقط `event_time` دارد: `assumed_latency` ثابت محافظه‌کارانه + پرچم `knowledge_time_assumed=true`.
4. **شناسه:** `instrument_id` ثابت (UUID) + `symbol_history`؛ نماد به شکل نرمال‌شده (یکسان‌سازی «ی/ي»، «ک/ك»، نیم‌فاصله، ارقام) تطبیق می‌شود، نه رشته‌ی خام.
5. **لایه‌ها:** `raw` → `clean` → `adjusted` → `curated`؛ هر لایه قابل بازسازی از قبلی.
6. **رد صریح:** ردیف نامعتبر در جدول `dq_rejections` با دلیل ثبت می‌شود؛ حذف بی‌صدا ممنوع.

## ۱. جدول‌های هدف

### instruments / symbol_history
```
instruments(instrument_id PK, instrument_class, market, segment, isin NULL, created_at)
symbol_history(instrument_id, symbol_norm, symbol_raw, from_date, to_date NULL, source_ref)
```
قید: بازه‌های `symbol_history` برای یک `instrument_id` هم‌پوشان نباشند. نمادهای حذف‌شده حذف نمی‌شوند (`to_date` دارند).

### calendar / market_status_events
```
calendar(date PK, jalali_date, is_trading_day, market_status, segment, source_ref)
market_status_events(event_id PK, scope(market/segment/symbol), status, from_ts, to_ts NULL, source_ref, knowledge_time)
```
`market_status ∈ {open, closed_holiday, closed_unscheduled, halted_symbol}`. روزهای تعطیل رکورد معامله‌ی ساختگی ندارند؛ در محاسبه‌ی نوسان/شارپ حذف می‌شوند (نه صفر).

### rules
```
rules(rule_key, scope, value, unit, effective_from, effective_to NULL, source_ref, confidence, verified_by, knowledge_time)
```
هم‌پوشانی بازه‌ها برای `(rule_key, scope)` ⇒ خطا. دسترسی فقط `rule_at(key, scope, date)`.

### equity_daily (قرارداد داده، ARCHITECTURE بخش ۲۴)
```
keys: (instrument_id, trade_date, knowledge_time)
open, high, low, close, last: decimal rial
volume: int64; value: decimal; trade_count: int64
base_volume: int64 NULL
price_limit_upper, price_limit_lower: decimal NULL   # از rules، نه از منبع
status: enum {open, halted, closed, suspended}
jalali_date, regime_epoch, source_id, knowledge_time_assumed: bool
checks: low ≤ open,close ≤ high؛ close در دامنه مگر استثنای ثبت‌شده؛ volume,value ≥ 0؛ یکتایی کلید
freshness_sla: روز معاملاتی بعد تا ساعت ۲۰:۰۰
```

### corporate_actions / adjust_factors
```
corporate_actions(event_id PK, instrument_id, action_type, ex_date, ratio NULL, cash_per_share NULL,
                  record_date NULL, source, source_ref, knowledge_time)
adjust_factors(instrument_id, trade_date, adj_factor, method_version, computed_at, based_on_event_ids)
```
`action_type ∈ {bonus, cash_dividend, capital_increase_contribution, capital_increase_reserves, split, merger, rights}`. ضریب تعدیل فقط از این جدول؛ تست پیوستگی ارزش پرتفوی در `ex_date`؛ تطبیق با سری رسمی/منبع دوم و گزارش اختلاف روزانه (`SPEC_VALUATION` بخش ۱).

### real_legal_daily
```
(instrument_id, trade_date, buy_real_count, buy_legal_count, sell_real_count, sell_legal_count,
 buy_real_volume, buy_legal_volume, sell_real_volume, sell_legal_volume, *_value, knowledge_time)
```
بدون `knowledge_time` واقعی ⇒ `assumed_latency` + پرچم؛ فیچرهای مبتنی بر آن هشدار می‌دهند.

### universe_log
```
(date, instrument_id, in_universe: bool, reason)   # دلیل حذف هر نماد در هر روز (SPEC_ML بخش ۱)
```

## ۲. وضعیت فعلی (مشاهده‌شده در ممیزی؛ نه طراحی)

| جدول فعلی | ستون‌های مشاهده‌شده | مشکل (ID) | هدف مهاجرت |
|---|---|---|---|
| `brsapi_historical_daily` (۵٬۵۵۴٬۶۲۵ ردیف) | `symbol, date(varchar جلالی), time, trade_count, trade_volume, trade_value, price_min, price_max, price_yesterday, price_first, price_last, price_last_change, price_last_change_pct, price_close, price_close_change, price_close_change_pct, created_at, ins_id, instrument_id, updated_at, gregorian_date, shamsi_date` | `gregorian_date`/`shamsi_date` = تاریخ sync نه معامله (G-01)؛ `updated_at` ⇒ upsert بازنویسی می‌کند؛ hypertable نیست؛ بدون knowledge_time (G-03) | افزودن `trade_date`، `first_seen_at`؛ حفظ ستون‌ها؛ `equity_daily` به‌صورت view/لایه‌ی جدید |
| `brsapi_historical_real_legal` (۴٬۸۹۷٬۶۵۹) | `symbol, date, buy/sell_real/legal_count/volume/value, gregorian_date, shamsi_date, created_at, updated_at` | همان مشکلات | `real_legal_daily` |
| `corporate_action_events` (۵۸۶ ردیف) | `symbol_id, ex_date, action_type, ratio, dps, source, codal_ref, notes, created_at` | فقط `capital_increase`، همه `dps=0` (C-05) | افزودن `cash_dividend` و انواع دیگر |
| `corporate_actions` | `symbol, action_type, ex_date, record_date, params, applied, source, raw_text` | **۰ ردیف** | تصمیم: ادغام با بالا یا حذف |
| `daily_adjust_factors` (۶۲۱٬۸۱۸) | `symbol_id, trade_date, adj_factor, computed_at` | بک‌تست استفاده نمی‌کند (C-04)؛ منبع/روش محاسبه نامعلوم | `adjust_factors` با `method_version` |
| `vw_daily_history_adjusted` | — (ویو) | بی‌استفاده | مبنای بارگذاری تعدیل‌شده پس از تطبیق |
| `symbols` (۵۱۱ ردیف) | — | کمتر از ۲۴۰۷ نماد تاریخی (C-08) | `instruments`/`symbol_history` |
| `brsapi_nav_records` (۳٬۵۸۸)، `brsapi_gold_coin_history` (۴۴٬۹۶۵)، `brsapi_codal_announcements` (۷۸٬۷۸۹) | نامشخص | بدون knowledge_time | بعد از R2 در ماتریس پوشش |
| `brsapi_currency_history`, `brsapi_option_snapshots` | کوئری عمومی خطا داد (اسکیمای متفاوت) | G-06 | بررسی جدا |

## ۳. مهاجرت (Strangler)
1. ستون‌ها/ویوهای جدید **کنار** جدول‌های فعلی؛ حذف یا تغییر ستون فعلی ممنوع.
2. هر migration: فایل SQL پیشنهادی + تست rollback + تست تطبیق «قدیم در برابر جدید»؛ اجرا با مالک.
3. اختلاف خروجی قدیم و جدید توضیح داده شود (غالباً نشانه‌ی باگ قدیمی).

## ۴. چک‌های DQ (تولید خودکار از قرارداد)
- ناسازگاری قیمت (low ≤ open,close ≤ high)، جهش غیرممکن، قیمت خارج از دامنه‌ی `rule_at` همان روز.
- حجم/ارزش منفی یا ناسازگار؛ تکرار؛ سوراخ نسبت به تقویم؛ روز تعطیل با رکورد معامله.
- افت ex-date: سقوط قیمت در `ex_date` سود نقدی با مقدار سود سازگار باشد (در نبود رویداد سود ⇒ هشدار).
- اختلاف با منبع دوم/سری رسمی؛ DQ Score هر مجموعه؛ زیر آستانه ⇒ هشدار/توقف بک‌تست.
