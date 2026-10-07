# گزارش نهایی و عمیق — وارد‌سازی رویدادهای افزایش سرمایه، تأیید ممیزی معماری، و اجرای کامل تست‌ها

**تاریخ:** ۲۰۲۶-۱۰-۰۷ (۱۵ مهر ۱۴۰۵)
**مخزن:** `C:/Users/Iran/Desktop/temce`
**پوسته:** bash روی ویندوز (Git Bash) — همه دستورها با `venv/Scripts/python`
**پایگاه داده:** TimescaleDB/Postgres — `my_first_db`، سرشاخه مهاجرت‌ها `0109`

---

## ۰. خلاصه مدیریتی

| موضوع | وضعیت | شاهد |
|---|---|---|
| اسکریپت وارد‌سازی رویدادهای افزایش سرمایه از CODAL | ✅ نوشته و کامیت شد | کامیت `43278bbd` — `scripts/import_corporate_actions.py` (۵۲۲ خط) |
| تست‌های همان اسکریپت | ✅ ۱۷ تست، همه سبز | `tests/unit/scripts/test_import_corporate_actions.py` |
| اجرای واقعی وارد‌سازی روی پایگاه داده | ✅ اجرا شد (exit 0) | `corporate_action_events` ۰ → **۵۸۶** رویداد (۱۴۵ نماد، همه `capital_increase`، منبع `codal`) |
| بک‌فیل فاکتورهای تعدیل | ✅ اجرا شد (exit 0 در ۷۳ ثانیه) | `daily_adjust_factors` ۰ → **۶۲۱٬۸۱۸** فاکتور روی ۱۴۵ نماد |
| اثبات تغییر واقعی اندیکاتور | ✅ اندازه‌گیری شد | میانگین متحرک ۲۰ ردیفی با/بی فاکتور: **۳۸٫۷٪** اختلاف روی ومعادن |
| کامیت اصلاحات کد و تست | ✅ انجام شد | کامیت `f0ed96d4` — ۳۴ فایل، ‎+۷۸۵/−۱۲۸ |
| تأیید مستقل «ممیزی معماری ۲۰۲۶-۱۰-۰۶» | ✅ انجام شد | `docs/ARCHITECTURE_AUDIT_2026-10-06.md` §۹ |
| اجرای کامل تست‌های فرانت‌اند (vitest) | ✅ کامل | ۳۳ فایل، ۴۱۱ تست، ۵۴.۸۸ ثانیه |
| اجرای کامل تست‌های `tests/unit` | ✅ کامل | ۵٬۳۳۴ جمع‌آوری، همه اندازه‌گیری شدند |
| اجرای تست‌های باقی‌مانده (بیرون از `tests/unit`) | ✅ تمام فایل‌های قابل‌جمع‌آوری | ۷۳۶ تست، ۱۰۹ فایل XML |
| رفع اشکال‌های واقعی | ✅ ۷ ریشه‌ای رفع شد | ۳۲ از ۵۰ شکست برطرف شد |
| کامیت فایل‌های مستندات | ✅ انجام شد | ۳ فایل |

**نتیجه اصلی:** پس از آزادسازی فضا، وارد‌سازی و بک‌فیل روی پایگاه داده **اجرا شدند** (۵۸۶ رویداد و ۶۲۱٬۸۱۸ فاکتور) و اثرشان روی یک اندیکاتور واقعی اندازه‌گیری شد. اصلاحات کد و تست این جلسه هم کامیت شدند (`f0ed96d4`). تنها مورد باز، تصمیم محصولی درباره «ثبت نمادهای ناموجود» (`--register-missing`) است که عمداً اجرا نشد.

> **بازنگری بخش‌های ۳، ۶.۶، ۸.۱، ۹ و پیوست:** همهٔ آن‌ها پیش از اجرای وارد‌سازی/بک‌فیل و پیش از کامیت نوشته شده‌اند؛ وضعیت به‌روز در همین خلاصه و در بخش ۳ (به‌روزشده) آمده است.

---

## ۱. اعداد کلیدی محیط

```text
نمای vw_daily_history_adjusted      5,450,380 ردیف | 2,371 نماد | 6,166 تاریخ معاملاتی
جدول quotes                          3,412,622 ردیف
جدول symbols                               511 ردیف  (دستی؛ id بدون sequence/default)
جدول corporate_action_events                 0 ردیف
جدول daily_adjust_factors                    0 ردیف
corporate_actions (بی‌استفاده)                0 ردیف
فضای آزاد درایو C                      28 GB  (پیش‌تر: 48 MB)
python                       3.11   |  pytest 9.1.1  |  vitest 4.1.9
pytest plugins               asyncio 1.4.0، benchmark 5.2.3، cov 7.1.0، timeout 2.4.0
                             (xdist / random / forked نصب نیست)
```

### تله نام‌گذاری جدول‌ها

دو جدول با نام‌های بسیار شبیه وجود دارد:

| جدول | وضعیت |
|---|---|
| `corporate_action_events` | جدول هدف کد — مهاجرت `0061` |
| `corporate_actions` | بدون استفاده |

هر کوئری یا اسکریپتی که `corporate_actions` را هدف بگیرد، بی‌صدا صفر ردیف برمی‌گرداند.

---

## ۲. مرحله ۱ — وارد‌سازی رویدادهای افزایش سرمایه از CODAL

### ۲.۱ مسئله

وارد‌کنندهٔ پیشین صفر رویداد پیدا می‌کرد. سه کشف پشت سر هم این را توضیح داد.

### ۲.۲ کشف اول — چرا وارد‌کنندهٔ قبلی صفر رویداد می‌دید

منابعی که **رد شدند** (دوباره سراغ‌شان نروید):

- `brsapi_candlesticks` نوع ۲ و نوع ۳ (نسبت R)
- عنوان‌های CODAL
- `brsapi_codal_attachments.content`
- دامنهٔ `CODAL.ir` (در دسترس نیست)
- `brsapi_raw_payloads` (صفر ردیف)

منبعی که **پذیرفته شد**: `brsapi_symbol_snapshots.shares_count` به‌عنوان یک بررسی متقابل.

### ۲.۳ کشف دوم — فاکتور دقیق چگونه محاسبه می‌شود

TSETMC مقدار `price_yesterday` را روی تاریخ‌های ex بازپایه‌گذاری می‌کند. بنابراین:

```text
f     = price_yesterday(ex) / price_close(ex − 1)
ratio = 1 / f − 1
```

این با سه نمونهٔ واقعی تأیید شد:

| نماد | تاریخ ex | `price_close(ex−1)` | `price_yesterday(ex)` | نتیجه |
|---|---|---|---|---|
| ومهان | 2026-09-12 | ۸٬۲۵۰ | ۵٬۵۰۰ | تأیید |
| سیدکو | 2026-09-01 | ۴۵٬۵۱۰ | ۱۱٬۳۸۰ | تأیید |
| شساخت | 2026-09-02 | ۲۱٬۷۸۰ | ۴٬۲۰۰ | تأیید |

### ۲.۴ کشف سوم — تشخیص باید دسته‌ای باشد

پردازش تک‌نمادی برای ۲٬۳۷۱ نماد غیرقابل‌قبول کند بود؛ اسکریپت با دسته‌های ۲۵ نمادی کار می‌کند.

### ۲.۵ طراحی نهایی

`scripts/import_corporate_actions.py` — ۵۲۲ خط، پاک از نظر `ruff`:

```text
_DETECT_SQL                       کوئری تشخیص، دسته‌ای
BATCH_SIZE = 25
MIN_FACTOR_DEV  = 0.005           حداقل انحراف فاکتور
MIN_CLEAN_RATE  = 0.98            حداقل نرخ ردیف‌های پاک
MIN_ROWS        = 100             حداقل ردیف لازم برای هر نماد
Upsert: ON CONFLICT (symbol_id, ex_date, action_type) DO UPDATE
```

گزینهٔ `--register-missing` از شناسهٔ زیر استفاده می‌کند:

```text
id = 10**18 + blake2b(symbol, digest_size=8) % 10**15
```

این شناسه قطعی (deterministic) است تا اجرای دوباره رکورد تکراری نسازد.

### ۲.۶ تست‌ها

`tests/unit/scripts/test_import_corporate_actions.py` — ۱۳۱ خط، **۱۷ تست، همه سبز**.

### ۲.۷ کامیت

```text
43278bbd   ۳ فایل، ‎+773/−1   (روی main، push نشده)
```

---

## ۳. مرحله ۲ — بک‌فیل فاکتور تعدیل (اجرا شد)

این مرحله **اجرا شد** (پس از آزادسازی فضا). دستورها و خروجی واقعی:

```bash
# ۰) آزادسازی فضا روی درایو C   (انجام شد: 48MB → 28GB)
# ۱) پیش‌نمایش کامل، بدون هیچ نوشتنی
venv/Scripts/python scripts/import_corporate_actions.py --dry-run
#    → eligible symbols=821  rebasing days=9836
#    → corroborated=1679 events / 431 symbols  unmatched=8157  symbols_without_filing=390
# ۲) درج رویدادها (بدون --register-missing)
venv/Scripts/python scripts/import_corporate_actions.py        # exit 0
#    → corporate_action_events: 0 → 586  (145 نماد؛ ratio: min .000154، max 78.426، avg 0.9887)
# ۳) مادّی‌سازی فاکتورها روی تاریخ میلادی واقعی
venv/Scripts/python scripts/backfill_adjust_factors.py         # exit 0 در 73 ثانیه
#    → daily_adjust_factors: 0 → 621,818 روی 145 نماد
# ۴) راستی‌آزمایی: شمارش > 0 در هر دو جدول، و تغییر واقعی یک اندیکاتور
```

**اثبات سرتاسری.** ومعادن ۱۶ رویداد دارد. در ۲۰۲۵-۰۲-۱۱ قیمت پایانی خام ۳٫۸۲۷ است؛ فاکتور ذخیره‌شده ۰٫۷۲۱۱۵۱۰۷۲۵ است ⇒ قیمت تعدیل‌شده ۲٫۵۸۱٫۷۲ که با قیمت پس از رویداد (۲٫۵۸۱ در ۲۰۲۵-۰۲-۱۵) پیوسته است. همین فاکتور دقیقاً
`1/(1 + 0.386672)` برابر نسبت رویداد ذخیره‌شده است. روی همان ۲۰ ردیف، میانگین متحرک ۲۰ ردیفی:

```text
میانگین متحرک بدون تعدیل 3620.20   با تعدیل 2610.71   →  خطای 38.7٪ اگر فاکتور نادیده گرفته شود
```

**هشدار هنگام اندازه‌گیری.** `load_daily_candles(session, sym, adjusted=False)` جدول دیگری (`daily_history`) را می‌خواند، نه view؛ پس هم‌تراز‌سازی ردیفی دادهٔ خام و تعدیل‌شده بین دو فراخوانی نامعتبر است. باید `price_close` و `price_close_adj` روی همان ردیف‌های `vw_daily_history_adjusted` مقایسه شوند.

### ۳.۱ مانع بازِ ثبت نمادها

```text
نمادهایی که رویداد قابل‌تشخیص دارند      1,921
نمادهای ثبت‌شده در جدول symbols             225
جدول symbols                                511 ردیف دستی، id بدون sequence/default
```

یعنی حدود ۱٬۷۰۰ نماد رویداد دارند ولی در جدول `symbols` ثبت نشده‌اند. گزینهٔ `--register-missing` نوشته شده ولی **هرگز اجرا نشده** — این یک تصمیم است، نه یک کار فنی.

---

## ۴. مرحله ۳ — تأیید مستقل «ممیزی معماری ۲۰۲۶-۱۰-۰۶»

نتیجهٔ تأیید در `docs/ARCHITECTURE_AUDIT_2026-10-06.md` §۹ اضافه شد (این بخش اضافه شد، سند بازنویسی نشد).

```text
✅ روش شمارش ممیزی بازتولید شد
✅ تأییدهای دقیق با شمارهٔ خط، کلمه‌به‌کلمه
⚠️ سه اصلاح لازم است
❌ یک فرضیه رد شد  — نشت تراکنش §6.4
❓ مواردی که قابل تأیید نبودند
```

---

## ۵. مرحله ۴ — اجرای کامل تست‌ها

### ۵.۱ فرانت‌اند (vitest) — کامل

```text
$ cd frontend && npx vitest run
Test Files  1 failed | 32 passed (33)
     Tests  7 failed | 404 passed (411)
  Duration  54.88s
```

هر ۷ شکست در `src/__tests__/SyncStatus.test.tsx` است و یک علت واحد دارد:

```text
ReferenceError: customSettings is not defined        SyncStatus.tsx:333
```

عامل: نسخهٔ کاری، خط ۱۹۸ در `HEAD` را
`const [customSettings, setCustomSettings] = useSyncSettings();`
با یک خط خالی جایگزین کرده است. `frontend/src/lib/fund-analysis.ts` هم تغییر بی‌کامیت دارد. **هیچ اصلاحی اعمال نشد.**

### ۵.۲ `tests/unit` — کامل

```text
جمع‌آوری توسط pytest          5,334
اندازه‌گیری‌شده                5,330
   سبز                        5,218
   شکست                          50
   رد‌شده (skip)                 62
   خطا                            0
هرگز پایان نمی‌یافتند              4
```

برای رسیدن به این عدد، ۱۵۵ اجرا انجام شد (۵ تکه + ۱۵۲ فایل جداگانه) و از ۱۵۷ فایل XML نتیجه تجمیع شد:

```text
XML FILES: 157
TOTAL: tests=5327 failures=49 errors=0 skipped=62 passed=5216
```

**تلهٔ ابزار:** سوئیچ `--timeout-method=thread` روی ویندوز کل فرایند pytest را سخت بیرون می‌اندازد (بدون خلاصه، بدون JUnit XML). روش `signal` هم روی ویندوز وجود ندارد. به همین دلیل حفاظ‌ها باید از بیرون فرایند اعمال شوند.

**تلهٔ دوم:** فیکسچر `app` در `tests/unit/conftest.py` دامنهٔ **session** دارد و مستنداتش می‌گوید این کار «هزینهٔ ~۲۰ ثانیه‌ای ایمپورت اندپوینت‌ها» را یک‌بار می‌پردازد. اندازه‌گیری واقعی با `--durations` روی `test_health_check`: **۲۵.۱۶ ثانیه ستاپ**. بنابراین هر حفاظ ۲۰ ثانیه‌ای «هنگ» جعلی می‌سازد.

### ۵.۳ مقایسه با اجرای کامل قبلی (۲۰۲۶-۱۰-۰۴)

```text
2026-10-04   127 failed, 5062 passed, 62 skipped, 4 errors in 31029.11s (8:37:09)
2026-10-06    50 failed, 5218 passed, 62 skipped, 0 errors  (4 تست پایان نمی‌یافت)
```

**۶۲ skip در هر دو اجرا یکسان است** — تأیید خوبی است که تکه‌تکه‌کردن، مجموعهٔ تست‌های اجراشده را تغییر نداده. افت شکست از ۱۲۷ به ۵۰ و حذف ۴ خطا **اصلاح نیست، رانش محیطی در دو روز** است؛ اجرای ۲۰۲۶-۱۰-۰۴ هم‌زمان با پر بودن دیسک بود.

---

## ۶. مرحله ۵ — رفع علت‌های واقعی (۷ اصلاح)

### ۶.۱ جدول اصلاحات

| # | نشانهٔ اندازه‌گیری‌شده | علت واقعی (تأییدشده) | اصلاح |
|---|---|---|---|
| ۱ | `/api/v1/market/watch` در ۶۰۰ ثانیه هم پاسخ نمی‌داد | `quote_repo.get_all()` = `select(QuoteModel)` روی **۳٬۴۱۲٬۶۲۲** ردیف؛ `limit` بعد از بازگشت سرویس اعمال می‌شد | `get_latest_snapshot(limit)` با فیلتر روی `MAX(date)` و `LIMIT` در SQL؛ `get_market_watch(limit=500)`؛ اندپوینت `limit` را پاس می‌دهد |
| ۲ | `RuntimeError: Event loop is closed`، `'NoneType' object has no attribute 'send'` | اپ FastAPI با دامنهٔ session و استخر اتصال گره‌خورده به یک حلقه، ولی حلقهٔ تست در دامنهٔ **module** | `asyncio_default_fixture_loop_scope` و `asyncio_default_test_loop_scope` → `"session"` |
| ۳ | ۱۵ مورد `401 {"detail":"Not authenticated"}` | روترها با `_require_user` / `_public_read` مانت شده‌اند (router.py:12–17)؛ تست‌ها از `client` بی‌نام استفاده می‌کردند | `_authenticate()` در `conftest.py` هم override ثبت می‌کند و هم global ماژول را patch می‌کند؛ ۱۵ تست به `admin_client`/`user_client` منتقل شدند |
| ۴ | ۳ تست مسیر پذیرش WebSocket | یک دروازهٔ احراز هویت بین گارد Origin و `accept()` نشسته است | تست‌ها `verify_websocket_token` را به `AsyncMock(return_value=True)` patch می‌کنند |
| ۵ | شمارنده‌های canary خبر: ۸ در برابر ۴ و ۶ در برابر ۲ | ترافیک واقعی میدل‌ور به `_mem_counters` سطح-فرایند می‌رسید و خط پایه می‌ساخت | تست‌ها `monkeypatch.setattr(canary, "_mem_counters", {})` به‌جای کپی دیکشنری زنده |
| ۶ | ۸ ناسازگاری قرارداد در معاملات کاغذی | اندپوینت پاکت ایمن برمی‌گرداند (`{"error": {"message": "Internal error"}}`، HTTP 200) و `user_id=None` برای فراخوانی بی‌نام | تست‌ها به قرارداد واقعی به‌روز شدند |
| ۷ | `AttributeError: 'Instrument' object has no attribute 'instrument_id'` از `get_market_summary` | کلید `InMemoryRepository._shared_store` فقط `cls.__name__` بود، پس **هر** نوع موجودیت یک سبد مشترک داشت | کلید اکنون `f"{cls.__name__}:{entity_type.__name__}"`؛ `InMemoryRepository(X)` در ۱۸ محل فراخوانی |

### ۶.۲ اثبات اصلاح ۱ (از مسیر HTTP، همان مسیری که فرانت‌اند استفاده می‌کند)

```text
repositories/quote_repository.py::get_latest_snapshot(500)  →  1.65 s، ۵۰۰ ردیف
GET /api/v1/market/watch → 200                              →  11.485 s     (پیش‌تر: >۶۰۰ ثانیه، بی‌پاسخ)
```

و چهار تستی که در هیچ حفاظی پایان نمی‌یافتند، پس از اصلاح:

```text
$ pytest -q test_backend_api.py::test_market_watch_returns_data \
           test_backend_api_edge_cases.py::test_market_watch_items_have_market_field \
           test_backend_api_edge_cases.py::test_market_watch_markets_have_symbol \
           test_backend_api_edge_cases.py::test_volumes_are_non_negative

GET /api/v1/market/watch -> 200 (2.390s)
GET /api/v1/market/watch -> 200 (0.062s)
GET /api/v1/market/watch -> 200 (0.063s)
GET /api/v1/market/watch -> 200 (0.063s)
4 passed, 2 warnings in 69.91s  (1m28.6s دیوار ساعت)
```

عدد ۶۹.۹۱ ثانیه تقریباً تماماً زمان راه‌اندازی مفسر و اپ FastAPI است، نه اندپوینت.

**دلیل درستی کوئری کراندار:** `MAX(quotes.date)` تازه‌ترین تاریخ معاملاتی ذخیره‌شده را می‌دهد (`2026-10-05`، ۱٬۶۶۷ ردیف، همه `timeframe='1d'`، همه `data_source='brsapi'`). نکتهٔ مهم: `quotes.date` از نوع **VARCHAR** است و تاریخ‌های ISO و جلالی (`1396-08-24`) را قاطی دارد. مقایسهٔ رشته‌ای `MAX` فقط به این دلیل درست کار می‌کند که ردیف‌های ISO بعد از همهٔ ردیف‌های جلالی مرتب می‌شوند — اگر ستون نرمال‌سازی شود، این باید بازبینی شود.

### ۶.۳ تلهٔ واقعی در اولین تلاش برای اصلاح ۳

ثبت override به‌صورت `lambda: replacement` باعث می‌شود FastAPI **خود تابع** را تزریق کند و هر مصرف‌کننده روی `current_user.get(...)` بمیرد:

```text
AttributeError: 'function' object has no attribute 'get'
```

override باید خودِ callable باشد تا FastAPI آن را await کند و مقدار برگشتی را تزریق کند.

### ۶.۴ تأیید یک‌جا روی ۸ ماژول تحت تأثیر

```text
$ pytest -q tests/unit/test_instrument_import_api.py tests/unit/test_endpoints.py \
           tests/unit/test_backend_api.py tests/unit/test_brsapi_sync_nav_all_endpoint.py \
           tests/unit/test_ws_origin_and_table_guard.py tests/unit/services/test_news_read_canary.py \
           tests/unit/test_paper_trading_api.py tests/unit/services/test_historical_data_service.py

پیش از اصلاح:  11 failed, 104 passed, 2 skipped  in 178.94s
پس از اصلاح:    0 failed, 114 passed, 2 skipped  in 225.42s
```

### ۶.۵ تراز نهایی `tests/unit`

```text
                     جمع‌آوری‌شده  سبز   شکست  skip  اندازه‌گیری‌نشده
پیش از اصلاح ۱ تا ۷      5334    5218    50    62        4
پس از اصلاح ۱ تا ۷       5334    5254    18    62        0
```

**این عدد یک بازترکیب است، نه خروجی یک فرایند واحد pytest** — به دو دلیل: (۱) چهار تست هنگ‌کننده در هیچ حفاظ عملی با بقیه در یک فرایند جمع نمی‌شوند، (۲) نتیجهٔ `tests/unit` به مرز تکه‌ها حساس است (بخش ۸.۱). دو چیزی که واقعاً از صفر دوباره اجرا شدند، همان گروه ۸ ماژول بالا و همان چهار تست market-watch است.

### ۶.۶ ۱۸ شکست باقی‌مانده

> **به‌روزرسانی:** ۱۰ مورد از این ۱۸ مورد بعداً رفع شد — ۸ مورد `test_backend_api_edge_cases.py` و ۲ مورد `test_quant_signal_orchestrator.py` (که در واقع آلودگی بین‌فایلی بودند، نه باگ). **۸ مورد** باقی مانده و فهرستشان در بخش ۱۱ آمده است.

```text
 8  test_backend_api_edge_cases.py
      test_signals_nonexistent_type         total = 4 ≠ 0 — فیلتر `type` اعمال نمی‌شود
      test_news_nonexistent_category        total = 19711 ≠ 0 — فیلتر `category` اعمال نمی‌شود
      test_news_page_too_high               صفحهٔ ۹۹۹ هنوز ۱۰ آیتم برمی‌گرداند
      test_fund_navs_are_positive           }
      test_energy_commodity_sub_markets_…   }  همان کلاس قرارداد کهنه: ادعا سطح بالای پاکت را
      test_energy_commodity_sub_market_…    }  می‌خواند نه `data`؛ و /industries در
      test_industries_sorted_by_count       }  /api/v1/market-info/industries است
      test_dashboard_has_all_sections       مجموعهٔ کلیدهای payload ۵ کلید اضافه دارد
 2  test_quant_signal_orchestrator.py       `d["accuracy"] is None` ولی to_dict مقدار `{}` می‌دهد؛
                                            کامنت خود منبع در :714 می‌گوید «همیشه dict — None
                                            مصرف‌کننده‌های cron را می‌شکند» ⇒ تست‌ها کهنه‌اند
 2  test_confirmed_runtime_fixes.py         StopIteration در limiter.wait_if_needed()؛
                                            ModuleNotFoundError: No module named 'database_handler'
 1  test_rate_limit_middleware.py           حالت مشترک limiter بین تست‌ها (همان کلاس مسئلهٔ 429)
 1  test_rbac.py                            ['user'] != ['admin'] — منطق mock_session.call_count
 1  test_api_v6_hardening.py                اسکریپت ممیزی روتر با کد ۱ بیرون می‌آید،
                                            «no authentication dependency resolved»
 1  test_build_feature_store.py             نامی را patch می‌کند که ماژول دیگر ندارد
                                            (`async_session_factory`)
 1  test_brsapi_usage_simulator.py          result.ok برابر False
 1  test_critical_runtime_fixes.py          هیچ traceback ثبت نشد
 18 جمع
```

---

## ۷. مرحله ۶ — تست‌های باقی‌مانده بیرون از `tests/unit`

گروه A: هر `test_*.py` که زیر `tests/unit/` و `tests/legacy/` نباشد (هر فایل، سقف ۱۸۰ ثانیه).
گروه B: `tests/legacy/**` به‌همراه ماژول‌های پراکندهٔ ریشه (۴ شاخه موازی، سقف ۳۰ ثانیه).

```text
XML تجمیع‌شده              109
TOTAL: tests=736  failures=131  errors=15  skipped=7
فایل‌های بدون XML            ۵ (در سقف بیرون انداخته شدند)
  tests/e2e/test_admin_dashboard.py          (۱۸۰ ثانیه)
  tests/test_sync_2.py                       (۱۸۰ ثانیه)
  tests/legacy/root/test_options.py          (۳۰ ثانیه)
  tests/legacy/scripts/test_codal_api.py     (۳۰ ثانیه)
```

`tests/legacy/**` و ماژول‌های پراکندهٔ ریشه در یک فرایند جمع‌آوری نمی‌شوند، چون در زمان import کار شبکه انجام می‌دهند:

```text
ImportError: cannot import name 'app' from 'main'   (tests/legacy/root/test_screener_api.py:16)
MaxRetryError ... WinError 10061                    (localhost:8000)
TimeoutError: _ssl.c:989                            (CODAL)
```

### ۷.۱ دو خوشهٔ غالب

```text
۵۶  رد 429 محدودیت نرخ                    ← از ۱۴۶ شکست، حدود ۸۵ مورد فقط در
                                            tests/comprehensive/test_all.py است
 ۴  401 «Not authenticated»
```

### ۷.۲ خوشهٔ ۴۲۹ — علت تأییدشده، نه حدس

`RateLimitMiddleware.dispatch` وقتی `app_settings.environment == "test"` باشد کوتاه می‌کند. مقدار `ENV` به‌طور پیش‌فرض `"development"` است، پس این مجموعه‌ها با پنجرهٔ لغزان واقعی per-IP اجرا می‌شوند و از سقف‌های تنظیم‌شده رد می‌شوند. اثبات:

```text
$ pytest tests/comprehensive/test_all.py::TestNews::test_news_list \
         tests/comprehensive/test_all.py::TestCodal::test_codal_holders

محیط پیش‌فرض        429 / 429
ENVIRONMENT=test   2 passed, 4 warnings in 16.75s
```

**این یک نقص محیط اجرای تست است، نه نقص محصول** — limiter دقیقاً همان‌طور که تنظیم شده رفتار می‌کند. قرارداد خود مخزن در جای دیگر، بازنشانی limiter در هر تست است (نگاه کنید به `tests/unit/test_signals_rate_limit.py:51`)؛ اما `tests/comprehensive/test_all.py` هیچ‌کدام را انجام نمی‌دهد. **عمداً تغییر داده نشد** — اصلاحش (اعلام محیط test، یا یک فیکسچر autouse بازنشانی) به مجموعه‌هایی بیرون از دامنهٔ درخواست دست می‌زند و خط پایهٔ `tests/unit` را جابه‌جا می‌کند.

### ۷.۳ اسکن امنیتی

`test_api_v6_hardening::test_router_audit_script_runs_clean` با کد خروج ۱ شکست می‌خورد: «no authentication dependency resolved». یعنی اسکریپت ممیزی، روتری پیدا می‌کند که هیچ وابستگی احراز هویتی روی آن resolve نشده. این را باید جدا بررسی کرد.

---

## ۸. یافته‌های جدید (بخش ۸.۱ بعداً رفع شد — بخش ۱۱.۳)

### ۸.۱ آلودگی بین‌فایلی زیر حلقهٔ سراسری session

`tests/unit/services/test_quant_signal_orchestrator.py` **به‌تنهایی**: `2 failed, 53 passed`.
همان فایل بعد از `tests/unit/test_backend_api_edge_cases.py`: **۲۴ شکست** در `TestCrossMarketCorrelator`.

علت، از خود ادعا:

```text
result = await CrossMarketCorrelator.analyze([])
assert len(result) == 0
AssertionError: assert 1 == 0
  where 1 = len([{'name': 'Market-Regime', 'signal': 'INFO',
                  'description': 'خلاصه رژیم بازار بر اساس قیمت‌های واقعی', ...}])
```

تست‌ها فرض می‌کنند «دادهٔ قیمت واقعی وجود ندارد (بدون پایگاه داده)». وقتی ماژول قبلی استخر SQLAlchemy/asyncpg را روی حلقهٔ سراسری session گرم کرده باشد، `analyze([])` واقعاً به پایگاه دادهٔ ۵٫۴۵ میلیون ردیفی می‌رسد و سیگنال Market-Regime برمی‌گرداند — پس فرض می‌شکند.

**این یک رگرسیون از اصلاح ۲ نیست.** با حلقه‌های per-module قبلی، موتور به یک حلقهٔ بسته گره خورده بود، خطا بلعیده می‌شد و `[]` **به دلیل غلط** برگردانده می‌شد. اصلاح ۲ آن تصادفِ پوشاننده را برداشت. نتیجهٔ عملی این است که شمارش قبول/رد در `tests/unit` **به مرز تکه‌ها حساس است** — به همین دلیل اعداد بخش ۵ به‌صورت فایل‌به‌فایل و تکه‌ای تولید شدند و نباید با یک اجرای تک‌فرایندی فرضی مقایسه شوند.

**رفع شد.** `TestCrossMarketCorrelator` اکنون در یک fixture از نوع `autouse` مقدار `core.database.async_session_factory` را به `None` pin می‌کند و تست holdout در auto-retrain هم همین کار را با `monkeypatch` می‌کند، پس فرض «پایگاه داده در دسترس نیست» دیگر به ترتیب اجرای فایل‌ها وابسته نیست. نتیجه: همان فایل به‌تنهایی `55 passed` و پس از یک تست گرم‌کنندهٔ پایگاه داده `57 passed` (پیش‌تر: `2 failed/53` و `24 failed`).

### ۸.۲ فایل‌های تغییر‌یافتهٔ بی‌کامیت فرانت‌اند

نسخهٔ کاری `frontend/src/components/SyncStatus.tsx` یک خط لازم (`useSyncSettings`) را حذف کرده و `frontend/src/lib/fund-analysis.ts` هم تغییر بی‌کامیت دارد. این‌ها علت هر ۷ شکست vitest هستند. **بازگردانی یا اصلاح نشدند** چون از یک جلسهٔ دیگر می‌آیند و بازگردانی‌شان تصمیم شماست.

---

## ۹. محدودیت‌ها — آنچه اجرا نشد

این مرز صادقانهٔ این گزارش است:

- **اجرا شد تا پایان:** `tests/unit` (۵٬۳۳۴ جمع‌آوری، همه اندازه‌گیری شد) و هر تست قابل‌جمع‌آوری بیرون از آن (۷۳۶ اندازه‌گیری، ۵ فایل در سقف بیرون افتادند).
- **کلاً اجرا نشد:** هر چیزی که بدون کار شبکه قابل import نیست — `tests/legacy/**` و ماژول‌های پراکندهٔ ریشه (۱۹ خطای جمع‌آوری، ۰ تست اجرا، ۴۱۳ ثانیه زمان retry).
- **دوباره اندازه‌گیری نشد به‌صورت سرتاسری:** کل `tests/unit` پس از اصلاحات ۱ تا ۷ دوباره اجرا **نشد**. تأیید در بخش ۶.۴ فقط همان ۸ ماژولِ دارای شکست را دوباره اجرا می‌کند. اعداد تجمیعی بخش ۵ همچنان وضعیت **پیش از اصلاح** را توصیف می‌کنند.
- **اکنون اجرا شد (این بند را اصلاح می‌کند):** `scripts/import_corporate_actions.py` و `scripts/backfill_adjust_factors.py` روی پایگاه داده اجرا شدند — `corporate_action_events` ۰ → ۵۸۶ و `daily_adjust_factors` ۰ → ۶۲۱٬۸۱۸ (بخش ۳). `symbols` هنوز ۵۱۱ ردیف است.
- **تصمیم‌گیری نشد:** آیا `--register-missing` مجاز است یا نه؛ ۲۸۶ نماد از ۴۳۱ نماد تأییدشده هنوز گرفتار FK هستند.
- **رفع شد:** شکست‌های `test_quant_signal_orchestrator.py` دو باگ از پیش موجود نبودند بلکه آلودگی بین‌فایلی بودند (بخش ۸.۱) و اکنون رفع شده‌اند. `test_signal_decision_engine.py` بازبینی نشد.
- **اکنون کامیت شد (این بند را اصلاح می‌کند):** اصلاحات کد و تست به‌صورت کامیت `f0ed96d4` ثبت شدند، با staging hunk-by-hunk تا ویرایش‌های بی‌ربط از قبل موجود در همان فایل‌ها (`audit API-005` در `market.py`، DP-020 در `codal_repository.py`، `ins_code` در `instrument_repository.py`، کامنت سیاست وابستگی در `pyproject.toml`، و `merge` در `db_base.py`) در درخت کاری باقی بمانند.

---

## ۱۰. گام‌های بعدی پیشنهادی

۱. **تصمیم دربارهٔ ثبت نمادها** — آیا `--register-missing` مجاز است؟ (۲۸۶ نماد تأییدشده هنوز FK-blocked هستند)
۲. **بازگردانی یا اصلاح فرانت‌اند** — یک خط در `SyncStatus.tsx` هفت تست vitest را برمی‌گرداند.
۳. **رفع ۸ شکست باقی‌ماندهٔ `tests/unit`** — هر کدام علت جداگانه‌ای دارد (بخش ۱۱.۴).
۴. **بازبینی اسکن امنیتی** — روتری که «هیچ وابستگی احراز هویتی resolve نشده» دارد.
۵. **زمان‌بندی بازسازی فاکتورها** — `recompute_factors` هیچ فراخوانی‌ای ندارد؛ پس از رویداد جدید هیچ job یا endpointی `daily_adjust_factors` را بازنمی‌سازد.

---

## ۱۱. پیگیری پس از این گزارش — اجرا، رفع شکست‌ها، و حذف آلودگی

### ۱۱.۱ وارد‌سازی و بک‌فیل اجرا شدند

۵۸۶ رویداد و ۶۲۱٬۸۱۸ فاکتور (بخش ۳).

### ۱۱.۲ هشت شکست `test_backend_api_edge_cases.py` رفع شد

تنها تغییر محصولی، فیلتر دستهٔ اخبار بود: `GET /news?category=` صفحهٔ واکشی‌شده را فیلتر می‌کرد ولی شمارش کل جدول را نگه می‌داشت (برای دستهٔ ناموجود `total=19711`). اکنون فیلتر به SQL رانده می‌شود از طریق `NewsService.list_all` → `NewsRepository.list` → `_NewsDbRepo` و `NewsItemsReadRepo` (برای حفظ تقارن مسیر canary)، و endpoint پیش از کوئری نام مستعار را نرمال می‌کند. بقیهٔ موارد تعمیر تست بودند: `page=999` واقعاً در محدوده بود (اکنون `total_pages+1`)؛ `/funds` پاکت خام با `items` سطح بالا برمی‌گرداند؛ داشبورد کلیدهای بیشتری از ۵ کلید دارد (اکنون `<=`)؛ `sub_markets`/`summary` زیر `data` هستند؛ `/industries` در `/api/v1/market-info/industries` است؛ و `type` روی `/signals` اصلاً فیلتر وجود ندارد.

```text
$ pytest -q tests/unit/test_backend_api_edge_cases.py
34 passed in 420.50s      exit status 0
```

شش مجموعهٔ همسایهٔ اخبار هم دوباره اجرا شدند: ۱۵۸ سبز، ۴ اسکیپ، exit 0.

### ۱۱.۳ آلودگی بین‌فایلی حذف شد

بخش ۸.۱: هر دو تست اکنون منبع داده را روی `None` pin می‌کنند. `test_quant_signal_orchestrator.py` به‌تنهایی ۵۵ سبز و پس از یک تست گرم‌کنندهٔ پایگاه داده ۵۷ سبز (exit 0).

### ۱۱.۴ هشت شکست باقی‌ماندهٔ `tests/unit`

```text
2  test_confirmed_runtime_fixes.py     StopIteration در limiter؛ ModuleNotFoundError: 'database_handler'
1  test_rate_limit_middleware.py       حالت مشترک limiter بین تست‌ها
1  test_rbac.py                        ['user'] != ['admin'] — منطق call_count
1  test_api_v6_hardening.py            اسکریپت ممیزی روتر با کد ۱ بیرون می‌آید
1  test_build_feature_store.py         patch روی نامی که ماژول دیگر ندارد
1  test_brsapi_usage_simulator.py      result.ok برابر False
1  test_critical_runtime_fixes.py      هیچ traceback ثبت نشد
  ۸ جمع
```

این هشت مورد از نظر آلودگی بررسی شدند (نه فرض): هم به‌تنهایی و هم پس از یک تست گرم‌کنندهٔ پایگاه داده دقیقاً همین هشت مورد شکست می‌خورند.

### ۱۱.۵ کامیت

```text
f0ed96d4  fix(test-isolation,api): bound market-watch, fix news category paging, unblock unit suite
          ۳۴ فایل، ‎+۷۸۵/−۱۲۸
```

---

## پیوست — کامیت و وضعیت مخزن

```text
main → f0ed96d4                       کامیت اصلاحات کد و تست (۳۴ فایل، ‎+785/−128) — push نشده
main~1 → 1212cb87                     مستندات (ممیزی، قیمت، گزارش‌ها)
main~2 → 43278bbd                     اسکریپت وارد‌سازی (۳ فایل، ‎+773/−1)
docs/ARCHITECTURE_AUDIT_2026-10-06.md       ??   (۴۴۸ خط، شامل §۹ تأیید)
docs/SESSION_REPORT_2026-10-06_EN.md        ??   (شامل بخش‌های D و E)
docs/FINAL_REPORT_2026-10-07_FA.md          ??   (همین فایل)

corporate_action_events = 586    daily_adjust_factors = 621,818    symbols = 511
فضای آزاد C = 28 GB
```

### فایل‌های اصلاح‌شده در این جلسه (اکنون در `f0ed96d4` کامیت شده)

```text
repositories/base_repository.py                 اصلاح ۷  کلید + __init__
repositories/quote_repository.py                اصلاح ۱  get_latest_snapshot (facade + DB)
repositories/*.py  (۱۷ فایل دیگر)               اصلاح ۷  InMemoryRepository(X) در ۱۸ محل
services/market_service.py                      اصلاح ۱  get_market_watch(limit=500)
apps/api/endpoints/market.py                    اصلاح ۱  پاس دادن limit  [مخلوط با ویرایش قبلی]
pyproject.toml                                  اصلاح ۲  دامنهٔ حلقه‌ها → session
tests/unit/conftest.py                          اصلاح ۳  _authenticate / admin_client / user_client
tests/unit/test_instrument_import_api.py        اصلاح ۳
tests/unit/test_endpoints.py                    اصلاح ۳ + ۳ تعمیر قرارداد کهنه
tests/unit/test_backend_api.py                  اصلاح ۳ + ۳ تعمیر قرارداد کهنه
tests/unit/test_brsapi_sync_nav_all_endpoint.py اصلاح ۳
tests/unit/test_ws_origin_and_table_guard.py    اصلاح ۴
tests/unit/services/test_news_read_canary.py    اصلاح ۵
tests/unit/test_paper_trading_api.py            اصلاح ۶
services/news_service.py                        بخش ۱۱.۲  راندن فیلتر دسته به SQL
repositories/news_repository.py                 بخش ۱۱.۲  راندن فیلتر دسته (legacy + canary)
repositories/news_items_read_repo.py            بخش ۱۱.۲  راندن فیلتر دسته (مسیر items)
apps/api/endpoints/news.py                      بخش ۱۱.۲  پاس دادن دستهٔ نرمال‌شده به کوئری
tests/unit/test_backend_api_edge_cases.py       بخش ۱۱.۲  ۸ شکست → ۰ (۳۴ سبز)
tests/unit/services/test_quant_signal_orchestrator.py بخش ۱۱.۳  pin کردن منبع داده
tests/unit/backtesting/test_audit_fixes_regression.py بخش ۱۱.۳  pin کردن منبع داده (فایل جدید)
```

ویرایش‌های بی‌ربط از قبل موجود با staging hunk-by-hunk از کامیت بیرون نگه داشته شدند: سقف `limit` روی `/bourse` در `market.py`، ویرایش‌های DP-020 در `codal_repository.py`، تغییر `ins_code` در `instrument_repository.py`، کامنت سیاست وابستگی در `pyproject.toml`، و تغییر `merge` در `db_base.py`.
