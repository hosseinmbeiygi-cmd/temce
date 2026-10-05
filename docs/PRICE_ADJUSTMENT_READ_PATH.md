# 📐 مسیر خواندن قیمت تعدیل‌شده برای اندیکاتورها

> Migration: `0108` (view) روی `0061` (جداول رویداد/ضریب) | تاریخ: 2026-10-05 | تست: `tests/unit/services/test_adjusted_price_reader.py`

## ۱. مشکلی که حل می‌شود

`daily_history` قیمت خام TSETMC را نگه می‌دارد. یک افزایش سرمایه قیمت را
یک‌شبه نصف می‌کند، پس هر اندیکاتوری که پنجره‌اش از تاریخ ex بگذرد
(MA/EMA، RSI، MACD، Bollinger، Ichimoku، ATR، Pivot) از آن لحظه تا پایان
پنجره **غلط** است — چه در precompute شبانه و چه در محاسبه JIT.

Migration `0061` ضریب تجمعی هر `(symbol_id, trade_date)` را در
`daily_adjust_factors` ساخته بود، ولی **هیچ‌جا خوانده نمی‌شد**. این تغییر
حلقه را می‌بندد.

## ۲. قطعات

| قطعه | نقش |
|---|---|
| `vw_daily_history_adjusted` (migration `0108`) | همه `daily_history` + `adj_factor` + ستون‌های `price_*_adj`؛ price خام هم دست‌نخورده می‌ماند |
| `services/adjusted_price_reader.py` | انتخاب منبع (view/خام)، ساخت کندل، probe کش‌شده وجود view |
| `services/indicator_precompute_service.py` | کندل‌های snapshot شبانه از مسیر تعدیل‌شده + شمارش نمادها به‌شکل ایندکس‌محور |
| `services/stock_read_through.py` | مسیر JIT تب اندیکاتور از همان reader (پس precompute و JIT هرگز اختلاف ندارند) |

```sql
-- هسته‌ی view
SELECT d.*, COALESCE(f.adj_factor, 1) AS adj_factor,
       d.price_last * COALESCE(f.adj_factor, 1) AS price_last_adj, ...
FROM daily_history d
LEFT JOIN daily_adjust_factors f
       ON f.symbol_id = d.symbol_id AND f.trade_date = d.trade_date
```

قواعد ضریب (منبع یگانه: `services/corporate_action_service.py`):

* `capital_increase` / `bonus` → `1/(1+ratio)` برای تاریخ‌های **قبل** از ex-date
* `dividend` → `(close_at_ex − dps)/close_at_ex`
* از ex-date به بعد ضریب `1` است (سری خام)

## ۳. کارایی روی ~۱۰ میلیون ردیف

`daily_history` یک **view** روی `brsapi_historical_daily` است و خودش هم یک
`LEFT JOIN symbols` دارد؛ پس هر join اضافه باید با اثبات اندازه‌گیری شود
(اندازه‌گیری روی DB dev، `brsapi_historical_daily` = ۵٫۴۵M ردیف):

| عملیات | قبل | بعد |
|---|---|---|
| خواندن کندل یک نماد (LIMIT 260) | ۲ ms (خام) | ۲–۹ ms (تعدیل‌شده) — هر ردیف یک PK probe روی `daily_adjust_factors` |
| شمارش نمادها برای job شبانه | `GROUP BY symbol` روی کل view: **۵۴٬۰۷۲ ms** | `CROSS JOIN LATERAL` روی `idx_hist_symbol_gregorian`: **۸۳ ms سرد / ۹ ms گرم** |

نکته‌ها:

* view مادیالایز نشده است؛ planner آن را inline می‌کند و `symbol = :sym`
  را تا `idx_hist_symbol_gregorian` پایین می‌برد — هیچ ایندکس جدیدی لازم نیست.
* **مسیرهای market-wide از view تعدیل‌شده نمی‌خوانند**: شمارش
  `MAX(trade_date)` به تعدیل نیازی ندارد و join آن روی ۵٫۴M ردیف فقط هزینه
  است (به همین دلیل `_select_symbols` مستقیم روی جدول پایه کار می‌کند).
* ستون‌های `trade_volume`/`trade_value` عمداً تعدیل **نمی‌شوند** (هم‌راستا با
  کنوانسیون `auto_adjust` و برای سازگاری با جریان پول خام)، و
  `*_change_pct` هم چون یک ضریب ثابت در نسبت درون‌روزی حذف می‌شود.

## ۴. فلگ و fallback

* `INDICATOR_ADJUSTED_PRICES=true` (پیش‌فرض) — مسیر تعدیل‌شده.
* `false` → قیمت خام (بدون probe).
* اگر view وجود نداشته باشد (migration اجرا نشده) خواندن **خودکار** به خام
  برمی‌گردد و یک warning یک‌بار لاگ می‌شود؛ هیچ‌وقت خطا نمی‌دهد.
* probe وجود view در سطح پروسه کش می‌شود؛ بعد از اجرای migration روی پروسه
  در حال اجرا، پروسه را restart کنید (یا در تست/اسکریپت
  `reset_adjusted_source_cache()` را صدا بزنید).

## ۵. شواهد صحت

* `17/17` تست `tests/unit/services/test_adjusted_price_reader.py` سبز است:
  - وقتی `daily_adjust_factors` خالی است، خروجی تعدیل‌شده **دقیقاً** برابر
    خام است (پاریتی کامل ⇒ روشن‌کردن فلگ بی‌اثر است).
  - با درج ضریب ساختگی `0.5` برای یک تاریخ، فقط همان تاریخ مقیاس می‌شود و
    بقیه بایت‌به‌بایت یکسان می‌مانند (تراکنش rollback می‌شود).
  - شمارش نمادها با `LATERAL` همان خروجی `GROUP BY` را می‌دهد (پاریتی).
* اجرای واقعی `IndicatorPrecomputeService.run(batch_limit=1, symbol=…)` با
  ضریب ساختگی: `RSI 51.9 → 21.6`، `EMA20 6220 → 5664`، `MACD 179 → −254`
  و upsert داخل تراکنش انجام و rollback شد (هیچ ردیفی باقی نماند).

## ۶. محدودیت‌های شناخته‌شده

1. **پوشش نماد:** join روی `symbol_id` است و این ستون از `symbols` می‌آید.
   در DB dev، ۴٫۵M از ۵٫۴۵M ردیف `symbol_id` ندارند (نمادهای قدیمی/حذف‌شده)
   و هیچ‌وقت تعدیل نمی‌شوند (`adj_factor = 1`). این با FK
   `corporate_action_events → symbols(id)` سازگار است: نماد ثبت‌نشده اصلاً
   نمی‌تواند رویداد داشته باشد.
2. **🔴 محور تاریخ (بلاکر واقعی):** در `daily_history`، ستون `trade_date` از
   `gregorian_date` می‌آید که **تاریخ fetch** است، نه تاریخ معامله
   (هشدار migration `0034`). اندازه‌گیری روی DB dev:

   ```text
   rows=5,450,380 · distinct symbol=2,371 · distinct trade_date=17
   یک (symbol, trade_date) تا 5,902 ردیف تکراری دارد
   ```

   یعنی سری‌ای که امروز به اندیکاتور داده می‌شود سری روزانه نیست. تاریخ
   واقعی معامله در ستون `date` (شمسی، رشته‌ای مثل `1405-04-28`) است و
   `scripts/backfill_dates.py` قرار بود `trade_date_utc` بسازد که ساخته نشده.
   تا وقتی این اصلاح نشود، ضریب‌های تعدیل هم روی همان محور اشتباه محاسبه
   می‌شوند (`corporate_action_events.ex_date` میلادی است و با تاریخ fetch
   مقایسه می‌شود). **اقدام پیشنهادی:** ساخت `trade_date_utc` (تبدیل
   شمسی→میلادی، یک‌بار برای ۵٫۴۵M ردیف)، dedupe به `(symbol, trade_date_utc)`
   و سپس تغییر **همان‌جا** که منبع خواندن تعریف شده
   (`services/adjusted_price_reader.py`) — چون مسیر خواندن مرکزی شده، اصلاح
   محور تاریخ فقط یک نقطه تغییر دارد و precompute و JIT با هم درست می‌شوند.

## ۷. اجرا

```bash
alembic upgrade head            # view را می‌سازد
python scripts/backfill_adjust_factors.py            # همه نمادهای دارای رویداد
python scripts/backfill_adjust_factors.py --symbol وبانک
```

بعد از بارگذاری رویدادهای واقعی CODAL، ضریب‌ها را دوباره backfill کنید
(اسکریپت idempotent است).
