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
| `scripts/import_corporate_actions.py` | پر کردن `corporate_action_events` از فایل‌های CODAL + تاریخ ex و نسبت از بازپایه‌گذاری TSETMC (بخش ۹) |

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
   مؤثر می‌شوند (بخش ۹).

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

## ۹. پر کردن رویدادها: `scripts/import_corporate_actions.py`

ضریب‌ها تا وقتی `corporate_action_events` خالی است هیچ اثری ندارند. این اسکریپت
آن جدول را پر می‌کند و بعد `backfill_adjust_factors.py` ضریب‌ها را می‌سازد.

### ۹٫۱ دو منبع، دو نقش

* **CODAL** (`codal_reports_backup.summary LIKE '%ثبت افزایش سرمایه%'` +
  `brsapi_codal_announcements.title ILIKE '%آگهی ثبت افزایش سرمایه%'`) → **برچسب
  رویداد** + ارجاع (`codal_ref`). مجموعاً ۴۷۶ نماد.
* **بازپایه‌گذاری خود TSETMC** → **تاریخ ex و نسبت** (دقیق).

روی روز ex، TSETMC مقدار `price_yesterday` را روی پایه‌ی تعدیل‌شده بازنشانی
می‌کند و درصد تغییر همان روز را نسبت به همان پایه گزارش می‌کند؛ پس تعدیل از
`price_close_change_pct` پنهان می‌ماند. روی هر روز معاملاتی دیگرِ یک نماد سالم،
`price_yesterday` **دقیقاً** برابر close روز قبل است. مقادیر تأییدشده:

```text
ومهان   2026-09-12  8250 → py 5500   f = 1/1.5    (ratio = 0.5)
سیدکو   2026-09-01 45510 → py 11380  f = 1/4      (ratio = 3)
شساخت   2026-09-02 21780 → py  4200  f = 1/5.19   (ratio = 4.19)
```

پس `ratio = 1/f − 1` که دقیقاً معکوسِ `1/(1+ratio)` در
`services/corporate_action_service.py` است.

### ۹٫۲ چرا تشخیص نماد‌به‌نماد گارد شده است

`price_yesterday` **سراسری** قابل اعتماد نیست؛ فقط per-symbol است. روی ۲٬۲۳۱ نماد
با ≥۱۰۰ ردیف (از ۲۰۲۳):

```text
۳۷۰ نماد   price_yesterday == prev_close روی ۱۰۰٪ ردیف‌ها
۸۳۸ نماد   ۹۰–۱۰۰٪
t~۷۵۰ نماد  <۳۰٪      ← ردیف‌های آشغال (مثلاً price_close = 1 در برابر py = 41,330)
```

یک فیلتر سراسری `|f−1| > ε` حدود **۱٫۲۵M** «رویداد» پیدا می‌کند؛ یعنی بی‌فایده.
بنابراین:

1. یک نماد فقط وقتی واجد شرایط است که `clean_rate` خودش بالا باشد
   (`--min-clean-rate`، پیش‌فرض `0.98`) و ≥ `--min-rows` ردیف قابل استفاده داشته
   باشد.
2. فقط روزهایی که `f < 1` هستند کاندیداند (افزایش سرمایه همیشه به **پایین**
   بازپایه می‌کند).
3. یک افزایش سرمایه فقط وقتی نوشته می‌شود که یک فایل CODAL تاریخ ex را تأیید کند
   (`--window-before`/`--window-after`، پیش‌فرض `−120…+240`).

روزهای تأییدنشده به‌صورت پیش‌فرض **رد** می‌شوند (از آرتیفکت داده قابل تفکیک
نیستند)؛ `--include-dividends` آن‌ها را به‌عنوان `dividend` با
`dps = close·(1−f)` می‌نویسد، به‌طوری‌که `(close − dps)/close` دقیقاً `f` را
بازتولید کند.

### ۹٫۳ چرا تشخیص دسته‌ای (batch) است

نسخه‌ی تک‌کوئری (window روی کل view) Postgres را وادار می‌کند همه‌ی ۵٫۴۵M ردیف
را مرتب و به `base/pgsql_tmp` بریزد — روی دیسک پر با
`DiskFullError: could not write to file base/pgsql_tmp/...` شکست می‌خورد و حتی
وقتی جا باشد کند است. اسکریپت ۲۵ نماد در هر پرس‌وجو می‌گیرد
(`--batch-size`) و predicate روی `symbol` توسط `idx_hist_symbol_date` سرو
می‌شود؛ پس مرتب‌سازی در حافظه می‌ماند و view هرگز کامل اسکن نمی‌شود.

### ۹٫۴ محدودیت مهم: پوشش رجیستری نماد

`corporate_action_events.symbol_id` و `daily_adjust_factors` هر دو FK به
`symbols(id)` دارند و view هم ضریب را از طریق `symbols` وصل می‌کند. اما:

```text
نمادهای دارای داده‌ی قیمت      = 2,371
ردیف‌های symbols (seed دستی)   =   511
نمادهای دارای رویداد قابل تشخیص = 1,921
از آن‌ها ثبت‌شده در symbols     =   225   ← بقیه ۸۳٪ تاریخ قیمت را پوشش می‌دهند
```

هیچ job‌ی `symbols` را پر نمی‌کند (فقط seed اولیه)، در حالی که precompute
اندیکاتورها روی **همه‌ی** نمادهای `brsapi_historical_daily` می‌چرخد. یعنی تا وقتی
نمادهای گمشده در `symbols` ثبت نشوند، قیمت آن‌ها هیچ‌وقت تعدیل نمی‌شود (بند ۱ در
بخش ۷).

اسکریپت به‌صورت پیش‌فرض رجیستری را **دست نمی‌زند** و فقط گزارش می‌کند:

```bash
python scripts/import_corporate_actions.py --dry-run --report-unregistered
```

با `--register-missing` نمادهای تأییدشده‌ی گمشده را در `symbols` درج می‌کند
(name/isin از جدیدترین `brsapi_symbol_snapshots`، و `id` از یک hash قطعی در بازه‌ی
`[10^18, 10^18+10^15)` که با idهای seed‌شده برخورد نمی‌کند). این تغییر در
رجیستری اثر دارد و عمداً opt-in است.

### ۹٫۵ اجرا

```bash
# پیش‌نمایش (هیچ نوشتنی)
python scripts/import_corporate_actions.py --dry-run --report-unregistered

# ثبت نمادهای گمشده + درج رویدادها
python scripts/import_corporate_actions.py --register-missing

# ضریب‌ها روی تاریخ میلادی واقعی
python scripts/backfill_adjust_factors.py
```

هر دو اسکریپت idempotent هستند (`ON CONFLICT (symbol_id, ex_date, action_type)` و
`ON CONFLICT (symbol_id, trade_date)`). تست‌های واحد منطق خالص:
`tests/unit/scripts/test_import_corporate_actions.py`.

### ۹٫۶ وضعیت اجرا (۲۰۲۶-۱۰-۰۶)

کد و تست‌ها آماده‌اند (۱۷ تست سبز، ruff پاک) و اجرای تک‌نماد درست کار می‌کند
(ومهان: ۷ روز بازپایه، `clean_rate 0.9916`، ۵ رویداد تأییدشده توسط CODAL).
اجرای دسته‌ای هم روی ۱٬۰۰۰ از ۲٬۳۷۱ نماد رسید و ۳٬۵۷۷ روز بازپایه پیدا کرد.
اما **اجرای کامل انجام نشده**: درایو `C:` روی ۱۰۰٪ است و آزاد آن در جریان همین
اسکن‌ها از ۱٫۳GB به **۴۸MB** رسید؛ Postgres برای اسکن/بک‌فیل کامل
`DiskFullError: could not write to file base/pgsql_tmp/...` می‌دهد. تا آزاد
نشدن فضا، `corporate_action_events` و `daily_adjust_factors` خالی می‌مانند
(تأیید‌شده: هر دو صفر ردیف).

> **به‌روزرسانی (۲۰۲۶-۱۰-۰۷) — این بند باطل شد، نه اصلاح.** فضا آزاد شد (۴۸MB → ۲۶GB) و هر دو اسکریپت روی پایگاه دادهٔ واقعی **اجرا شدند**: واردسازی با exit 0 و **۵۸۶ رویداد** در `corporate_action_events` (۱۴۵ نماد، همه `capital_increase` و `source='codal'`) و بک‌فیل با exit 0 در ۷۳ ثانیه و **۶۲۱٬۸۱۸ فاکتور** در `daily_adjust_factors`. اثر واقعی هم اندازه‌گیری شد: روی ومعادن، میانگین متحرک ۲۰ ردیفی خام **۳۶۲۰٫۲۰** در برابر تعدیل‌شده **۲۶۱۰٫۷۱** ⇒ **۳۸٫۷٪** خطا اگر فاکتور نادیده گرفته شود. شرح کامل در `docs/SESSION_REPORT_2026-10-06_EN.md` بخش A14 و `docs/FINAL_REPORT_2026-10-07_FA.md` بخش ۳. `symbols` دست‌نخورده و هنوز ۵۱۱ ردیف است؛ ۲۸۶ نماد از ۴۳۱ نماد تأییدشده همچنان گرفتار FK هستند و `--register-missing` عمداً اجرا نشد.

## ۱۰. وضعیت مخزن و شواهد تأیید (۲۰۲۶-۱۰-۰۶)

سه فایل زیر در یک commit واحد روی `main` قرار گرفتند:

```text
43278bbd  feat(corporate-actions): import CODAL capital increases with
          TSETMC-derived ratios

  docs/PRICE_ADJUSTMENT_READ_PATH.md                 | 121 ++++-   (+120/−1)
  scripts/import_corporate_actions.py                | 522 ++++++++  (جدید)
  tests/unit/scripts/test_import_corporate_actions.py | 131 ++++++  (جدید)
  3 files changed, 773 insertions(+), 1 deletion(-)
```

هیچ‌کدام از تغییرات از پیش موجود و نامرتبط (ده‌ها فایل `M`) در این commit نیامد؛
فقط همین سه مسیر stage شدند. push انجام نشد.

شواهد تأیید (کد همه با capture شدن exit status):

| بررسی | فرمان | نتیجه |
|---|---|---|
| lint | `ruff check scripts/import_corporate_actions.py tests/unit/scripts/test_import_corporate_actions.py` | exit 0 — `All checks passed!` |
| تست | `pytest tests/unit/scripts/test_import_corporate_actions.py` | exit 0 — ۱۷ passed |
| محتوای commit | `git show --name-only HEAD` | دقیقاً ۳ مسیر مورد نظر |
| درخت کاری | `git status --short <۳ فایل>` | تمیز (بدون تغییر باقی‌مانده) |
| عدم نوشتن در DB | `SELECT count(*)` روی سه جدول | `corporate_action_events`=0، `daily_adjust_factors`=0، `symbols`=511 |

نکته: در این مخزن commitlint/husky/commit-msg hook وجود ندارد (فقط `post-checkout` و
`post-commit`)، و پیام commit با سبک موجود هم‌خوان است (طول subject این مخزن
۷۳ تا ۱۰۰ کاراکتر است).

## ۱۱. پیوست: اعداد پوشش و خطاهای مسیر کار (تأیید مجدد ۲۰۲۶-۱۰-۰۶)

### ۱۱٫۱ فضای شناسه و پوشش رجیستری

```text
symbols                                  = 511
  که در screener_profiles هم هستند      = 511 / 511
  که gregorian_date دارند               = 511 / 511
  market_type: stock 499 + ETF 12
instruments                              = 499
  که id شان دقیقاً برابر symbols.id است = 499 / 499   ← فضای id مشترک
brsapi_symbol_snapshots (نماد متمایز)    = 2,375
  که در symbols ثبت شده‌اند             = 237
brsapi_historical_daily ∩ symbols        = 238
vw_daily_history_adjusted ∩ instruments  = 226
```

`ins_id` در اسنپ‌شات‌ها **منبع** `symbols.id` نیست:

```text
خودرو: ins_id=65883838195688438  vs  symbols.id=1234567890123456
فولاد: ins_id=46348559193224090  vs  symbols.id=39934567890123456
وبملت: ins_id=778253364357513    vs  symbols.id=50134567890123456
```

### ۱۱٫۲ خطاهای محیطی مشاهده‌شده

| خطا | توضیح |
|---|---|
| `InsufficientPrivilegeError: permission denied to examine "data_directory"` | `SHOW data_directory` روی نقش `hossein`؛ مسیر داده دستی پیدا شد: `C:\Program Files\PostgreSQL\18\data` |
| تایم‌اوت پرس‌وجوی اندازه | `pg_total_relation_size` روی همهٔ جدول‌ها (`pg_statio_user_tables` LIMIT 15) بعد از ۱۸۰s درخواست پاسخ نداد (دیسک پر) |
| اسکن `du` ناتمام | `du -sh` روی درایو پر عملاً تمام نشد و kill شد — توزیع مصرف فضای کل درایو اندازه‌گیری نشد |

`SELECT 1` و `pg_stat_activity` سریع جواب می‌دادند (۳ نشست فعال)، پس مشکل «DB خاموش» نبود؛ فقط I/O و دیسک.

### ۱۱٫۳ خطاهای مسیر توسعه و رفع آن‌ها

| # | خطا | رفع |
|---|---|---|
| ۱ | `F401` — `timedelta` بلااستفاده | import حذف شد |
| ۲ | `TypeError: int() argument must be ... not 'NoneType'` از `symbol_id` تهی view | ابتدا شرط `symbol_id IS NOT NULL` (که بعداً با تغییر کامل رویکرد به symbol-keyed جای‌گزین شد) |
| ۳ | `DiskFullError` در `CREATE TEMP TABLE` روی view | تبدیل تشخیص به batch نمادها |
| ۴ | `AmbiguousColumnError: column reference "prev_close" is ambiguous` در پروب | ستون‌ها صریح alias شدند |
| ۵ | `AttributeError: 'str' object has no attribute 'toordinal'` (پاس‌دادن رشتهٔ تاریخ به asyncpg) | `date.fromisoformat` |
| ۶ | پیشنهاد ruff برای ساده‌سازی `if/else` | تبدیل به عملگر سه‌گانه |
| ۷ | تست لبهٔ پنجره ابتدا با محاسبهٔ غلط روزها (ادعای `None` برای فایلی دقیقاً روی لبهٔ +۲۴۰) | تست اصلاح شد تا لبه‌ها «شامل» و یک روز بعد «رد» را بسنجد — assertion ضعیف نشد |

### ۱۱٫۴ نکات دیگر مخزن

* در حین جست‌وجوها چند worktree دیگر مخزن هم پیدا شد: `.kilo/worktrees/{exuberant-authority,flicker-cello,highly-process,nonstop-power,shadowed-chicken}` (کپی‌های کاری، دست‌نخورده).
* `scripts/backfill_dates.py` که در سشن قبل برای ستون `trade_date_utc` نوشته شده بود، عملاً لازم نیست: `0109` تبدیل را در SQL انجام می‌دهد و آن اسکریپت فقط برای جداول دیگر (`brsapi_intraday_trades`, `brsapi_codal_announcements`, …) قابل استفاده است.
* `_run_ms.py` و سایر فایل‌های فهرست ابتدای سشن، در این کار لمس نشدند.

### ۱۱٫۵ ریزکارهای پیاده‌سازی importer و اصلاحات میانی

ساختار نهایی فایل: کلاس `Adjustment` (فیلدها: `symbol`, `ex_date`, `prev_close`,
`close`, `f`)؛ توابع `run`, `pick_filing`, `synthetic_symbol_id`, `_register_symbols`,
`_dividend_rows`, `main`؛ ثابت‌های SQL: `_DETECT_SQL`, `_SYMBOLS`, `_CODAL_CAPITAL`,
`_SYMBOL_IDS`, `_MISSING_SYMBOLS`, `_INSERT_SYMBOL`, `_UPSERT`.

اصلاحاتی که در مسیر همین سشن انجام شد (و در گزارش اولیه نبودند):

| # | مشکل | اصلاح |
|---|---|---|
| ۱ | `_dividend_rows` ابتدا `async def` با پارامترهای `(conn, adjustments, used, ids, args)` بود | به تابع **خالص sync** با `(adjustments, matched_pairs, ids)` تبدیل شد تا unit-testable باشد |
| ۲ | رد کردن روزهای تأمین‌شده با `used.get(adj.symbol)` **درشت** بود (همهٔ روزهای یک نمادِ دارای فایل رد می‌شد؛ سود نقدی همان نماد در سال دیگر از دست می‌رفت) | به مجموعهٔ دقیق `matched_pairs = {(symbol, ex_date)}` تغییر کرد |
| ۳ | `needed` فقط `matched_symbols` بود → با `--include-dividends`، نمادهای بدون فایل هیچ شناسه‌ای نمی‌گرفتند و dividend برایشان ناممکن بود | `if args.include_dividends: needed \|= eligible` |
| ۴ | `{symbol_filter}` در WHERE بیرونی بود (full scan، اجرای تک‌نماد کند) | به داخل CTE پایه منتقل شد تا predicate به `idx_hist_symbol_date` push شود |
| ۵ | شرط `sid is None and not args.register_missing: continue` به‌همراه یک `if sid is None: continue` تکراری | به یک شرط ساده تبدیل شد |
| ۶ | بلوک `if/else` برای `symbols` (تذکر ruff) | عملگر سه‌گانه |

ماژول‌های خوانده‌شده در مسیر طراحی: migrations `0001`، `0061`، `0108`، `0109`؛
`services/corporate_action_service.py`، `services/adjusted_price_reader.py`،
`services/indicator_precompute_service.py`، `services/symbol_service.py`،
`scripts/backfill_adjust_factors.py`، `scripts/migrate_symbols_to_instruments.py`،
`scripts/import_initial_symbols.py`، `scripts/fetch_all_symbols_full.py`،
`scripts/sync_symbol_details_all.py`، `jobs/definitions/sync_jobs.py`،
`core/ids/__init__.py`.

### ۱۱٫۶ بخش‌هایی که بررسی **نشدند** و شکاف‌های باز (اسکن مصرف‌کننده‌ها)

اسکن مصرف‌کننده‌های این قابلیت کامل شد؛ نتیجه:

```text
نویسندگان corporate_action_events:
  scripts/import_corporate_actions.py       ← این کار
  [در انتظار اعمال] brsapi/models/tsetmc.py  ← بستهٔ DP-022 (پایین را ببینید)

نویسندگان daily_adjust_factors:
  scripts/backfill_adjust_factors.py   (تنها نویسندهٔ واقعی)

خوانندگان view/ضریب:
  services/adjusted_price_reader.py        (مسیر اندیکاتور)
  services/corporate_action_service.py     (فقط داخل خودش)
  core/config/__init__.py:266              (فلگ indicator_adjusted_prices)

هیچ ارجاعی در jobs/ و apps/ وجود ندارد
```

**دو شکاف واقعی که در این کار حل نشدند:**

1. **`recompute_factors` هیچ فراخوانی ندارد.** جست‌وجوی استاتیک در
   `services/`, `jobs/`, `apps/`, `scripts/`, `tests/`, `workers/`, `backtesting/`,
   `BrsApi_Forecasting/` فقط تعریف خودش را برگرداند. یعنی:
   `daily_adjust_factors` **تنها** با اجرای دستی
   `scripts/backfill_adjust_factors.py` ساخته می‌شود؛ هیچ job/endpoint/testی آن را
   صدا نمی‌زند و خودش هم واحدتست ندارد. پس پس از هر ورود رویداد جدید، بازسازی
   ضریب‌ها **خودکار نیست** و باید دستی اجرا شود.
2. **بستهٔ DP-022 اعمال نشده است.** دو اسکریپت untracked
   `scripts/_dp_batch.py` و `scripts/_dp_batch2.py` (توضیح خود‌شان: «One-shot batch
   editor ... run once, then deletable») در نظر دارند یک مسیر ذخیره‌سازی **دوم**
   برای رویدادهای `price_adjustment` اضافه کنند:

   ```python
   elif event_type == "price_adjustment":
       await self._storage.write_corporate_action(instrument_id, event.data)
   ```

   اما `grep` نشان می‌دهد `write_corporate_action` در `brsapi/models/tsetmc.py`
   **وجود ندارد** و هیچ‌جا فراخوانی نمی‌شود ⇒ این بستهٔ وصله هرگز اعمال نشده و شکاف
   حسابرسی DP-022 باز است. نکتهٔ مهم: آن نویسندهٔ پیشنهادی
   `ratio = data.get("adjusted_price")` و `ex_date = COALESCE(date, CURRENT_DATE)`
   می‌نویسد که با قرارداد نسبت در `corporate_action_service` (`1/(1+ratio)`)
   هم‌معنا نیست — پیش از اعمال باید اصلاح شود.

بخش‌هایی از برنامه که در این کار بررسی نشدند: کل فرانت‌اند، `BrsApi_Forecasting/`،
`backtesting/`، `domain/`، `repositories/`، اکثر `apps/api/endpoints/`، اکثر
`services/`، `brsapi/models/tsetmc.py` (۲۷KB)، و عمدهٔ ۷۹ migration — چون به این
قابلیت مربوط نمی‌شدند.

## ۱۲. پیوست: کارنامهٔ کامل و زمان‌بندی‌شدهٔ سشن (۲۰۲۶-۱۰-۰۶)

هر گام به ترتیبی که اجرا شد؛ شامل تست‌ها، پروب‌های عددی، اجراهای lint و خطاهای رفع‌شده.

### ۱۲٫۱ فاز ۰ — خواندن زمینه

| # | کار | نتیجه |
|---|---|---|
| ۱ | خواندن `0109_true_trade_date.py` | view با `jalali_to_gregorian` + هر دو تقویم؛ جوین ضریب روی `symbols.id` |
| ۲ | خواندن `0108_daily_history_adjusted_view.py` | کامنت خود migration: فقط ۲۳۸ از ۲٬۳۷۱ نماد در `symbols` |
| ۳ | خواندن `scripts/_dbg_adj.py` | فیلتر `symbol_id IS NOT NULL` |
| ۴ | خواندن `scripts/import_corporate_actions.py` | نسخهٔ قبلی رویکرد candle-ratio |

### ۱۲٫۲ فاز ۱ — تشخیص ریشهٔ باگ «صفر رویداد»

| # | کار | نتیجه |
|---|---|---|
| ۵ | ساخت/اجرای `_dbg_sym.py` | `symbols`=۵۱۱، join=۲۳۸، ومهان/شساخت/سیدکو در `symbols` نیستند |
| ۶ | `code_search` روی `INSERT INTO symbols\|Symbol\(\|symbols\.symbol\|FROM symbols` | ۷ نتیجه (شامل نویز `eslint_report.json`) |
| ۷ | خواندن `0061_corporate_actions.py` | FK هر دو جدول به `symbols(id)` |
| ۸ | `grep -rn symbols -l` روی سرویس/جاب/اپ | فهرست سرویس‌های مرتبط |
| ۹ | `grep` روی `instrument_import_service`/`history_backfill_service` | کشف جدول `instruments` |
| ۱۰ | ساخت/اجرای `_dbg_sym2.py` | `instruments`=۴۹۹، `screener_profiles`=۱٬۵۶۲ |
| ۱۱ | `ls migrations/versions` | ۷۹ فایل، head=`0109` |
| ۱۲ | `code_search` در `migrations/versions` | ۰ نتیجه (cwd) |
| ۱۳ | `find -name ids.py` | `core/ids.new_id()` — منبع idها نیست |
| ۱۴ | خواندن `0001_initial_schema.py` | `symbols.id` بدون sequence/default |
| ۱۵ | `grep` سراسری `INSERT INTO symbols` | فقط جدول‌های نامرتبط |
| ۱۶ | `ls scripts \| grep sym\|instrument` | کشف `migrate_symbols_to_instruments.py` |
| ۱۷ | خواندن `services/symbol_service.py` | روی `instruments` کار می‌کند |
| ۱۸ | `grep` روی ۴ اسکریپت sym/instrument | `fetch_all_symbols_full` → `sync_all_symbols` |
| ۱۹ | خواندن `migrate_symbols_to_instruments.py` | سابقهٔ موجود برای ثبت گروهی |
| ۲۰ | `grep` در `jobs/definitions` | `sync_jobs` مقصدش `brsapi_symbol_snapshots` |
| ۲۱ | تست hashها روی ۶ جفت نماد→id | ۰ تطابق؛ `UnicodeEncodeError` codec کنسول |
| ۲۲ | ساخت/اجرای `_dbg_sym3.py` | snapshot ۳٬۰۳۰٬۸۵۴ ردیف/۲٬۳۷۵ نماد؛ `ins_id` ≠ `symbols.id` |
| ۲۳ | خواندن `indicator_precompute_service.py` | precompute روی همهٔ نمادها می‌چرخد |
| ۲۴ | خواندن `adjusted_price_reader.py` | خواندن بر اساس نام نماد |
| ۲۵ | خواندن `backfill_adjust_factors.py` | `WHERE symbol_id=$1` |
| ۲۶ | خواندن `corporate_action_service.py` | قواعد `1/(1+ratio)` و `(close−dps)/close` |

### ۱۲٫۳ فاز ۲ — پروب‌های عددی و اندازه‌گیری‌ها

| # | پروب/تست | نتیجهٔ اندازه‌گیری‌شده |
|---|---|---|
| ۲۷ | `_dbg_sym4.py` — آستانهٔ سراسری لوکس | **۱٬۲۵۱٬۰۵۸** روز / ۱٬۹۲۱ نماد / فقط ۲۲۵ ثبت‌شده ← بی‌فایده |
| ۲۸ | `_dbg_sym5.py` — توزیع سال‌به‌سال | ۲۰۰۱–۲۰۰۷: ~۹۹٪ سالم؛ ۲۰۰۹+: ~۵۷٪ |
| ۲۹ | `_dbg_sym6.py` — سری عینی `فولاد` | ۲۰۲۴/۲۰۲۶ تمیز؛ خطای `toordinal` → رفع با `date.fromisoformat` |
| ۳۰ | `_dbg_sym7.py` — decile سلامت | ۳۷۰ نماد ۱۰۰٪، ۸۳۸ نماد ۹۰–۱۰۰٪، ~۷۵۲ نماد <۳۰٪ |
| ۳۱ | `_dbg_sym8.py` نسخهٔ ۱ | خطای `AmbiguousColumnError` → alise صریح |
| ۳۲ | `_dbg_sym8.py` نسخهٔ ۲ | نماد آشغال: `close=1.0` برابر `py=41,330` |
| ۳۳ | `_dbg_adj2.py` — `CREATE TEMP TABLE` | همگام: تایم‌اوت ۶۰۰s؛ پس‌زمینه: `DiskFullError` |
| ۳۴ | `df -h /c` | آزاد **۱٫۳GB** |
| ۳۵ | `_dbg_space.py` | `InsufficientPrivilegeError` روی `SHOW data_directory`؛ تایم‌اوت پرس‌وجوی اندازه |
| ۳۶ | `SELECT 1` + `pg_stat_activity` | ok — ۳ نشست فعال |
| ۳۷ | `du -sh` پس‌زمینه | ناتمام؛ `pkill` شد |
| ۳۸ | اندازهٔ پگ‌دیتا | `pg_wal`=۸۹۷M، `log`=۲۸۹M، `pgsql_tmp`=۱۲K |
| ۳۹ | `ls -d pgdata` | فقط PostgreSQL ۱۸ |

### ۱۲٫۴ فاز ۳ — پیاده‌سازی

| # | کار | نتیجه |
|---|---|---|
| ۴۰ | بازنویسی کامل importer | symbol-keyed + گارد clean_rate + تأیید CODAL + `--register-missing` |
| ۴۱ | ۶ اصلاح میانی | `matched_pairs`، `needed \|= eligible`، `_dividend_rows` خالص/sync، انتقال فیلتر به CTE، حذف شرط تکراری، ternary (بند ۱۱٫۵) |
| ۴۲ | **ruff #۱** | `All checks passed!` |
| ۴۳ | اجرای تک‌نماد `ومهان --dry-run` | ۷ روز، `clean_rate 0.9916`، ۵ تأییدشده، هشدار ثبت‌نشدن |
| ۴۴ | اجرای کامل پس‌زمینه (تک‌کوئری) | `DiskFullError` روی `pgsql_tmp` |
| ۴۵ | نوشتن فایل تست (۱۳۱ خط) | ۱۴ تابع، ۱۷ مورد با پارامترسازی |
| ۴۶ | **pytest #۱** | **۱ failed + ۱۶ passed** (باگ محاسبهٔ روز لبه) |
| ۴۷ | اصلاح تست لبهٔ پنجره | لبه‌ها «شامل»، یک روز بعد «رد» — assertion ضعیف نشد |
| ۴۸ | **pytest #۲** | `17 passed in 3.23s` |
| ۴۹ | خواندن `test_clean_historical_data.py` | هم‌سبک شدن با الگوی پروژه |
| ۵۰ | حذف ۱۲ پروب throwaway | `_recon_*`، `_probe_*`، `_dbg_adj` |
| ۵۱ | کشف/خواندن/حذف ۶ پروب `_probe_cap_*` | همه «Throwaway probe» |
| ۵۲ | حذف پروب‌های موقت خودم | `_dbg_sym*`، `_dbg_adj2`، `_dbg_space` |
| ۵۳ | `git status` / `ls-files --others` | ۳ فایل من untracked؛ ۷ فایل نامرتبط دست‌نخورده |
| ۵۴ | بازنویسی تشخیص به دسته‌ای | `_SYMBOLS` + `_DETECT_SQL` با `$4=text[]` + حلقهٔ batch ۲۵ |
| ۵۵ | **ruff #۲** | ۱ خطا: `if/else` → ternary |
| ۵۶ | رفع → **ruff #۳** | `All checks passed!` |
| ۵۷ | اجرای کامل دسته‌ای | رسید به **۱٬۰۰۰/۲٬۳۷۱ نماد / ۳٬۵۷۷ روز** سپس توقف (دیسک ۴۸MB) |
| ۵۸ | تأیید عدم نوشتن | ۳ جدول: ۰ / ۰ / ۵۱۱ |
| ۵۹ | افزودن §۹ به docs | ۱۶۴ → ۲۷۷ خط |
| ۶۰ | اصلاح §۹٫۶ | ۲۷۷ → ۲۸۰ خط |

### ۱۲٫۵ فاز ۴ — تأیید نهایی و commit

| # | کار | نتیجه |
|---|---|---|
| ۶۱ | **pytest #۳** با `set -o pipefail` | `17 passed in 2.38s`، `pytest exit=0` |
| ۶۲ | **ruff #۴** با pipefail | `All checks passed!`، `ruff exit=0` |
| ۶۳ | بررسی ساختار docs | بخش‌های ۱–۹، هر کدام یک‌بار |
| ۶۴ | `git log --oneline` + `%B` دو commit قبلی | سبک: `type(scope):` + بدنهٔ مفصل + footer |
| ۶۵ | بررسی commitlint/husky + طول subject | هیچ hook پیام commit نیست؛ مدین ۷۳، بیشینه ۱۰۰ |
| ۶۶ | `git add` سه فایل | `--cached --name-status` = دقیقاً ۳ فایل |
| ۶۷ | `git commit` | **`43278bbd`** — ۳ فایل، **+۷۷۳/−۱** |
| ۶۸ | تأیید commit | `show --stat`/footer/`--name-only`/worktree تمیز |
| ۶۹ | افزودن §۱۰ | ۲۸۰ → ۳۱۱ خط |
| ۷۰ | تأیید مجدد اعداد پوشش از DB | `instruments` ۴۹۹/۴۹۹ id مشترک؛ snapshot ۲٬۳۷۵/۲۳۷ |
| ۷۱ | افزودن §۱۱ در ۳ ویرایش | ۳۱۱ → ۳۶۴ خط |
| ۷۲ | بررسی ساختار | بخش‌های ۱–۱۱، ۲۲ fence زوج |
| ۷۳ | افزودن §۱۱٫۵ | ۳۶۴ → ۳۹۰ خط |
| ۷۴ | بررسی نهایی | هدر یکتا، fence زوج، newline پایانی، بدون mojibake، escape جدول درست |

### ۱۲٫۶ همهٔ اجراهای pytest (۳ بار)

```text
#۱  pytest tests/unit/scripts/test_import_corporate_actions.py -q
    → ۱ failed + ۱۶ passed   (باگ در محاسبهٔ روزِ لبهٔ پنجره)
#۲  (بعد از اصلاح تست)               → 17 passed in 3.23s
#۳  (تأیید نهایی، set -o pipefail)   → 17 passed in 2.38s   pytest exit=0
```

### ۱۲٫۷ همهٔ اجراهای ruff (۴ بار)

```text
#۱  scripts/import_corporate_actions.py     → All checks passed!
#۲  (بعد از تغییرات batch)                 → ۱ خطا: if/else → ternary
#۳  (بعد از رفع)                           → All checks passed!
#۴  هر دو فایل، set -o pipefail             → All checks passed!   ruff exit=0
```

### ۱۲٫۸ ابزارهای تعاملی

```text
ask_user          ۱ بار — دو سؤال (رجیستری نماد + دیسک)؛ گزینه‌ای انتخاب نشد
                  → پیش‌فرض محافظه‌کارانه: رجیستری دست‌نخورده
suggest_followups ۳ بار — ۳+۳+۳ پیشنهاد گام بعد
```

### ۱۲٫۹ وضعیت پایانی آن مرحله (۲۰۲۶-۱۰-۰۶)

> **ابراز‌شده — ببینید §۱۲٫۱۰.** بلوک زیر عکس لحظه‌ای آن مرحله است؛ همهٔ سه ردیفِ «صفر» و جملهٔ «هرگز اجرا نشد» از آن زمان به بعد باطل شده‌اند.

```text
main → 43278bbd  (۳ فایل، +۷۷۳/−۱، push نشده)
docs/PRICE_ADJUSTMENT_READ_PATH.md = M   (§۱۰ و §۱۱ و §۱۲ هنوز commit نشده)
corporate_action_events = 0
daily_adjust_factors    = 0
symbols                 = 511
C: آزاد                 = 48MB
```

هرگز اجرا نشد: ورود کامل رویدادها، بکفیل `daily_adjust_factors`، و اندازه‌گیری
تغییر واقعی اندیکاتور (دیسک پر). همچنین تست‌های `test_signal_decision_engine.py` و
`test_quant_signal_orchestrator.py` (۲۴ شکست از پیش موجود و نامرتبط) اجرا نشدند.

### ۱۲٫۱۰ وضعیت به‌روز (۲۰۲۶-۱۰-۰۷)

```text
main   → 4c1f7b0e   fix(tests): … legacy import-time scripts    (۱ فایل، +۱۴)   — push نشده
main~1 → ba4f0667   docs: record the executed import/backfill …  (۲ فایل، +۳۳۰/−۶۲)
main~2 → f0ed96d4   fix(test-isolation,api): …                  (۳۴ فایل، +۷۸۵/−۱۲۸)
main~3 → 1212cb87   docs: audit verification, price-read-path …  (۴ فایل، +۲۰۸۰)
main~4 → 43278bbd   feat(corporate-actions): …                  (۳ فایل، +۷۷۳/−۱)

docs/PRICE_ADJUSTMENT_READ_PATH.md = tracked   (§۱۰ و §۱۱ و §۱۲ از طریق 1212cb87)
corporate_action_events = 586
daily_adjust_factors    = 621,818
symbols                 = 511   (دست‌نخورده؛ ۲۸۶ نماد تأییدشده گرفتار FK)
C: آزاد                 = 26 GB
```

از سه مورد «هرگز اجرا نشد» بالا، **هر سه اجرا شد** (واردسازی، بک‌فیل، و اندازه‌گیری واقعی اندیکاتور — §۹٫۶ و بخش ۳ گزارش فارسی). از دو فایل تست نام‌برده، `test_quant_signal_orchestrator.py` اجرا شد و شکست‌هایش **آلودگی بین‌فایلی** بود، نه باگ؛ رفع شد و اکنون ۵۵ سبز می‌دهد (پیش‌تر `2 failed/53`). `test_signal_decision_engine.py` هنوز بازبینی نشده است. شرح کامل در بخش‌های E و F گزارش انگلیسی.
