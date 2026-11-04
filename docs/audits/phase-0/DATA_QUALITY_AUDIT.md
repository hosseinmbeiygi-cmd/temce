# ممیزی کیفیت داده — فاز صفر

**مبنا:** خواندن `brsapi/`، `src/gold_desk/{freshness,phase1,phase2,snapshot_service}.py`، تست‌های gold، و اجرای ۴۳۴ تست gold (سبز).
**محدودیت:** پروفایل کامل جدول‌های دیتابیس، نرخ خطای واقعی provider و کیفیت داده تاریخی انجام نشد.

---

## 1. منابع داده

| منبع | نوع | تنظیمات | شواهد |
|---|---|---|---|
| BrsApi | REST (TSE/IME/طلا/ارز/کریپتو) | timeout=30s، max_retries=3، backoff=1.5 تا 60s، rate limit پیش‌فرض 30/min + سقف per-endpoint | `brsapi/config.py:395-398,42` |
| BrsApi master switch | `BRSAPI_ENABLED` | پیش‌فرض `True`؛ `False` = DB-only بدون HTTP | `brsapi/config.py:390-394` |
| Codal | اطلاعیه/صورت مالی | endpointهای جدا | `apps/api/endpoints/codal*.py` |
| IME | گواهی/صندوق/آتی | مدل‌های `brsapi.models.ime` | `src/gold_desk/phase1.py` |
| TGJU | منبع ثانویه طلا | همیشه `DELAYED` (بدون timestamp منبع) | `tests/gold_desk/test_phase0_snapshot_provenance.py` |
| Redis | cache | `cache_ttl_default=55s` | `brsapi/config.py:400-401` |

---

## 2. قرارداد کیفیت داده

### 2.1 فیلدهای اجباری (GoldDesk)

| فیلد | معنا | شاهد |
|---|---|---|
| `value`/`price` | مقدار | `phase1_schemas.py` |
| `unit` | `rial`/`ounce` | schema Literal |
| `source` | `brsapi`/`tgju`/`cache` (mixed ممنوع) | `antigravity/engine.ALLOWED_SOURCES` |
| `asOf` | زمان **منبع**، نه زمان ساخت پاسخ | `test_phase0_snapshot_provenance.py` |
| `quality` | `LIVE/DELAYED/SAMPLE/EDUCATIONAL/NO_DATA` | schema + `DataTrustBadge.tsx` |
| `data_gaps` | دلیل فارسی داده غایب | `phase1.py` |

**قاعده fail-closed:** مقدار غایب = `None` + دلیل؛ هرگز صفر یا تخمین. تست‌های `test_missing_row_is_no_data_and_is_not_zero`، `test_missing_nav_is_null_and_never_zero`، `test_missing_ticker_item_is_no_data_with_a_note` این را پین می‌کنند.

### 2.2 تازگی (Freshness)

`src/gold_desk/freshness.py` برای ۱۳ منبع آستانه دارد:

| منبع | آستانه | وضعیت |
|---|---|---|
| قیمت زنده طلا/سکه و ارز | ۱۲۰ دقیقه | `ok/stale/empty/missing` |
| تاریخچه روزانه | ۲۸۸۰ دقیقه | — |
| NAV صندوق | ۱۴۴۰ دقیقه | — |
| snapshot/score | ۳۰ دقیقه | — |
| پرتفوی/هشدار | ۱۴۴۰/۵۲۵۶۰۰ | — |

- خطای خواندن جدول → `missing` (نه `ok`).
- ردیف صفر یا زمان نامعتبر → `empty`.
- ستون naive به‌عنوان **زمان تهران** تفسیر می‌شود (`_as_utc` با `tehran_to_utc`).
- **ریسک:** این تفسیر در کد است، نه در schema؛ اگر نویسنده‌ای UTC naive بنویسد، سن ۳.۵ ساعت اشتباه می‌شود. نیازمند تست در فاز ۱/۵.

### 2.3 برچسب‌های LIVE/DELAYED/SAMPLE

- `LIVE` فقط با اثبات تازگی از BrsApi.
- مقدار ناشناخته در UI → `DELAYED` (fail-closed)، `NO_DATA` صریح باقی می‌ماند (`DataTrustBadge.tsx:28-38`).
- `SAMPLE` پس‌زمینه solid rose + ring (متمایز از LIVE سبز) و فقط برای what-if preview.
- `EDUCATIONAL` برای محتوای آموزشی، نه قیمت.

---

## 3. دریافت، اعتبارسنجی و ذخیره

| مرحله | رفتار | شاهد |
|---|---|---|
| dedup درخواست | کلید `endpoint.path + params`؛ `dedup_seconds` | `sync_service.py:352-355` |
| upsert snapshot | `ON CONFLICT (symbol, fetched_at) DO UPDATE` | `sync_service.py:458-473` |
| rowcount واقعی | `result.rowcount` با fallback مستند | `repositories/base.py:329-339` |
| انتخاب ردیف | جدیدترین `fetched_at` برنده می‌شود | تست provenance |
| unique constraint | `(symbol, fetched_at)` روی snapshot | `brsapi/models/tsetmc.py:134-140` |
| تبدیل واحد | Toman→Rial صریح؛ FX history ریال (بدون ×۱۰) | `phase1._toman_to_rial`, تست phase2 |
| Jalali→UTC | `_parse_jalali` + `tehran_to_utc` | تست NAV |

---

## 4. ریسک‌ها و ایرادهای تأییدشده

| ID | ریسک | شاهد | اثر |
|---|---|---|---|
| ISSUE-119 | کلید BrsApi در cooldown سمت ارائه‌دهنده | پیام `Suspend.php` در ۵ تست | قیمت‌ها کهنه می‌شوند؛ UI `DELAYED` نشان می‌دهد اما تحلیل محدود می‌شود |
| ISSUE-116 | تست‌های واحد به state سراسری cooldown وابسته‌اند | ۵ شکست retry | نتیجه تست غیرقطعی؛ مصرف کلید در تست |
| — | دو board فاز ۲ بدون feed | `phase2.py:16-20` (verified schema 2026-10-26) | ستون‌ها با `NO_DATA` می‌مانند، حذف نمی‌شوند |
| — | `enabled=True` پیش‌فرض | `brsapi/config.py:390` | در نبود کلید معتبر، تلاش شبکه و cooldown |
| — | naive datetime | مدل‌ها `DateTime` بدون tz | تفسیر Tehran در freshness؛ ریسک اگر نویسنده UTC بنویسد |
| — | Redis نامشخص | در تست `null cache` | cache hit نامعلوم؛ بار روی DB/provider |

---

## 5. جلوگیری از داده ساختگی

| مسیر | نتیجه |
|---|---|
| `useMarketData` و هوک‌های زنده | fallback ساکت به mock پیدا نشد؛ `isLive/isError` و `LiveDataBanner` |
| what-if طلا | فقط preview با `SAMPLE`، هیچ نوشتنی ندارد (`api.py:144-145`) |
| فاز ۱/۲ | `None` + `data_gaps`، تست‌شده |
| `docs/handoff.md` | ادعای «no fabricated 2650/85000» با تست/کد هم‌راستاست |
| `auto_trade` | dry-run پیش‌فرض؛ **هیچ route مصرف‌کننده ندارد** (خارج از دامنه) |

**ریسک باقی‌مانده:** `latest row wins` بر اساس `fetched_at` است؛ اگر provider ردیف قدیمی را با `fetched_at` جدید بفرستد، «تازه» تلقی می‌شود. تست فقط ترتیب زمانی را می‌سنجد، نه اصالت داده provider.

---

## 6. پروفایل داده واقعی (T14 — اجرا شد)

منبع: دیتابیس اپ `my_first_db` (PostgreSQL 18.4، ۵۱GB)، **فقط خواندن**، `statement_timeout=120s`. اسکریپت‌ها: `_audit_tmp/gold_quality_report.py`، `gold_quality_followup.py`، `gold_date_check.py`.

### 6.1. حجم و تازگی

| جدول | ردیف | نمادها | آخرین رکورد | سن داده |
|---|---|---|---|---|
| `brsapi_gold_currency_pro_daily_history` | ۳۲۱٬۷۳۶ | ۷۲ | 2026-09-14 (زمان درج) | **۴۲ روز** |
| `brsapi_gold_coin_history` | ۴۴٬۹۶۵ | ۲۴ | 2026-09-14 | **۴۲ روز** |
| `brsapi_nav_records` | ۳٬۵۸۸ | ۳۳۰ | 2026-10-05 | **۲۱ روز** |
| `funds` (snapshot) | ۵۸۹ | ۵۸۹ | 2026-10-23 | ۳ روز |
| `brsapi_gold_coin_prices` / `currency_prices` | ۹ / ۲۸ | — | بدون `updated_at` | قابل تعیین نیست |

### 6.2. ایراد تأییدشده ۱ — تاریخچه دوبار با فرمت متفاوت درج شده و ستون‌های تاریخ میلادی/شمسی بی‌معنا هستند

- `date` در همان جدول دو فرمت دارد: `1405/05/01` (۱۶۰٬۲۹۳ ردیف) و `1405-06-23` (۱۶۱٬۴۴۳ ردیف) — همان تاریخچه دو بار با جداکننده متفاوت ذخیره شده است.
- `gregorian_date` تبدیل تاریخ نیست؛ **تاریخ اجرای ingestion** است: ۱۶۰٬۲۹۳ ردیف مقدار `2026-07-23` و ۱۶۰٬۲۹۳ ردیف مقدار `2026-08-31` دارند، در حالی که `date` از ۱۳۴۸ تا ۱۴۰۵ شمسی پراکنده است.
- `shamsi_date` هم همان تاریخ اجرا است (برای `AED` همه ردیف‌ها `1405-06-23`، در حالی که `date` شامل ۰۶-۱۲ تا ۰۶-۲۳ است).
- اثر: هر فیلتر/join بر `gregorian_date` (تازگی، بازه بک‌تست، dedup، «۳۰ روز اخیر») نتیجه غلط می‌دهد؛ `last30=0` در حالی که ردیف‌های ۱۴۰۵-۰۶ موجودند. حذف تکراری‌ها هم شکست می‌خورد چون کلید یکتا بر `date` رشته‌ای ناهمسان است.
- ثبت: **ISSUE-127**.

### 6.3. ایراد تأییدشده ۲ — `nav` صندوق‌ها کپی `price_last` است؛ حباب/تخفیف ساختاراً صفر

- ۵۸۹ صندوق: فقط **۳۲** مورد `nav > 0` دارند و در **۳۲ از ۳۲** مورد `nav == price_last` (اختلاف صفر).
- برای برخی از همین نمادها رکورد NAV واقعی وجود دارد (مثلاً `اطلس`: ۱۴ رکورد تا 2026-10-05) اما `funds.nav` از آن خوانده نشده است.
- نتیجه اندازه‌گیری‌شده: توزیع `price/nav - 1` برای هر ۳۲ صندوق **دقیقاً صفر** (`p05=p50=p95=min=max=0`)؛ بنابراین معیار «حباب صندوق طلا» در داده فعلی هیچ اطلاعاتی ندارد و هر نمایشی از آن گمراه‌کننده است.
- ثبت: **ISSUE-128**.

### 6.4. ایراد تأییدشده ۳ — OHLC ناسازگار در تاریخچه طلا/سکه

| جدول | high<low | close خارج از [low,high] | open خارج از بازه | extreme ≤ ۰ | close ≤ ۰ |
|---|---|---|---|---|---|
| `gold_daily` | ۷۴ | ۹۰ | ۶۷۶ | ۶ | ۰ |
| `coin_history` | ۴۷ | ۶۴ | ۶۳ | ۱۷ | ۱۷ |

نرخ خطا کوچک است (<۱٪) اما در جدول «تاریخچه روزانه» بدون هیچ فلگ کیفیت ذخیره می‌شود و مصرف‌کننده نمی‌تواند ردیف خراب را تشخیص دهد. ثبت در ISSUE-127 به‌عنوان بخشی از همان مسیر ingestion.

### 6.5. آنچه هنوز بررسی نشده

- نرخ خطای واقعی هر endpoint BrsApi در ۲۴ ساعت گذشته (نیازمند لاگ provider).
- سیاست نگهداری/حذف داده و نرخ رشد ماهانه (فقط حجم فعلی اندازه‌گیری شد).
- صحت فرمول‌های NAV/ترکیب صندوق در سطح محاسبه (فاز ۵) — این بخش فقط **داده** را سنجید، نه فرمول.
- Redis و اثر cache در production (خارج از دامنه این پروفایل).
