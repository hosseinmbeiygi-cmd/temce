# تحقیق و تحلیل عمیق ۱۶۰ لایه — سامانه TEMCE / Iran Market Platform

| | |
|---|---|
| **تاریخ تحلیل** | ۲۰۲۶-۱۱-۱۳ (۱۳:۲۰ به وقت تهران) |
| **کامیت مبنا** | `091fdf31333b1a3283c3695b0882ef6687f872f6` — `fix(quant): F10 use jalali_to_gregorian...` |
| **شاخه** | `main` · ۳۹۸ کامیت · ۴۱ کامیت فقط در امروز |
| **وضعیت worktree** | ۶ فایل اصلاحنشده و کامیتنشده (`git status`) — **دستکاری نشدهاند** |
| **روش** | خواندن مستقیم فایلها، پارس AST، شمارش با اسکریپت فقطخواندنی، تطبیق با `git log`، راستیآزمایی ادعاهای ۵ سند حسابرسی موجود |
| **محدوده** | کل مخزن: کد، پیکربندی، استقرار، تست، داده، مستندات، فرانتاند، CI |
| **تعهد** | **هیچ فایل کدی تغییر نکرده است.** تنها خروجی، همین فایل گزارش است. اجرای تست کامل، اتصال به DB زنده و بوت سرور انجام نشد (تحلیل ایستا + شواهد اسناد عددی موجود). |

> ⚠️ **یافته محوری:** مخزن در حالت **چرخه اصلاح فعال** است. سه یافته بحرانیِ `AUDIT_REPORT_2026-11-12.md` (افق ارزیابی سیگنال، تجمیع دقت، proxy نقدینگی) و بخش بزرگی از یافتههای `OPTIONS_DEEP_ANALYSIS_2026-11-13.md` **همین امروز در کد رفع شدهاند**. بنابراین تقریباً تمام اسناد حسابرسی موجود، از جمله `README.md`، هماکنون **تاریخمصرفگذشته**اند. این گزارش وضعیت «کد زنده» را مبنا قرار داده، نه ادعاهای اسناد.

---

## ۰. خلاصه اجرایی

سامانه TEMCE یک **پلتفرم دادهمحور بازار سرمایه ایران** است: گردآوری داده از TSETMC/کدال/BrsApi/منابع جهانی، ذخیره در PostgreSQL+TimescaleDB، لایه سرویس تحلیلی (سیگنال، پول هوشمند، غربالگری، آپشن، طلا)، موتور بکتست، لایه ML، و فرانتاند Next.js. هسته اجرا یک **FastAPI monolit** (`apps.api.app:app`) با ۴ ریزسرویس FastAPI مستقل و ۳ worker است.

از نظر **مهندسی نرمافزار** پروژه کمپلکس ولی منضبط است: لایهبندی DDD واقعاً اعمال شده، ۴ قرارداد import-linter برقرار است، ۹۴ مهاجرت Alembic زنجیرهای خطی و تکhead دارند، CI شامل ratchet typing و گارد پاریتی بکتست است، و ۳٬۱۱۶ فایل پایتون از ۳٬۱۱۸ فایل بررسیشده بدون خطای نحویاند.

از نظر **صحت داده و اندازهگیری عملکرد**، شواهد عددی `NUMERIC_AUDIT_2026-11-12.md` تصویر تندتری میدهد: دیتابیس ۵۰٫۱۷ GiB با ۲۳۲ جدول که ۵۰٫۹٪ آنها خالیاند؛ ۴۶٬۹۰۶ پیشبینی ML همگی `prediction_failed=true`؛ ۷٬۸۰۵ ران بکتست `completed` بدون حتی یک ردیف معامله؛ ۳٬۷۰۵ رکورد دقت سیگنال ۱۰۰٪ یتیم. تیم توسعه دقیقاً مشغول بستن همین شکافهاست (کامیتهای امروز: `persist individual fills to backtest_trades`، `F10 use jalali_to_gregorian`، `register screener job`، `wire OptionsNormalizeJob`).

### جدول اندازهگیریهای سخت (همه از کد/دیسک، نه از مستندات)

| معیار | مقدار واقعی | ادعای `README.md` | اختلاف |
|---|---|---|---|
| فایل پایتون (بدون کش) | **۳٬۵۰۶** / ۵۱۴٬۸۶۴ خط | — | — |
| فایل endpoint | **۸۴** | ۶۰ | +۴۰٪ |
| تعداد route (`@router.*`) | **۶۶۸** + ۲ WebSocket | ~۴۳۸ | +۵۳٪ |
| `include_router` در `router.py` | **۸۰** | — | — |
| مهاجرت Alembic | **۹۴**، head منفرد `0123` | ۳۹ / head `0039` | ۲٫۴× |
| مدلهای ORM (`__tablename__`) | **۱۴۹** در ۵۲ فایل | ~۱۲۲ / ۱۳۷ | — |
| صفحه فرانتاند `page.tsx` | **۱۵۳** | ۸۸ | +۷۴٪ |
| فایل تست | **۶۶۴** / ۷٬۴۳۷ تابع تست | ۲۵۰ | ۲٫۷× |
| فایل سرویس | **۲۷۷** / ۸۹٬۳۱۵ خط | ۱۰۳ | ۲٫۷× |
| ماژول بکتست | **۳۰۲** / ۲۹٬۵۵۷ خط | ۲۷۵ | — |
| job زمانبندیشده | **۲۹** (کامیت مبنا؛ HEAD=32) | ۱۹ | +۵۳٪ |
| فایل تحت کنترل git | **۷٬۰۱۵** | — | — |
| کل فایلهای روی دیسک | **۱۸۷٬۳۵۵** | — | شامل کش/venv/node_modules |

### ۱۰ یافته برتر

1. **اسناد از کد عقباند** — `README.md`، `ARCHITECTURE.md`، `migrations/README.md` و هر ۵ سند حسابرسی ریشه، اعداد و معماری متفاوتی از کد زندهگزارش میکنند. `ARCHITECTURE.md` اساساً مربوط به زیرپروژه کوچک `BrsApi_Forecasting/` است، نه پلتفرم اصلی.
2. **چرخه اصلاح فعال** — ۴۱ کامیت امروز، عمدتاً `fix(options/signals/backtest/scheduler)`؛ نتیجه: ریسک واقعی «کد خراب» نیست، ریسک «اعتماد بهگزارش کهنه» است.
3. **P0#3 رفع شد** — `quant_signal_orchestrator.py:1843` تابع `_evaluate_past_signals` با پنجره ۹۰روزه و `CASE sa.timeframe` (خط ۱۸۷۸) برای افق ۲/۳/۵/۸/۲۳/۶۵ روز دارد.
4. **P0#4 رفع شد** — همان فایل `:2062-2094` دقت را بهصورت `correct/total` تجمیع و با `_MIN_SNAPSHOT_SAMPLES = 20` گیت میکند.
5. **P1b رفع شد** — `:1235-1253` نقدینگی را از حجم واقعی میگیرد و در نبود داده حالت `degraded` صریح (۰٫۳/۰٫۴) برمیگرداند.
6. **ثابتها متمرکز شدند (ناقص)** — `core/trading_constants.py` چهار ثابت ۲۴۰/۲۵۰/۲۵۲/۳۶۵ را تعریف کرده و `services/` از آن استفاده میکند؛ ولی **۵۰ هاردکد ۲۵۲** (در ۲۸ فایل) در `backtesting/`، `src/forecasting/` و `services/options_ml_service.py` باقی است.
7. **۱۱ بسته از ۳۲ بسته `domain/` هیچ مصرفکنندهای بیرون از دامنه ندارند** (bonds, energy, fx, metals, commodities, indices, watchlists, trades, audit, indicators, pricing_version) — داربست معماری بدون اتصال به جریان اجرا.
8. **دیتابیس زنده نیمی خالی است** — ۱۱۸ جدول از ۲۳۲ جدول، و ۶ جدول پایش (`data_freshness`, `data_gaps`, `decision_results`, ...) صفر ردیف.
9. **تکینگیهای اجرایی شکسته**: `make worker` → `python -m jobs.worker` (فایل وجود ندارد)، `apps/strategy_worker/__init__.py` ماژول ناموجود import میکند، `apps/api/main.py` خالی است، دو Dockerfile روی پورت ۸۰۰۲ هستند.
10. **بدهی فنی ساختاری**: دو درخت مهاجرت، دو سیستم تنظیمات، دو سیستم feature flag، چهار استک لایهای موازی، یک worktree clone کامل ۲۳۳ MB، و ۵٫۲ GB فایل `transactions.db` در ریشه.

---

# فصل A — لایه ۱ تا ۱۲: فیزیک مخزن و آمار

### لایه ۱ — ابعاد کلی
روی دیسک ۱۸۷٬۳۵۵ فایل وجود دارد؛ ۷٬۰۱۵ فایل تحت کنترل git. اختلاف عظیم ناشی از `venv/` (۵۴٬۸۱۹ فایل، ۲٫۲ GB)، `frontend/.next/` و `node_modules/` (۵٬۳۰۶ فایل)، `.workbuddy-ai/` (پروفایلهای Chrome) و `__pycache__`. **نتیجه:** اندازه مخزن git کوچک، ولی checkout محیط توسعه چند گیگابایتی است.

### لایه ۲ — زبان غالب
پایتون مطلقاً غالب است: ۳٬۵۰۶ فایل `.py` و ۵۱۴٬۸۶۴ خط کد (بدون کشها). پس از آن JSON (۲٬۵۴۰)، Markdown (۹۸۵)، PNG (۴۴۰)، TSX (۴۲۸)، TS (۳۱۰)، Go (۵۲)، YAML (۲۸). **نتیجه:** تکزبانهای پایتونمحور با فرانتاند TypeScript و یک ابزار جانبی Go (`mimicode-go/`).

### لایه ۳ — توزیع حجم کد
`tests/` با ۱۲۹٬۳۳۴ خط (**۲۵٪ کل کد**) بزرگترین بخش است؛ سپس `services/` ۸۹٬۳۱۵، `scripts/` ۴۹٬۲۵۰، `apps/` ۳۹٬۶۸۶، `backtesting/` ۲۹٬۵۵۷، `src/` ۱۸٬۷۶۶، `brsapi/` ۱۶٬۶۹۹، `core/` ۱۵٬۴۴۸، `domain/` ۱۵٬۱۸۹. **نتیجه:** نسبت کد تست به کد تولید تقریباً ۱ به ۳ — پوشش اسمی بالا، ولی لزوماً پوشش مؤثر نیست (لایه ۱۴۰).

### لایه ۴ — تراکم منطقی
شمارش AST: `services/` ۵۶۲ کلاس / ۲٬۸۶۳ تابع، `backtesting/` ۴۶۷ / ۱٬۷۸۹، `core/` ۲۷۷ / ۱٬۰۰۰، `domain/` ۲۶۵ / ۶۹۰، `schemas/` ۲۹۶ کلاس (عمدتاً Pydantic DTO)، `tests/` ۱٬۳۰۵ کلاس / ۱۰٬۰۶۵ تابع. ۷٬۷۳۶ تابع `async` در سراسر کد. **نتیجه:** معماری async-native و شیءگرا، با حجم بالای DTO.

### لایه ۵ — نقشه دایرکتوریهای اصلی
۱۴ دایرکتوری سطحبالا بیش از ۱۰۰ فایل پایتون دارند: `tests`, `scripts`, `services`, `providers`, `domain`, `apps`, `core`, `ml`, `schemas`, `backtesting` و…؛ در کنار ۹ «انبار داده/گزارش» (`data/`, `json/`, `transactions_data/`, `history_data/`, `reports/`, `logs/`, `AUDIT_REPORTS/`, `docs/`, `new_symbol_reports/`). **نتیجه:** کد و داده/گزارش در یک ریشه مخلوطاند.

### لایه ۶ — حجم دیسک
`transactions.db` = **۵٬۲۹۹ MB**؛ `venv/` ۲٬۲۶۷ MB؛ `frontend/` ۲٬۰۳۶ MB؛ `data/` ۳۶۱ MB؛ `.freebuff/` ۲۳۳ MB؛ `logs/` ۱۲۴ MB؛ `docs/` ۱۷ MB. بزرگترین فایل منفرد غیرباینری `data/top50_funds_intraday.json` = ۳۲۵ MB و `logs/startup_backend.log` = ۶۶ MB. **نتیجه:** هزینه clone/backup/جستجو بهشدت متأثر از دادههای محلی است.

### لایه ۷ — آرتیفکتهای محیط توسعه
`venv/`, `codal_env/`, `Redis/` (شامل `.exe` و `.dll`), `node_modules/`, `catboost_info/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.import_linter_cache/`, `dump.rdb` در ریشه حضور دارند. `.gitignore` بیشتر آنها را پوشش میدهد ولی `Redis/` و `codal_env/` را نه. **نتیجه:** آلودگی مخزن به باینری و محیط اجرا.

### لایه ۸ — worktree تکراری
`.freebuff/worktrees/72c673be-.../` یک کپی تقریباً کامل مخزن (۴٬۷۱۴ فایل `.py`, ۲۳۳ MB) بهعلاوه `_FRONTEND_BACKEND_COPY/backend/` است. **نتیجه:** هر جستجوی سراسری ساده (مثلاً شمارش تستها) بدون prune، اعداد را ۲–۶ برابر میکند؛ احتمالاً منشأ عدد «۴٬۴۴۰ فایل تست» در `AUDIT_REPORT_2026-11-12.md` همینجاست (عدد واقعی ۶۶۴).

### لایه ۹ — فایلهای بکاپ و وصله
`z.py` + `z.py.bak`, `.env.bak.1790980646`, `backend_attempt.patch` (۱۸ KB), `screener_audit_fixes.patch` (۵۹ KB), `proposed_patches/` (۹ فایل), `migrations_backup_20261030/` (۹۲ فایل), `services/*.bak`, `services/smart_money/services - Shortcut.lnk`. **نتیجه:** تاریخچه تغییرات بهجای git، بهصورت فایل در درخت نگهداری میشود.

### لایه ۱۰ — فایلهای تهی و نام aberrant
`apps/api/main.py` (۰ بایت), `temp_content.py` (۰), `security_report.html` (۰), `pytest_result.txt` (۰), `warnings.txt` (۰), `probe_out.txt` (۰), `%PYFILE%` (۰), `=2.0` (۴۷ بایت — بقایای یک `pip install x>=2.0` ناقص), `t.txt` (۱ بایت), `gen_all.py` (۱۵ بایت). **نتیجه:** حداقل ۹ فایل مرده در ریشه/اپ.

### لایه ۱۱ — اسکریپتهای تکمنظوره ریشه
بیش از ۳۸ فایل `.py` در ریشه با نامهای `fix_*.py`, `check_volumes*.py`, `analyze_*.py`, `run_*.py`, `split_to_10.py`, `z.py`. `scripts/` نیز ۲۹۳ فایل دارد. **نتیجه:** عملیات دستی/ممیزی بهجای تبدیل به ابزار پایدار، بهصورت اسکریپت انباشته شدهاند.

### لایه ۱۲ — الگوی نامگذاری و نسخهها
`screener_v2.py`, `funds_v2.py`, `stocks_v2.py`, `smart_screener_v2.py`, `domain/decision_engine_v5/`, `risk_engine_v1.py`, `_7d_gate/`, `_8_gate/`. **نتیجه:** نسخهبندی در نام فایل بهجای حذف نسخه قدیم؛ مصرفکننده باید بداند کدام نسخه زنده است.

---

# فصل B — لایه ۱۳ تا ۲۴: پیکربندی، وابستگیها، ابزار توسعه

### لایه ۱۳ — شناسنامه بسته
`pyproject.toml`: `name = "iran-market-platform"`, `version = 0.1.0`, `requires-python >= 3.11`, setuptools. **هیچ `[project.scripts]` و `entry_points.txt` وجود ندارد**؛ تمام نقاط ورود از طریق `uvicorn ...` یا `python -m ...`اند. **نتیجه:** نصب بسته، فرمان اجرایی نصب نمیکند.

### لایه ۱۴ — وابستگیهای اصلی
FastAPI، Uvicorn، Pydantic v2، SQLAlchemy 2.0 async، Alembic، httpx، pandas/numpy، redis، APScheduler، PyJWT، OpenTelemetry، Prometheus، aiohttp، minio، structlog، asyncpg، aiosqlite. ML بهصورت extras اختیاری (`sklearn/xgboost/lightgbm/catboost/torch/shap`). **نتیجه:** پشته استاندارد و کمحاشیه.

### لایه ۱۵ — drift وابستگیها
`requirements.txt` شامل `celery[redis]`, `sentry-sdk[fastapi]`, `jdatetime`, `finpy-tse`, `tsetmc`, `tehran-stocks`, `tse-utils`, `feedparser`, `defusedxml`, `openpyxl` است که در `pyproject.toml` نیستند؛ برعکس `pytz` و `python-dotenv` در هر دو متفاوتاند. `requirements-overrides.txt` تداخل `SQLAlchemy/tehran-stocks` را override کرده. **نتیجه:** دو مسیر نصب با نتایج متفاوت؛ CI از `requirements.lock` (پینشده) استفاده میکند.

### لایه ۱۶ — کیفیت ابزارها
`ruff`: `select = E,F,I,N,W,UP,B,SIM,ARG,C4`، `line-length=120`، `exclude = code_dump`. `mypy`: `explicit_package_bases=true` چون `apps/` فاقد `__init__.py` است؛ ۱۰ ماژول `services.*` و `core.calibration_bootstrap` تحت strict hand-expanded flags؛ `backtesting/ ml/ migrations/ scripts/ integrations/ models/` کاملاً `ignore_errors = true`. `bandit`: `skips = B608, B613, B104` با توجیه مکتوب. **نتیجه:** کیفیت «راتچت» است، نه مطلق.

### لایه ۱۷ — تنظیمات یکپارچه *(اصلاحشده در قسمت ۰۳)*
`core/config/__init__.py` (**۵۵۳ خط**) یک `Settings(BaseSettings)` با **۱۱۸ فیلد**، ۶۰ `Field()`، ۸ validator، ۷ property و `get_settings()` با `lru_cache`. اسکن دوباره: **۲۱۷ ارجاع `from core.config import settings` در ۱۸۷ فایل** (عدد ۱۲۸ کهنه بود). `validate_production()` **هفت** شرط دارد (کلید پیشفرض، `AUTH_DISABLED`, `CORS=*`, SQLite، کوکی ناامن، WS token قدیمی، نبود OTLP) و از **شش** نقطه ورود فراخوان میشود، ولی خط ۴۹۱ با `environment == "development"` بیدرنگ برمیگردد؛ `extra="ignore"` غلطاملایی متغیرها را بیسروصدا میبلعد و `settings` شیء قابلتغییر سراسری است. **نتیجه:** تکمنبع تنظیمات واقعی همین فایل است، ولی گیت production به `ENV` وابسته است که **هیچ فایل استقراری آن را ست نمیکند** (`CFG-01`).

### لایه ۱۸ — تنظیمات شکسته موازی
`core/config/` علاوه بر فایل اصلی **۱۷ فایل** دارد (۱۸ فایل با احتساب `__init__.py`). **تصحیح قسمت ۰۳:** فقط **۱۴** ماژول صفرمصرفکنندهاند؛ `acceptance_loader.py` (۵۳۳ خط، ۳ مصرفکننده production + تستها)، `ime_engine.py` (۵ مصرفکننده) و `storage.py` (۱ مصرفکننده) **زندهاند**. اسکن AST کل مخزن **۱۸ زیرکلاس `BaseSettings`** نشان داد: ۱۵ تا در `core/config/` و `BrsApiSettings`, `IngestionConfig`, `CurrencyServiceSettings` بیرون از آن. **نتیجه:** ۱۴ ماژول مرده با پیشفرضهای ناامن (`cors_origins=["*"]`, `allowed_hosts=["*"]`) همچنان بدهیاند، ولی «همه موازیها مردهاند» نادرست بود.

### لایه ۱۹ — متغیرهای محیطی
`.env.example` حدود ۱۰۵ متغیر دارد؛ `.env` (محلی، ۲٫۸ KB) شامل `DATABASE_URL`, `REDIS_URL`, `BRSAPI_API_KEY`, `GOLDAPI_KEY`, `FRED_API_KEY`, `FINNHUB_API_KEY`, `FMP_API_KEY`, `ALPHA_VANTAGE_API_KEY`, `GOLD_API_TOKEN_SALT`, `SECRET_KEY` است. `.env`, `.env.*` در `.gitignore`اند. **تصحیح قسمت ۰۳:** `.env.production` **۹ کلید** دارد (نه ۱۱) و فاقد `SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS`, `OTLP_ENDPOINT`, `AUTH_COOKIE_SECURE` است؛ `AUTH_COOKIE_SECURE`ای که گیت production الزامی میداند **حتی در `.env.example` هم مستند نشده** (مانند `REGISTRATION_OPEN` و `JOB_QUEUE_TOKEN`). `.env.production` همچنین `ENV=production` ندارد. **نتیجه:** پیکربندی production از دو طرف ناسازگار است — با `ENV` درست بوت شکست میخورد، بدون آن بوت میشود ولی تمام گیتها خاموشاند (`CFG-01`/`CFG-03`/`CFG-04`).

### لایه ۲۰ — دو سیستم feature flag
`core/feature_flags/` (۵ فایل: `manager/flags/defaults/evaluators`) و `core/config/feature_flags.py` (`FeatureFlagSettings` با پیشوند `FF_`). **تصحیح قسمت ۰۳:** در واقع **سه** سیستم است — سومی همان فیلدهای `Settings` زنده (`news_read_mode` چهارحالته، پرچمهای parity/halt، `enable_csrf`, `registration_open`, ...)؛ `core/feature_flags/` فقط self-import و `tests/unit/core/test_feature_flags.py` را دارد و `core/config/feature_flags.py` **صفر واردات**. `FeatureFlag.enabled` مستقیماً `os.environ` میخواند، پس حتی اگر وصل میشد از `env_file` لنگرانداختهشده عبور نمیکرد. **نتیجه:** تنها `Settings` حاکم است؛ دوتای دیگر مردهاند.

### لایه ۲۱ — پیکربندی YAML دامنهای
`config/` شامل `backtest_costs.yaml`, `ime_engine_config.yaml`, `macroeconomics.yaml`, `signal_policy.yaml`, `smart_money.yaml`, `symbols.yaml` + `timeframes.py`. `acceptance.yaml` در ریشه، نسخهدار (`version 1.0`, `last_updated 2026-10-13`) و حاوی `fee_schedule`, `signal_filter`, `market_hours` و آستانههای Production Gate. **نتیجه:** الگوی درست «یک منبع حقیقت» در سند؛ اجرای ناقص در کد (لایه ۱۰۹).

### لایه ۲۲ — آستانههای پذیرش
`acceptance.yaml`: `min_wfe=0.50`, `min_dsr=0.95`, `min_oos_sharpe=1.00`, `max_drawdown=0.20`, `min_profit_factor=1.30`, `min_trade_count=50`, `min_net_profit_pct=2.0`, `min_risk_reward=2.0`. بخشی از اعداد `provenance: assumption` یا `unavailable` دارند. **نتیجه:** صداقت مستندسازی خوب؛ ولی `fee_per_side` آتی و آپشن `null` است، پس محاسبات آن بازارها نمیتواند complete باشد.

### لایه ۲۳ — Makefile
اهداف `install/lint/typecheck/test/dev/api/admin/worker/docker-*/migrate/prod-check/clean`. دو ضعف مشخص: `typecheck: mypy ... || true` (همیشه سبز) و `lint: ruff check . --fix` (لینتر **فایلها را تغییر میدهد**). `worker: python -m jobs.worker` به فایل ناموجود اشاره دارد. **نتیجه:** ابزار محلی قابلاتکا نیست؛ CI جایگزین واقعی گاردهاست.

### لایه ۲۴ — بستهبندی و نگهداری
۹ Dockerfile، ۵ فایل compose، `k8s/` (۴ YAML ویژه decision-engine)، `deploy/helm/gold-desk/` (Chart), `deploy/nginx/nginx.conf`, `prometheus.yml`, `nginx-golddesk.conf`, `Makefile`, ۴ فایل `*.ps1` اجرا. **نتیجه:** چند مسیر استقرار همزمان (Compose / Swarm / K8s / Helm / NSSM در سند قدیمی) بدون یک مرجع واحد.

---

# فصل C — لایه ۲۵ تا ۳۶: نقاط ورود و توپولوژی اجرا

### لایه ۲۵ — نقطه ورود اصلی
`main.py` (۱۹ خط) → `uvicorn.run("apps.api.app:app", host/port/reload/workers/log_level از settings)`. `apps/api/app.py` (۱٬۲۳۹ خط) دارای `create_app()` در خط ۱۰۶۴ و `app = create_app()` در ۱۲۳۸. **نتیجه:** ASGI تکهدف اصلی مشخص است.

### لایه ۲۶ — lifespan
`apps/api/app.py:885-1061` یک `@asynccontextmanager` حجیم: `validate_production`, `init_database`, `register_all_models`, کش، `SchedulerApp().start()`, ضبط مصرف BrsApi، صف outcome، `RealtimeService`، WS Armor، **۷ وظیفه پسزمینه** (از طریق `_track_background_task`): `_brsapi_startup_sync`, `_fetch_news_on_startup`, `_decision_engine_startup_seed`, `_orchestrator_hourly_cron`, `warm_signal_cache`, `_fund_sync_cron`, `_ml_model_preload` — بهعلاوه `_check_cron_alerts` که با `await` مستقیم (نه background) در lifespan فراخوانی میشود. **نتیجه:** API_monolit علاوه بر HTTP، cron و scheduler داخلی هم اجرا میکند.

### لایه ۲۷ — state درونپردازهای
`_cron_state`, `_alert_state` و `_background_tasks` بهصورت dict/set ماژولlevel تعریف شدهاند و خود کد اذعان میکند برای چند replica آنها را به Redis آیینه میکند (`_load_cron_state_from_store`, `_cron_state_transaction`, `_with_startup_lock`). **نتیجه:** طراحی «stateless» وابسته به Redis است؛ قطع Redis = رفتار متفاوت cron.

### لایه ۲۸ — ریزسرویسهای FastAPI مستقل
`apps/admin/app.py:admin_app` (۸۰۰۱), `apps/currency_service/app.py:currency_app` (۸۰۰۲), `apps/decision_engine/app.py:app` (هم ۸۰۰۲!), `apps/funds/main.py:app` (Sandooghyar), `apps/gateway/app.py:GatewayApp` (فقط CORS، بدون route). **نتیجه:** ۶ اپ ASGI مجزا؛ دو تاشان پورت مشترک دارند.

### لایه ۲۹ — workerها
`apps/worker/__main__.py` و `apps/scheduler/__main__.py` نقاط `python -m`اند. `apps/analytics_worker`, `apps/backtest_worker`, `apps/ingestion_worker`, `apps/ml_worker`, `apps/strategy_worker` کلاس دارند ولی `__main__` ندارند. `apps/strategy_worker/` **فقط `__init__.py` دارد** در حالی که آن فایل `from apps.strategy_worker.app import StrategyWorkerApp` میکند → `ModuleNotFoundError` قطعی هنگام import. **نتیجه:** ۵ worker اسمی، ۲ worker قابل اجرا، ۱ ماژول شکسته.

### لایه ۳۰ — CMD داکرفایلها
`Dockerfile` → `python -m ingestion.main` (بدون HTTP)، `Dockerfile.api` → uvicorn 8000، `admin` 8001، `currency` 8002، `decision-engine` 8002، `worker` → `python -m apps.worker`، `scheduler` → `python -m apps.scheduler`، `golddesk` → `python -m apps.scheduler.app --only gold_desk`، `frontend` → `node server.js`. **نتیجه:** تمایز درست ingestion/API (توضیح `DEP-01` در compose)، ولی تداخل پورت ۸۰۰۲ باقی است.

### لایه ۳۱ — سرویسهای compose پیشفرض
`docker-compose.yml`: `timescaledb`, `redis`, `api`, `ingestion`, `worker`, `currency`, `frontend`. کامنتها صریحاً توضیح میدهند `Dockerfile` ریشه collector است و قبلاً اشتباهاً با `backend` shared بوده. MinIO بهصورت کامنت/profile اختیاری است. **نتیجه:** برخلاف `AUDIT_REPORT_2026-11-12.md` (ادعا: سرویس `api` وجود ندارد)، **اکنون وجود دارد** — نمونهای دیگر از کهنهبودن گزارشها.

### لایه ۳۲ — امنیت compose
`${DEV_POSTGRES_PASSWORD:?...}`, `${DEV_REDIS_PASSWORD:?...}`, `${DEV_JOB_QUEUE_TOKEN:?...}`, `${GOLD_API_TOKEN_SALT:?...}` بدون مقدار پیشفرض اجباری شدهاند؛ کامنت فارسی هشدار میدهد پیشفرض committed در `src/gold_desk/api_token.py` وجود داشته و توکنها پس از تغییر salt باید بازصدور شوند. `LAKE_*` همچنان `minioadmin` پیشفرض دارند. **نتیجه:** مسیر کانتینری امنتر از مسیر اجرای مستقیم کد است.

### لایه ۳۳ — compose production / sandooghyar
`docker-compose.production.yml` سرویس `api` را با `image: ghcr.io/.../api:latest` و ۲ replica تعریف میکند؛ `docker-compose.sandooghyar.yml` و `docker-compose.decision-engine.yml` استقرارهای جداگانهاند. `JOB_QUEUE_ENABLED=true` برای جلوگیری از اجرای Nباره job در N رپلیکا. **نتیجه:** آگاهی از مسئله duplicate-cron وجود دارد.

### لایه ۳۴ — کامپوننت K8s/Helm
`k8s/` چهار مانیفست decision-engine (configmap/deployment/secret.example/service) و `deploy/helm/gold-desk/` سه فایل. `secrets-scan.yml` یک جاب اسکن جداگانه است. **نتیجه:** پوشش استقرار پراکنده؛ هیچ Chart واحدی کل پلتفرم را تعریف نمیکند.

### لایه ۳۵ — CLI و ابزارهای جانبی
`apps/cli/main.py` چهار زیرفرمان `run/list/serve/seed` دارد و `serve` به `main.py` ریشه delegte میکند. `assistant.py` یک REPL مستقل OpenAI/AvalAI است (کامنتش به کلید hardcoded در تاریخ git اشاره دارد). `mimicode-go/` یک ابزار Go جداگانه (۵۲ فایل). **نتیجه:** چند ابزار کمکی بیارتباط با هسته در همان مخزن.

### لایه ۳۶ — انطباق معماری مستند با واقعیت
`ARCHITECTURE.md` ساختار `BrsApi_Forecasting/{core,services,api,static,deploy}`, استقرار Native ویندوز با **NSSM** و Caddy، و فرانتاند «HTML/CSS خالص» را شرح میدهد. کد واقعی `apps/core/domain/services/` + Docker + Next.js 16 است. **`README.md` ساختار درستتر را دارد ولی اعدادش کهنهاند.** **نتیجه:** دو سند معماری متناقض؛ هیچکدام مرجع قابلاتکای فعلی نیستند.

---

# فصل D — لایه ۳۷ تا ۴۹: لایه HTTP و سطح API

### لایه ۳۷ — هسته مسیریابی
`apps/api/router.py` (۷۶۱ خط) با `Router.setup()` و **۸۰ فراخوان `include_router`** زیر پیشوند `/api/v1`. فهرست `_ENDPOINTS` (خطوط ۲۳–۱۶۵) ۴۴ مسیر سطحبالا را مستند میکند. **نتیجه:** سطح API بسیار گسترده و تکمرکز.

### لایه ۳۸ — تراکم واقعی routeها
۸۴ فایل در `apps/api/endpoints/`، **۶۶۸ دکوراتور HTTP** + ۲ WebSocket. پرتراکمترینها: `codal_professional.py` (۴۹), `brsapi.py` (۴۴), `backtests.py` (۳۳), `funds_compliance.py` (۳۱), `options.py` (۳۰), `gold_analytics.py` (۲۶), `gold.py` (۲۴), `market.py` (۲۲), `tabdeal.py` (۲۰), `auth.py` (۱۹). **نتیجه:** README عدد ~۴۳۸ راگزارش میکند؛ واقعیت ۶۶۸ است.

### لایه ۳۹ — import تنبل
`router.py:202-206` صریحاً مینویسد ایمپورت ماژولی ۴۵ فایل endpoint حدود ۴۵ ثانیه طول میکشد، برای همین همه `from apps.api.endpoints.X import router` داخل `setup()` انجام میشود. **نتیجه:** بهینهسازی startup به قیمت پنهانشدن وابستگیها و خطاهای import تا هنگام بوت.

### لایه ۴۰ — سطوح دسترسی
چهار ردیف وابستگی تعریف شده: `_public_read = Depends(require_user_for_writes)` (خواندن ناشناس، نوشتن با توکن)، `_require_user(user/analyst/admin)`, `_require_analyst(analyst/admin)`, `_require_admin`. `/auth` بدون محافظ؛ `/health`, `/golddesk`, `/gold/analytics` عمومی؛ `/data-import`, `/jobs`, `/tests`, `/dashboard`, `/tables` ادمینی. **نتیجه:** مدل RBAC سهمرتبهای + الگوی «خواندن عمومی» مشخص و مستند.

### لایه ۴۱ — روترهای عمداً نصبنشده
۸ ماژول در پوشه `endpoints/` در `router.py` import نمیشوند، ولی **فقط ۷ تای آنها router واقعیاند**: `comprehensive_analysis`, `ime`, `monitoring`, `proposals`, `scanner`, `sentiment`, `symbol_alerts`. هشتمی (`backtest_requests.py`، ۷۶ خط) هیچ `APIRouter`ای تعریف نمیکند و ماژول کمکی/اسکیماست. کامنت `API-05` (خطوط ۱۸۲–۲۰۰)، `tests/unit/api/test_api05_mount_decisions.py` (`DECISIONS` هفت عضو) و `tests/unit/test_api_router_surface_inventory.py` (`KNOWN_UNMOUNTED` هفت عضو) دقیقاً همان هفت router را با دلیل (عدم مصرفکننده، همپوشانی، هزینه اسکن کامل بازار، افشای متریک) ثبت و گارد میکنند. **نتیجه:** کد مرده ولی **تصمیمآگاهانه، مستند و تستشده** — نقطه قوت حاکمیت.

### لایه ۴۲ — پشته میانافزار
`apps/api/app.py:1073-1089` نه لایه، به ترتیب اضافهشدن: `CORSMiddleware`, `SecurityMiddleware`, `CSRFMiddleware`, `InputSanitizationMiddleware`, `TimingMiddleware`, `MetricsMiddleware`, `LoggingMiddleware`, `RateLimitMiddleware`, `RequestContextMiddleware` (آخری بیرونیترین تا `trace_id` در دسترس بقیه باشد). همگی `BaseHTTPMiddleware`اند. **نتیجه:** ترتیب قصدشده و مستند، ولی BaseHTTPMiddleware سربار stream و محدودیت در contextvars دارد.

### لایه ۴۳ — محدودسازی نرخ
`RateLimitMiddleware` (`apps/api/middleware.py:505`) از `core/rate_limit/` (limiter, adaptive, budget_manager, tokens, windows, policy) و `settings.endpoint_rate_limits` (حدود ۴۰ نگاشت مسیر→RPM) استفاده میکند و هدرهای `X-RateLimit-*` صادر میکند. `GET /api/v1/rate-limits` و `/cache-stats` وضعیت را علنی میکند. **نتیجه:** لایه rate limit هم درونفرایندی و هم وابسته به Redis/تنظیمات است.

### لایه ۴۴ — CORS و CSRF
CORS: `allow_credentials=True`, `allow_methods/headers=["*"]`, مبدأها از `settings.cors_origins`؛ صحت آن **کاملاً وابسته** به `validate_production()` است که `["*"]` را رد میکند. `GatewayApp` همان حالت را صریحاً با `allow_creds = origins != ["*"]` مدیریت میکند. `CSRFMiddleware` و `InputSanitizationMiddleware` جداگانهاند. **نتیجه:** دو پیادهسازی متفاوت از یک قانون امنیتی.

### لایه ۴۵ — خطاها و پاسخها
`apps/api/error_handlers.py` → `register_error_handlers()`؛ `schemas/common/responses.py` → `ApiResponse[T]` یکپارچه؛ `pagination.py`؛ `openapi_security.py` → `install_openapi_security()` تزریق `bearerAuth`. `docs_url` در production بسته میشود. **نتیجه:** قرارداد پاسخ یکدست، ولی `extractArray()` در فرانتاند خطاها را به `[]` تبدیل میکند (لایه ۱۴۸).

### لایه ۴۶ — تزریق وابستگی
`apps/api/dependencies.py`: یک فکتوری جنریک `get_service()` (خطوط ۸۱–۱۱۴) **در کنار** ~۳۵ تابع دستنویس `get_*_service` (۱۱۷–۵۳۷)، بهعلاوه `get_current_user`, `get_optional_user`, `require_role`, `require_user_for_writes`, `owned_scope`. `core/dependency_injection/` (container/providers/factories/registries/lifecycle) هم وجود دارد. **نتیجه:** سه سبک DI همزمان.

### لایه ۴۷ — احراز هویت در عمل
`get_current_user` توکن Bearer را با `core/security/tokens.decode_access_token` باز میکند، `jti` blacklist و cutoff نشست کاربر را چک میکند (`_reject_if_revoked`). `apps/api/auth.py:_auth_required()` از `AUTH_DISABLED` میخواند. **نتیجه:** ابطال توکن پیادهسازی شده؛ `AUTH_DISABLED` یک kill switch نرمافزاری است که production gate جلوی آن را میگیرد.

### لایه ۴۸ — مسیرهای درون `app.py`
علاوه بر ۸۰ روتر، خود `app.py` هشت route درونخطی دارد: `/`, متریکها، `_orchestrator-cron status/history/toggle/run-now`, `/api/v1/rate-limits`, `/api/v1/cache-stats`, `GET {settings.metrics_path}`. **نتیجه:** کنترل عملیاتی (اجرای دستی cron) روی همان پورت API در معرض است و باید با `_require_admin` محافظت شود.

### لایه ۴۹ — WebSocket و حالت لحظهای
۲ route WebSocket در endpoints، `apps/api/endpoints/websocket.py` + `precompute_ws.py`، `api/ws_manager.py` (`ArmorWsManager`) و `services/realtime_service.py`. `apps/api/app.py:998` به Armor WS در lifespan وصل است. **نتیجه:** دو کانال لحظهای موازی (عمومی + داشبورد Armor).

---

# فصل E — لایه ۵۰ تا ۵۹: امنیت، هویت و اسرار

### لایه ۵۰ — ماژولهای امنیتی
`core/security/` یازده فایل: `tokens.py`, `hashing.py`, `saas.py`, `permissions.py`, `ime_rbac.py`, `totp.py`, `redaction.py`, `sanitizers.py`, `auth_context.py`, `secrets.py`. CI یک گام **مسدودکننده** `mypy core/security --strict` دارد (`.github/workflows/ci.yml:113`). **نتیجه:** امنیت تنها بخشی است که تایپچک strict و بلاککننده روی آن اعمال میشود.

### لایه ۵۱ — ژورنال اسرار
`docker-compose.yml:10-13` کامنت میکند «پیشفرض dev دوبار قبلاً لو رفته» و بههمین خاطر `${...:?...}` اجباری است. `docs/SECRET_ROTATION_CHECKLIST.md`, `docs/SECRETS_ROTATION_2026-09-16.md`, `docs/security/secret_rotation.md`, `.gitleaks.toml` و `scripts/scan_secrets.py` وجود دارند. CI اسکن «محدوده تحت مالکیت» را بلاککننده و «کل درخت» را advisory نگه داشته (بدهی تاریخی `k8s/decision-engine-secret.yaml` و دو compose). **نتیجه:** فرایند چرخش اسرار مستند، ولی پوشش کامل هنوز advisory است.

### لایه ۵۲ — salt توکن GoldDesk
`src/gold_desk/api_token.py` هنگام import نبود `GOLD_API_TOKEN_SALT` را خطا میدهد؛ `apps/api/app.py:39` صرفاً برای «fail fast» همان `SALT` را import میکند. compose برای `api` و `worker` مقدار یکسان اجباری کرده و هشدار داده که تغییر salt توکنهای قدیمی را باطل میکند. **نتیجه:** وابستگی پنهان startup به یک متغیر محیطی، با مستندسازی خوب.

### لایه ۵۳ — کلید امضای توسعه صندوقها
`apps/funds/auth.py:101`: `_DEV_SECRET = os.environ.get("SANDOOGHYAR_JWT_SECRET") or secrets.token_hex(32)` — کلید تصادفی **هر پردازه**؛ `apps/funds/main.py:26-39` فقط در production/staging جلوی آن را میگیرد. **نتیجه:** در محیط dev، توکن صادرشده توسط یک replica در replica دیگر نامعتبر است؛ ریسک بالا در صورت بالا آمدن ناخواسته غیر-dev.

### لایه ۵۴ — تزریق SQL
۱۷۳ الگوی `text(f"...")` / `execute(f"...")` در کد دیده شد. توجیه `pyproject.toml:182-195` میگوید identifierها توسط `_identifier()` در `query_builder.py`، allowlist در `brsapi/quality.py`، `_quote_model_identifier()` و `_SAFE_IDENTIFIER` در `endpoints/tables.py` پاکسازی میشوند و مقادیر کاربر bind parameterاند. **نتیجه:** ادعا قابلقبول ولی **غیرقابل اثبات ایستا**؛ هر فایل f-string جدید میتواند از این چتر خارج شود و bandit `B608` سراسری خاموش است.

### لایه ۵۵ — رمزنگاری و الگوریتم
`jwt_algorithm` در Settings مقدار `"none"` را رد میکند؛ SHA1 تنها ۳ بار همگی با `usedforsecurity=False` (digest غیرامنیتی)؛ `ml/model_loader.py` هنگام بارگذاری pickle، **هش HMAC artifact را بررسی میکند** و در صورت ناهماهنگی از بارگذاری خودداری میکند (`ML-007`)، با escape hatch صریح `ML_ALLOW_UNVERIFIED_MODELS=1`. **نتیجه:** امنیت زنجیره تأمین مدل، یکی از پیشرفتهترین نقاط سامانه است.

### لایه ۵۶ — CSRF/کوکی/Session
Settings شامل تنظیمات CSRF cookie، `AUTH_COOKIE_SECURE`, `samesite` و اعتبارسنجی وابستگی `secure`/`samesite`. CI گام `prod-check` این موارد را با `ENV=production` و مقادیر تست اجرا میکند. **نتیجه:** fail-closed پیکرهای در CI شبیهسازی میشود، نه فقط در مستندات.

### لایه ۵۷ — RBAC دامنهای
`core/security/permissions.py`, `ime_rbac.py`, `saas.py` و `apps/api/dependencies.py:require_roles`؛ `require_any_role` بهمعنای «هر یک از نقشها» است، نه «همه». `apps/decision_engine/app.py` کل روتر را با `Depends(get_current_user)` محافظت میکند. **نتیجه:** مدل نقش ساده و قابلپیشبینی، بدون مجوز سطحداده (row-level) در لایه API.

### لایه ۵۸ — ردپای حسابرسی
`models/audit_log.py`, `apps/admin/audit.py`, `monitoring/incidents.py`, `services/codal_analysis/` تحلیلهای فارنزیک. ولی `NUMERIC_AUDIT` گزارش میدهد جدول `decision_results` صفر ردیف است. **نتیجه:** ابزار حسابرسی در کد وجود دارد، خروجیاش در DB زنده خالی است.

### لایه ۵۹ — جمع بندی امنیتی
نقاط قوت: fail-closed production, revocation, strict typecheck امنیت, HMAC مدلها, اسکن بلاککننده. نقاط ضعف: کلید تصادفی dev، `B608` سراسری خاموش، افشای متریک/کنترل cron در همان پورت، و اسکن کامل درخت advisory. **ارزیابی: 🟢 خوب با ۳ استثنای مشخص.**

---

# فصل F — لایه ۶۰ تا ۷۲: معماری لایهای و دامنه (DDD)

### لایه ۶۰ — جهت وابستگی واقعی
بررسی مستقیم importها: `core → domain|services|apps` صفر، `services → apps` صفر، `repositories → services|apps` صفر، `domain → core` تنها ۱۰ مورد (همگی `core.time`, `core.constants`, `core.logging`, `core.trading_constants`). جهت مؤثر: `core` (shared kernel) ← `domain` (قواعد خالص) ← `repositories`/`services` ← `apps` (HTTP). **نتیجه:** معماری لایهای واقعاً رعایت شده، فقط «اعلام» نشده.

### لایه ۶۱ — قراردادهای import-linter
`.importlinter` چهار قرارداد `forbidden` فاز صفر: منع `logging` مستقیم در services/repositories، منع `ml → apps.api.endpoints`، منع `repositories → services|apps`، منع `sqlalchemy` مستقیم در services با `allow_indirect_imports=true`. `root_packages` هشت بستهاند. **نتیجه:** قراردادها «Advisory: measure, don't block» نامگذاری شدهاند؛ CI آنها را از طریق `scripts/quality_ratchet.py check --tool imports` بهصورت ratchet (فقط تخلف جدید بلاک میشود) اجرا میکند.

### لایه ۶۲ — ترفند `core.database`
`services/` هیچ `import sqlalchemy` مستقیمی ندارد ولی ۳۹۲ بار `text(...)` صدا میزند؛ `core/database.py:12-59` نمادها را با الگوی `X as X` بازصادر میکند تا قرارداد import-linter برقرار بماند. **نتیجه:** راهحلی هوشمندانه ولی «قانونشکنی شکلی»؛ مرز واقعی دسترسی به DB کمتر از آنچه قرارداد نشان میدهد شفاف است.

### لایه ۶۳ — هسته `core/`
۱۷۷ فایل در ۲۳ زیربسته: `config`, `security`, `rate_limit`, `feature_flags`, `dependency_injection`, `logging`, `health`, `exceptions`, `enums`, `constants`, `resilience`, `retry`, `concurrency`, `validation`, `time`, `ids`, `json`, `markets`, `typing`, `question_bank`, `scenario_bank`, `context`. فایلهای تک: `database.py`, `cache.py`, `cache_manager.py`, `event_bus.py`, `freshness.py`, `indicators.py`, `circuit_breaker.py`, `trading_constants.py`. **نتیجه:**.shared kernel بسیار حجیم و در عمل «همهچیزدان».

### لایه ۶۴ — کش سه لایه
`core/cache_manager.py`: L1 حافظه (OrderedDict LRU), L2 Redis (یک کلاینت بهازای هر پردازه), L3 محاسبه/DB. روی missing همزمان، قفل `SET NX` با TTL ۳۰ ثانیه و ۵۰ تلاش ۰٫۱ ثانیهای single-flight اجرا میکند؛ در نبود Redis به L1 degrade میشود. **نتیجه:** طراحی ضد stampede دقیق و مستند. عدد hit کش زنده ۶۳٫۱۳٪ است (پایین).

### لایه ۶۵ — باس رویداد درونپردازهای
`core/event_bus.py`: `subscribe/unsubscribe/publish`، پشتیبانی همزمان از handlerهای sync و async، و ایزولهکردن خطای هر handler تا بقیه اجرا شوند. **نتیجه:** مکانیزم سبک درونپردازهای؛ رویدادهای بینسرویسی از مسیر Redis Streams میروند (لایه ۱۳۱)، یعنی دو باس موازی.

### لایه ۶۶ — دامنه، ۳۲ بسته
`domain/` شامل `options`(۱۹ فایل), `instruments`(۱۴), `common`(۱۱), `analytics`(۹), `codal`(۸), `portfolios`(۸), `funds`/`news`(۷), و ۲۳ بسته ۴–۶ فایلهای دیگر. موجودیتها `BaseEntity`, `ValueObject`, `DomainError`, `Specification` دارند. **نتیجه:** DDD خالص (dataclass، بدون SQLAlchemy) — نقطه قوت معماری.

### لایه ۶۷ — بستههای دامنه بدون مصرفکننده
۱۱ بسته **هیچ import بیرونی** ندارند: `audit`, `bonds`, `commodities`, `energy`, `fx`, `indicators`, `indices`, `metals`, `pricing_version`, `trades`, `watchlists`. بستههای کممصرف: `alerts`(۱), `decision_engine_v5`(۱), `ml`(۱), `quotes`(۱), `recommendations`(۱), `signals`(۱), `pricing_version`(۰). در مقابل `common`(۷۰), `options`(۲۷), `trading`(۱۵), `news`(۱۳), `market_data`(۱۲) پراستفادهاند. **نتیجه:** حدود یکسوم دامنه داربست/آرزوی معماری است، نه کد زنده.

### لایه ۶۸ — قرارداد سیمی `contracts/`
چهار فایل (`events.py`, `schemas.py`, `exceptions.py`, `__init__.py`) شامل رویدادهای Pydantic `PRECOMPUTATION_*`, `SymbolGroup`, `JobStatus`, `PrecomputeStatusResponse` و سلسلهمراتب `PrecomputeError`. **نتیجه:** این بسته «قرارداد خط لوله پیشمحاسبه Armor» است، نه محل قراردادهای import-linter — نامگذاری گمراهکننده.

### لایه ۶۹ — مخازن داده
`repositories/` ۲۳ فایل: `BaseRepository`, `InMemoryRepository`, `db_base` و ۲۱ مخزن مشخص (`quote`, `market`, `instrument`, `signal`, `fund`, `news`, `news_items_read`, `orderbook`, `portfolio`, `ml`, `prediction`, `trade`, `user`, ...). ۱۰۹ فراخوان `.execute(`. **نتیجه:** لایه مخزن باریک؛ SQL خام عمدتاً در `services/` میماند.

### لایه ۷۰ — اسکیمها و مدلها
`schemas/` ۱۰۴ فایل / ۲۹۶ کلاس Pydantic در گروههای `api/`, `admin/`, `backtest/`, `ml/`, `providers/`, `reporting/`, `common/`. `models/` ۵۲ فایل / ۱۴۹ `__tablename__` با `Base(DeclarativeBase)` و `TimestampMixin`؛ `models/__init__.py` همه را برای Alembic وارد میکند. **نتیجه:** جداسازی DTO/ORM برقرار است؛ تعداد جدولها در DB زنده (۲۳۲) بیش از مدلهای تعریفشده (۱۴۹) است ← جداول ساختهشده توسط SQL خام/migration بدون مدل.

### لایه ۷۱ — استکهای لایهای موازی
چهار مجموعه کامل در کنار هم: (۱) ریشه `models+schemas+repositories+services`؛ (۲) `apps/funds/` با `models/schemas/services/db/router/auth/metrics/scoring/adapters` مستقل؛ (۳) `app/alert_hub/` با `models/repository/schemas/assessment/services`؛ (۴) `apps/currency_service/` با `domain/infra/services/endpoints`. همچنین `src/gold_desk/` (~۵۰ فایل) در برابر `services/gold/` (۲۸ فایل). **نتیجه:** بزرگترین بدهی معماری؛ D6 «تکمنبعسازی منطق صندوق» خود README به آن اذعان دارد.

### لایه ۷۲ — پیشبینی و موتورهای تکراری
`src/forecast_engine/forecasting_service.py` (ادغامشده از BrsApi_Forecasting، حباب/EMA) در برابر `src/forecasting/service.py` (drift+volatility با `sqrt(252)` هاردکد)، در برابر `apps/api/endpoints/forecast.py` و `forecast_engine.py`، در برابر زیرپروژه مستقل `BrsApi_Forecasting/` (۱۶ فایل + `ARCHITECTURE.md` مخصوص خود). **نتیجه:** پنج مسیر برای «پیشبینی»؛ تشخیص منبع حاکم بدون خواندن تکتک فایلها ممکن نیست.

---

# فصل G — لایه ۷۳ تا ۸۳: پایگاه داده، مهاجرتها و وضعیت داده زنده

### لایه ۷۳ — لایه دسترسی
`core/database.py`: `create_async_engine` (asyncpg / aiosqlite)، `async_session_factory`, `replica_engine`, `replica_session_factory`؛ `init_database()` با `pool_size=20, max_overflow=30, pool_pre_ping, pool_recycle=3600`؛ `get_session()` بهعنوان FastAPI DI با commit/rollback/close. `create_all` فقط وقتی `database_auto_create_tables=True`. **نتیجه:** مسئولیت تراکنش در لایه HTTPDI متمرکز است.

### لایه ۷۴ — محافظ replica
`_install_readonly_session_guard` (همان فایل، خطوط ۱۲۷–۱۵۴) با رویدادهای `before_flush` و `do_orm_execute` و تابع `_statement_is_write()` جلوی نوشتن روی نشست خواندنی را میگیرد. **نتیجه:** کنترلی ظریف و کمیاب در پروژههای متوسط.

### لایه ۷۵ — گراف مهاجرتها
پارس AST تمام ۹۴ فایل `migrations/versions/`: از `0001_initial_schema` تا `0123_ingestion_core_tables`، **بدون انشعاب، بدون والد گمشده، و دقیقاً یک head (`0123`)**. `migrations/env.py` ستون `alembic_version.version_num` را به `VARCHAR(255)` widening میکند. **نتیجه:** سالمترین بخش مخزن. درخت موازی `migrations_backup_20261030/` با ۹۲ فایل و `migrations/README.md` (ادعای head `0020`/`0119`) منابع گمراهیاند.

### لایه ۷۶ — انحراف اسناد مهاجرت
`README.md:27` عدد ۳۹ و `README.md:372` عدد `0119` را بهعنوان head معرفی میکند؛ عیبیابی همان فایل (`:832`) هم از «زنجیره ۰۰۳۹» میگوید. **نتیجه:** سه عدد متفاوت برای یک حقیقت؛ `alembic upgrade head` امروز `0123` میدهد.

### لایه ۷۷ — SQL خام
۳۹۲ `text(...)` در `services/` و ۱۰۷ رشته SQL خام (`SELECT/INSERT/UPDATE/...`)، ۱۷۳ الگوی f-string SQL در کل کد. `core/db_utils.py`, `core/dbcompat.py`, `query_builder._identifier()` ابزارهای پاکسازیاند. **نتیجه:** ORM و SQL خام همزیستی سنگینی دارند؛ query plan و ایندکسها وابسته به رشتههای داخل سرویساند.

### لایه ۷۸ — تصویر دیتابیس زنده
`NUMERIC_AUDIT_2026-11-12.md` (PostgreSQL 18.4 محلی، عکسبرداری ۲۰۲۶-۱۱-۱۲): **۵۰٫۱۷ GiB**، ۲۳۲ جدول public + ۱۶ view + ۴٬۱۵۲ ستون، **۱۱۸ جدول خالی (۵۰٫۹٪)**، ۱۱٬۲۲۷ شیء رابطهای. بزرگترین جدول `brsapi_intraday_trades` با ۶۰٬۷۴۱٬۱۹۹ ردیف (۱۹۱ چانک TimescaleDB). **نتیجه:** حجم داده واقعی عظیم، ولی نیمی از اسکیم بلااستفاده.

### لایه ۷۹ — سلامت خروجیهای تحلیلی (عددی)
همان سند: `ml_predictions` ۴۶٬۹۰۶ ردیف، **۱۰۰٪ `prediction_failed=true`** و صفر ردیف با accuracy/confidence/samples>0؛ `backtests` ۷٬۸۰۵ ران `completed` با میانگین بازده ۰٫۰۱۱٪ و **`backtest_trades` صفر ردیف**؛ `signal_accuracy` ۳٬۷۰۵ ردیف در برابر `signals` فقط ۴ ردیف → ۱۰۰٪ یتیم، صحت جهت ۳۸٫۴۹٪؛ معاملات کاغذی ۳٬۰۲۸ ردیف، نرخ برد ۲۸٫۴۳٪، ۳٬۰۲۵ تایشان بدون stop/target. **نتیجه:** لایههای تصمیم/ML/بکتست تا دیروز خروجی قابلاتکا تولید نکردهاند.

### لایه ۸۰ — پایش عملاً خاموش
شش جدول `data_freshness`, `data_gaps`, `market_data_quality_events`, `signal_performance`, `signal_weight_accuracy`, `decision_results` همگی **۰ ردیف** دارند، در حالی که `monitoring/` ۲۶ ماژول (`drift.py`, `data_freshness.py`, `model_performance.py`, `sla.py`, `incidents.py`, ...) و `Prometheus /metrics` در کد وجود دارد. **نتیجه:** شکاف «ابزار پایش نوشته شده / تزریق داده انجام نشده».

### لایه ۸۱ — کیفیت تاریخ (F10)
`gregorian_date` در همه ۵٬۷۰۷٬۱۹۶ ردیف `brsapi_historical_daily` پر است ولی فقط ۱۹ مقدار متمایز (۲۰۲۶-۰۷-۱۶ → ۲۰۲۶-۱۱-۱۰) دارد؛ ستون رشتهای `date` در نمونه ۱٪ بهتنهایی ۵٬۵۶۴ تاریخ شمسی (۱۳۸۰ → ۱۴۰۵) دارد. یعنی `gregorian_date` عملاً برچسب ingestion است نه تاریخ معاملاتی. **آخرین کامیت امروز (`091fdf31`) دقیقاً همین را با `jalali_to_gregorian` اصلاح کرده است** — نمونهای از چرخه بستن شکافها.

### لایه ۸۲ — کیفیت حجم و آمار planner
۶۰٫۲۱٪ ردیفهای `brsapi_historical_daily` حجم صفر/تهی دارند (پس گیتهای نقدینگی روی اکثریت داده بیاثر است). آمار planner تا ۸۴ برابر با واقعیت اختلاف دارد (`brsapi_symbol_snapshots`: ۳۶٬۹۹۸ در برابر ۳٬۰۹۲٬۴۳۱) و ۸ کوئری ممیزی با تایماوت شکستند؛ `ANALYZE` ضروری است. جدول پشتیبان `brsapi_historical_daily_backup` با ۴٫۵ میلیون ردیف / ۰٫۹۸ GiB همچنان نگهداری میشود.

### لایه ۸۳ — فایل SQLite عظیم
`transactions.db` (۵٫۲ GB) در ریشه، توسط `.gitignore` (`*.db`) نادیده گرفته میشود؛ `transactions_data/` ۶۹۴ فایل JSON و `history_data/` ۹۵ فایل JSON در کنار آن. `pyproject.toml:152-155` توضیح میدهد تستهای `needs_db` حدود ۵٫۵ میلیون ردیف را اسکن میکنند. **نتیجه:** داده آفلاین و داده PostgreSQL زنده دو جهان موازیاند؛ مشخص نیست کدام «منبع حقیقت» معاملات است.

---

# فصل H — لایه ۸۴ تا ۹۶: دریافت داده، فراهمکنندگان و دریاچه داده

### لایه ۸۴ — موتور گردآوری
`ingestion/main.py::IngestionEngine.start()` بهترتیب: `HttpClient`, `RawDataLake`, ثبت ۷ parser, `DeduplicationEngine` (Redis), `StorageLayer`, `IdentityResolver`, `IngestionWorker`, ثبت sourceها، و `MarketScheduler.on_tick(worker.ingest_all)`. کل پکیج ۵۹ فایل / ۷٬۰۵۸ خط. **نتیجه:** خط لوله مستقل، بدون HTTP، با `Dockerfile` جداگانه.

### لایه ۸۵ — parserها و sourceها
هفت parser: `TsetmcMarketWatch`, `TsetmcTrade`, `TsetmcOrderBook`, `FinpyTse`, `TsetmcLib`, `TehranStocks`, `TseUtils`. سورسها: `tsetmc` (instrument/marketwatch/orderbook/trade), `codal`, `crypto`, `derivatives`, `energy`, `ifb`, `global_markets`, `library_sources` (finpy/pytse/sadra/algotik). `DATA_500` هشدار میدهد برخی sourceها parserregistered نیستند. **نتیجه:** چندمنبعی واقعی، با ناهمخوانی احتمالی سورس/پارسر.

### لایه ۸۶ — کتابخانههای بازار ایران
`ingestion/library_sources/` چهار آداپتور بر روی `finpy-tse`, `pytse-client`, `tehran-stocks`, `tse-utils` (همه در `requirements.txt`) + `universal_collector.py`. **نتیجه:** وابستگی شدید به کتابخانههای متنباز کمثبات خارجی، بدون پیننسخه در `requirements.txt`.

### لایه ۸۷ — معماری `providers/`
۲۵۱ فایل در ۱۵ زیربسته: `realtime`(۴۳), `macro`(۴۶), `reference`(۳۳), `news`(۲۹), `historical`(۲۸), `base`(۱۷), `macro_sources`(۱۳), `web_scraping`(۸), `manual`(۸), `health`(۷), `capabilities`(۵), `funds`(۵), `gold_spot`(۴), `tsetmc`(۲), `codal`(۲). `base/` شامل `base_provider`, `registry`, `rate_policy`, `health`, `auth`, `http_client`, `result`. **نتیجه:** انتزاع فراهمکننده کاملاً مهندسیشده (capability matrix, SLA, incidents, health score).

### لایه ۸۸ — نقشه منابع خارجی
۱۴۶ URL یکتا در کد؛ نمونهها: `api.brsapi.ir`, `cdn.tsetmc.com/api`, `old.tsetmc.com/tsev2`, `call3.tgju.org`, `goldapi.io`, `query1.finance.yahoo.com`, `finnhub.io`, `alphavantage.co`, `fred`/`fmp`, `publicreporting.cftc.gov`, `www.gold.org/goldhub`, `www.kitco.com`, `feeds.reuters.com`, `www.mining.com`, `www.bls.gov`, `nfs.faireconomy.media` (ForexFactory), `api.telegram.org`. RSSهای فارسی: tgju, ibna, sana, boursepress, isna, fardayeeghtesad, ecoiran, tejaratnews, eghtesadonline. **نتیجه:** پوشش گسترده داخلی/جهانی، با وابستگی بالا به scraping و RSS.

### لایه ۸۹ — فراهمکنندگان الگو/ناکامل
۸۹ مورد `example.com` / `placeholder` / `stub` در ۴۲ فایل؛ پرتکرارترین `services/gold/feature_source.py` و سه فایل `providers/news/foreign/*` (هرکدام ۷). `providers/macro/commodities/*`, `energy/*`, `metals/*` آدرس `https://api.example.com/...` دارند. **نتیجه:** برخی «منابع داده» صرفاً قرارداد/داربستاند؛ هر reportی که تعداد منابع را بشمارد باید آنها را جدا کند.

### لایه ۹۰ — مقاومت شبکهای
`ingestion/http_client.py`, `retry.py`, `quotas.py`, `providers/base/rate_policy.py`, `providers/web_scraping/` (browser_pool, captcha_guard, proxy_rotation, robots_policy, scrape_scheduler), `core/resilience/`, `core/retry/`, `core/circuit_breaker.py`, `brsapi/client.py` با retry/circuit-breaker. **نتیجه:** لایه مقاومت چندبار و تکراری (حداقل ۳ پیادهسازی backoff متفاوت).

### لایه ۹۱ — بودجهبان BrsApi
`brsapi/budget.py::BrsApiBudgetGovernor`: شمارنده روزانه پایدار Redis `INCRBY` بر اساس تاریخ شمسی، پنجره ۵دقیقهای sorted set، cooldown ۹۰۰ ثانیه پس از HTTP 302، هشدار ۸۵٪ / reject نرم ۹۵٪، پیشفرض ۴۰۰۰ درخواست روز. `usage_recorder.py`, `readiness.py`, `rate_limiter.py`, `quality.py`, `json_sink.py`, `pipelines/`, `parsers/`, `repositories/`, `services/`, `models/`, `jobs/`, `migrations/` (زیرمجموعه ۷۸ فایل / ۱۶٬۶۹۹ خط). **نتیجه:** پیچیدهترین یکپارچهسازی خارجی، با حاکمیت مصرف واقعی.

### لایه ۹۲ — Kill switch حالت DB-only
`BRSAPI_ENABLED=false` تمام تماسهای زنده را متوقف میکند؛ `brsapi/client.py:471` پیام «DB-only mode» میدهد. `DATA_500_PROBLEMS_REPORT.md` ۲۴ مورد نخست خود را به همین وضعیت و تناقض `.env` / `.env.production` / مستندات اختصاص داده است. **نتیجه:** یک کلید واحد میتواند «تازگی داده» کل سامانه را صفر کند؛ رابطه آن با `isLive` فرانتاند (لایه ۱۴۸) حیاتی است.

### لایه ۹۳ — لایهدار کردن ذخیره خام
`ingestion/layered_store.py`, `ingestion/storage/layered_pipeline.py`, `dedup.py`, `storage/` ریشه (`layout.py`, `naming.py`, `partitions.py`, `snapshots.py`, `manifests.py`, `retention.py`, `archive.py`, `file_manager.py`). **نتیجه:** الگوی data lake (raw → validated → partitioned) در کد طراحی شده؛ `ml_artifacts/` و `backtest_data_all/` عملاً خالیاند.

### لایه ۹۴ — MinIO و شکاف استقرار
`ingestion/lake/__init__.py:21-45` هنگام startup اتصال MinIO و وجود باکت را بررسی میکند، ولی `docker-compose.yml` سرویس MinIO را **کامنت کرده** و `LAKE_ENDPOINT=http://minio:9000` به میزبان ناموجود اشاره دارد (با `LAKE_ACCESS_KEY=minioadmin` پیشفرض). **نتیجه:** مسیر ذخیره raw در استقرار پیشفرض یا fail میکند یا به fallback میرود؛ `DATA_500` آن را «بالا» درجهبندی کرده. **تکمیل قسمت ۰۳:** بدتر از غیاب سرویس، **نام متغیرها هم به کلاس نمیرسد** — compose `LAKE_*` تزریق میکند ولی `IngestionConfig` با `env_prefix="INGESTION_"` دنبال `INGESTION_LAKE_*` است (`CFG-17`، نام درست در `docs/env-vars.md:483-486` و پیام خطای خود کد)، و گارد fail-closed اعتبار MinIO در `ingestion/lake/__init__.py:22-32` چون `ENV=production` تنظیم نشده هرگز اجرا نمیشود.

### لایه ۹۵ — کیفیت و تازگی داده
`ingestion/raw_validation.py`, `validation.py`, `fx/quality_gate.py`, `gold/quality_gate.py`, `parser/validator.py`, `core/freshness.py`, `monitoring/data_freshness.py`, `backtesting/data_quality/`, `providers/health/*`. `core/freshness.py` و Point-in-time ماژولها وجود دارند ولی جداول `data_freshness`/`data_gaps` خالیاند. **نتیجه:** منطق تازگی نوشته شده، تلهmetrیاش تزریق نشده.

### لایه ۹۶ — جهان نمادها
`all_symbols.json`, `symbol_trade_days/` (۳۹ JSON), `market_holidays.json`, `domain/instruments/symbol_catalog.py`, `symbol_finglish.py`, `aliases.py`, `listing_rules.py`, `ingestion/scanners/all_symbols.py`, `ingestion/identity/`, `providers/reference/instrument_master/`, `providers/reference/alias_manager/`. `acceptance.yaml` و `config/symbols.yaml` و `domain/calendar/trading_calendar.py` تقویم/مقررات را نگه میدارند. **نتیجه:** حداقل ۶ نقطه نگهداری فهرست نمادها — نقض اصل «تکمنبع حقیقت نماد» که خود `ARCHITECTURE.md` (زیرپروژه BrsApi) اعلام کرده.

---

# فصل I — لایه ۹۷ تا ۱۰۹: پردازش، سیگنال، تصمیم و قیمتگذاری

### لایه ۹۷ — خط لوله سیگنال کوانت
`MultiMarketSignalEngine → EnsembleEngine → ConfidenceScorer → DecisionEngine → انتشار → SignalAccuracyTracker → AutoRetrainPipeline → ModelLoader.invalidate()`. ماژولهای کلیدی در `services/`: `quant_signal_orchestrator.py` (۲٬۱۴۲ خط), `signal_decision_engine.py`, `signal_voting_system.py`, `probability_calibrator.py`, `ml_signal_connector.py`, `auto_retrain_pipeline.py`, `accuracy_outcome_queue.py`. **نتیجه:** حلقه بازخورد کامل طراحی شده؛ تا دیروز بهدلیل افق/تجمیع نادرست، متریکهایش مسموم بود (لایههای ۱۰۱/۱۰۲).

### لایه ۹۸ — یازده دروازه تصمیم
`services/signal_decision_engine.py:440-489` یازده `_gate_*` را بهترتیب اجرا میکند: `data_quality, model, probability, regime, consensus, liquidity, risk_reward, net_profit, expectancy, portfolio, execution`. `DecisionResult` با `verdict ∈ {BLOCK, WARN, PASS}` و `is_approved = all(verdict != BLOCK)`. README میگوید «۱۰ دروازه» — کد ۱۱ تاست. **نتیجه:** گیتها واقعی و قابلردیابیاند (`gate_results` روی هر سیگنال ذخیره میشود).

### لایه ۹۹ — Fail-closed
`quant_signal_orchestrator.py:1300-1327`: هر استثنای موتور تصمیم → `decision_verdict = "reject"` / `REJECTED_ON_ERROR`، نه release. `portfolio_approved` از دفتر معاملات کاغذی (`services.portfolio_risk`) میآید و ناخوانا بودن دفتر = `False` → Gate 9 بلاک میکند. **نتیجه:** ایمنی مالی، قویترین بُعد سامانه (امتیاز ۹/۱۰ در حسابرسی قبل).

### لایه ۱۰۰ — کیفیت داده سیگنال
`:1221-1233` از `compute_data_quality_score(total_fields, missing_fields, total_price_points)` در `core/indicators.py` استفاده میکند (ضرب کاملیت فیلد × کفایت تاریخچه)؛ در نبود تاریخچه، `_price_points = max(20, n_votes*10)` یک proxy صریح است. **نتیجه:** جایگزینی هاردکد ۱٫۰ با محاسبه واقعی انجام شده، ولی fallback هنوز مصنوعی است.

### لایه ۱۰۱ — P0#3 / افق ارزیابی — **رفعشده ✅**
`quant_signal_orchestrator.py:1843` تعریف تابع `_evaluate_past_signals` با پنجره ۹۰روزه؛ `CASE sa.timeframe` در خط ۱۸۷۸: daily/1d→۲ روز، 2day→۳، 3day→۵، weekly/1w→۸، monthly/1m→۲۳، quarterly/3m→۶۵، ناشناخته→۵ روز، `LIMIT 100`. پرچم `outcome_set_at IS NULL` مانع ارزیابی دوباره است. `signal_accuracy` شامل `sa.timeframe` شده (کامیت `9b44797b`). **نتیجه:** یافته «بحرانی» گزارش ۲۰۲۶-۱۱-۱۲ دیگر زنده نیست.

### لایه ۱۰۲ — P0#4 و P1b — **رفعشده ✅**
`:2062-2094` دقت را از `get_accuracy_by_market` (گروهبندی `(market, source)`) با جمع `correct/total` **بهازای هر بازار** تجمیع میکند و بازارهای با کمتر از ۲۰ نمونه را حذف میکند؛ `overall` میانگین است. `:1235-1253` نقدینگی/پرشدن را از `volumes` واقعی (`vol_ratio`) میگیرد و نبود داده را «degraded صریح ۰٫۳/۰٫۴» اعلام میکند، نه proxy از `abs(change_pct)`. **نتیجه:** هر سه یافته بحرانی/بالای حسابرسی قبل در کد فعلی بسته شدهاند.

### لایه ۱۰۳ — پول هوشمند ۹ لایه
`services/smart_money/` ۲۱ فایل: `layer1_price_volume` … `layer9_breakout_quality`، بهعلاوه `parallel_engine`, `scoring_engine`, `feature_store`, `normalizer`, `confidence`, `data_quality`, `resilience`, `stats`, `phase_alerts`, `advanced_analytics`, `config_loader`. وزنهای لایه ۱ از `config/smart_money.yaml` خوانده میشوند. کامیتهای امروز `fix(smart_money)` فرمول ESS/BCP و عبارات مرده را اصلاح کردهاند. **نتیجه:** زیرسیستمی بالغ ولی پر از ریزباکَهای عددی تازهکشفشده.

### لایه ۱۰۴ — غربالگری سه نسل
`screener_service.py` (پایه), `smart_screener_v2.py` (۴۰۰+ فیلتر، OR/AND), `screener110_service.py` (CANSLIM، ۱۱۰ ستون) + `services/screener/`, `saved_filters`. امروز `b7f775fb` نرمالسازی امتیاز خام به ۰–۱۰۰ انجام شده تا آستانه خرید قابلدسترس باشد و `4201313e` نام کلاس اشتباه import را اصلاح کرده. **نتیجه:** نسخههای موازی همچنان همزمان mountاند (`/screener`, `/screener-v2`, `/screener110`).

### لایه ۱۰۵ — موتور تصمیم سازمانی
`apps/decision_engine/app.py` اپ FastAPI جداگانه، `apps/api/endpoints/decision_engine.py` (۱۷ route), `domain/decision_engine_v5/` (۴ فایل: models/pricing_tiered/trading/validation)، auto-seeding از JSON هنگام startup (`_decision_engine_startup_seed`). **نتیجه:** دو «Decision Engine» متفاوت: یکی موتور ۱۱ دروازهای سیگنال در `services/`، یکی سامانه معماری سازمانی در `apps/` — تشابه اسمی شدیداً گمراهکننده.

### لایه ۱۰۶ — قیمتگذاری آپشن (۱۹ ماژول)
`domain/options/`: `pricing` (Black-Scholes), `greeks`, `higher_order_greeks`, `heston_model`, `monte_carlo`, `tree_pricing`, `margin_engine`, `strategy_engine`, `var_calculator`, `volatility`, `payoff`, `probability` (Max Pain, Prob-of-Touch), `cointegration`, `commodity_pricing`, `symbol_parser`, `signals`. (**DOM-12 تصحیح:** `black76.py` در این پوشه وجود ندارد — `domain/options/` هیچ فایل black76 ندارد؛ پیادهسازی black-76 در `src/gold_desk/black76.py` و `services/gold/black76_engine.py` است.) `OPTIONS_DEEP_ANALYSIS_2026-11-13.md` پانزده راستیآزمایی عددی گزارش کرده (Put-Call Parity خطای 2.27e-13، IV round-trip 3.23e-06، ولی Vomma خطای ۹٬۸۷۸٪ و Heston=0). **نتیجه:** هسته ریاضی قوی، گریکهای مرتبهبالا و Heston مشکلدار — که کامیتهای `ace9339f`/`8831b574` امروز دقیقاً آنها را نشانه گرفتهاند.

### لایه ۱۰۷ — اسکیمهای موازی آپشن
همان سند: `brsapi_option_snapshots` ۱٬۲۸۱٬۶۷۸ ردیف، `brsapi_ime_options` ۱۳۶٬۱۶۳، `options` (legacy) ۳٬۲۲۵، `commodity_options` ۴۷۶، در مقابل `option_contracts` و `option_snapshots` (نرمالشده) **۰ ردیف** و `gold_option_iv_history` صفر. ۲۶٫۸٪ نمونهها زیر ارزش ذاتی، ۵۶۷٬۵۱۱ رکورد OI صفر، ۸۳۰٬۶۷۹ رکورد Volume صفر. امروز `d77d663e` یک `OptionsNormalizeJob` برای پر کردن اسکیم نرمال وصل کرده است. **نتیجه:** شکاف «طراحی اسکیم / writer» در حال بسته شدن است، ولی داده تاریخی همچنان در ۴ اسکیم قدیمی است.

### لایه ۱۰۸ — طلا / کامودیتی
`services/gold/` ۲۸ فایل: `black76_engine`, `options_chain`, `futures_term`, `physical_arbitrage`, `macro_sync`, `kill_switch`, `feature_source`, `options_matrix`، ...؛ `src/gold_desk/` **۵۸ فایل** (نه «حدود ۵۰» — **DOM-12 تصحیح**: شمارش دقیق ۵۸ است) (`signal_engine`, `snapshot_service`, `ws_hub`, `backtest`, `telegram_bot`, `antigravity/*`)؛ `domain/metals/`, `domain/commodities/`, `domain/energy/`, `domain/fx/`. `acceptance.yaml` و `PLAN_GOLD.md` (۲۸ KB) و `GOLD_SILVER_ASSISTANT_SPEC.md` اسناد حاکم. **نتیجه:** گستردهترین حوزه دامنه، با بیشترین تکرار پیادهسازی.

### لایه ۱۰۹ — تحلیل کدال و اخبار
`services/codal_analysis/` **۳۴ فایل** (نه ۳۵ — **DOM-12 تصحیح**) (IFRS/forensic/audit)، `services/news_*` (dedup, dual_write, parity)، **DOM-12 تصحیح:** `read_canary` در `core/news_read_canary.py` است (نه `services/news_*`)؛ `providers/macro_sources/news_rss.py` ماژول RSS است (نه `providers/news/rss`)، `core/news_tags.py`. تنظیمات `NEWS_READ_MODE` چهارحالته (off/shadow/canary/full) + آستانه parity/halt. **نتیجه:** کاناری خواندن اخبار، پیچیدهترین مکانیسم rollout سامانه است.

# فصل J — لایه ۱۱۰ تا ۱۲۱: موتور بکتست، هزینه تراکنش و اعتبارسنجی آماری

### لایه ۱۱۰ — تجمیع شش موتور (یافته D1)
`backtesting/runner.py` صریحاً خود را «the single entry point» و پیادهکننده «audit finding D1» معرفی میکند. جدول داخل docstring شش موتور را فهرست میکند: `simulator` (`BacktestSimulator`، ✅ canonical)، `replay` (`ReplayEngine`)، `hybrid` (`HybridMarketSimulator`)، `portfolio` (`PortfolioBacktestSimulator`)، `simulation` (`SimulationEngine`، 🔴 deprecated بدون مصرفکننده پروداکشن)، `backtest_engine` (`BacktestEngine`، 🔴 deprecated فقط smoke تست). `BacktestRunner().run("simulator", ...)` یا پذیرش instance موتور، خروجیها را از «normalisation واحد + مدل هزینه واحد» عبور میدهد. **نتیجه:** تکثر موتورها حذف نشده، بلکه *مهار* شده است؛ این الگوی درست مهندسی برای codebase بالغ است، ولی ۲ موتور مرده همچنان بار نگهداری دارند.

### لایه ۱۱۱ — هسته canonical و ۲۸ ماژول `engine/`
`backtesting/engine/` با ۲۸ فایل، بزرگترین زیربسته بکتست است؛ `BacktestSimulator` تنها موتوری است با «synchronous, deterministic core» (به نقل runner). مصرفکنندگان production نامبرده: `services/backtest_service`، `cascade_engine`، `strategy_generator`، `mass_scanner`، `composer`، walk-forward و `scripts/`. در کنار آن ۴۴ زیرپوشه دیگر (`abm`, `alpha`, `analytics`, `calibration`, `capital`, `composer`, `corporate_actions.py`, `microstructure`, `observability`, `regime`, `risk`، ...) قرار دارند. **نتیجه:** ۳۰۲ ماژول / ۲۹٬۵۵۷ خط بکتست یعنی بکتست بهتنهایی یک محصول مجزا است، نه یک ویژگی API.

### لایه ۱۱۲ — مدل هزینه واحد (یافته F1)
`backtesting/costs/iran_costs.py` docstring: «Single source of truth (audit finding F1)». نرخها از `domain/trading/iran_costs.MARKET_RATES` وارد میشوند (`BROKER_PCT`, `CLEARING_FEE_PCT`, `SELL_TAX_PCT`, `buy_rate()`, `sell_rate()`) و **هیچ کپی محلی** وجود ندارد. هشدار صریح: «the 0.5% transfer tax is already INSIDE the equity sell rates, never added on top». `IranTransactionCosts` یک `@dataclass(frozen=True)` با `buy_cost/sell_cost/compute` و `normalize_side()` است که Enum و str را یکسان میکند. **نتیجه:** جلوگیری از «دوبار شمارش مالیات فروش» — یکی از پرتکرارترین خطاهای مالی در بکتست بازار ایران — بهصورت ساختاری بسته شده است.

### لایه ۱۱۳ — جدول تعرفه ۱۴۰۵ و ده بازار
`config/backtest_costs.yaml` با تیتر «Canonical backtest cost config — single source of truth» ده کلاس را با نرخ all-in فهرست میکند: `tse_equity` خرید ۰٫۳۷۱۲٪ / فروش ۰٫۸۸٪ (رفتوبرگشت ۱٫۲۵۱۲٪)، `ifb_equity` (۱٫۲۴۳۲٪)، `taseh` (۰٫۷۳٪)، `debt` (۰٫۱۴۵٪)، `etf_equity` (۰٫۴۵۴۵٪)، `etf_mixed`، `etf_fixed` (۰٫۰۷۳۷۵٪)، `etf_commodity`، `commodity_cert`، `coin_cert`. `market_close` برای هر ده بازار جداگانه «12:30:00» تعریف شده و کامنت میگوید «No single global default». کامنت هشدار میدهد پیش از استفاده زنده با جدول SEO و کارگزاری بازبینی شود. **نتیجه:** نرخها نسخهدار و مستنداند، ولی `last_updated` برای تعرفه مشخص نشده؛ ریسک کهنگی تعرفه واقعی است.

### لایه ۱۱۴ — گارد پاریتی هزینه (یافته F2)
docstring `iran_costs.py`: «Every fill producer charges through `IranTransactionCosts.compute(...)` so all backtest paths converge on identical costs (audit finding F2)». CI این ادعا را بهصورت اجرایی قفل کرده: `.github/workflows/ci.yml:269` مرحله «Backtest integrity guard (cost parity + engine runner D1)» با `pytest tests/unit/backtesting/test_cost_parity.py tests/unit/backtesting/test_engine_runner.py -v -x`. `backtesting/costs/` هشت فایل دارد: `apply_costs`, `transaction_cost_model`, `spread_estimator`, `fx_costs`, `gold_costs`, `execution_analytics` و `__init__`. **نتیجه:** یکی از معدود مواردی که مستندات، کد و CI، هر سه همسو و قفلشدهاند (امتیاز کامل).

### لایه ۱۱۵ — لغزش، زمانبندی اجرا و مشارکت در حجم
همان YAML: `base_slippage_bps: 5.0`، `volume_impact_factor: 0.15`، `min_slippage_bps: 3.0`، `max_slippage_bps: 150.0`، `execution_timing: next_open` (کامنت: «default, realistic» در برابر `same_close`)، `max_participation: 0.05`، `allow_partial_fill: true`، `seed: 42`. کران بالای ۱۵۰ bps و سقف ۵٪ ADV یعنی شبیهسازی از خوشبینی «پر شدن کامل با قیمت بسته» جلوگیری میکند. `backtesting/execution/` (۱۰ فایل) و `backtesting/microstructure/` (۱۰ فایل) پیادهساز این لایهاند. **نتیجه:** مدل اجرا از نظر طراحی جزو نقاط قوت است؛ نکته حساس اینجاست که `NUMERIC_AUDIT` نشان میدهد هیچ fill ای تا دیروز ذخیره نمیشد، پس این دقت هرگز روی داده واقعی پسآزمایی نشده است.

### لایه ۱۱۶ — مبنای بهای تمامشده FIFO و اقدامات شرکتی
`backtesting/position_manager.py` (یکی از ۶ فایل ازپیش تغییریافته کاربر، **دستنخورده**)، `backtesting/corporate_actions.py`، `backtesting/sizing.py`، `backtesting/commission.py`، `backtesting/portfolio/` (۹ فایل) و `backtesting/capital/` زنجیره نگهداری موقعیت را میسازند. `types.py` و `contracts.py` قراردادهای مشترکاند. **نتیجه:** محاسبه PnL با مبنای FIFO و تعدیل افزایش سرمایه/تقسیم سود پیادهسازی شده، ولی چون `types.py`/`performance.py`/`position_manager.py` همگی در `git status` اصلاحنشدهاند، وضعیت نهایی این لایه در کامیت مبنا **ناپایدار** است.

### لایه ۱۱۷ — دوازده ماژول متریک و آمار مقاوم
`backtesting/metrics/`: `performance`, `return_metrics`, `risk_metrics`, `drawdown_metrics`, `trade_metrics`, `turnover_metrics`, `exposure_metrics`, `benchmark_metrics`, `deflated_sharpe`, `risk_free_rate`, `dynamic_risk_free`, `__init__`. وجود `deflated_sharpe.py` و `dynamic_risk_free.py` نشان میدهد دفورمیشن «Sharpe خام» شناخته شده است: `acceptance.yaml` حداقل `min_dsr: 0.95` میطلبد. `return_metrics_wrapper.py` و `execution_simulator_wrapper.py` در ریشه، لایه سازگاری با کد قدیماند. **نتیجه:** ابزار آماری لازم برای رد overfitting موجود است؛ مسئله این نیست که متریک کم است، بلکه اینکه ورودیاش (trades) خالی بوده است.

### لایه ۱۱۸ — Walk-forward، purge و مونتکارلو
`backtesting/optimization/walk_forward.py`، `backtesting/experiment/purged_walk_forward.py`، `backtesting/optimization/monte_carlo.py`، `backtesting/scenarios/` (۹ فایل)، `backtesting/validation.py`، `backtesting/calibration/` (۹ فایل). `acceptance.yaml` آستانهها را تعریف میکند: `min_wfe: 0.50`، `min_dsr: 0.95`، `min_oos_sharpe: 1.00`، `max_drawdown: 0.20`، `min_profit_factor: 1.30`، `min_trade_count: 50`. «Purged» بهمعنای حذف پنجره همپوشان train/test برای جلوگیری از نشت اطلاعات است (همان خطایی که `DEEP_REVIEW_PART1.md` P0#2 «target leakage» ادعا کرده و رد شده بود). **نتیجه:** چارچوب aceptance از بسیاری پروژههای مشابه جلوتر است؛ گلوگاه، وصل کردن خروجی واقعی رانها به این گیت است.

### لایه ۱۱۹ — ABM و ریزساختار
`backtesting/abm/` (۸ فایل)، `backtesting/microstructure/` (۱۰)، `backtesting/hybrid/` (۶)، `backtesting/market/`, `backtesting/orderbook` در `domain/orderbook/`، و `backtesting/regime/` (۸). `HybridMarketSimulator` همان موتوری است که runner آن را «ABM + microstructure» توصیف میکند. **نتیجه:** لایهای پژوهشی و بسیار پیشرفته، اما با ارتباط کم به مسیر production (موتور canonical همچنان `simulator` ساده میلهای است) — نمونه دیگری از «داربست معماری بدون جریان اجرا» (لایه ۷/۵۱).

### لایه ۱۲۰ — گیت پذیرش زنده
`acceptance.yaml` علاوه بر آستانهها، `signal_filter` را هم شامل میشود (`min_net_profit_pct: 2.0`، `min_risk_reward: 2.0`، `require_positive_ev: true`)، `market_rules.gold` سه رژیم (`global_xau` با `risk_free_rate: 0.045` / ۲۵۲ روز، `domestic_ime` و `domestic_etf` با ۰٫۳۰۰ / ۲۴۰ روز)، و `fee_schedule` نسخهدار با فیلد `provenance` (سهحالته `spec` / `assumption` / `unavailable`) و هشدار «نباید بهجایش صفر گذاشت». **نتیجه:** `acceptance.yaml` تنها سند ریشه است که با کد زنده همخوان و بهعنوان منبع واحد اعداد مصرف میشود؛ الگویی که باید به سایر اسناد تسری یابد.

### لایه ۱۲۱ — شکاف «ران کامل بدون معامله» و رفع امروز
`NUMERIC_AUDIT_2026-11-12.md`: **۷٬۸۰۵** ران بکتست با وضعیت `completed` در مقابل **۰ ردیف** در `backtest_trades`؛ یعنی تمام متریکهای لایههای ۱۱۷/۱۱۸ محاسبهپذیر نبودهاند. کامیت `603059da` امروز با عنوان `fix(backtest): persist individual fills to backtest_trades on run completion` دقیقاً این شکاف را هدف گرفته، و `backtesting/platform/job_queue.py` مسیر اجرای ناهمزمان رانها را فراهم میکند. **نتیجه:** مهمترین تغییر امروز از منظر صحت مالی؛ تا زمان backfill رانهای قدیمی، نتایج تاریخی `completed` همچنان **بیاعتبار**اند و نباید مبنای تصمیم قرار گیرند.

---

# فصل K — لایه ۱۲۲ تا ۱۳۲: یادگیری ماشین، ویژگیها و رجیستری مدل

### لایه ۱۲۲ — نقشه ۱۱۸ ماژول ML
`ml/` شامل ۱۱۸ فایل پایتون در هفت زیربسته: `models/` **۴۲**، `features/` **۱۶**، `training/` **۱۱**، `datasets/` **۱۱**، `inference/` **۱۰**، `evaluation/` **۱۰**، بهعلاوه فایلهای ریشه `artifacts.py`, `constants.py`, `contracts.py`, `dataset_builder.py`, `exceptions.py`, `experiments.py`, `feature_store.py`, `metrics.py`, `model_loader.py`, `model_registry.py`, `global_registry.py`, `policies.py`, `registry.py`, `train_weight_optimizer.py`, `types.py`, `utils.py`, `weight_validator.py`. `src/forecasting/` در مقابل **فقط `service.py`** دارد. **نتیجه:** تمرکز واقعی ML در `ml/` است، نه `src/forecasting/`؛ ولی ۴۲ ماژول `models/` در برابر ۱۱ ماژول `training/` یعنی تعریف مدل بسیار جلوتر از فرایند آموزش است.

### لایه ۱۲۳ — `ModelLoader` و LRU کراندار
`ml/model_loader.py`: `_DEFAULT_MAXSIZE = 20`، «keeps at most maxsize models in an LRU cache»، بارگذاری تنبل بهازای نماد، و `functools.lru_cache` «one per process, thread-safe». متد `invalidate()` (که در لایه ۹۷ توسط `AutoRetrainPipeline` فراخوانی میشود) LRU را با بازماندگان بهترتیب «oldest-first» گرم میکند تا ترتیب تازگی حفظ شود؛ `diagnostics()` اطلاعات کش را برمیگرداند. نمادهای بدون artifact «skipped silently» میشوند. **نتیجه:** طراحی حافظهبندی درست است، ولی سکوت در نبود artifact یعنی افت کیفیت پیشبینی بدون هشدار عملیاتی — همان الگوی «degraded خاموش» که در لایه ۱۰۲ اصلاحشده بود.

### لایه ۱۲۴ — راستیآزمایی امضای artifact (ML-006 / ML-007)
همان فایل: هنگام ذخیره، sha256 در `artifact_hash` داخل `metadata.json` ثبت میشود؛ هنگام بارگذاری، `_verify` با `hashlib.new(algorithm, raw).hexdigest()` و **`hmac.compare_digest`** مقایسه میکند و «Refuse to unpickle an artifact that fails its recorded hash (ML-007)». عدم تطابق یعنی «file changed after it was saved». escape hatch صریح: `ML_ALLOW_UNVERIFIED_MODELS=1` برای artifactهای قدیمی فاقد هش. **نتیجه:** امنیت زنجیره تأمین مدل (مقابل pickle RCE) واقعاً پیادهسازی شده؛ ریسک باقیمانده فقط روشن ماندن آن متغیر محیطی در پروداکشن است.

### لایه ۱۲۵ — Feature Store و ۱۶ ماژول ویژگی
`ml/feature_store.py` یک رجیستری درونحافظهای ساده است: `register_feature(name, group, dtype)`, `get_features()`, `get_features_by_group()`, `list_groups()`, `remove_feature()`. `ml/features/` شانزده فایل و `ml/dataset_builder.py` ساخت.dataset را بر عهده دارند؛ `jobs/definitions/feature_store_jobs.py` (از ۶ فایل تغییریافته کاربر) وظیفه پر کردن آن را دارد. **نتیجه:** برخلاف نام «Feature Store»، پیادهسازی یک کاتالوگ متادیتا است نه ذخیرهساز point-in-time؛ بنابراین ادعای جلوگیری از look-ahead bias در لایه آموزش باید با احتیاط خوانده شود.

### لایه ۱۲۶ — رجیستری و نسخهبندی مدل
`ml/model_registry.py`: `register(name, task, framework, tags) -> str`، `add_version(...)`, `get_version(model_id, version)`, `get`, `list_models`. در کنار آن `ml/registry.py`, `ml/global_registry.py`, `ml/policies.py`, `ml/weight_validator.py`, `ml/train_weight_optimizer.py` و `ml/contracts.py` لایه حاکمیت را میسازند. **نتیجه:** چهار مفهوم «registry» (`registry`, `model_registry`, `global_registry` و `domain/ml/`) همزیستاند — تکثر مشابه تنظیمات (لایه ۱۶) در مقیاس کوچکتر.

### لایه ۱۲۷ — چرخه آموزش تا استنتاج
`training/` ۱۱، `datasets/` ۱۱، `inference/` ۱۰، `evaluation/` ۱۰، `ml/experiments.py`, `ml/metrics.py`, `ml/utils.py`. `DEEP_REVIEW_PART1.md` ادعای «P0#1 training unreachable» مطرح کرده بود و همان سند آن را **رد** کرده است؛ مسیر `jobs/model_training.py` + `jobs/model_retraining.py` + `jobs/definitions/` در ریشه `jobs/` نیز وجود دارد. **نتیجه:** آموزش از نظر اتصال کد قابلدسترس است؛ مسئله «غیرقابلدسترس بودن» نبوده، بلکه «خالی/شکستخورده بودن خروجی» است (لایه ۱۳۰).

### لایه ۱۲۸ — حلقه بازآموزی خودکار
`services/auto_retrain_pipeline.py` + `services/accuracy_outcome_queue.py` + `services/signal_accuracy_tracker` (در لایه ۹۷) + `ModelLoader.invalidate()` زنجیره «ارزیابی → ثبت نتیجه → آستانه افت دقت → بازآموزی → باطل کردن کش» را میسازند. `jobs/signal_eval_daily.py` و `jobs/risk_monitor.py` محرکهای زمانبندیشدهاند. **نتیجه:** حلقه MLOps از نظر گراف کامل است، ولی چون `NUMERIC_AUDIT` دقت سیگنال را ۱۰۰٪ یتیم گزارش کرده، ورودی محرک آن تا دیروز سالم نبوده است.

### لایه ۱۲۹ — ۴۶٬۹۰۶ پیشبینی، ۱۰۰٪ شکستخورده
`NUMERIC_AUDIT_2026-11-12.md`: ۴۶٬۹۰۶ ردیف `ml_predictions` که **همگی** `prediction_failed=true` هستند. در کنار آن ۳٬۷۰۵ رکورد `signal_accuracy` با ۱۰۰٪ ارجاع یتیم و ۳٬۰۲۵ از ۳٬۰۲۸ معامله کاغذی بدون stop/target. **نتیجه:** جدیترین شکاف عددی کل سامانه؛ هیچکدام از متریکهای ML، دقت سیگنال یا مدیریت ریسک کاغذی تا تاریخ آن سند قابلاتکا نبودهاند. این یک باگ isolated نیست، بلکه نشانه «نوشتن بدون خواندن/بازبینی» در سه زیرسیستم موازی است.

### لایه ۱۳۰ — قرارداد خلوص ML
`.importlinter` شامل `phase0-ml-purity` است (در کنار `phase0-logging`, `phase0-no-cross-domain-repos`, `phase0-repositories-are-only-db-door-for-services`). CI آن را با `python scripts/quality_ratchet.py check --tool imports` اجرا میکند. هدف: جلوگیری از وابستگی لایه ML به `apps/` / `services/` / فریمورک HTTP. **نتیجه:** برخلاف اکثر لایهبندیها که فقط در مستنداتاند، این یکی توسط ابزار اعمال میشود؛ نقطه قوت معماری (لایه ۶۰–۷۲).

### لایه ۱۳۱ — jobs مرتبط ML و پرچمهای کیفیت
`jobs/definitions/` ۲۵ فایل پایتون با ۶۸ کلاس job (شمارش regex) شامل `feature_store_jobs.py` و `model_retraining`؛ `apps/api/app.py` در lifespan تابع `_ml_model_preload()` دارد تا مدلها پیش از اولین درخواست گرم شوند. **نتیجه:** preload + LRU + invalidate سهگانهای منسجماند؛ تنها کمبود، نبود متریک «تعداد نمادهای بدون artifact» در `monitoring/model_performance.py` است.

### لایه ۱۳۲ — جمعبدندی ML
داراییها: ۱۱۸ ماژول، امضای HMAC، گارد خلوص، رجیستری نسخهدار، حلقه بازآموزی، preload. بدهیها: چهار رجیستری موازی، feature store غیردورهای، سکوت در نبود artifact، و از همه مهمتر **خروجی تاریخی ۱۰۰٪ شکستخورده**. **نتیجه:** امتیاز «زیرساخت ML» بالا و «اعتبار نتایج ML» نزدیک صفر — تمایزی که `AUDIT_REPORT_2026-11-12.md` (میانگین ۶٫۸/۱۰) بهخوبی منعکس نکرده است.

---

# فصل L — لایه ۱۳۳ تا ۱۴۲: تستها، کیفیت و زنجیره CI/CD

### لایه ۱۳۳ — ابعاد پوشه تست
**۶۶۴ فایل تست / ۷٬۴۳۷ تابع تست** در برابر ادعای ۲۵۰ در `README.md` (۲٫۷×). توزیع: `tests/unit/` **۵۱۳**، `tests/gold_desk/` **۴۹**، `tests/legacy/` **۲۲**، `tests/integration/` **۱۶**، `tests/e2e/` **۱۰**، `tests/performance/` **۸**، `tests/iran_market_data/` **۷**، `tests/fixtures/` **۵**، `tests/comprehensive/` **۱**، `tests/load/` **۰**. **نتیجه:** حجم تست چشمگیر است، ولی ۷۷٪ آن unit و تنها ۱۶ فایل integration و ۱۰ فایل e2e است؛ پوشش «تعامل بین سرویسها» بهنسبت ضعیف است.

### لایه ۱۳۴ — پیکربندی pytest و پنج marker
`pyproject.toml`: `addopts = ["--capture=no", "-m", "not needs_db"]`, `asyncio_default_fixture_loop_scope = "session"`, `asyncio_default_test_loop_scope = "session"`. پنج marker تعریفشده: `performance`, `e2e`, `integration`, `slow`, `needs_db` («requires a live PostgreSQL instance; skipped when unreachable»). **نتیجه:** پیشفرض محلی تستهای نیازمند DB را حذف میکند؛ یعنی `pytest` ساده محلی با `pytest CI` معادل نیست — تفاوتی که باید در `CONTRIBUTING` برجسته شود.

### لایه ۱۳۵ — `conftest.py` و سه تنظیم پنهان
`tests/conftest.py` پیش از هر import اپ: `os.environ.setdefault("ENV", "test")` (غیرفعالسازی bypass نرخ)، `os.environ.setdefault("ENABLE_CSRF", "false")` (چون httpx client هدر Origin نمیفرستد)، و `pytest_collection_modifyitems` برای auto-skip هوشمند `needs_db` با یکبار بررسی اتصال. همچنین `_reconfigure_stream` خروجی ویندوز را UTF-8 میکند تا متن فارسی `UnicodeEncodeError` ندهد. **نتیجه:** تستسuite عملاً محیط اجرای متفاوتی از پروداکشن میسازد (CSRF خاموش، rate limit خاموش)؛ بنابراین تستها رفتار میانافزارها را پوشش نمیدهند.

### لایه ۱۳۶ — شغل Lint & Typecheck
`.github/workflows/ci.yml` job `lint` (Python 3.11 / Node 20) بهترتیب: `ruff`, «Import contracts (ratchet — new violations fail)», «Typecheck Python (ratchet)», «Typecheck core/security (strict, blocking)», «Typecheck src/gold_desk (strict ratchet)», «Production config gate (prod-check)», چهار مرحله Dockerfile lint، سپس `tsc --noEmit` و Vitest فرانتاند، و دو مرحله secret scan. **نتیجه:** گستردهترین جاب CI؛ نکته کلیدی آن است که «سختگیری» فقط برای `core/security` مطلق است و بقیه بهصورت **ratchet** (جلوگیری از بدتر شدن) اعمال میشود.

### لایه ۱۳۷ — فلسفه ratchet و خروجی ۲
`scripts/quality_ratchet.py` docstring: «Snapshot the current debt once, then fail only when a violation grows»؛ کلید mypy `(file, error-code)` بدون شماره خط تا ریفکتورها baseline را نلرزانند؛ baseline در `ci/quality_baseline.json`؛ **«Exit codes: 0 = no regression, 1 = regression, 2 = the tool itself failed (a broken gate must never read as a pass)»**. کامنتی هم توضیح میدهد که گام قدیمی `domain` را پاس میداد در حالی که در `[tool.mypy].exclude` بود و با `|| true` مخفی میشد. **نتیجه:** درسگرفتن مستند از یک باگ CI قدیمی؛ بالغترین بخش فرایند کیفیت.

### لایه ۱۳۸ — شغل Backend Tests
`ci.yml:228-327`: گارد پاریتی (لایه ۱۱۴) → `pytest tests/unit --cov=. --cov-report=xml --timeout=60 -x -v` → `pytest tests/gold_desk --timeout=120 -v` (با توضیح صریح «I5 — این تستها در هیچ مرحلهای اجرا نمیشدند» و `GOLD_API_TOKEN_SALT: ci-only-salt-not-a-real-secret`) → Codecov با `fail_ci_if_error: false` → «Celery chain integration (real broker)» با worker subprocess واقعی. **نتیجه:** `-x` یعنی اولین شکست کل جاب را متوقف میکند؛ پوشش خوب، ولی آپلود coverage غیرمسدودکننده و پوشش `tests/legacy`/`e2e`/`performance` در CI اصلی دیده نمیشود.

### لایه ۱۳۹ — جاب `needs-db`
job جداگانه `needs-db` با سرویس TimescaleDB، «Enable TimescaleDB extension»، «Migrate database» (اجرای ۹۴ مهاجرت) و «Run needs_db tests». وجود این جاب یعنی مهاجرتها بهصورت عملی روی دیتابیس خالی صحتسنجی میشوند، نه فقط بهصورت گراف AST (لایه ۷۶). **نتیجه:** تنها نقطهای که انسجام ۹۴ مهاجرت بهصورت اجرایی اثبات میشود؛ حذف آن، بالاترین ریسک رگرسیون دیتابیس را ایجاد میکند.

### لایه ۱۴۰ — جاب Docs و قرارداد نمودار
job `docs` با «Install jsdom (for mermaid.parse sandbox)» و «Check Mermaid diagram syntax». `.github/workflows/ci-pr.yml` علاوه بر آن شامل benchmark با `continue-on-error` است. شش workflow موجود: `ci.yml`, `ci-pr.yml`, `decision-engine.yml`, `fund-service.yml`, `release.yml`, `secrets-scan.yml`. **نتیجه:** حتی نحو نمودارهای مستندات گیت میشود، ولی **محتوای عددی همان مستندات** نه (لایه ۱) — دقیقاً وارونهای از اولویت واقعی.

### لایه ۱۴۱ — مرز مسدودکننده / توصیهای
مسدودکننده: Ruff، import ratchet، mypy ratchet، `mypy core/security --strict`، prod-config gate، secret scan «owned scope» ( blocking )، تستها، Docker build. **غیرمسدودکننده**: secret scan «full tree» با `continue-on-error: true`، benchmark در `ci-pr.yml`، Codecov `fail_ci_if_error: false`، و محلی `Makefile` تایپچک با `mypy ... || true`. همچنین `Makefile` هدف `lint: ruff check . --fix` فایلها را تغییر میدهد. **نتیجه:** مرز «امنیت مالکیتی‌شده» مسدود است و «امنیت کل مخزن» توصیهای؛ شکافی قابلدفاع ولی باید صریحاً پذیرفته شود.

### لایه ۱۴۲ — آنچه CI پوشش نمیدهد
`ruff_remediation_report.md`, `AUDIT_REPORT` و `DEEP_REVIEW_PART2` موضوع «CI gates not blocking» را مطرح کردهاند؛ بررسی مستقیم نشان میدهد گیتها اکنون تا حد زیادی مسدوداند. باقیماندهها: `tests/legacy/` (۲۲)، `tests/e2e/` (۱۰)، `tests/performance/` (۸)، `tests/load/` (۰ فایل)، Frontend `eslint` بهعنوان جاب مستقل CI (فقط `lint` محلی)، و ۴۷ هاردکد ۲۵۲ (لایه ۶). **نتیجه:** پیشرفت محسوس نسبت به گزارشهای قبل؛ ریسک باقیمانده «شکاف پوشش» است، نه «گیت خاموش».

---

# فصل M — لایه ۱۴۳ تا ۱۵۰: فرانتاند، قرارداد API و تجربه کاربر

### لایه ۱۴۳ — پشته فرانتاند
`frontend/package.json`: `next 16.4.1`، `react/react-dom 19.2.4`، `@tanstack/react-query ^5.101.0`، `recharts ^3.8.1`، `lightweight-charts ^5.2.0`، `framer-motion ^12.43.0`، `@sentry/nextjs ^10.75.2`، `xlsx ^0.18.5`، `typescript ^5`، `vitest ^4.1.12`، Tailwind 4. اسکریپتها: `dev`, `build: node scripts/build-with-heap.js` (نشانه تنظیم دستی حافظه heap هنگام بیلد)، `start`, `lint: eslint`, `test: vitest run`. `next.config.ts` با `output: "standalone"` و `outputFileTracingRoot` به ریشه مخزن و `optimizePackageImports` برای پنج کتابخانه سنگین. **نتیجه:** پشتهای مدرن و بهروزیافته، همراه با نشانههای فشار حافظه در بیلد.

### لایه ۱۴۴ — ۱۵۳ صفحه در برابر ادعای ۸۸
`frontend/src/app/` بیش از ۵۰ پوشه مسیر (`admin`, `alerts`, `alpha`, `armor`, `backtest`, `brsapi`, `codal`, `decision-engine`, `gold`, `macro`, `market-depth`, `multi-market-signals`, `options`, `paper-trading`, `predictions`, `pre-buy`, ...) و **۱۵۳ فایل `page.tsx`**؛ کل فایلهای `.tsx` فرانتاند **۴۰۹**. `README.md` میگوید ۸۸ صفحه (+۷۴٪ اختلاف). `frontend/src/components/` دهها کامپوننت تکفایل بهعلاوه زیرپوشههای `admin/`, `app/`, `charts/`, `DebugPanel/`. **نتیجه:** گستردگی UI از API هم جلو زده؛ نگهداری ۱۵۳ صفحه بدون «Route registry» مرکزی (`nav-config.tsx` تا حدی این نقش را دارد) ریسک صفحات یتیم/تکراری را بالا میبرد.

### لایه ۱۴۵ — پروکسی سمت سرور و عدم نشت `API_URL`
`next.config.ts` دو `rewrite` دارد: `/api/v1/currency/:path*` → `currency:8002` (باید **پیش از** catch-all باشد، کامنت صریح) و `/api/v1/:path*` → `api:8000`. نکته امنیتی مهم: «API_URL is NOT a NEXT_PUBLIC_* var, so it never leaks to the browser». `allowedDevOrigins` پیشفرض `127.0.0.1`. `instrumentation.ts`, `instrumentation-client.ts`, `sentry.server.config.ts`, `sentry.edge.config.ts` و `withSentryConfig` (غیرفعال بدون `SENTRY_AUTH_TOKEN`) لایه observability اند. **نتیجه:** طراحی صحیح BFF؛ تنها ناسازگاری، برخورد پورت ۸۰۰۲ بین `currency` و `decision-engine` است (لایه ۱۵۲).

### لایه ۱۴۶ — پاکت پاسخ و خطای سهحالته
`frontend/src/lib/api-envelope.ts` کامنت کلیدی: `schemas/common/responses.py::ApiResponse` تقریباً همه routeها را در `{success, data, error, message, data_as_of, cache_hit}` میپیچد و «سه وضعیت برای خانهای که فقط `data` را میخواند یکسان بهنظر میرسند: (۱) موفق + ردیف، (۲) موفق + آرایه خالی، (۳) `success:false` شکست منبع». `extractArray()` حالتهای ۲ و ۳ را به `[]` فرو میکاست و صفحه «empty» یا «mock data» نشان میداد؛ `apiRequest()` اکنون روی (۳) exception میدهد. **نتیجه:** نمونهای کمیاب از رفع یک باگ **معناشناسی API** در لایه کلاینت، مستندشده در کد؛ مستقیماً به یافتههای `DATA_500_PROBLEMS_REPORT.md` درباره `isLive` مربوط است.

### لایه ۱۴۷ — تازگی داده و انحراف ساعت
همان فایل: `DEFAULT_FRESHNESS_MS = 5 * 60 * 1000` («همراستا با `isDataFresh` داشبورد») و `FUTURE_SKEW_MS = 2 * 60 * 1000` («اختلاف ساعت سرور/مرورگر که هنوز «آینده» محسوب نمیشود»). `ApiEnvelopeMeta` شامل `success: boolean | null` (null یعنی پاسخ پاکتندارد) و `dataAsOf`. `frontend/src/lib/market-mock.ts` و `PagePlaceholder.tsx` نشان میدهند fallback ماک همچنان در برخی صفحات زنده است. **نتیجه:** تازگی ۵ دقیهای در برابر `NUMERIC_AUDIT` (جداول `data_freshness` و `data_gaps` صفر ردیف) یعنی معیار تازگی فقط سمت کلاینت اعمال میشود، نه از سرور.

### لایه ۱۴۸ — هوکها، Query و بلادرنگ
`frontend/src/hooks/` **۲۰ هوک**: `useWebSocket`, `useGoldWS`, `useMarketData`, `useClientData`, `useFundNavEngine`, `useFundLedger`, `useFundIntraday`, `useFundCompliance`, `useSyncSettings`, `usePrecomputeStatus`, `useApiMonitor`, `useDebugLogs`, `useBackgroundBackfill`, `useNotifications`, `useTheme`, ... . `providers.tsx` (QueryClient), `notification-provider.tsx`, `csrf.ts`, `api-errors.ts`, `auth-context.tsx`, `persona-context.tsx`, `RoleGate.tsx`. سمت سرور تنها `apps/api/endpoints/websocket.py` و ۲ route WebSocket (لایه ۳۰) وجود دارد. **نتیجه:** معماری داده کلاینت غنی، ولی تکیه بر polling/Query بهمراتب بیشتر از WS است؛ ۲ route WS برای ۱۵۳ صفحه کم است.

### لایه ۱۴۹ — تستهای فرانتاند و نمودارها
`frontend/src/__tests__/` **۸۰ فایل**، بهعلاوه تستهای colocated مانند `lib/dates.test.ts`, `lib/pre-buy.test.ts`, `lib/gold-silver-spec.test.ts`, `lib/seeded-random.test.ts`. CI مرحله «Frontend unit tests (vitest)» و `tsc --noEmit` را اجرا میکند؛ `eslint.config.mjs` و فایلهای `lint_report.txt`, `eslint_report.json`, `lint_full.txt`, `frontend_out.txt`, `output.txt` در ریشه فرانتاند باقیاند. **نتیجه:** پوشش تست معقول، ولی ۸۰ تست در برابر ۴۰۹ کامپوننت (≈۲۰٪) و نبود تست بصری/اسنپشات برای ۹ نمودار مختلف.

### لایه ۱۵۰ — بقایای طراحی و موبایل
`frontend/DESIGN_NOTES.md`, `PERSONAS.md`, `capacitor.config.ts`, `package.cap.json`, `Dockerfile.dev` (مسیر موبایل/کاپاسیتور)، و فایلهای HTML ایستای `s3.html`, `s4.html`, `s5.html`, `s6.html`, `s7.html`, `silver2.html`, `silver_check.html`, `s3.html` در ریشه فرانتاند، همراه `dashboard_live.png`. **نتیجه:** حداقل سه نسل رابط (HTML ایستا → Next.js → Capacitor) همزمان در مخزناند؛ پاکسازی بدون تأثیر بر runtime، کمهزینهترین کاهش بدهی فنی کل پروژه است.

---

# فصل N — لایه ۱۵۱ تا ۱۵۶: استقرار، عملیات و پایش

### لایه ۱۵۱ — توپولوژی پیشفرض compose
`docker-compose.yml` هفت سرویس: `timescaledb`, `redis`, `api`, `ingestion`, `worker`, `currency`, `frontend`. متغیرهای اجباری با الگوی `${VAR:?...}` (شامل `GOLD_API_TOKEN_SALT`), `JOB_QUEUE_ENABLED=true`. سرویس MinIO **کامنت شده**، در حالی که `integrations/object_store.py` و `brsapi/json_sink.py` به ذخیرهساز شیئی اشاره دارند. ریشه `Dockerfile` مربوط به collector ingestion است و `Dockerfile.api` مربوط API — تمایزی که بهراحتی اشتباه خوانده میشود. **نتیجه:** استقرار پیشفرض کامل نیست (object store غایب)؛ `brsapi/json_sink` یا به فایل مینویسد یا در پروداکشن بیصدا شکست میخورد.

### لایه ۱۵۲ — نه Dockerfile و برخورد پورت
`Dockerfile` → `python -m ingestion.main`؛ `Dockerfile.api` → `uvicorn apps.api.app:app:8000`; `Dockerfile.worker` → `python -m apps.worker`; `Dockerfile.scheduler` → `python -m apps.scheduler`; `Dockerfile.admin` → `admin_app:8001`; `Dockerfile.currency` → `currency_app:8002`; `Dockerfile.decision-engine` → `app:8002`; `Dockerfile.frontend` → `node server.js`; `Dockerfile.golddesk` → `python -m apps.scheduler.app --only gold_desk`. CI ماتریس بیلد پنج تارگت (`api`, `frontend`, `worker`, `admin`, `scheduler`) را میسازد. **نتیجه:** دو اپ روی ۸۰۰۲ و غیاب `decision-engine` در ماتریس بیلد؛ همچنین `Dockerfile.golddesk` اجرای `apps.scheduler.app` بهعنوان ماژول (`-m`) است در حالی که سایرین از شیء `app` استفاده میکنند.

### لایه ۱۵۳ — تکینگیهای اجرایی شکسته
`Makefile: worker → python -m jobs.worker` (**فایل وجود ندارد**؛ ورودی معتبر `python -m apps.worker` است). `apps/strategy_worker/__init__.py` ماژول ناموجود `apps.strategy_worker.app` را import میکند و پوشه فقط همان یک فایل را دارد. `apps/api/main.py` صفر بایت است. `jobs/README.md` و `apps/api/README.md` این تمایزها را توضیح نمیدهند. **نتیجه:** چهار نقطه «مرده» که توسعهدهنده جدید را به خطا میاندازد؛ همگی بیهزینه و بدون تغییر رفتار قابلحذف/تصحیحاند.

### لایه ۱۵۴ — لایه پایش و مشاهدهپذیری
`core/logging/` هفت ماژول (`setup`, `formatters`, `filters`, `correlation`, `context`, `request_logging`, `audit_logging`)، `core/observability_sentry.py`، `apps/api/metrics.py` (Middleware متریک)، `monitoring/` پانزده ماژول (`health.py`, `data_freshness.py`, `drift.py`, `model_performance.py`, `job_monitor.py`, `sla.py`, `incidents.py`, `gold_monitor.py`, `fx_monitor.py`, `logs.py`, `profiling.py` + `alerts/`, `dashboards/`, `metrics/`, `tracing/`), `integrations/observability/prometheus_exporter.py`، `prometheus.yml`, `monitoring/golddesk-prometheus.yml`، و Sentry در هر دو سمت. **نتیجه:** کمبود ابزار پایش وجود ندارد؛ مشکل دقیقاً لایه ۸۳/۱۲۹ است — جداول و متریکهایی که این ابزارها باید پر کنند (`data_freshness`, `data_gaps`, `decision_results`) در DB زنده صفر ردیفاند.

### لایه ۱۵۵ — سلامت پراکنده و دروازه آمادگی بلااستفاده *(اصلاحشده در بررسی جزءبهجزء)*
شش نقطه سلامت یافت شد: `apps/api/endpoints/health.py:18`, `brsapi.py:44 /health`, `forecast_engine.py:33 /health` («Redis + registry»), `gold.py:320 /futures/health`, `news.py:508 /sources/health`, `codal_professional.health_score`. **تصحیح:** برخلاف ادعای اولیه، `/api/v1/health/ready` **وجود دارد** و بهدرستی DB و Redis را جداگانه چک کرده و هنگام خرابی ۵۰۳ میدهد؛ `/health/live` و `/health/full` نیز موجوداند. اشکال واقعی دو تاست: (۱) `full_health()` متغیر `overall` را **فقط** هنگام خرابی DB تغییر میدهد (خط ۱۰۸)، پس خرابی Redis یا BrsApi همچنان `success=True, status="ok"` و HTTP ۲۰۰ برمیگرداند؛ (۲) `docker-compose.yml` برای `timescaledb`, `redis`, `worker`, `currency`, `frontend` هلثچک دارد ولی **برای سرویس `api` هیچ هلثچکی تعریف نکرده**، بنابراین `/ready` در استقرار پیشفرض هیچ مصرفکنندهای ندارد. **نتیجه:** ابزار آمادگی ساخته شده ولی نه کامل وصل است و نه محاسبهاش درست — ریسک «ترافیک به سرویس نیمهمرده». **تکمیل قسمت ۰۳ (`CFG-07`):** همین اشکال در `docker-compose.production.yml` هم هست؛ هلثچک سرویس `api` آنجا نیز `/api/v1/health` (liveness، همیشه ۲۰۰) را صدا میزند نه `/api/v1/health/ready`. یافته منحصر به محیط توسعه نیست.

### لایه ۱۵۶ — صف job در عملیات
`jobs/queue_consumer.py` docstring چهار مرحله: `BRPOP job:queue` (round-robin میان workerها) → راستیآزمایی token مشترک (پیام بدون token حذف و شمارش میشود) → `job_dispatcher` با قفل توزیعشده `JobLocking` (اجرای exactly-once حتی با چند رپلیکای scheduler) → شکست سخت تا `max_retries=3` در `job:retry` سپس `job:dead` (dead-letter) برای بررسی دستی. `_BENIGN_ERROR_MARKERS = ("Lock not acquired", "Duplicate")`. حالت `JOB_QUEUE_ENABLED=false` باعث idle شدن worker و اجرای in-process توسط scheduler میشود. `jobs/replay.py` بازپخش DLQ است. ۲۹ کرون در کامیت مبنا (`apps/scheduler/app.py`) — در حال حاضر (HEAD) ۳۲ جاب ثبت‌شده — در برابر ۱۹ ادعای README. **نتیجه:** قویترین طراحی عملیاتی مخزن؛ تنها ریسک، «صف dead-letter بدون هشدار» است چون `monitoring/job_monitor.py` باید آن را پایش کند و شواهدی از اتصال آن دیده نشد.

---

# فصل O — لایه ۱۵۷ تا ۱۶۰: ماتریس ریسک، بدهی فنی، نقشه راه و حکم نهایی

### لایه ۱۵۷ — ماتریس ریسک (اولویتبندی بر پایه شواهد)

| # | ریسک | شدت | شاهد | وضعیت |
|---|---|---|---|---|
| R1 | نتایج تاریخی ML/سیگنال/بکتست بیاعتبار | 🔴 بحرانی | ۴۶٬۹۰۶ پیشبینی `failed`، ۳٬۷۰۵ دقت یتیم، ۷٬۸۰۵ ران بدون trade | در حال رفع (`603059da`, `9b44797b`)؛ **backfill لازم است** |
| R2 | تصمیمگیری بر اساس اسناد منسوخ | 🔴 بحرانی | ۱۴ سند ریشه + ۴۰+ سند `docs/`؛ `ARCHITECTURE.md` مربوط به زیرپروژه دیگر | باز |
| R3 | جدولهای پایش خالی | 🟠 بالا | ۱۱۸/۲۳۲ جدول خالی؛ `data_freshness`/`data_gaps`/`decision_results` صفر | باز |
| R4 | تعرفه ۱۴۰۵ بدون تاریخ بازبینی | 🟠 بالا | `config/backtest_costs.yaml` «Re-verify before live use» | باز |
| R5 | ۵۰ هاردکد ۲۵۲ در برابر `core/trading_constants` (در ۲۸ فایل) | 🟠 بالا | `backtesting/`, `src/forecasting/`, `options_ml_service.py`, `domain/options/` | نیمهرفعشده |
| R6 | برخورد پورت ۸۰۰۲ و MinIO غایب | 🟠 بالا | `Dockerfile.currency` / `Dockerfile.decision-engine`؛ compose کامنت | باز |
| R7 | ۷ router عمداً mount نشده + ۱ ماژول کمکی | 🟡 متوسط | `monitoring`, `proposals`, `scanner`, `sentiment`, `symbol_alerts`, `ime`, `comprehensive_analysis` (API-05)؛ `backtest_requests.py` فاقد `APIRouter` است | تصمیم آگاهانه (API-05) |
| R8 | چهار تکینگی اجرایی مرده | 🟡 متوسط | `make worker`, `strategy_worker`, `apps/api/main.py`, ۲×۸۰۰۲ | باز |
| R9 | `ML_ALLOW_UNVERIFIED_MODELS` / `BRSAPI_ENABLED=false` | 🟡 متوسط | escape hatch صریح در کد | پذیرفتهشده، نیازمند پایش |
| R10 | ۵٫۲ GB `transactions.db` و clone کامل worktree | 🟢 کم | ریشه مخزن + `.workbuddy-ai/` محافظتشده | باز |
| R11 *(قسمت ۰۳)* | گیت production هرگز فعال نمیشود | 🔴 بحرانی | `CFG-01`: `docker-compose.production.yml` فاقد `ENV=production`؛ هفت شرط `validate_production()` در خط ۴۹۱ رد میشوند | ✅ **بسته شد** در `d6962d0a` (`ENV: production` در `:22`) |
| R12 *(قسمت ۰۳)* | پیکربندی/اسرار استقرار ناوصل | 🟠 بالا | `CFG-02` (پوشه `secrets/` همچنان ناموجود، هیچ خواننده `/run/secrets`)، `CFG-03/04`, `CFG-17/18` | **نیمهباز**: `CFG-03/04/07/17/18` بسته شدند؛ `CFG-02` باز است |
| R13 *(قسمت ۰۴)* | استقرار پایگاه داده تولید قابل بوت نیست | 🔴 بحرانی | `DB-01`: سرویس `postgres` در `docker-compose.production.yml:118` فاقد `image` / `build` / `extends`؛ `DB-02`: ده `create_hypertable()` بیگارد در `0001` و هیچ `CREATE EXTENSION` در استقرار (فقط سه ورکفلو CI) | **باز** |
| R14 *(قسمت ۰۴)* | رجیستری ناقص ORM و بازگشتناپذیری مهاجرت | 🟠 بالا | `DB-03/04`: ۴۱ جدول (۲۷٫۵٪) وارد `Base.metadata` نمیشوند و `--autogenerate` میتواند حذفشان را پیشنهاد دهد؛ `DB-05/06`: شش `downgrade()` تهی و صفر فراخوان `alembic downgrade` در کل مخزن | **باز** |

**نتیجه:** برخلاف لحن `AUDIT_REPORT_2026-11-12.md`، هیچ «باگ محاسباتی بحرانی زنده» در کد فعلی یافت نشد؛ بحرانیترین چیزها **داده تاریخی بیاعتبار** و **اسناد گمراهکننده**اند.

### لایه ۱۵۸ — دفتر بدهی فنی ساختاری
دو درخت مهاجرت (`migrations/versions/` ۹۴ فایل + `migrations_backup_20261030/` ۹۲ فایل)؛ **تکهتکهبودن پیکربندی** (تصحیح قسمت ۰۳: `core/config/__init__.py` با **۵۵۳ خط / ۱۱۸ فیلد / ۶۰ `Field` / ۸ validator / ۲۱۷ ارجاع در ۱۸۷ فایل**، در برابر **۱۸ زیرکلاس `BaseSettings`**، **شش مسیر خواندن `.env`**، **چهار فایل env**، **هفت فایل YAML** و **سه سیستم پرچم** که دوتایش مردهاند)؛ چهار رجیستری ML؛ دو «Decision Engine» (لایه ۱۰۵)؛ سه نسل screener (لایه ۱۰۴)؛ چهار اسکیم آپشن (لایه ۱۰۷)؛ سه نسل رابط (لایه ۱۵۰)؛ ۱۱ بسته `domain/` بلامصرف (لایه ۵۱)؛ ۵۱ فایل BOM و ۲ خطای نحوی واقعی در `code_dump/20_scripts/`؛ ۱٬۸۰۹ `except Exception`، ۳٬۹۵۳ `print(`) و ۱۷۳ الگوی f-string SQL. **نتیجه:** الگوی تکرارشونده «افزودن لایه جدید بهجای حذف لایه قدیم»؛ دلیل اصلی فاصله اعداد README تا کد زنده همین است.

### لایه ۱۵۹ — نقشه راه پیشنهادی (بدون هیچ تغییر کد)
1. **فوری** — backfill/بازاجرای `ml_predictions`، `signal_accuracy` و `backtest_trades` یا علامتگذاری صریح ردیفهای قدیمی بهعنوان `invalidated`، تا هیچ داشبوردی عدد بیاعتبار نشان ندهد.
2. **فوری** — تکمنبع کردن اعداد: انتقال جدول «اندازهگیریهای سخت» این گزارش به `docs/INDEX.md` و ساخت یک چک CI که اعداد `README.md` را با شمارش واقعی مقایسه کند (الگوی `scripts/_verify_readme.py` از قبل موجود است).
3. **کوتاهمدت** — بازنویسی `ARCHITECTURE.md` بر اساس `apps/ + core/ + domain/ + services/ + Docker + Next.js` و آرشیو کردن ۵ سند حسابرسی ریشه با برچسب «superseded».
4. **کوتاهمدت** — حذف/تصحیح چهار تکینگی اجرایی، رفع برخورد ۸۰۰۲، **وصل کردن هلثچک سرویس `api` در هر دو compose به `/health/ready`** و اصلاح محاسبه `overall` در `/health/full`، وصل کردن `monitoring/job_monitor.py` به `job:dead`؛ و پیش از همه **ست کردن `ENV=production` در anchor تولید و تکمیل `.env.production` / `.env.example`** (`CFG-01`…`CFG-04`) که بدون آن بقیه گیتها اصلاً اجرا نمیشوند.
5. **میانمدت** — جایگزینی ۵۰ هاردکد ۲۵۲ (در ۲۸ فایل) با `core/trading_constants`، حذف ۲ موتور deprecated بکتست، ادغام چهار رجیستری ML، و تعیین تکلیف ۱۱ بسته `domain/` بلامصرف.
6. **میانمدت** — تبدیل secret scan «full tree» و benchmark از advisory به ratchet (نه مسدود مطلق)، و افزودن `tests/e2e`/`legacy` به یک جاب شبانه.
7. **مستمر** — تعیین مالک و `last_updated` برای تعرفهها، `acceptance.yaml` و `fee_schedule.provenance` باقیمانده `assumption`.

**نتیجه:** ترتیب بر اساس «اثر بر صحت تصمیم مالی» است، نه سهولت اجرا؛ بند ۱ و ۲ تقریباً بدون ریسک و بیشترین بازده را دارند.

### لایه ۱۶۰ — حکم نهایی و محدودیتهای روش
سامانه TEMCE از منظر **معماری و انضباط مهندسی** پروژهای بالغ است: لایهبندی DDD با قراردادهای اعمالشده، ۹۴ مهاجرت خطی تکhead، مدل هزینه تکمنبع با گارد پاریتی در CI، ratchet کیفیت با «خرابی ابزار = شکست»، fail-closed مالی در یازده دروازه تصمیم، صف Redis با قفل توزیعشده و DLQ، و ۶۶۴ فایل تست. امروز ۴۱ کامیت عمدتاً `fix(...)` نشان میدهد تیم دقیقاً در فاز بستن شکافهای عددی است و سه یافته P0 گزارش قبل عملاً رفع شدهاند.

از منظر **اعتبار خروجیهای تحلیلی** اما سامانه هنوز در وضعیت «زیرساخت آماده، داده تاریخی نامعتبر» است: ۵۰٫۱۷ GiB دیتابیس با نیمی جداول خالی، ۱۰۰٪ پیشبینیهای شکستخورده، رانهای بکتست بدون معامله، و جداول تازگی صفر. بنابراین **خطر اصلی نه خرابی کد، بلکه اعتماد به اعداد قدیمی و به مستندات منسوخ است**.

**محدودیتها:** این تحلیل ایستا است؛ تست کامل اجرا نشد، به DB زنده متصل نشدیم، سرور بوت نشد، و رفتار زماناجرا (نرخ خطای واقعی BrsApi، مصرف حافظه بیلد Next، تأخیر صف) راستیآزمایی نشد. اعداد «داده زنده» از `NUMERIC_AUDIT_2026-11-12.md` و `OPTIONS_DEEP_ANALYSIS_2026-11-13.md` نقل و با کد/کامیتها تطبیق داده شدند، نه مستقیماً از DB پرسوجو شدند. ۶ فایل ازپیش اصلاحشده در `git status` (`backtesting/metrics/performance.py`, `backtesting/position_manager.py`, `backtesting/types.py`, `jobs/definitions/__init__.py`, `jobs/definitions/feature_store_jobs.py`, `providers/macro_sources/fmp.py`) **لمس نشدند**.

> ✅ **تعهد نهایی:** در تمام ۱۶۰ لایه، **هیچ فایل کدی، پیکربندی، تست، مهاجرت یا مستند موجودی تغییر نکرد**. تنها خروجی این پژوهش، همین فایل `DEEP_ANALYSIS_160_LAYERS_2026-11-13.md` است. تمام شمارشها با اسکریپتهای فقطخواندنی، پارس AST آگاه به BOM، و خواندن مستقیم فایلها بر روی کامیت `091fdf31` انجام شد.

---

## پیوست — فهرست منابع بررسیشده

| دسته | منابع |
|---|---|
| اسناد حاکم | `acceptance.yaml`, `README.md`, `ARCHITECTURE.md`, `.importlinter`, `pyproject.toml`, `Makefile`, `config/backtest_costs.yaml` |
| حسابرسیهای پیشین | `AUDIT_REPORT_2026-11-12.md`, `DEEP_REVIEW_PART1.md`, `DEEP_REVIEW_PART2.md`, `NUMERIC_AUDIT_2026-11-12.md`, `OPTIONS_DEEP_ANALYSIS_2026-11-13.md`, `OPTIONS_MARKET_REPORT.md`, `DATA_500_PROBLEMS_REPORT.md`, `ruff_remediation_report.md` |
| کد اجرا | `main.py`, `apps/api/{app,router,dependencies,middleware,metrics,error_handlers,openapi_security,pagination}.py`, `apps/worker`, `apps/scheduler/app.py`, `ingestion/main.py` |
| دامنه و سرویس | `core/`, `domain/` (۳۴ بسته), `services/` (۱۶۳ فایل ریشه), `repositories/`, `schemas/`, `models/base.py` |
| داده و ML | `migrations/versions/` (۹۴), `providers/` (۲۵۱), `brsapi/`, `ml/` (۱۱۸), `jobs/` + `jobs/definitions/` (۲۵) |
| کیفیت و استقرار | `.github/workflows/` (۶), `ci/quality_baseline.json`, `scripts/quality_ratchet.py`, `tests/` (۶۶۴), `frontend/` (۱۵۳ صفحه / ۴۰۹ tsx / ۸۰ تست), ۹ `Dockerfile*`, `docker-compose.yml`, `prometheus.yml`, `monitoring/` |
| تاریخچه | `git log` (۳۹۸ کامیت، ۴۱ کامیت ۲۰۲۶-۱۱-۱۳)، `git status` (۶ فایل اصلاحنشده، دستنخورده) |

### تصحیحات حاصل از «بررسی قسمتبهقسمت» (۲۰۲۶-۱۱-۱۴)

بررسی عمیق جزءبهجزء (`deep_dive/`) تا پایان قسمت ۰۴ **هجده ادعای** این گزارش را دقیقتر کرد؛ متن لایههای مربوطه درجا اصلاح شد (قسمت ۰۳ یازده ردیف، قسمت ۰۴ هفت ردیف):

| لایه | ادعای اولیه | واقعیت تأییدشده |
|---|---|---|
| ۴۱ | «۸ ماژول router نصبنشده» | ۷ router نصبنشده (مطابق `API-05` و دو گارد تست) + `backtest_requests.py` که اصلاً `APIRouter` ندارد |
| ۱۵۵ | «نبود یک `/ready` واحد» | `/api/v1/health/ready` موجود و ۵۰۳ میدهد؛ اشکال واقعی: `full_health()` فقط خرابی DB را در `overall` لحاظ میکند و compose برای سرویس `api` هلثچک ندارد |
| ۱۵۹ | «افزودن `/ready` ترکیبی» | نیاز واقعی: وصل کردن هلثچک `api` به `/ready` موجود + اصلاح `overall`؛ و پیش از آن `ENV=production` |
| ۱۷ *(۰۳)* | «۵۵۴ خط، ~۱۲۰ فیلد، ۱۲۸ مصرفکننده» | ۵۵۳ خط، ۱۱۸ فیلد، ۲۱۷ ارجاع در ۱۸۷ فایل؛ `validate_production()` هفت شرط و شش نقطه فراخوان |
| ۱۸ *(۰۳)* | «۱۷ ماژول تنظیمات مرده» | ۳ ماژول زنده (`acceptance_loader`, `ime_engine`, `storage`) + ۱۴ صفرمصرفکننده؛ ۱۸ زیرکلاس `BaseSettings` در کل مخزن |
| ۱۹ *(۰۳)* | «`.env.production` فقط ۱۱ کلید» | ۹ کلید؛ فاقد پنج کلید الزامی، و `AUTH_COOKIE_SECURE` حتی در `.env.example` مستند نشده |
| ۲۰ *(۰۳)* | «دو سیستم feature flag، ۸ ارجاع» | سه سیستم؛ دوتا فقط self-import/تست، یکی (`Settings`) حاکم |
| ۹۴ *(۰۳)* | «MinIO غایب، `LAKE_ENDPOINT` به میزبان ناموجود» | علاوه بر آن پیشوند `LAKE_*` ≠ `INGESTION_LAKE_*` و گارد credential به دلیل نبود `ENV` خاموش است |
| ۱۵۵ *(۰۳)* | هلثچک فقط در compose توسعه | `docker-compose.production.yml` هم از liveness `/health` استفاده میکند (`CFG-07`) |
| ۱۵۸ *(۰۳)* | «دو سیستم تنظیمات» | ۱۸ زیرکلاس `BaseSettings` + شش مسیر `.env` + هفت YAML + سه سیستم پرچم |
| ۱۵۷ *(۰۳)* | ماتریس R1–R10 | دو ردیف تازه `R11` (گیت production خاموش) و `R12` (اسرار/استقرار ناوصل) افزوده شد |
| ۵ / ۱۵۸ *(۰۴)* | «۹۴ مهاجرت، head منفرد `0123`» | در HEAD `bfd1e78d`: **۹۵ ریویژن، head `0124`** (`0124_drop_historical_daily_backup`)؛ زنجیره همچنان خطی و تکhead است |
| ۲۱ / ۲۲ *(۰۴)* | «۱۴۹ موجودیت ORM» | عدد تأیید شد، ولی `models/__init__.py` تنها ۳۶ ماژول از ۵۱ ماژول را وارد میکند؛ **۴۱ جدول (۲۷٫۵٪) هرگز در `Base.metadata` ثبت نمیشوند** (`DB-03`) |
| ۷۶ / ۵۱۷ *(۰۴)* | «انسجام ۹۴ مهاجرت بهصورت اجرایی اثبات میشود» | CI فقط مسیر `upgrade` را اثبات میکند؛ `alembic downgrade` در کل مخزن **صفر** بار صدا شده و شش `downgrade()` بدنه `pass` دارند |
| ۱۵۵ *(۰۴)* | هلثچک compose | `CFG-07` در HEAD تازه بسته شد: `docker-compose.production.yml:63-64` اکنون `/health/ready` را صدا میزند |
| ۱۵۸ *(۰۴)* | «۱۸ زیرکلاس `BaseSettings` / ۱۴ ماژول مرده» | `2b4d9ddc` چهارده ماژول مرده را حذف کرد؛ `core/config/` اکنون فقط `__init__.py` + همان ۳ ماژول زنده شناساییشده در قسمت ۰۳ دارد |
| ۹۴ *(۰۴)* | MinIO / `LAKE_*` | `CFG-17/18` بسته شدند: `docker-compose.yml:98,104-106` اکنون `postgresql://` و `INGESTION_LAKE_*` میدهد |
| R11 / R12 *(۰۴)* | هر دو «باز» | `R11` بسته شد؛ `R12` نیمهباز (`CFG-02` همچنان باز)؛ دو ردیف تازه `R13` و `R14` افزوده شد |

### بهروزرسانی زنده حین تدوین سری جزءبهجزء (۲۰۲۶-۱۱-۱۴)

مخزن پس از کامیت مبنای این گزارش **۱۰ کامیت دیگر جلو رفت** (`091fdf31` → `9a100a6f`، ۵۷ فایل، ۴۶۸+/۱۳۶−). کامیتها عمدتاً دقیقاً ریسکهای جدول لایه ۱۵۷ را نشانه گرفتهاند:

| کامیت | ریسک | وضعیت |
|---|---|---|
| `102305fc` | R1 — ۴۶٬۹۰۶ پیشبینی شکستخورده | **کد** اصلاح شد (`services/inference_service.py` و ...)؛ ردیفهای تاریخی همچنان بیاعتباراند |
| `24d18cf1` | R3 — ۶ جدول پایش خالی | writer + `jobs/definitions/monitoring_snapshot_job.py` اضافه شد؛ جداول تا اولین اجرای job خالیاند |
| `11e5e39d` | R5, R8 — ۴ تکینگی اجرایی + ۴۷ هاردکد ۲۵۲ | `Makefile`, `apps/api/main.py`, `apps/strategy_worker/__init__.py` و ثابتها اصلاح شدند |
| `7bfd9937` | R5, R6 — برخورد پورت ۸۰۰۲ | `Dockerfile.decision-engine` اصلاح شد و **۱۹ هاردکد ۲۵۲ اضافی** یافت شد (جمعاً ۶۶، نه ۴۷) |
| `ded29624`, `82024866`, `4f4290ab`, `26660f89`, `b9d3c87f`, `9a100a6f` | jobها، بکتست، آپشن، fmp، تست طلایی | اصلاحات تکمیلی |

**این گزارش کماکان مبنای `091fdf31` است و اعدادش دستنخوردهاند**؛ جدول کامل تطبیق در `deep_dive/README.md` نگهداری میشود. تمایز حیاتی: **رفع کد ≠ پاکسازی داده تاریخی**. R1 و R3 اکنون «code-fixed / data-pending»اند و بند ۱ نقشه راه (backfill یا علامتگذاری `invalidated`) همچنان پابرجاست. همچنین فایلهای تحلیلشده در قسمتهای ۰۱/۰۲ (`apps/api/app.py`, `router.py`, `middleware.py`, `dependencies.py`, `health.py`, `docker-compose.yml`, ...) در این ۱۰ کامیت تغییر نکردهاند، بنابراین ۲۹ یافته تازه آنها در برابر HEAD فعلی زنده است.

**افزوده قسمت ۰۳ (۲۰۲۶-۱۱-۱۴):** `deep_dive/PART_03_config_secrets.md` با ۱۹ یافته `CFG-01`…`CFG-19`، اسکن AST پیکربندی (۱۸ زیرکلاس `BaseSettings`)، مقایسه چهار فایل env، بررسی دو compose و گیت CI، و ماتریس ریسک تجمیعی هفت خوشهای در `deep_dive/README.md`. دو حدس اولیه حین راستیآزمایی **رد** شدند: نبود کش در `acceptance_loader` (کش روی `_load` هست) و غلطبودن نام `INGESTION_DB_DSN` (نام درست است؛ مشکل scheme مقدار و پیشوند `LAKE_*` است). مخزن تا `d551242c` (۱۲ کامیت پس از مبنا) پیش رفت و `iran_market_data` ایزولاسیون env گرفت، ولی شش مسیر خواندن `.env` پابرجاست. **هیچ کدی تغییر نکرد.**

**افزوده قسمت ۰۴ (۲۰۲۶-۱۱-۱۴):** `deep_dive/PART_04_database_migrations.md` با ۲۰ یافته `DB-01`…`DB-20`، گراف AST دو درخت مهاجرت (۹۵ ریویژن / head `0124` در برابر ۹۰ ریویژن پشتیبان)، ممیزی رجیستری ۱۴۹ موجودیت ORM، پروفایل ۲۲۴ عملیات SQL خام و بررسی سه ورکفلو CI. چهار حدس اولیه **رد** شدند: خالیبودن `target_metadata` (واردات بسته `models/__init__.py` را اجرا میکند)، اجرای `CREATE INDEX CONCURRENTLY` در تراکنش (همه در docstringاند)، چندheadبودن زنده (پشتیبان بیرون از مسیر Alembic است) و برخورد ریویژن `0022` (`brsapi_0001` شدهاست). ماتریس ریسک تجمیعی در `deep_dive/README.md` به **۱۱ خوشه** رسید و ترتیب بستن به `H → B → J → I → E → G → K` تغییر کرد.

**مهمترین رویداد این فاز:** مخزن تا `bfd1e78d` (**۲۸ کامیت** پس از مبنا) پیش رفت و تیم با کامیتهای `d6962d0a` و `2b4d9ddc` — که صریحاً شناسههای `CFG-*` قسمت ۰۳ را در عنوان خود نام میبرند — هفت یافته آن قسمت را بست. `b3a196f1` نیز یافتههای `EX-*` / `HTTP-*` مربوط به ترتیب CORS، احراز هویت `/metrics` و هاردکد `api_prefix` را اصلاح کرد. بنابراین این سری دیگر صرفاً توصیفگر نیست، **محرک اصلاح است**؛ از قسمت ۰۴ به بعد وضعیت یافتههای قسمت قبل نیز بازخوانی میشود. اعداد مبنای `091fdf31` در متن ۱۶۰ لایه عمداً دستنخورده مانده و بهروزشوندگیها در جدول تصحیحات و `deep_dive/README.md` نگهداری میشوند. **هیچ کدی تغییر نکرد.**

**پایان گزارش — ۱۶۰ لایه، بدون تغییر کد.**

