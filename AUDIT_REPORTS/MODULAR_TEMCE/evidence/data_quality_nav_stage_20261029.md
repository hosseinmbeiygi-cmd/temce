# مرحلهٔ ۸ — کیفیت داده/NAV: شاهد اجرا (۲۹ اکتبر ۲۰۲۶)

دامنه: DB-04 (`trade_date`)، قواعد OHLC/timezone، overwrite تاریخچه، مقایسهٔ NAV با قیمت بازار.
هیچ DB/سرویس زنده لمس نشد؛ تست‌های DB-محور این محیط همان‌طور که در baseline بودند
(`InvalidPasswordError` برای user «market») fail می‌شوند و در شمارش جدا آمده‌اند.

## ۱) DB-04 — محور تاریخ معاملات

**قبل:** `services/adjusted_price_reader.py` اگر view `vw_daily_history_adjusted` نبود، بی‌صدا
به `daily_history` برمی‌گشت که `trade_date` آن **تاریخ fetch** است (۵٫۴۵M ردیف، ~۱۷ تاریخ
متمایز، تا ۵٬۹۰۲ ردیف روی یک `(symbol, trade_date)`). یعنی MA/RSI/MACD روی محور روزانهٔ
واقعی محاسبه نمی‌شد. `populate_profiles_service` هم همان جدول خام را با همان ترتیب می‌خواند.

**بعد:**
- [`AdjustedPriceSourceUnavailable`](file:///C:/Users/Iran/Desktop/temce/services/adjusted_price_reader.py#L55):
  وقتی dial روشن است و view نیست، reader استثنا می‌دهد — نه سری اشتباه.
- [`resolve_price_source`](file:///C:/Users/Iran/Desktop/temce/services/adjusted_price_reader.py#L171):
  فقط `INDICATOR_ADJUSTED_PRICES=false` یا `adjusted=False` صریح به raw می‌رود (حالت parity/backtest).
- مصرف‌کننده‌ها: `stock_read_through` (JIT) و `indicator_precompute_service` استثنا را می‌گیرند،
  لاگ می‌کنند و سری خالی برمی‌گردانند ⇒ «شاخص نیست» صریح، نه عدد غلط.
- [`populate_profiles_service`](file:///C:/Users/Iran/Desktop/temce/services/populate_profiles_service.py#L217)
  از view («۶۰ روز معاملاتی واقعی») می‌خواند.

**تست:** `tests/unit/services/test_adjusted_price_reader.py` — دو تست قرارداد به‌روز شد
(`test_missing_view_refuses_the_raw_fetch_date_axis`, `test_probe_failure_does_not_silently_use_raw`).
۷ تست DB-محور این فایل (converter SQL و خواندن واقعی view) در این محیط با خطای اتصال
PostgreSQL fail می‌شوند — همان TEST-01؛ **اجرای migration 0109 روی DB واقعی BLOCKED است**.

## ۲) overwrite تاریخچه → append-only

**قبل:** هر دو حلقهٔ `history_fetch_service` (crypto و gold/coin/FX) با
`ON CONFLICT (symbol, date) DO UPDATE` ردیف موجود را با fetch جدید بازنویسی می‌کردند؛ کامنت
کنار code ادعا می‌کرد «existing history is never rewritten» — در تضاد با SQL.

**بعد:** [`DO NOTHING`](file:///C:/Users/Iran/Desktop/temce/brsapi/services/history_fetch_service.py#L269)
در هر دو مسیر؛ `rowcount` تعیین می‌کند ردیف «نوشته شد» یا «از قبل موجود بود» و لاگ
`%d already stored` اضافه شد. `record_count` فقط نوشته‌های واقعی را می‌شمارد. اصلاح یک بار
provider نیازمند عملیات maintenance صریح است، نه backfill پس‌زمینه.

**تست:** `test_reingesting_an_existing_bar_does_not_rewrite_it`،
`test_crypto_history_is_append_only` (SQL شامل `DO NOTHING` و بدون `DO UPDATE`؛ شمارش درست).

## ۳) timezone — تاریخ بازار به وقت تهران

`jdatetime.date.today()`/`date.today()` از ساعت میزبان می‌خوانند. روی میزبان UTC از ۲۰:۳۰ UTC
تا نیمه‌شب، تاریخ تهران یک روز جلوتر است: مهر تاریخ پولت/دیده‌بانی NAV و استمپ کندل
درون‌روزی می‌توانست یک سشن عقب بیفتد.

- [`core.time.today_jalali_tehran()`](file:///C:/Users/Iran/Desktop/temce/core/time/__init__.py#L62)
  (Asia/Tehran) اضافه شد.
- `brsapi/parsers/tsetmc.py` (استمپ کندل intraday) و `brsapi/services/sync_service.py`
  (dedupe روزانهٔ NAV، دو نقطه) به آن منتقل شدند.
- گارد: `tests/unit/core/test_market_date_tehran.py` — محاسبه در مرز UTC، استمپ کندل با
  تاریخ تهران، و عدم وجود `date.today()` در دو مسیر نوشتن.
  **باقی‌مانده:** چند مسیر فقط-خواندن (`hidden_accumulation`, `iran_fear_greed_index`,
  `fund_discovery`) همچنان از تاریخ میزبان برای پنجره استفاده می‌کنند؛ خطای آن‌ها حداکثر یک
  روز است و به این برش وارد نشد.

## ۴) NAV در برابر قیمت بازار

**قبل:** `_latest_nav` هر NAV را (حتی یک‌ماهه) برمی‌داشت و `bubble = price − nav` بدون توجه به
تاریخ NAV محاسبه می‌شد؛ حباب «تخفیف/پرمیوم» می‌ساخت که واقعی نبود.

**بعد:**
- [`_latest_nav_with_date`](file:///C:/Users/Iran/Desktop/temce/src/gold_desk/nav_checker.py#L118)
  تاریخ همان ردیف را هم برمی‌گرداند (batch هم).
- [`MAX_NAV_AGE_DAYS=7` و `_nav_is_comparable`](file:///C:/Users/Iran/Desktop/temce/src/gold_desk/nav_checker.py#L148):
  NAV کهنه/بی‌تاریخ ⇒ `bubble_abs/bubble_pct = None` (مقایسه انجام نمی‌شود) ولی `nav_per_unit`
  و `market_price` و `nav_as_of` گزارش می‌شوند؛ warning هم ثبت می‌شود.
- واحدها یکسان‌اند: `gold_snapshots.market_price` با `round_to_rial(..., "toman")` در رایل
  ذخیره می‌شود و NAV سهام صندوق هم رایل است؛ قرارداد در docstring/تست تثبیت شد.

**تست:** `test_fresh_nav_computes_the_bubble`، `test_stale_nav_is_not_compared_with_a_live_price`،
`test_undated_nav_is_not_compared` + به‌روزرسانی تست batch (ردیف چهارستونه با تاریخ).

## ۵) قواعد OHLC — وضعیت

- اعمال `daily_bar_issues` روی crypto و gold/coin/FX (quarantine + شمارش) از قبل بود و اکنون
  با append-only سازگار است (ردیف invalid هرگز نوشته/بازنویسی نمی‌شود).
- **باز:** مسیر candlestick و `sync_history_price` (TSETMC) فیلتر OHLC ندارند؛ ردیف با
  high<low می‌تواند ذخیره شود. این نیازمند تصمیم دربارهٔ سرنوشت ردیف (reject/quarantine) در
  `sync()` عمومی است و به این برش وارد نشد.

## ۶) اجرای تست

| مجموعه | نتیجه |
|---|---|
| `tests/unit/core/test_market_date_tehran.py` | ۴ passed |
| `tests/unit/brsapi/test_history_fetch_quality.py` | ۱۱ passed |
| `tests/unit/brsapi/test_history_savepoints.py` | ۱ passed |
| `tests/gold_desk/test_nav_checker.py` | ۱۴ passed |
| `tests/unit/gold_desk/test_nav_date_normalization.py` + `test_nav_seven_day_window.py` | ۸ passed |
| `tests/unit/services/test_adjusted_price_reader.py` | ۱۶ passed، ۷ failed (DB auth — محیط) |
| `tests/unit/brsapi` + `tests/unit/gold_desk` + `tests/gold_desk` + `tests/unit/core/test_market_date_tehran.py` | ۷۳۳ passed، ۱ skipped، ۲ failed (PostgreSQL) |
| ruff روی همهٔ فایل‌های تغییریافته | پاک |

**محدودیت‌ها:** migration 0109 و خواندن واقعی view اجرا نشد (PostgreSQL در دسترس نیست)؛
۷ تست DB-محور reader و ۲ تست snapshot integration به همین دلیل fail می‌شوند (پیش از این برش
هم در baseline همین‌طور بودند)؛ قواعد OHLC روی candlestick/history خام اعمال نشده است.
