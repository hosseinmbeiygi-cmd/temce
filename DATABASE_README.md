# 🗄️ راهنمای جامع دیتابیس — سامانه تحلیل بازار سرمایه

> **آخرین بهروزرسانی:** ۱۴۰۵/۰۵/۱۴ (۲۰۲۶-۰۸-۰۵) — بر اساس بررسی مستقیم دیتابیس زنده (PostgreSQL، ~۱۴ GB، ۱۲۲ جدول)

این سند نتیجه یک **چکاپ کامل و عمیق** از تمام جدولها، روابط، کیفیت داده و مشکلات شناساییشده است.

---

## 📋 خلاصه وضعیت

| شاخص | مقدار |
|-------|-------|
| تعداد کل جدولها | **۱۲۲** |
| حجم کل دیتابیس | **~۱۴ GB** |
| جدولهای با داده | ۵۹ |
| جدولهای خالی (۰ ردیف) | ۵۵ |
| جدولهای تقریباً خالی (۱–۱۰ ردیف) | ۸ |
| مجموع ردیفهای کل | ~۵۲ میلیون |
| نسخه PostgreSQL | 16 (TimescaleDB برای هیپرتیبلها) |

---

## 🏗️ معماری کلی — ۵ لایه دیتابیس

```
┌─────────────────────────────────────────────────────────────┐
│  لایه ۱: سینک BrsApi (brsapi_*) — ۳۰ جدول                  │
│  داده خام از API برس (نماد، تاریخچه، ریزمعاملات، کدال...)     │
├─────────────────────────────────────────────────────────────┤
│  لایه ۲: مدل‌های دامنه (models/) — ~۳۵ جدول                 │
│  نمادها، نقل‌قول‌ها، آپشن‌ها، سیگنال‌ها، ML، کاربران...        │
├─────────────────────────────────────────────────────────────┤
│  لایه ۳: Star Schema کدال (dim_*/fact_*) — ۱۵ جدول          │
│  تحلیل مالی: ابعاد + حقایق + lineage                         │
├─────────────────────────────────────────────────────────────┤
│  لایه ۴: کالا/ارز/طلا (commodity_*, gold_*) — ~۱۲ جدول      │
├─────────────────────────────────────────────────────────────┤
│  لایه ۵: عملیاتی/زیرساخت — ~۱۵ جدول                         │
│  لاگ، سلامت، جاب‌ها، بکتست، قیاس، استراتژی‌ها                │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔗 روابط بین جدولها (Foreign Keys)

> ⚠️ **مشکل ساختاری مهم:** از ۱۲۲ جدول فقط ~۲۵ رابطه FK واقعی وجود دارد. اکثر جدولهای `brsapi_*` **هیچ FK ندارند** و ارتباطشان از طریق ستون متنی `symbol` است.

### گراف روابط اصلی

```
symbols (511)  ◄── daily_history (88K)      [symbol_id]
     ▲         ◄── daily_real_legal (388K)  [symbol_id]
     │         ◄── intraday_trades (9.1M)   [symbol_id]
     │         ◄── etf_nav (12)             [symbol_id]
     │         ◄── candlesticks (0)         [symbol_id]
     │         ◄── orderbook_snapshots (0)  [symbol_id]
     │         ◄── shareholders (2.4K)      [symbol_id]
     │         ◄── symbol_snapshots (0)     [symbol_id]
     │
option_contracts ◄── option_snapshots ◄── option_trades
     ▲             ◄── open_interest_history
     │
users  ◄── saved_filters
     │
dim_company ◄── fact_financials, fact_ratios, fact_growth,
│               fact_quality_signals, fact_text_analytics,
│               analysis_reports
dim_document ◄── fact_financials, fact_text_analytics, data_lineage
dim_account  ◄── fact_financials, account_mappings
dim_date     ◄── fact_financials, fact_growth, fact_ratios,
                 fact_quality_signals
dim_report_type ◄── fact_financials, dim_document
```

### جدولهای بدون FK (گسسته)

تمامی جدولهای `brsapi_*`، `tabdeal_*`، `commodity_*` (غیر از بازار)، `funds`، `instruments`، `quotes`، `trades`، `signals` و... **هیچ رابطه FK ندارند** — بهصورت مستقل با `symbol` متنی ذخیره شدهاند.

### FK های ناقص/مشکلدار

| FK | وضعیت | مشکل |
|----|--------|------|
| `symbol_snapshots.symbol_id → symbols.id` | ⚠️ | جدول `symbol_snapshots` **۰ ردیف** دارد ولی جدول موازی `brsapi_symbol_snapshots` با **۸۲۵K ردیف** فعال است |
| `intraday_trades.symbol_id → symbols.id` | ⚠️ | جدول ۹.۱M ردیفی فقط **۳۲۸ نماد** را پوشش میدهد (از ۵۱۱) و فقط ۱ ماه داده |
| `candlesticks.symbol_id → symbols.id` | ⚠️ | جدول **خالی** — جایگزین آن `brsapi_candlesticks` (۸۱۹ ردیف) است |
| `daily_history.symbol_id → symbols.id` | ⚠️ | فقط **۱۱۵ نماد** پوشش دارد، در حالی که `brsapi_historical_daily` **۵۸۵ نماد** دارد |
| `etf_nav → symbols` | ⚠️ | فقط ۱۲ ردیف در برابر ۱۱۴ ردیف `brsapi_nav_records` |
| FK های `dim_* → fact_*` | ❌ | همه جدولهای dim/fact **خالی** هستند (پایپلاین کدال اکسل هنوز داده نمیریزد) |

---

## 📊 فهرست کامل جدولها به تفکیک لایه

### لایه ۱ — سینک BrsApi (۳۰ جدول) ✅ فعال

| جدول | ردیف | توضیح |
|------|------|--------|
| `brsapi_symbol_snapshots` | 824,855 | اسنپشات قیمت همه نمادها (هر ۲ دقیقه) |
| `brsapi_historical_daily` | 8,648,224 | تاریخچه قیمت روزانه — **۵۸۵ نماد، از ۱۳۸۰ تا ۱۴۰۵/۰۵/۱۲** |
| `brsapi_historical_real_legal` | 909,684 | تاریخچه حقیقی/حقوقی روزانه — ۵۵۹ نماد |
| `brsapi_intraday_trades` | 1,637,032 | ریزمعاملات — ⚠️ فقط ۶۸ نماد (سینک ۳۰۰ نماد ناتمام) |
| `brsapi_index_values` | 3,437 | شاخصها |
| `brsapi_option_snapshots` | 375,791 | آپشنهای TSETMC |
| `brsapi_ime_funds` | 21,019 | صندوقهای IME |
| `brsapi_ime_options` | 48,213 | آپشنهای IME |
| `brsapi_ime_futures` | 7,562 | آتیهای IME |
| `brsapi_ime_certificates` | 3,819 | گواهیهای IME |
| `brsapi_ime_physical_trades` | 687 | معاملات فیزیکی IME |
| `brsapi_gold_currency_pro_daily_history` | 160,567 | تاریخچه طلا/ارز تا **۱۴۰۵/۰۵/۱۴** ✅ |
| `brsapi_gold_coin_history` | 44,207 | تاریخچه سکه |
| `brsapi_crypto_daily_history` | 18,609 | تاریخچه کریپتو تا **۱۴۰۵/۰۵/۱۴** ✅ |
| `brsapi_codal_announcements` | ~4,000 | اطلاعیههای کدال (در حال backfill به ۱ ماه قبل) |
| `brsapi_codal_attachments` | 359 | پیوستهای کدال |
| `brsapi_shareholder_records` | 773,330 | سهامداران |
| `brsapi_symbol_details` | 1,280 | جزئیات نمادها |
| `brsapi_candlesticks` | 819 | کندلها (فقط ۳۰ نماد) |
| `brsapi_nav_records` | 114 | NAV صندوقها |
| `brsapi_sync_log` | 25,990 | لاگ سینک |
| `brsapi_raw_payloads` | 0 | پیلود خام (خالی) |
| + قیمتهای لحظهای | — | `gold_coin_prices`(9), `currency_prices`(28), `crypto_prices`(19), `gold_currency_pro_prices`(19), `commodity_prices`(7,462) |
| + ۲۴ ساعته | — | `gold_24h`(0), `currency_24h`(0), `gold_currency_pro_history_24h`(0) |

### لایه ۲ — مدلهای دامنه (مصرفی اپلیکیشن)

| جدول | ردیف | وضعیت |
|------|------|--------|
| `symbols` | 511 | ✅ مرجع اصلی نمادها |
| `instruments` | 499 | ✅ ابزارها |
| `trades` | 14,851,701 | ⚠️ **فقط ۱۴۰۵/۰۳/۱۶ تا ۰۴/۱۳** (۱ ماه قدیمی) — ۶۲۴ نماد |
| `intraday_trades` | 9,115,538 | ⚠️ فقط ۲۰۲۶-۰۶-۰۶ تا ۰۷-۰۴ (میلادی) — ۳۲۸ نماد |
| `quotes` | 3,360,308 | ⚠️ تا ۰۸-۰۴ (دیروز) |
| `daily_history` | 88,961 | ⚠️ فقط ۱۱۵ نماد |
| `daily_real_legal` | 387,701 | ⚠️ ناقص |
| `shareholders` | 2,390 | ✅ |
| `gold_currency_prices` | 74,463 | ✅ |
| `commodity_trades` | 320,005 | ✅ |
| `commodity_futures` | 60 | ⚠️ کم |
| `commodity_certificates` | 125,256 | ✅ |
| `commodity_options` | 476 | ⚠️ کم |
| `commodity_funds` | 186 | ⚠️ کم |
| `indices` | 4 | ⚠️ باید ~۴۰ باشد |
| `options` | 3,225 | ⚠️ با `brsapi_option_snapshots` همپوشانی دارد |
| `etf_nav` | 12 | ⚠️ خیلی کم |
| `funds` | 26 | ⚠️ خیلی کم |
| `signals` | 4 | ⚠️ خیلی کم |
| `signal_accuracy` | 20,550 | ✅ |
| `news_articles` | 1,819 | ✅ |
| `screener_profiles` | 1,562 | ✅ |
| `ml_models` / `ml_model_versions` | 359 / 638 | ✅ |
| `ml_training_runs` | 6,078 | ✅ |
| `ml_predictions` / `ml_symbol_results` | 19,960 / 5,506 | ✅ |
| `codal_reports` | 226,818 | ✅ گزارشهای مالی تاریخی |
| `codal_financial_statements` | 451 | ✅ |
| `codal_audit_summary` | 451 | ✅ |
| `import_document_files` | 95,418 | ✅ |
| `import_document_tables` | 524,314 | ✅ |
| `backtest_runs` | 1,579 | ✅ |
| `users` | **0** | ❌ **خالی! رجیستر فعلاً در این جدول نمینویسد** |
| `saved_filters` / `portfolios` / `portfolio_positions` | 0 | ❌ خالی |
| `recommendations` / `queue_analysis_results` / `screener_signals` / `screener_snapshots` | 0 | ❌ خالی |
| `orderbooks` / `orderbook_snapshots` / `option_snapshots` / `option_trades` / `option_contracts` / `open_interest_history` | 0 | ❌ خالی |
| `candlesticks` / `symbol_snapshots` / `codal_announcements` | 0 | ❌ خالی (دوگانههای brsapi) |
| `signals` / `indices` / `etf_nav` | 4 / 4 / 12 | ⚠️ ناقص |

### لایه ۳ — Star Schema کدال (همه خالی ❌)

| جدول | وضعیت |
|------|--------|
| `dim_company`, `dim_account`, `dim_date`, `dim_document`, `dim_report_type` | ❌ خالی |
| `fact_financials`, `fact_growth`, `fact_quality_signals`, `fact_ratios`, `fact_text_analytics` | ❌ خالی |
| `account_mappings`, `analysis_reports`, `data_lineage`, `audit_trail` | ❌ خالی |

> ساختار schema کامل و FK ها تعریف شدهاند، اما پایپلاین import اکسل کدال داده را به این جدولها نمیریزد (مدلها موجودند: `models/codal_analysis.py`).

### لایه ۵ — عملیاتی

| جدول | ردیف | وضعیت |
|------|------|--------|
| `alerts` | 1 | ⚠️ فقط ۱ هشدار |
| `alert_history` | 274 | ✅ |
| `decision_architectures` | 1 | ✅ (seed) |
| `decision_results` | 0 | ❌ |
| `job_runs` / `provider_health` / `provider_health_history` | 0 | ❌ خالی |
| `generated_strategies` / `generation_batches` | 0 | ❌ خالی |
| `compare_results` / `backtest_trades` | 0 | ❌ خالی |
| `audit_logs` / `audit_trail` / `analysis_reports` / `calibration_models` / `macro_indicators` / `indicators` / `markets` | 0 | ❌ خالی |
| `tabdeal_*` (۷ جدول) | 0 | ❌ همه خالی |
| `volatility_surface` / `corporate_actions` | 0 | ❌ خالی |

---

## 🐛 مشکلات شناساییشده (خلاصه اولویتبندیشده)

### 🔴 بحرانی

| # | مشکل | جزئیات |
|---|-------|--------|
| ۱ | **دو جدول ریزمعاملات ناقص و کهنه** | `brsapi_intraday_trades` فقط ۶۸ نماد (سینک ۳۰۰ نماد ناتمام)، `intraday_trades` فقط ۳۲۸ نماد و ۱ ماه میلادی، `trades` فقط ۱ ماه شمسی (۰۴/۱۳) |
| ۲ | **`users` خالی است** | ۰ کاربر — جریان ثبتنام فرانتاند در این جدول نمینویسد |
| ۳ | **فرمت تاریخ مخلوط شمسی/میلادی** | `brsapi_intraday_trades.trade_date` هر دو را دارد (`1405-05-10` و `2024-06-15`)؛ `brsapi_gold_currency_pro_daily_history` حتی سال `1348` دارد |
| ۴ | **بیش از ۱۰۰ ستون تاریخ بهصورت VARCHAR** | مقایسه/سورت تاریخ در SQL غیرممکن یا ناصحیح است (نمونه: تمام جدولهای brsapi) |
| ۵ | **ناسازگاری نمادها** | `brsapi_symbol_snapshots` ۱٬۷۵۶ نماد متمایز دارد ولی جدول `symbols` فقط ۵۱۱ — **۱٬۵۳۳ نماد در مرجع اصلی نیستند** (باعث شکست JOIN میشود) |

### 🟠 بالا

| # | مشکل | جزئیات |
|---|-------|--------|
| ۶ | **دوگانگی جدولها** | جفتهای `daily_history`/`brsapi_historical_daily`، `candlesticks`/`brsapi_candlesticks`، `symbol_snapshots`/`brsapi_symbol_snapshots`، `intraday_trades`/`brsapi_intraday_trades`، `codal_announcements`/`brsapi_codal_announcements` — داده واقعی فقط در نسخه brsapi است و نسخه دوم خالی |
| ۷ | **۵۵ جدول خالی** | نیمی از schema ساخته شده ولی هرگز پر نشده |
| ۸ | **بدون ایندکس روی جدولهای کلیدی** | ۱۳ جدول فقط PK دارند (بدون ایندکس ثانویه): `commodity_certificates`, `commodity_funds`, `commodity_futures`, `commodity_options`, `commodity_trades`, `dim_date`, `generation_batches`, `indices`, `options`, `portfolios`, `tabdeal_accounts`, `brsapi_symbol_details`, `calibration_models` |
| ۹ | **سینک کدال ناقص** | فقط ۱۱ روز داده دارد — backfill به یک ماه در حال اجراست (باگ `start_page` رفع شد) |
| ۱۰ | **`brsapi_historical_daily` فقط ۵۱K تخمین** | آمار `n_live_tup` بهروز نیست — `ANALYZE` اجرا نشده (عدد واقعی ۸.۶M است) |

### 🟡 متوسط

- تاریخ `brsapi_gold_coin_history` تا `1348` — داده قدیمی/ناسازگار
- `indices` فقط ۴ ردیف
- `etf_nav`/`funds`/`signals` خیلی کم
- FK های `option_snapshots`/`option_trades` به `option_contracts` ساخته شدهاند ولی همه ۳ جدول خالیاند
- `import_*` جدولها داده دارند ولی `import_audit_log` و dim/fact خالیاند

---

## 🧭 راهنمای «کدام جدول منبع حقیقت است؟»

| دامنه | جدول اصلی (منبع حقیقت) | جدول جایگزین (خالی/کهنه) |
|--------|------------------------|---------------------------|
| تاریخچه قیمت روزانه | **`brsapi_historical_daily`** (585 نماد) | `daily_history` (115) |
| ریزمعاملات | **`brsapi_intraday_trades`** (بهروز اما 68 نماد) | `intraday_trades`, `trades` (کهنه) |
| حقیقی/حقوقی | **`brsapi_historical_real_legal`** | `daily_real_legal` |
| کندل | **`brsapi_candlesticks`** | `candlesticks` (خالی) |
| اسنپشات قیمت | **`brsapi_symbol_snapshots`** | `symbol_snapshots` (خالی) |
| اطلاعیه کدال | **`brsapi_codal_announcements`** | `codal_announcements` (خالی) |
| NAV صندوق | **`brsapi_nav_records`** | `etf_nav` |
| آپشن | **`brsapi_option_snapshots`** | `option_snapshots`/`option_contracts` (خالی) |
| طلا/ارز/کریپتو | **`brsapi_gold_currency_pro_*`** | `gold_currency_prices`, `commodity_prices` |

---

## 🛠️ دستورات مفید

```bash
# اتصال و مشاهده جدولها
psql "$DATABASE_URL" -c "\dt"

# حجم هر جدول
psql "$DATABASE_URL" -c "
  SELECT tablename, pg_size_pretty(pg_total_relation_size(quote_ident(tablename))) AS size
  FROM pg_tables WHERE schemaname='public' ORDER BY 2 DESC LIMIT 15;"

# بهروزرسانی آمار تخمینی
psql "$DATABASE_URL" -c "ANALYZE;"

# رفع تاریخهای مخلوط در ریزمعاملات (نمونه — پاکسازی میلادیهای ناخواسته)
# ⚠️ قبل از اجرا از داده بکاپ بگیرید
# DELETE FROM brsapi_intraday_trades WHERE trade_date ~ '^20[0-9]{2}-';
```

---

## 📌 وضعیت سینکهای جاری

| سینک | وضعیت |
|------|--------|
| کدال → ۱ ماه قبل (backfill) | 🔄 در حال اجرا — `scripts/sync_codal_backfill.py --start 175 --until 1405-04-14` |
| ریزمعاملات ۳۰۰ نماد | ⏸️ ناتمام — با `--skip 145` ادامه دهید |
| همه جدولها تا امروز | ✅ انجام شد (گزارش قبلی) |

---

## 🧾 خلاصه گزارش مشکلات — جمعبندی

- **۵۵ جدول خالی** + **۸ جدول تقریباً خالی** = ۶۳ جدول بیاستفاده/نیمهکاره
- **~۲۵ رابطه FK** از ۱۲۲ جدول (کمبود شدید یکپارچگی ارجاعی)
- **۱۰۰+ ستون تاریخ VARCHAR** — باید به `DATE`/`TIMESTAMPTZ` مهاجرت کنند
- **فرمتهای تاریخ مخلوط** در ۳ جدول فعال
- **دوگانگی جدولها** در ۵ دامنه (brsapi_* vs بدون پیشوند)
- **`users` و لایه تحلیلی کدال (dim/fact) کاملاً خالی**
