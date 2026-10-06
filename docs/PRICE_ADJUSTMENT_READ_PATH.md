# 📐 مسیر خواندن قیمت تعدیل‌شده و تاریخ واقعی معامله

> Migrations: `0108` (view) و `0109` (تاریخ واقعی + هر دو تقویم) روی `0061` (جداول رویداد/ضریب)
> تاریخ: 2026-10-06 · تست: `tests/unit/services/test_adjusted_price_reader.py` (۲۳ تست)

## ۱. دو مشکلی که حل می‌کند

**الف) تعدیل رویداد شرکتی.** `daily_history` قیمت خام TSETMC را نگه می‌دارد. یک
افزایش سرمایه قیمت را یک‌شبه نصف می‌کند، پس هر اندیکاتوری که پنجره‌اش از تاریخ ex
بگذرد (MA/EMA، RSI، MACD، Bollinger، Ichimoku، ATR، Pivot) **غلط** است.
Migration `0061` ضریب تجمعی را در `daily_adjust_factors` ساخته بود ولی هیچ‌جا
خوانده نمی‌شد.

**ب) محور تاریخ.** `daily_history` (view از `0034`) ستون `trade_date` را از
`gregorian_date` می‌گیرد که **تاریخ fetch** است، نه تاریخ معامله. اندازه‌گیری روی
DB dev (۵٫۴۵M ردیف):

```text
rows = 5,450,380 · distinct symbol = 2,371 · distinct trade_date = 17
یک (symbol, trade_date) تا 5,902 ردیف تکراری
```

یعنی سری‌ای که به اندیکاتور داده می‌شد سری روزانه نبود و ضریب تعدیل هم روی همان
محور اشتباه محاسبه می‌شد (در حالی که `corporate_action_events.ex_date` میلادی
واقعی است).

تاریخ واقعی از قبل در جدول بود: ستون `date` (شمسی `YYYY-MM-DD`) — و
`(symbol, date)` **یونیک** است (ایندکس معتبر + صفر گروه تکراری؛ همه‌ی ۶٬۱۶۶ مقدار
موجود تاریخ شمسی معتبرند).

## ۲. قطعات

| قطعه | نقش |
|---|---|
| `jalali_to_gregorian(text) → date` (migration `0109`) | تبدیل شمسی→میلادی در SQL؛ IMMUTABLE/STRICT/PARALLEL SAFE |
| `vw_daily_history_adjusted` (`0109`) | هر کندل روزانه + **هر دو تقویم** + `adj_factor` + `price_*_adj` |
| `services/adjusted_price_reader.py` | منبع واحد خواندن کندل برای precompute و JIT |
| `services/indicator_precompute_service.py` | snapshot شبانه از همین مسیر + شمارش نمادها با تاریخ واقعی |
| `services/corporate_action_service.py` + `scripts/backfill_adjust_factors.py` | ضریب‌ها روی تاریخ **میلادی واقعی** |

```sql
-- هسته‌ی view (0109)
SELECT jalali_to_gregorian(h.date) AS trade_date,   -- میلادی (برای محاسبات)
       h.date                     AS trade_date_shamsi,  -- شمسی (برای نمایش)
       h.time                     AS trade_time,
       h.gregorian_date           AS fetch_date,     -- فقط برای ردیابی
       COALESCE(f.adj_factor, 1)  AS adj_factor,
       h.price_last * COALESCE(f.adj_factor, 1) AS price_last_adj, ...
FROM brsapi_historical_daily h
LEFT JOIN symbols s ON s.symbol = h.symbol
LEFT JOIN daily_adjust_factors f
       ON f.symbol_id = s.id AND f.trade_date = jalali_to_gregorian(h.date)
```

قواعد ضریب (منبع یگانه: `services/corporate_action_service.py`):

* `capital_increase` / `bonus` → `1/(1+ratio)` برای تاریخ‌های **قبل** از ex-date
* `dividend` → `(close_at_ex − dps)/close_at_ex`
* از ex-date به بعد ضریب `1` است (سری خام)

`daily_adjust_factors.trade_date` از این پس **تاریخ میلادی واقعی معامله** است.

## ۳. کارایی روی ~۱۰ میلیون ردیف (اندازه‌گیری‌شده)

| عملیات | نتیجه |
|---|---|
| خواندن ۳۲۰ کندل یک نماد (تعدیل‌شده) | **۱۳ ms گرم / ۵۰ ms سرد** |
| همان خواندن با `ORDER BY trade_date` (میلادی مشتق‌شده) | ۱۱۳–۲۸۳ ms ❌ |
| شمارش ۴۰۰ نماد برای job شبانه | ۸۳ ms سرد / ۹ ms گرم (قبل: **۵۴٬۰۷۲ ms** با `GROUP BY`) |
| اعمال migration `0109` | **۲۶ ثانیه** |

نکته‌ی کلیدی: خواندن بر اساس `trade_date_shamsi` مرتب می‌شود که لبه‌ی
`idx_hist_symbol_date` است؛ پس planner بعد از `LIMIT` تازه تاریخ میلادی را مشتق
می‌کند. ترتیب شمسی `YYYY-MM-DD` با ترتیب زمانی یکسان است (zero-padded)، لذا نتیجه
دقیقاً همان ترتیب میلادی است.

### چرا تاریخ میلادی **ستون** نشد؟

نوشتن مقدار در جدول یعنی بازنویسی ۵٫۴۵M ردیف، و این جدول **۱۲ ایندکس** دارد؛ پس
هر ردیف بازنویسی‌شده ۱۲ درج ایندکس هم می‌سازد. اندازه‌گیری‌شده روی DB dev:

* فراخوانی تبدیل برای هر ردیف: بعد از >۱۰ دقیقه لغو شد
* همان کار با نقشه‌ی تاریخ‌های متمایز (۶٬۱۶۶ تبدیل) + `UPDATE` کل جدول: بعد از
  **۲۸ دقیقه** لغو شد

در مقابل، مشتق‌کردن هنگام خواندن یک فراخوانی به‌ازای هر ردیف **بازگشتی** است
(حداکثر چند صد ردیف) و برای روزهای معاملاتی جدید هم **هیچ‌وقت کهنه نمی‌شود**
(چیزی که یک نقشه‌ی ۶٬۱۶۶ ردیفی می‌شد). اگر روزی اسکن بازه‌ای سراسری روی تاریخ
میلادی لازم شد، همان موقع می‌توان ستون یا expression index
`(symbol, jalali_to_gregorian(date))` را در maintenance window اضافه کرد؛ API
این reader تغییری نمی‌کند.

## ۴. صحت تبدیل تاریخ

* الگوریتم: پورت PL/pgSQL از `jalaali.c` (همان پیاده‌سازی `jdatetime` که در
  `scripts/backfill_dates.py` استفاده می‌شود) — پس SQL و پایتون هیچ‌وقت اختلاف
  ندارند.
* پایتون در برابر `jdatetime`: **۵۵٬۱۵۲ تاریخ (۱۳۰۰…۱۴۵۰) — ۰ اختلاف**
* تابع SQL در برابر پایتون روی داده‌ی واقعی: **۱۲٬۰۱۰ تاریخ — ۰ اختلاف**
* تاریخ‌های نامعتبر (مثل ۳۰ اسفند سال غیرکبیسه، ماه ۱۳، `junk`) → `NULL`؛ دقیقاً
  همان‌جا که `jdatetime.date()` استثنا می‌دهد
* در کل جدول **۰ ردیف** بدون تاریخ میلادی (`0 / 5,450,380`)

## ۵. فلگ و fallback

* `INDICATOR_ADJUSTED_PRICES=true` (پیش‌فرض) — مسیر تعدیل‌شده + تاریخ واقعی.
* `false` یا نبود view → مسیر خام (`daily_history`، تاریخ fetch). در این حالت
  `date_shamsi` برابر `None` است.
* probe وجود view در سطح پروسه کش می‌شود؛ بعد از migration روی پروسه‌ی در حال
  اجرا، restart (یا `reset_adjusted_source_cache()`).

## ۶. شواهد صحت (اجرای واقعی)

* `23/23` تست سبز؛ از جمله: تطابق تابع SQL با `jdatetime` روی >۱۰٬۰۰۰ تاریخ،
  یکسان‌بودن قیمت تعدیل‌شده با خام وقتی جدول ضریب خالی است، مقیاس‌شدن **فقط**
  همان تاریخ ex با ضریب ساختگی (و باقی‌ماندن حجم خام)، و یک‌کندل‌به‌ازای‌هر روز
  معاملاتی.
* اجرای `IndicatorPrecomputeService.run(batch_limit=1, symbol=…)` با ضریب ساختگی
  `0.5` روی آخرین تاریخ معامله: `RSI 48.3 → 18.9` و `EMA20 5189 → 4947`
  (تراکنش rollback شد؛ هیچ ردیفی باقی نماند).
* سری‌ها دیگر تکراری نیستند: `_load_candles(بورس)` = ۳۲۰ کندل، **۳۲۰ تاریخ
  متمایز**، از `2025-06-03` تا `2026-10-04` (شمسی `1405-07-12`).

## ۷. نکات باقی‌مانده

1. **پوشش نماد:** join ضریب روی `symbol_id` است، پس ردیف‌هایی که نمادشان در
   `symbols` نیست هیچ‌وقت تعدیل نمی‌شوند (`adj_factor = 1`) — سازگار با FK
   `corporate_action_events → symbols(id)`.
2. **ردیف‌های کهنه‌ی snapshot:** جدول `stock_indicators_snapshot` هنوز ۱٬۵۶۵ ردیف
   دارد که با محور fetch-date نوشته شده‌اند (فقط ۷ تاریخ متمایز؛ ۴۱۱ ردیف روی
   تاریخی نیست که برای آن نماد روز معامله باشد). precompute آن‌ها را بازنویسی
   نمی‌کند (idempotent روی `(symbol, trade_date)`) و چون `trade_date` کهنه‌شان
   جدیدتر است، ممکن است موقتاً به‌جای ردیف درست خوانده شوند. این جدول یک
   **کش مشتق** است و با اجرای precompute دوباره ساخته می‌شود؛ پاک‌سازی پیشنهادی
   (خارج از migration، دستی و عمداً حذف نشده تا داده‌ای بی‌اجازه پاک نشود):

   ```sql
   DELETE FROM stock_indicators_snapshot s
   WHERE NOT EXISTS (
       SELECT 1 FROM vw_daily_history_adjusted v
       WHERE v.symbol = s.symbol AND v.trade_date = s.trade_date
   );
   ```
3. ضریب‌ها وقتی رویداد واقعی CODAL لود و `backfill_adjust_factors.py` اجرا شود
   مؤثر می‌شوند (`corporate_action_events` و `daily_adjust_factors` فعلاً خالی‌اند).

## ۸. اجرا

```bash
alembic upgrade head                                   # view + تابع تبدیل تاریخ
python scripts/backfill_adjust_factors.py              # همه نمادهای دارای رویداد
python scripts/backfill_adjust_factors.py --symbol وبانک
```

اسکریپت backfill و سرویس `recompute_factors` هر دو idempotent هستند و از همین
view می‌خوانند، پس محور تاریخ در همه‌جا یکی است.

> `scripts/backfill_dates.py` (نوشته‌شده در سشن قبل) `trade_date_utc` را با
> `UPDATE` تک‌ردیفی می‌ساخت؛ روی ۵٫۴۵M ردیف عملی نیست و این کار لازم هم نیست چون
> `0109` تبدیل را در SQL انجام می‌دهد. آن اسکریپت فقط برای جداول دیگر
> (`brsapi_intraday_trades`, `brsapi_codal_announcements`, …) قابل استفاده است.
