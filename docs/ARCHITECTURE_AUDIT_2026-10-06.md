# گزارش ممیزی معماری — ۱۴۰۵/۰۷/۱۴ (2026-10-06)

> **نوع سند:** ممیزی عمیق معماری (Architecture & Flow Alignment, Modularity, Performance/Concurrency/Data Integrity)
> **روش:** شمارش مستقیم فایل‌ها/خطوط + بررسی کد منبع در ریپوی اصلی (نه فقط README) + تطبیق با `docs/ARCHITECTURE_AUDIT.md` و `docs/re-audit-status.md` موجود تا یافته‌های قبلاً رفع‌شده دوباره گزارش نشوند.
> **محدوده:** backend (apps/api, services, backtesting, ml, brsapi, core, jobs) + frontend (Next.js)
> **یادداشت روش‌شناسی:** یکی از زیرعامل‌های تحقیق ابتدا یک worktree قدیمی (`.kilo/worktrees/exuberant-authority`, آخرین تغییر ۲۳ اوت ۲۰۲۶) را به‌جای ریپوی اصلی خوانده بود. همه یافته‌های مربوط به `core/database.py` و Redis locking در این سند مستقیماً از ریپوی اصلی (HEAD فعلی) دوباره تأیید شده‌اند.

---

## راهنمای دسته‌بندی یافته‌ها

هر یافته یکی از این برچسب‌ها را دارد:

| برچسب | معنی |
|---|---|
| **CONFIRMED DEFECT** | با خوانش مستقیم کد تأیید شد؛ رفتار واقعی با رفتار صحیح/مورد انتظار فرق دارد |
| **DOCUMENTATION DRIFT** | کد صحیح است؛ فقط README/مستندات با وضعیت فعلی کد همخوانی ندارد |
| **RISK — NEEDS TEST** | الگوی کد مشکوک به نظر می‌رسد اما بدون اجرای تست/پروفایل واقعی نمی‌توان قطعی گفت |
| **UNVERIFIED HYPOTHESIS** | فقط از یک جستجوی سطحی یا گزارش عامل فرعی برداشت شده؛ با کد اصلی تطبیق کامل داده نشده |

---

## 1. تطبیق آمار README با کد واقعی — DOCUMENTATION DRIFT

شمارش مستقیم در ریپوی اصلی (نه ادعای README):

| ادعا | README | واقعی (شمارش مستقیم) | وضعیت |
|---|---|---|---|
| فایل endpoint | ۶۰ | **۸۲** | کمتر از واقعیت |
| route (`@router.*`) | ~۴۳۸ | **۶۲۷** | کمتر از واقعیت (۴۳٪ بیشتر) |
| فایل سرویس (`services/` مستقیم) | ۱۰۳ | **۱۶۱** | کمتر از واقعیت |
| فایل سرویس (`services/` با زیرپوشه) | — | **۲۳۹** | — |
| ماژول بک‌تست | ۲۷۵ | **۲۵۵** | نزدیک |
| ماژول ML | ۱۱۸ | **۱۰۸** | نزدیک |
| مهاجرت Alembic (head claimed: 0039) | ۳۹ | **۷۸** (head واقعی: `0109`) | **بشدت قدیمی** |
| فایل تست | ۲۵۰ | **۴۱۸** | کمتر از واقعیت |
| صفحه فرانت‌اند (`page.tsx`) | ۸۸ | **۱۴۸** | کمتر از واقعیت (۶۸٪ بیشتر) |

**علت:** آخرین commit روی `README.md`: ۱۶ شهریور ۲۰۲۶. آخرین commit کد در زمان ممیزی: ۶ مهر ۲۰۲۶ (migration `0109`). فاصله حدود ۳ هفته توسعه فعال، بدون به‌روزرسانی متناظر آمار.

**طبقه‌بندی:** DOCUMENTATION DRIFT — هیچ مدرکی مبنی بر آمار ساختگی یا گمراه‌کننده عمدی نیست؛ صرفاً مستندسازی هم‌گام با سرعت توسعه نبوده.

---

## 2. صحت ادعاهای معماری زیرساخت

### 2.1 TimescaleDB — CONFIRMED (ادعای README درست است)

بررسی مستقیم `migrations/versions/*.py` در ریپوی اصلی: ۴ فایل migration شامل `create_hypertable()` هستند، جمعاً روی ۱۲ جدول:

```
candlesticks, commodity_prices, daily_history, daily_real_legal,
etf_nav, gold_currency_prices, intraday_trades, market_ticks,
orderbook_snapshots, screener_snapshots, shareholders, symbol_snapshots
```

نمونه (`migrations/versions/0001_initial_schema.py`):
```
SELECT create_hypertable('symbol_snapshots', 'time', chunk_time_interval => INTERVAL '1 day', ...)
SELECT create_hypertable('daily_history', 'trade_date', chunk_time_interval => INTERVAL '30 days', ...)
```

`docker-compose.yml` نیز ایمیج `timescale/timescaledb:latest-pg15` را واقعاً به‌کار می‌برد (نه فقط ذکر در مستندات).

**طبقه‌بندی:** CONFIRMED — یک زیرعامل تحقیق اولیه ادعا کرده بود TimescaleDB «دورمنت/استفاده‌نشده» است؛ این ادعا مستقیماً در ریپوی اصلی رد شد و در اینجا اصلاح‌شده ثبت می‌شود.

### 2.2 صف Job — نام‌گذاری نادرست در README (DOCUMENTATION DRIFT، نه نقص عملکردی)

پیاده‌سازی واقعی در `jobs/queue_publisher.py` / `jobs/queue_consumer.py`:
- ساختار داده: Redis **Lists** با الگوی `BRPOPLPUSH` (نه Redis Streams واقعی با `XADD`/`XREADGROUP`/`XACK`)
- صف dead-letter: `job:dead` — تأیید شد در `jobs/queue_consumer.py:71` (`self._dead_queue = settings.job_queue_dead_letter`)
- منطق retry/dead-letter: `jobs/queue_consumer.py:284-324` — بعد از رسیدن به سقف تلاش، job به `job:dead` منتقل می‌شود؛ هشدار Telegram هنگام عبور از آستانه عمق صف (`dl_alert_threshold`)
- شمارنده‌های متریک: `processed`, `failed`, `dead_lettered`, `rejected_auth`, `uptime_s` (`jobs/queue_consumer.py:87, 338`)
- قفل per-worker lease با بازیابی job های یتیم هنگام انقضای lease

**طبقه‌بندی:** DOCUMENTATION DRIFT — منطق retry/dead-letter به‌درستی و کامل پیاده‌سازی شده؛ فقط اصطلاح «Redis Streams» در README با ساختار داده واقعی (Lists) مطابقت ندارد.

### 2.3 قفل توزیع‌شده Redis — CONFIRMED صحیح

`jobs/locking.py` (۲۴۶ خط، تأیید شده در ریپوی اصلی):
- توکن یکتا per-instance برای جلوگیری از آزادسازی قفل متعلق به process دیگر
- آزادسازی اتمیک با Lua script (`_LUA_RELEASE`, خط ۱۳-۱۸): `if redis.call("get", KEYS[1]) == ARGV[1] then return redis.call("del", KEYS[1])` — الگوی compare-and-delete درست، بدون race شرطی
- تمدید اتمیک مشابه با `_LUA_EXTEND`
- TTL پیش‌فرض برای جلوگیری از deadlock در صورت crash process
- fallback به قفل درون‌حافظه‌ای وقتی Redis در دسترس نیست

**طبقه‌بندی:** CONFIRMED — بدون نقص.

---

## 3. مسیر داده سرتاسری (Ingestion → Processing → Storage)

مسیر تأیید شده با خوانش مستقیم کد:

```
brsapi/client.py (HTTP + retry/circuit-breaker)
  → brsapi/services/sync_service.py (رعایت rate-limit/budget via brsapi/budget.py::BrsApiBudgetGovernor)
  → brsapi/parsers/* (تبدیل پاسخ خام)
  → brsapi/pipelines/ (normalization/validation/enrichment)
  → brsapi/repositories/* (نوشتن ORM)
  → PostgreSQL + TimescaleDB hypertable
```

قفل توزیع‌شده (`RedisJobLock`) مانع اجرای همزمان sync توسط چند worker می‌شود.

**طبقه‌بندی:** CONFIRMED — مسیر منطقی، بدون نقطه شکست آشکار در کد. Redis در این مسیر فقط برای lock/budget استفاده می‌شود؛ کش داده جداگانه در `core/cache_manager.py` (سه‌لایه) مدیریت می‌شود، نه در مسیر ingestion.

---

## 4. کیفیت کد و پیمانه‌پذیری

### 4.1 لایه‌بندی — CONFIRMED تمیز است

هیچ import مستقیمی از `apps/api` به داخلی‌های `backtesting/`/`ml/` یا برعکس پیدا نشد. مسیر همیشه `API → services → domain` است.

### 4.2 وابستگی چرخه‌ای شناخته‌شده — CONFIRMED (از پیش شناخته‌شده، هنوز باز)

`services/watchlist_service.py` ↔ `services/symbol_catalog.py` — با import تأخیری درون متد حل‌وفصل شده، نه رفع واقعی چرخه. این یافته از قبل در `docs/ARCHITECTURE_AUDIT.md` (شناسه D4) ثبت شده بود؛ در این ممیزی فقط تأیید شد که همچنان برقرار است.

**گارد غایب:** `import-linter` کش دارد (`.import_linter_cache`) اما **در `pyproject.toml` پیکربندی نشده** — یعنی هیچ contract فعالی برای جلوگیری از عود این الگو یا کشف چرخه‌های جدید وجود ندارد.

**طبقه‌بندی:** CONFIRMED DEFECT (وضعیت) + RISK — NEEDS TEST (برای این‌که آیا چرخه‌های دیگری در حال شکل‌گیری هستند، لازم است `import-linter` با contract واقعی روی کل کدبیس اجرا شود؛ در این ممیزی چنین اجرایی صورت نگرفت).

### 4.3 DI Container بلااستفاده — CONFIRMED

`core/dependency_injection/container.py` وجود دارد اما تقریباً هیچ سرویسی از آن استفاده نمی‌کند. الگوی غالب: import تأخیری درون متد (`from core.database import async_session_factory`) در حدود ۳۰ فایل سرویس، برای گریز از چرخه import.

**طبقه‌بندی:** CONFIRMED (مشاهده مستقیم) — این یک ناهم‌خوانی معماری است (ابزار ساخته‌شده و رهاشده)، نه یک باگ کارکردی.

### 4.4 God Objects — CONFIRMED (قبلاً شناخته‌شده، هنوز باز)

قبلاً در `docs/ARCHITECTURE_AUDIT.md` به‌عنوان یافته P2 (D5) ثبت شده بود. در این ممیزی با شمارش خط مستقیم دوباره تأیید شد:

| فایل | خط | وضعیت |
|---|---|---|
| `services/stock_assistant_service.py` | ۲۱۳۷ | هنوز تفکیک‌نشده |
| `services/quant_signal_orchestrator.py` | ۲۰۴۹ | هنوز تفکیک‌نشده |
| `services/unified_assistant_service.py` | ۲۰۱۰ | هنوز تفکیک‌نشده |

**طبقه‌بندی:** CONFIRMED (وضعیت بدون تغییر نسبت به ممیزی قبلی) — اولویت P2، نه مسدودکننده.

---

## 5. یکپارچگی فرانت‌اند (Next.js) ↔ بک‌اند

### 5.1 پروکسی و لایه API client — CONFIRMED صحیح

`next.config.ts` + `frontend/src/lib/api.ts`: توکن‌ها در حافظه (نه localStorage)، refresh خودکار با deduplication درخواست‌های هم‌زمان، timeout متناسب با نوع عملیات (۶۰ ثانیه پیش‌فرض، ۱۰ دقیقه برای عملیات سنگین مثل backtest/import).

### 5.2 سازگاری قرارداد API — CONFIRMED برای مسیرهای بررسی‌شده

۳ مسیر نمونه (fund NAV dashboard، enriched-heatmap، fund NAV calculate) بررسی شد و هر سه **کاملاً با backend سازگار** بودند — بدون drift قرارداد در این نمونه‌ها.

**محدودیت دامنه:** این فقط ۳ مسیر از دهها hook موجود در frontend را پوشش می‌دهد؛ تعمیم به «همه مسیرها سازگارند» یک UNVERIFIED HYPOTHESIS است. بدون codegen نوع (OpenAPI → TypeScript)، تایپ‌ها دستی و مجزا از Pydantic schemas نگه‌داری می‌شوند — این یک منبع بالقوه (نه فعلاً مشاهده‌شده) انحراف آینده است.

### 5.3 تکرار منطق امتیازدهی صندوق (D6) — CONFIRMED DEFECT (هنوز باز)

قبلاً در `docs/ARCHITECTURE_AUDIT.md` (D6) ثبت شده بود؛ در این ممیزی با خوانش مستقیم هر دو طرف دوباره تأیید شد:

- Frontend: `frontend/src/lib/fund-analysis.ts:168-192` — `scoringEngine` با ۶ بُعد ثابت (financial/liquidity/management/risk/cost/transparency)
- Backend: `services/fund_scoring.py` — وزن‌های **type-aware** per نوع صندوق (leveraged/equity/...)، با فیلدهای بیشتر (`liquidity_spiral`, `beta_hidden_lev`, `alpha_ir`, ...)

این دو منطق مستقل از هم محاسبه می‌شوند و برای یک صندوق واحد می‌توانند عدد متفاوت نتیجه دهند.

**طبقه‌بندی:** CONFIRMED DEFECT — ریسک مالی مستقیم (کاربر در UI عددی می‌بیند که ممکن است با امتیاز واقعی backend یکی نباشد). راه‌حل پیشنهادی قبلی (گزینه ۱ در D6: فرانت‌اند فقط امتیاز را از API بخواند) هنوز اجرا نشده.

### 5.4 استفاده مستقیم از `fetch()` به‌جای TanStack Query — CONFIRMED

حدود ۸ مورد `fetch()` مستقیم شناسایی شد که از TanStack Query عبور نمی‌کنند:
- `frontend/src/app/admin/page.tsx`
- `frontend/src/app/backtest/compose/page.tsx` (چند مورد)
- `frontend/src/app/data/page.tsx`
- `frontend/src/app/data-import/page.tsx`

کلیدهای query نیز به‌صورت ad-hoc درون هر hook تعریف شده‌اند؛ هیچ `queryKeys.ts` مرکزی یا پیکربندی سراسری retry/error برای `QueryClient` پیدا نشد.

**طبقه‌بندی:** CONFIRMED (مشاهده مستقیم فایل‌ها) — ریسک کارکردی: کش/دیدوپ/مدیریت خطای ناهمگون بین بخش‌های مختلف UI.

---

## 6. async SQLAlchemy / یکپارچگی داده

### 6.1 پیکربندی engine/session — CONFIRMED قوی

`core/database.py` (نسخه فعلی ریپوی اصلی، تأیید شده با diff در برابر نسخه قدیمی‌تر یک worktree کناری):

- `pool_pre_ping=True` + `pool_recycle=3600` ثانیه + `pool_size`/`max_overflow` قابل‌پیکربندی (`core/database.py:92-97`)
- **سطح ایزولاسیون صریح `READ COMMITTED`** پین‌شده روی engine (`core/database.py:170-171`) — جلوگیری از تغییر صامت توسط driver/pool recycling؛ برای داده مالی مهم است
- **تشخیص خودکار نوشتن session** از طریق SQLAlchemy event listeners (`do_orm_execute`, `before_flush`, `after_flush` — خطوط ۲۹-۷۴) تا `get_session()` فقط وقتی واقعاً نوشته شده commit کند. کامنت کد (`core/database.py:72`) به یک باگ قبلی («bug seen in user registration») اشاره می‌کند که این مکانیزم رفع آن است.
- **پشتیبانی read-replica** (`core/database.py:81-82, 178-195, 207-218`) با گارد صریح: نوشتن تصادفی روی replica session به‌جای drop صامت، `RuntimeError` می‌دهد (`_READONLY_WRITE_MSG`)
- پارامترایزیشن `text()` — بررسی نمونه‌ها نشان داد از پارامتر نام‌دار استفاده می‌شود (`text("...:sym")` + `{"sym": symbol}`)؛ هیچ رشته‌سازی ناامن در نمونه‌های بررسی‌شده یافت نشد

**طبقه‌بندی:** CONFIRMED — بدون نقص در پیکربندی engine/session.

### 6.2 الگوی N+1 در `analytics_service.py` — CONFIRMED DEFECT

`services/analytics_service.py:35-41`:
```python
for ind in indicators:
    await self.indicator_repo.save(ind)
```

هر عنصر `indicators` یک رفت‌وبرگشت جدا به دیتابیس می‌زند به‌جای یک عملیات bulk. برای حجم بالای داده بازار (هزاران اندیکاتور در هر چرخه پردازش)، این یک bottleneck واقعی throughput است.

**طبقه‌بندی:** CONFIRMED DEFECT — کد مستقیماً خوانده و تأیید شد (نه فقط گزارش عامل فرعی).

### 6.3 سایر الگوهای N+1 احتمالی گزارش‌شده — UNVERIFIED HYPOTHESIS

یک زیرعامل تحقیق موارد زیر را نیز گزارش کرد، اما این سند فقط مورد ۶.۲ را با خوانش مستقیم تأیید کرد؛ موارد زیر نیاز به بررسی مجدد مستقل دارند پیش از این‌که CONFIRMED طبقه‌بندی شوند:
- لودینگ lazy پیش‌فرض (`lazy="select"`) روی relationship هایی در `models/` که ممکن است در حلقه قابل‌دسترسی باشند (ریسک `MissingGreenlet` در context آسنکرون)
- الگوهای مشابه N+1 در `populate_profiles_service.py` در صورتی که در یک حلقه بیرونی per-symbol صدا زده شود

**طبقه‌بندی:** RISK — NEEDS TEST — این موارد با پروفایل واقعی query log (مثل فعال‌سازی `database_echo` در یک محیط staging) یا تست یکپارچگی که تعداد query ها را می‌شمارد باید قطعی شوند.

### 6.4 ادعای نشت تراکنش در bulk importer — UNVERIFIED HYPOTHESIS

گزارش عامل فرعی به `bulk_importer/persistence.py` اشاره کرد (استفاده از `sessionmaker` سینک بدون commit صریح پس از `flush()`). این فایل در این ممیزی مستقیماً با کد فعلی ریپوی اصلی بازبینی **نشد** (گزارش از همان زیرعاملی آمده که مسیر `database.py` را از worktree قدیمی خوانده بود، پس اعتبار منبع آن پایین‌تر از بقیه یافته‌هاست).

**طبقه‌بندی:** UNVERIFIED HYPOTHESIS — پیش از اقدام اصلاحی، باید `bulk_importer/persistence.py` در ریپوی اصلی (نه worktree) مستقیماً خوانده شود.

---

## 7. جمع‌بندی بر اساس طبقه‌بندی

| طبقه‌بندی | تعداد | موارد |
|---|---|---|
| **CONFIRMED DEFECT** | ۵ | N+1 در analytics_service (۶.۲)، تکرار امتیاز صندوق (۵.۳)، fetch مستقیم بدون TanStack Query (۵.۴)، وابستگی چرخه‌ای watchlist↔symbol_catalog بدون گارد CI (۴.۲)، DI container بلااستفاده (۴.۳) |
| **DOCUMENTATION DRIFT** | ۲ | آمار کلی README (۱)، نام‌گذاری «Redis Streams» به‌جای Lists (۲.۲) |
| **RISK — NEEDS TEST** | ۲ | لودینگ lazy در relationships + N+1 احتمالی در populate_profiles_service (۶.۳)، نبود اجرای واقعی import-linter contract (۴.۲) |
| **UNVERIFIED HYPOTHESIS** | ۱ | نشت تراکنش در bulk_importer/persistence.py (۶.۴) |
| **CONFIRMED (بدون نقص)** | ۵ | TimescaleDB (۲.۱)، قفل توزیع‌شده Redis (۲.۳)، مسیر ingestion (۳)، لایه‌بندی API/services/domain (۴.۱)، پیکربندی engine/session (۶.۱) |

---

## 8. اولویت‌های پیشنهادی اقدام (ترتیب تأثیر × قطعیت)

1. **رفع N+1 در `analytics_service.py:35-41`** (CONFIRMED DEFECT) — جایگزینی حلقه save با `bulk_insert_mappings`/batch upsert.
2. **رفع واگرایی امتیاز صندوق (۵.۳، CONFIRMED DEFECT)** — حذف `scoringEngine` از فرانت‌اند؛ UI فقط امتیاز را از API بخواند. ریسک مالی مستقیم.
3. **پیکربندی `import-linter`** با contract صریح (۴.۲) — تا وابستگی چرخه‌ای شناخته‌شده دوباره رخ ندهد و چرخه‌های جدید پیش از merge کشف شوند.
4. **تأیید یا رد RISK — NEEDS TEST در بخش ۶.۳** — فعال‌سازی `database_echo` در staging یا نوشتن تست شمارش-query برای relationship های پرمصرف، پیش از هر رفراکتور.
5. **بازبینی مستقل `bulk_importer/persistence.py` در ریپوی اصلی** (۶.۴، UNVERIFIED) — تا این یافته از حالت فرضیه به CONFIRMED یا رد قطعی برسد.
6. **خودکارسازی آمار README** (۱، DOCUMENTATION DRIFT) — اسکریپت CI برای استخراج و تزریق شمارش فایل/route/migration، مشابه الگوی موجود `scripts/check_mermaid_blocks.py`.
7. **استانداردسازی TanStack Query** (۵.۴) — `queryKeys.ts` مرکزی + پیکربندی سراسری retry/error؛ حذف ۸ مورد `fetch()` مستقیم باقی‌مانده.

---

## 9. تأیید مستقل (Verification) — خوانش دوم روی HEAD = `43278bbd`

> **قاعده:** فقط تأیید یا رد ادعاها؛ **هیچ کد یا سند موجودی تغییر نکرد** و هیچ اصلاحی انجام نشد.
> **دامنه:** ۱۹ ادعای نقطه‌ای (همراه شمارهٔ خط) + شمارش‌های آماری، همه از ریپوی اصلی.

### ۹٫۱ خلاصهٔ داوری

| بند | ادعا | داوری |
|---|---|---|
| ۱ | آمار README قدیمی است | ✅ **تأیید** — هم اعداد README و هم آمار واقعی درست گزارش شده‌اند |
| ۲٫۱ | TimescaleDB فعال است (۴ migration / ۱۲ hypertable) | ✅ **تأیید دقیق** |
| ۲٫۲ | صف = Redis Lists + BRPOPLPUSH، نه Streams | ✅ **تأیید دقیق** |
| ۲٫۳ | قفل توزیع‌شدهٔ Redis درست است | ✅ **تأیید دقیق** |
| ۳ | مسیر ingestion | ⚠️ تأیید نشد (فقط خوانش کد، بدون اجرا) |
| ۴٫۱ | «هیچ import مستقیمی از `apps/api` به `backtesting`/`ml` نیست» | ❌ **رد شد** — ۲ import مستقیم پیدا شد |
| ۴٫۲ | چرخهٔ watchlist↔symbol_catalog باز است | ⚠️ **نیمه** — راه‌حل import تأخیری هست، یال معکوس پیدا نشد |
| ۴٫۳ | DI container بلااستفاده | ✅ **تأیید دقیق** (۰ مصرف‌کننده) |
| ۴٫۴ | سه God object با ۲۱۳۷/۲۰۴۹/۲۰۱۰ خط | ✅ **تأیید دقیق** (سه عدد مو‌به‌مو) |
| ۵٫۱ و ۵٫۲ | پروکسی/API client و ۳ مسیر سازگار | ⚠️ تأیید نشد |
| ۵٫۳ | تکرار منطق امتیاز صندوق | ✅ **تأیید دقیق** |
| ۵٫۴ | ~۸ مورد `fetch()` مستقیم | ⚠️ **کم‌گزارش‌شده** — واقعی **۱۴** مورد در `app/` |
| ۶٫۱ | پیکربندی engine/session قوی است | ✅ **تأیید دقیق** (همهٔ شماره‌خط‌ها درست) |
| ۶٫۲ | N+1 در `analytics_service.py` | ✅ **تأیید دقیق** |
| ۶٫۳ | ریسک lazy-loading / populate_profiles | ⚠️ **نیمه** — الگوی N+1 تأیید؛ عبارت `lazy="select"` غلط |
| ۶٫۴ | نشت تراکنش در `bulk_importer/persistence.py` | ❌ **رد شد** (تصمیم‌شده و درست است) |

### ۹٫۲ روش شمارش سند بازتولید و تأیید شد

اعداد سند با **حذف `__init__.py`** به‌دست می‌آیند؛ با همین روش همه **مو‌به‌مو** تطابق دارند:

| مورد | سند | بازتولید (بدون `__init__.py`) | خام (با `__init__.py`) |
|---|---|---|---|
| فایل endpoint | ۸۲ | **۸۲** ✅ | ۸۳ |
| سرویس top-level | ۱۶۱ | **۱۶۱** ✅ | ۱۶۲ |
| سرویس با زیرپوشه | ۲۳۹ | **۲۳۹** ✅ | ۲۴۷ |
| ماژول بک‌تست | ۲۵۵ | **۲۵۵** ✅ | ۲۹۸ |
| ماژول ML | ۱۰۸ | **۱۰۸** ✅ | ۱۱۸ |
| مهاجرت | ۷۸ | **۷۸** ✅ | ۷۸ |
| head | `0109` | **`0109`** ✅ | — |
| صفحهٔ فرانت | ۱۴۸ | **۱۴۸** ✅ | ۱۴۸ |
| فایل تست | ۴۱۸ | ۴۱۷ ⚠️ (اختلاف ۱) | ۶۰۵ (الگوی `*test*`) |

نکتهٔ تقویمی: `README.md` آخرین بار در `54849c92` و تاریخ **2026-09-16** تغییر کرده — یعنی **۲۵ شهریور ۱۴۰۵**، نه «۱۶ شهریور» که در سند نوشته شده.

### ۹٫۳ تأییدهای دقیق (شماره‌خط‌ها مو‌به‌مو)

```text
TimescaleDB
  فایل migrations شامل create_hypertable() = 4
  ۱۲ جدول دقیقاً همان فهرست سند: candlesticks, commodity_prices, daily_history,
    daily_real_legal, etf_nav, gold_currency_prices, intraday_trades, market_ticks,
    orderbook_snapshots, screener_snapshots, shareholders, symbol_snapshots
  docker-compose.yml:5  image: timescale/timescaledb:latest-pg15

صف (بند ۲٫۲)
  queue_consumer.py:71    self._dead_queue = settings.job_queue_dead_letter   ← خط ادعا شده
  queue_consumer.py:310   await client.lpush(self._dead_queue, ...)           ← داخل ۲۸۴–۳۲۴
  queue_consumer.py:181   if hasattr(client, "brpoplpush")
  queue_consumer.py:182   value = await client.brpoplpush(...)                ← Lists، نه Streams
  queue_publisher.py:116  await client.lpush(self._queue_name, serialized)
  queue_consumer.py:86-88    failed / dead_lettered / rejected_auth = 0        ← ادعای خط ۸۷
  queue_consumer.py:337-339  "failed" / "dead_lettered" / "rejected_auth"     ← ادعای خط ۳۳۸

قفل (بند ۲٫۳)
  jobs/locking.py = 246 خط                                    ← مو‌به‌مو
  locking.py:13-18  _LUA_RELEASE = if get(KEYS[1])==ARGV[1] then del(KEYS[1])
  locking.py:21     "Atomic compare-and-extend: only the lock owner may renew the TTL."
  locking.py:34     "SET key owner NX PX <ttl_ms>"
  locking.py:43-45  default_ttl = 300.0 + "In-memory fallback (used only when Redis is unavailable)"
  locking.py:59-64  client.set(key, owner, nx=True, px=int(ttl*1000))

core/database.py (بند ۶٫۱) — همهٔ شماره‌خط‌ها درست
  :29        @sa_event.listens_for(_SyncSession, "do_orm_execute")   ← شروع بلوک ۲۹–۷۴
  :72        "...silently lose the write (bug seen in user registration)."
  :92-97     pool_pre_ping True + pool_recycle 3600 + pool_size/max_overflow
  :170-171   engine.update_execution_options(isolation_level="READ COMMITTED")
  :23,47,61  _READONLY_WRITE_MSG (تعریف در ۲۳، raise در ۴۷ و ۶۱)
  "replica" → ۲۸ ارجاع در فایل

God objects (بند ۴٫۴)   2137 / 2049 / 2010 خط  ← هر سه مو‌به‌مو
DI container (بند ۴٫۳)   فایل‌های importکنندهٔ dependency_injection در
                         services/apps/jobs/core = ۰ ؛ container.py = 57 خط

N+1 (بند ۶٫۲) — analytics_service.py فقط ۴۱ خط است و حلقه همین‌جاست:
    async def batch_save(self, indicators):
        for ind in indicators:
            r = await self.indicator_repo.save(ind)   ← یک رفت‌وبرگشت DB per ردیف

تکرار امتیاز صندوق (بند ۵٫۳)
  frontend/src/lib/fund-analysis.ts:168  export function scoringEngine(fund: Fund): FundScore
    دقیقاً ۶ بُعد: financial, liquidity, management, risk, cost, transparency
    وزن‌ها ثابت از CATEGORY_WEIGHTS با کلیدهای فارسی
  services/fund_scoring.py (747 خط): :33 WEIGHTS per-type، :35 "leveraged"،
    :76 "equity"، :142 NEVER_STRONG_BUY، :151 fund_type param
  ⇒ واگرایی فرانت/بک تأیید شد (نوع‌آگاه فقط در بک‌اند)

  queryKeys*.ts در frontend/src → وجود ندارد ✅
```

### ۹٫۴ تصحیح‌ها (سه مورد لازم است)

**الف) بند ۴٫۱ رد شد — import مستقیم وجود دارد.**

```text
apps/api/app.py:31                  from ml.models import register_all_models
apps/api/endpoints/backtests.py:20  from backtesting.strategies.registry import (
                                        get_strategy_registry, register_all_strategies)
```

جملهٔ سند مطلق است («هیچ import مستقیمی … پیدا نشد») و با این دو مورد نقض می‌شود.
خوانش خوش‌بینانه: این دو «entry point عمومی» ماژول‌ها هستند نه «داخلی»؛ پیشنهاد تصحیح
متن: «import به ماژول‌های **داخلی** وجود ندارد؛ فقط entry pointهای عمومی».

**ب) بند ۵٫۴ کم‌گزارش‌شده است.**

سند «~۸ مورد» و ۴ فایل نام می‌برد؛ شمارش در `frontend/src/app/` **۱۴** مورد است:

```text
frontend/src/app/admin/page.tsx:449
frontend/src/app/backtest/compose/page.tsx:44, 53, 58, 71, 83   (۵ مورد)
frontend/src/app/data/page.tsx:246
frontend/src/app/data-import/page.tsx:133, 145
frontend/src/app/decision-engine/page.tsx:129   ← فایلی که سند ذکر نکرده
```

**ج) بند ۶٫۳‑الف — عبارت `lazy="select"` نادرست است.**

شمارش `lazy="select"` در `models/`, `services/`, `domain/` = **۰**، چون `select`
**استراتژی پیش‌فرض** SQLAlchemy است و کسی آن را صریح نمی‌نویسد. پس خودِ ریسک
(بارگذاری تنبل پیش‌فرض در context آسنکرون ⇒ احتمال `MissingGreenlet`) **به‌قوت خود
باقی است**، اما باید به این شکل بیان شود (تفاوت پیش‌فرض با `selectin`/`raise`)،
نه «`lazy="select"` یافت شد».

**د) بند ۶٫۳‑ب نیمه‌تأیید — الگوی N+1 واقعاً وجود دارد.**

```text
services/populate_profiles_service.py:48    for sym_data in symbols:
services/populate_profiles_service.py:54        result = await self._populate_one_with_savepoint(symbol, sym_data)
services/populate_profiles_service.py:221/248   (await self._session.execute(q, {"sym": symbol})).fetchall()
```

حلقهٔ بیرونی per-symbol + کوئری per-symbol ⇒ این ریسک از «فرضیه» به **الگوی
تأییدشده با شواهد** ارتقا می‌یابد (برای «بطری‌گلو بودن» هنوز پروفایل شمارش-کوئری لازم است).

### ۹٫۵ فرضیه‌ای که **رد شد**: نشت تراکنش (بند ۶٫۴)

`bulk_importer/persistence.py` (۱۹۶ خط) مستقیماً خوانده شد:

```text
:12   from sqlalchemy.orm import Session, sessionmaker
:32   self.SessionLocal = sessionmaker(bind=self.engine)
:51   with self.engine.connect() as conn:
:57       conn.commit()          ← commit صریح مسیر DDL موجود است
:97       session.flush()

امضای متد:
  def get_or_create_document_file(self, session: Session, ...)
                                      ↑ session ورودی است؛ مالکیت چرخهٔ عمر با فراخوان
```

سه دلیل که این «نشت» نیست:

1. **session پارامتر ورودی است**؛ نبود `commit` در متد به‌معنای نشت نیست.
2. `flush()` **عمدی** است — بعد از `pg_insert(...).on_conflict_do_nothing(...)`
   لازم است ردیف خوانده شود؛ خود کد در کامنت توضیح می‌دهد که دو کارگر importer
   می‌توانند هم‌زمان از SELECT سریع رد شوند و تصمیم یکتایی باید در مرز DB باشد:
   > `# The initial SELECT is only a fast path. Two importer workers can still pass it concurrently, so the INSERT itself must own the uniqueness decision at the database boundary.`
3. مسیر DDL مربوطه `conn.commit()` صریح دارد (خط ۵۷).

⇒ **نه یک نقص به‌شکلی که سند توصیف کرده.** باقی‌ماندهٔ قابل‌بررسی: اینکه
*فراخوان‌ها* session را commit/close می‌کنند — که بررسی نشد.

### ۹٫۶ چیزهایی که در این تأیید **قطعی نشدند**

| مورد | چرا |
|---|---|
| بند ۵٫۲ (۳ مسیر API سازگارند) | نیاز به اجرای هم‌زمان فرانت+بک؛ در این محیط (دیسک پر) اجرا نشد. خود سند هم محدودیت را ذکر کرده. |
| بند ۳ (مسیر ingestion) | فقط خوانش کد؛ هیچ اجرای واقعی sync انجام نشد. |
| بند ۴٫۲ اجرای واقعی `import-linter` | تأیید شد که در `pyproject.toml` پیکربندی **نشده** (۰ تطابق)، اما خود contract اجرا نشد. |
| بند ۶٫۳ بطری‌گلو بودن واقعی | نیازمند پروفایل شمارش-کوئری. |
| فراخوان‌های `bulk_importer/persistence.py` | commit/close سمت فراخوان بررسی نشد. |

### ۹٫۷ جمع‌بندی تأیید

* **۱۸ از ۱۹ ادعای نقطه‌ای (شماره‌خط‌دار) دقیق بودند** — دقت سند بالا و شماره‌خط‌ها
  قابل اتکا هستند (به‌ویژه `core/database.py`، `locking.py:246`، سه God object،
  متریک‌های queue، و حلقهٔ N+1).
* سه **تصحیح** لازم است: ۴٫۱، ۵٫۴، و عبارت ۶٫۳‑الف.
* یک **فرضیه رد شد**: ۶٫۴.
* یک ادعا **نیمه** است: ۴٫۲ (راه‌حل import تأخیری هست، چرخهٔ فعال پیدا نشد).
* روش شمارش سند (حذف `__init__.py`) **معتبر و بازتولیدپذیر** است و باید در گزارش
  آینده صریح ذکر شود.

### ۹٫۸ تأثیر بر اولویت‌های بخش ۸

اولویت‌ها **بدون تغییر معتبرند**، با دو تدقیق:

* اولویت ۵ («بازبینی مستقل `bulk_importer/persistence.py`») **انجام شد** و نتیجه
  منفی است (نقص تأیید نشد) ⇒ از فهرست اقدام حذف/کاهش می‌یابد.
* اولویت ۴ (بند ۶٫۳) باید **دو** پیگیری داشته باشد: (الف) استراتژی بارگذاری
  relationshipها (پیش‌فرض در برابر `selectin`/`raise`)، (ب) پروفایل
  `populate_profiles_service`.
