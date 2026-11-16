# قسمت ۰۳ — پیکربندی، اسرار و محیط تولید

| | |
|---|---|
| **تاریخ** | ۲۰۲۶-۱۱-۱۴ |
| **کامیت مبنا** | `091fdf31` (بررسیشده در برابر `d551242c`) |
| **روش** | خواندن مستقیم، پارس AST، اسکریپت شمارش واردات روی ۳٬۵۴۴ فایل پایتون (با حذف worktree کلونشده)، مقایسه نام کلیدهای env **بدون خواندن/نقل مقادیر محرمانه**، تطبیق با `ci.yml` و دو فایل compose |
| **محدوده** | `core/config/` (۱۸ فایل), `core/feature_flags/`, `brsapi/config.py`, `ingestion/config.py`, `config/*.yaml`, `acceptance.yaml`, `.env*`, `docker-compose*.yml`, `core/observability_sentry.py` |
| **انجام نشد** | بوت در محیط production، `docker stack deploy`، خواندن مقادیر واقعی اسرار، اجرای `validate_production()` بهصورت زنده |

---

## ۱. نقشه منابع پیکربندی — هشت منبع همزمان

| # | منبع | حجم | وضعیت مصرف |
|---:|---|---:|---|
| ۱ | `core/config/__init__.py` → `Settings` | **۵۵۳ خط / ۱۱۸ فیلد / ۶۰ `Field()`** | ✅ **تکمنبع واقعی**: ۲۱۷ ارجاع در ۱۸۷ فایل |
| ۲ | `core/config/*.py` (۱۷ ماژول موازی) | ۹۹۳ خط | ⚠️ فقط ۳ ماژول زنده، **۱۴ تا کاملاً بلامصرف** |
| ۳ | `core/feature_flags/` + `core/config/feature_flags.py` | ~۱۵۰ خط | ❌ دو سیستم پرچم مرده |
| ۴ | `brsapi/config.py` → `BrsApiSettings` | ۵۴۰+ خط | ✅ زنده، `BRSAPI_` prefix |
| ۵ | `ingestion/config.py` → `IngestionConfig` | — | ✅ زنده، `INGESTION_` prefix |
| ۶ | فایلهای `.env*` | ۴ فایل | `.env` / `.env.example` / `.env.production` / بکآپ |
| ۷ | شش فایل YAML در `config/` + `acceptance.yaml` ریشه | — | ✅ `acceptance_loader` و `ime_engine` آنها را بار میکنند |
| ۸ | `apps/currency_service/config.py` → `CurrencyServiceSettings` | ۲۴ خط | ✅ زنده، `CURRENCY_` prefix، پیشفرض `port=8002` |

هیچ `[project.scripts]` یا نقطه پیکربندی واحدی وجود ندارد. **اسکن AST کل مخزن: ۱۸ زیرکلاس `BaseSettings` در ۱۸ فایل** — ۱۵ تای آنها در `core/config/` (شامل `Settings` زنده)، و `BrsApiSettings`, `IngestionConfig`, `CurrencyServiceSettings` بیرون از آن. پیکربندی بین این ۱۸ کلاس، **چهار فایل env**، **هفت فایل YAML** و **سه سیستم پرچم** پخش است و هیچ فرمانی فهرست کامل کلیدهای معتبر را تولید نمیکند.

---

## ۲. کالبد `Settings` (۵۵۳ خط)

```
خط ۱۴–۱۵   _REPO_ROOT / _ENV_FILE  ← لنگر انداختن .env به ریشه مخزن (نه CWD)
خط ۱۸–۳۸   _strip_inline_comment   ← کامنت # تنها وقتی حذف میشود که قبلش فاصله باشد؛ نقلقول محافظت میکند
خط ۴۱–۶۴   _parse_origin_list      ← پذیرش JSON لیست / رشته نقلقولشده / لیست کامایی
خط ۶۷–۷۴   SettingsConfigDict(env_file=..., case_sensitive=False, extra="ignore")
خط ۷۶–۴۱۴  ۱۱۸ فیلد
خط ۴۱۶–۴۷۲  ۸ validator  (بند ۱۲)
خط ۴۷۴–۵۴۴  ۷ property + validate_production()
خط ۵۴۷–۵۵۲  @lru_cache get_settings()  →  settings = get_settings()  (singleton سراسری)
```

**گروهبندی فیلدها:** هسته/سرور (۷۶–۸۲)، DB/Redis (۸۴–۹۳)، لاگ (۹۵–۹۷)، API/CORS/پراکسی (۹۹–۱۲۶)، ثبتنام و بوتاسترپ ادمین (۱۲۸–۱۳۵)، JWT/کوکی/CSRF/MFA (۱۳۷–۱۷۹)، ذخیرهسازی (۱۸۱–۱۸۷)، provider و **~۴۰ نگاشت نرخگیری** (۱۸۹–۲۵۳)، URLهای منبع داده (۲۵۵–۲۶۵)، ML (۲۶۷–۲۷۱)، بکتست (۲۷۳–۲۷۵)، پایش/Sentry (۲۷۷–۲۸۶)، ingestion/jobs/scheduler/DLQ (۲۸۸–۲۹۸)، **صف Redis job** (۳۰۰–۳۱۶)، **کاناری خواندن اخبار** (۳۱۸–۳۶۸)، Telegram (۳۷۳–۳۷۵)، قیمتهای تعدیلشده (۳۷۷–۳۸۷)، ویژگیهای طلا (۳۸۹–۴۱۴).

چهار نکته ساختاری:

- **`extra="ignore"`**: هر غلط املایی در نام متغیر محیطی **بیسروصدا نادیده گرفته میشود**. هیچ هشداری، هیچ لاگی. این مهمترین تفاوت رفتاری با `extra="forbid"` است و دلیل اصلی «کلید هست ولی اثری ندارد» در بند ۵.
- **`case_sensitive=False` + `populate_by_name=True`**: هم `ENV` و هم `environment` کار میکنند، ولی aliasها با پیشوند ماژولهای مرده (`DB_`, `SECURITY_`, ...) تداخل معنایی دارند.
- **`data_dir: str = str(Path.cwd() / "data")` (۱۸۵) و `ml_model_dir` (۲۶۷)**: برخلاف `_ENV_FILE` که به ریشه مخزن لنگر انداخته، این دو به **CWD** وابستهاند. اجرای همان کد از `scripts/` یا `tests/` دو مسیر داده متفاوت میسازد — ناهماهنگی مستقیم با کامنت خط ۱۱–۱۳.
- **`settings` یک شیء قابلتغییر سراسری است**: CI (`.github/workflows/ci.yml:121`) دقیقاً با `settings.environment='production'` آن را درون فرایند تغییر میدهد تا گیت تست شود. در تستها هم `monkeypatch.setattr(settings, ...)` رایج است؛ چون `@lru_cache` فقط ساخت نمونه را کش میکند، جهشها تا پایان فرایند باقی میمانند.

---

## ۳. `validate_production()` — هفت گیت، شش نقطه فراخوان، یک شکاف کشنده

```python
def validate_production(self) -> None:                       # :488
    if self.environment not in {"production", "staging"}:
        return                                              # ← دروازه ورود
    errors = []
    if secret_key == "change-me-in-production" ...  # ۱
    if auth_disabled ...                            # ۲
    if cors_origins == ["*"] ...                    # ۳
    if database_url.startswith("sqlite") ...        # ۴
    if not auth_cookie_secure ...                   # ۵
    if ws_allow_legacy_token is True ...            # ۶
    if otlp_endpoint is None ...                    # ۷
    raise RuntimeError(...)
```

هفت شرط (گزارش ۱۶۰ لایهای «۸ validator» گفته بود؛ منظورش validators کلاس بوده، نه شرطهای این تابع — تصحیح جزئی). فراخوانها واقعی و پراکندهاند: `apps/api/app.py:899` (در `try`، prod → `raise`، dev → warning)، `apps/admin/app.py:19`، `apps/currency_service/app.py:26`، `apps/decision_engine/app.py:147`، `apps/scheduler/__main__.py:21`، `apps/worker/__main__.py:19`. CI هم یک `prod-check` جداگانه با تمام متغیرها inline اجرا میکند.

**شکاف: خط ۴۹۱.** اگر `settings.environment` برابر `development` باشد، تابع **بیدرنگ برمیگردد** و هیچکدام از هفت بررسی اجرا نمیشود. تمام امنیت مربوط به تولید به یک متغیر محیطی واحد (`ENV`) گره خورده است که — همانطور که بند ۴ نشان میدهد — **در هیچ فایل استقراری تنظیم نشده**. این همان الگویی است که `apps/api/auth.py:18-33` صریحاً دربارهاش هشدار میدهد: «Authentication used to be gated on `is_production`, which made every non-production deployment an implicit auth bypass» (API-008). احراز هویت از آن دام رها شده، ولی **گیت پیکربندی همچنان در آن گرفتار است**.

---

## ۴. سیستم انتخاب محیطی که هرگز وصل نشد

`core/config/environments.py` (۲۹ خط):

```python
ENV_FILE_MAP = {
    DEVELOPMENT: ".env.development",
    STAGING:     ".env.staging",
    PRODUCTION:  ".env.production",
    TESTING:     ".env.testing",
}
def get_env_file(env=None) -> str: ...
```

اسکن ۳٬۵۴۴ فایل پایتون: **`get_env_file` صفر فراخوان، `ENV_FILE_MAP` صفر ارجاع خارج از خود فایل**. از چهار فایل نقشهشده فقط `.env.production` روی دیسک وجود دارد (۹ کلید) و آن هم فقط توسط `docker-compose.production.yml` بهعنوان `env_file` خوانده میشود — یعنی توسط **Docker**، نه توسط `Settings`.

و `Settings.model_config.env_file` در خط ۶۹ **ثابت** `str(_REPO_ROOT / ".env")` است. نتیجه زنجیره:

```
ENV تنظیم نشده  →  environment = "development"  →  Settings همیشه همان .env ریشه را میخواند
              →  validate_production() برمیگردد  →  docs_url=/docs, openapi_url=/openapi.json,
                 ws_legacy_token_enabled=True, auth_cookie_secure=False, is_development=True
```

`core/observability_sentry.py:87` هم `environment = "production" if settings.is_production else "development"` میگذارد، یعنی خطاهای استقرار production در Sentry با برچسب **development** ثبت میشوند.

---

## ۵. چهار فایل env — مقایسه کلیدها (بدون مقادیر)

| فایل | اندازه | کلید | تحت git | نقش |
|---|---:|---:|---|---|
| `.env.example` | ۱۱ KB | **۱۰۵** | ✅ تنها فایل tracked | مرجع مستند |
| `.env` | ۲٫۸ KB | **۲۰** | ❌ ignored | محلی / توسعه |
| `.env.production` | ۴۰۵ B | **۹** | ❌ ignored | `env_file` در compose تولید |
| `.env.bak.1790980646` | ۶٫۹ KB | — | ❌ ignored | بکآپ محلی |

| کلید حیاتی | `.env.example` | `.env` | `.env.production` |
|---|:---:|:---:|:---:|
| `ENV` | ✅ `development` | ❌ | ❌ |
| `SECRET_KEY` | ✅ (placeholder) | ✅ (۶۴ نویسه) | ❌ |
| `DATABASE_URL` | ✅ | ✅ | ❌ |
| `CORS_ORIGINS` | ✅ | ❌ | ❌ |
| `AUTH_COOKIE_SECURE` | **❌ مستند نشده** | ❌ | ❌ |
| `OTLP_ENDPOINT` | ✅ | ❌ | ❌ |
| `TRUSTED_PROXIES` | ✅ | ❌ | ❌ |
| `REGISTRATION_OPEN` | **❌ مستند نشده** | ❌ | ❌ |
| `JOB_QUEUE_TOKEN` | **❌ مستند نشده** | ❌ | ❌ |
| `GOLD_API_TOKEN_SALT` | ✅ | ✅ | ❌ (ولی compose `${:?}` میدهد) |

دو تناقض برجسته:

1. **`AUTH_COOKIE_SECURE` که `validate_production()` الزامی میداند، در هیچکدام از سه فایل env و حتی در `.env.example` وجود ندارد.** اپراتوری که طبق `.env.example` پیش برود، هنگام بالا آوردن production با شکست گیت مواجه میشود و راهحل را باید از سورس کد پیدا کند. CI همان کلید را inline پاس میکند (`AUTH_COOKIE_SECURE=true`)، پس تست هرگز این کمبود مستندات را نشان نمیدهد.
2. **`.env.production` فاقد `SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS`, `OTLP_ENDPOINT`, `AUTH_COOKIE_SECURE` است.** یعنی اگر `ENV=production` را درست تنظیم کنید، بوت با **حداقل ۴ خطا** شکست میخورد؛ و اگر تنظیم نکنید (وضعیت فعلی)، بوت میشود ولی در حالت development و بدون هیچ گاردی. پیکربندی تولید از دو طرف ناسازگار است.

کلیدهای `ENABLE_MARKET_DATA` و `ENABLE_HEATMAP` در `.env.production` **هیچ خوانندهای** در کل مخزن ندارند (جستوجو در `.py`, `.ts`, `.tsx`, `.yml`, `.yaml`). `.env.example` همچنین حاوی پیشفرضهای اعتباری توسعهای است (`LAKE_SECRET_KEY=minioadmin`, `ENCRYPTION_KEY=change-me-in-production`, `SECRET_KEY=change-me-in-production-use-strong-random-key`) — بیخطر تا وقتی کسی فایل را کپی و بدون تغییر استفاده کند.

---

## ۶. `docker-compose.production.yml` — چهار شکاف استقراری

| # | خط | مشکل |
|---:|---:|---|
| ۱ | anchor `x-app-prod` | `env_file: .env.production` + `environment:` شامل `SENTRY_*`, `GOLD_API_TOKEN_SALT`, `REGISTRATION_OPEN="false"` — **هیچ `ENV=production`ای وجود ندارد**. تنها جایی در کل مخزن که `ENV=production` دیده میشود، فرمان CI است. |
| ۲ | `secrets:` (۳ مورد) | به `./secrets/postgres_password.txt`, `secret_key.txt`, `api_key.txt` اشاره میکند؛ **پوشه `secrets/` اصلاً وجود ندارد** و اسکن کد هیچ خوانندهای برای `/run/secrets` پیدا نکرد. یعنی `docker stack deploy` یا شکست میخورد یا secretها نصب میشوند ولی هیچ سرویسای بهجایشان از env میخواند. |
| ۳ | `healthcheck` سرویس `api` | `urlopen('http://localhost:8000/api/v1/health')` → همان پروب **liveness** که همیشه `status=ok` و ۲۰۰ میدهد، نه `/api/v1/health/ready` (که ۵۰۳ میدهد). ادامه همان EX-05، این بار در استقرار تولید. |
| ۴ | `deploy.replicas: 2` (api و worker) | با `JOB_QUEUE_ENABLED` نامشخص در این فایل (پیشفرض کد `False`)، هر رپلیکا `SchedulerApp` و همه تسکهای پسزمینه قسمت ۰۱ را اجرا میکند؛ قفلها برخی را مهار میکنند ولی `RealtimeService` / `Armor subscriber` / `usage_recorder` / `accuracy_flusher` بیقفل تکثیر میشوند (EX-12). |

مقایسه جالب: `docker-compose.yml` (توسعه) حداقل `JOB_QUEUE_ENABLED=true`, `JOB_QUEUE_TOKEN`, `GOLD_API_TOKEN_SALT` و (پس از اصلاح worktree) پروب `/ready` دارد؛ **فایل «production» از فایل dev عقبتر است**.

`nginx` در همان فایل TLS خاتمه میدهد و `TRUSTED_PROXIES` را میطلبد، ولی هیچ فایل envـای آن را تنظیم نمیکند — پس در تولید یا همه کلاینتها پشت یک IP واحد پراکسی دیده میشوند، یا هدر `X-Forwarded-For` نادیده گرفته میشود (بند ۹).

---

## ۷. شش مسیر متفاوت خواندن `.env`

| کلاس | `env_file` | پیشوند | لنگر |
|---|---|---|---|
| `core.config.Settings` | `_REPO_ROOT / ".env"` | — (alias تکی) | ✅ ریشه مخزن |
| `brsapi.config.BrsApiSettings` | `".env"` | `BRSAPI_` | ❌ CWD |
| `ingestion.config.IngestionConfig` | `".env"` | `INGESTION_` | ❌ CWD |
| ۱۴ ماژول `core/config/*.py` | `".env"` | `APP_/API_/DB_/...` | ❌ CWD |
| `apps/currency_service/config.py` | `".env"` | `CURRENCY_` | ❌ CWD |
| `iran_market_data/app/storage/database.py` | `dotenv_values()` (بدون مسیر) | — | ❌ CWD |

دو ناهماهنگی واقعی در همین لایه با راستیآزمایی دوباره مشخص شد (و یک حدس اولیه **رد** شد — بند ۱۵):

- **پیشوند `LAKE_*`:** `docker-compose.yml:101-103` متغیرهای `LAKE_ENDPOINT`, `LAKE_ACCESS_KEY`, `LAKE_SECRET_KEY` را تزریق میکند، ولی `IngestionConfig` با `env_prefix="INGESTION_"` دنبال `INGESTION_LAKE_ENDPOINT` و `INGESTION_LAKE_ACCESS_KEY` / `INGESTION_LAKE_SECRET_KEY` است — همان نامهایی که `docs/env-vars.md:483-486` مستند کرده و پیام خطای `ingestion/lake/__init__.py:30` صریحاً چاپ میکند. نتیجه: این سه متغیر compose خوانده نمیشوند و پیشفرض `minioadmin` باقی میماند؛ گارد production همان فایل (`:22-32`) هم چون `settings.is_production` دقیقاً `environment == "production"` است، با CFG-01 خاموش میماند. **دو شکاف روی هم سوار میشوند.**
- **`INGESTION_DB_DSN` نامش درست است** (`db_dsn` + پیشوند)، ولی **مقدارش نه**: compose و `.env.example:82` هر دو `postgresql+asyncpg://…` میدهند و `ingestion/db/session.py:11-16` همان رشته را بیتبدیل به `asyncpg.create_pool()` تحویل میدهد؛ `field_validator("db_dsn")` فقط `str(v)` برمیگرداند. این یافته پیشتر بهعنوان `ROOT-002` در `docs/audits/tools/_manual_findings9.py` همراه خطای واقعی `ClientConfigurationError: invalid DSN` ثبت شده و اینجا تأیید مجدد میشود.

کامیت تازه `d551242c` (همین ساعت، «env isolation fixes») `iran_market_data` را از `load_dotenv()` به `dotenv_values()` برده تا `os.environ` را آلوده نکند — یعنی تیم همزمان مشغول بستن همین خانواده شکافهاست، ولی **شش مسیر خواندن env همچنان پابرجاست**.

توجه: داخل کانتینرها `.env` کپی نمیشود و مقادیر از `environment:` تزریق میشوند، بنابراین مشکل CWD بیشتر متوجه اجرای مستقیم اسکریپتها/تستها و workerهای خارج از Docker است.

---

## ۸. هفده ماژول موازی — فقط سه تای آنها زندهاند

اسکن واردات روی ۳٬۵۴۴ فایل (worktree کلونشده `.freebuff/` و `_FRONTEND_BACKEND_COPY/` حذف شدند):

| وضعیت | ماژولها | شواهد |
|---|---|---|
| ✅ زنده | `acceptance_loader.py` (۵۳۳ خط) | `apps/api/endpoints/backtests.py:943`, `services/signal_decision_engine.py:55`, `src/gold_desk/api.py:304` + ۳ فایل تست |
| ✅ زنده | `ime_engine.py` (۱۱۹ خط) | ۵ مصرفکننده production در `services/gold/*`, `services/ime_signal_factory.py`, `services/statistical_acceptance_gate.py` |
| ✅ زنده | `storage.py` | `integrations/filesystems/s3_compatible_storage.py:61` |
| ❌ **صفر مصرفکننده** | `app.py`, `api.py`, `database.py`, `security.py`, `ml.py`, `backtest.py`, `admin.py`, `paths.py`, `providers.py`, `indicators.py`, `monitoring.py`, `scheduler.py`, `feature_flags.py`, `environments.py` | **۱۴ ماژول**، هیچ ارجاعی حتی در تستها |

بدترین بخش ماجرا: ماژولهای مرده **پیشفرضهای ناامن** حمل میکنند که گیت `validate_production()` روی `Settings` زنده آنها را نمیبیند:

```python
# core/config/api.py        → cors_origins: list[str] = ["*"]      ← گیت فقط ["*"] روی Settings را چک میکند
# core/config/security.py   → allowed_hosts: list[str] = ["*"]
# core/config/admin.py      → secret_key: str = Field(..., alias="ADMIN_SECRET_KEY", min_length=16)  ← بدون پیشفرض، instantiate شود خطا میدهد
# core/config/storage.py    → encryption_enabled: bool = False
# core/config/ml.py         → enable_drift_detection, registry_uri, ...  ← قابلیتهایی که در Settings زنده وجود ندارند
```

اگر روزی کسی این ماژولها را جای `Settings` وصل کند، CORS wildcard وارد مسیر اجرا میشود، بیآنکه گیت production آن بگیرد. همچنین `monitoring.py` مسیرهای `/ready` و `/live` را تعریف میکند، ولی `health.py` زنده مسیرهایش را خودش ساخته — **دو تعریف موازی برای یک قرارداد**.

---

## ۹. سه سیستم feature flag، دوتای آنها مرده

| سیستم | پیادهسازی | مصرف |
|---|---|---|
| `Settings` (زنده) | `news_read_mode` چهارحالته + ۹ کلید parity/halt، `indicator_adjusted_prices`, `enable_csrf`, `enable_input_sanitization`, `database_replica_enabled`, `bootstrap_first_admin`, `registration_open` | ✅ `core/news_read_canary.py`, CI, compose |
| `core/config/feature_flags.py` | `FeatureFlagSettings` با ۱۱ پرچم (`FF_` prefix) | ❌ **صفر واردات** |
| `core/feature_flags/` | `FeatureFlag`, `FeatureFlags`, `FlagDefinition`×۹, `FeatureFlagManager` — خواندن `FF_<NAME>` از `os.environ` + override متنی | ❌ فقط self-import و `tests/unit/core/test_feature_flags.py` |

`FeatureFlag.enabled` مستقیماً `os.environ` را میخواند (نه `Settings`)، یعنی حتی اگر وصل میشد، از مسیر `env_file` لنگرانداختهشده عبور نمیکرد. پرچمهایی مثل `ENABLE_SENTRY`, `ENABLE_METRICS`, `USE_CACHE` در هر دو سیستم مرده تکرار شدهاند، در حالی که نسخه زنده (`sentry_dsn`, `metrics_path`, `redis_default_ttl`) نام دیگری دارد. **سه تعریف برای یک مفهوم، بدون هیچ کد تبدیلی.**

---

## ۱۰. `acceptance_loader.py` — قویترین قطعه این قسمت

۵۳۳ خط، برخلاف ۱۴ ماژول مرده، کاملاً زنده و دقیق است:

- `_TOP_LEVEL_REQUIRED` هفت کلید اجباری؛ `_REQUIRED_INSTRUMENT_KEYS` چهار فیلد برای هر ابزار؛ `_FEE_TERM_KEYS` پنج فیلد تعرفه؛ `PROVENANCE_VALUES = {spec, assumption, unavailable}` و `_validate_provenance`؛ `_validate_market_hours` با `_SESSION_KEYS` و `_TEST_SESSIONS` (شنبه تا چهارشنبه / پنجشنبه).
- `_METRIC_ALIASES` شش نام canonical با نامهای مستعار خروجی بهینهساز (`wfe ← walk_forward_efficiency`, `dsr ← deflated_sharpe`, `trade_count ← total_trades/trades`, ...).
- `@lru_cache(maxsize=8)` روی `_load` (خط ۲۰۶) → اعتبارسنجی و پارس YAML یکبار بهازای مسیر؛ **بررسی شد، برخلاف شک اولیه کش واقعاً وجود دارد**.
- `_load` در خطا حتماً نام فایل را در پیام میآورد، `yaml.safe_load` (نه `unsafe_load`) و import محلی PyYAML بهعنوان وابستگی اختیاری.
- `get_fee_terms`, `get_signal_filter`, `get_market_hours`, `get_assistant_rules`, `required_gross_move_pct`, `evaluate_walk_forward_result` — همگی از همان منبع واحد `acceptance.yaml` میخوانند، همانطور که کامنت سند ادعا میکند.

شش فایل YAML دیگر (`backtest_costs`, `ime_engine_config`, `macroeconomics`, `signal_policy`, `smart_money`, `symbols`) نیز توسط `ime_engine.load_ime_config` (deep-merge با `_defaults()` کد) و سرویسهای مربوطه بار میشوند. **نتیجه:** جایی که تیم «تکمنبع» را جدی گرفته (قسمت ۰۸ بکتست و دستیار طلا)، نتیجه عالی است؛ جایی که نگرفته (پیکربندی محیط)، هفت منبع موازی ساخته شده.

---

## ۱۱. امنیت اسرار — آنچه درست انجام شده

- فقط **`.env.example`** تحت git است (`git ls-files` تأیید کرد)؛ `.gitignore` الگوی `.env*` + استثنای `!.env.example` و `!frontend/.env.sentry.example` دارد.
- `SECRET_KEY` محلی ۶۴ نویسه و **برابر placeholder پیشفرض نیست** (بدون نقل مقدار بررسی شد).
- **Fail-fast دوزمنبعهای** `GOLD_API_TOKEN_SALT`: import-time در `src/gold_desk/api_token.py` + `${VAR:?}` در هر دو compose. کامنت compose هشدار میدهد عوض کردن salt توکنهای قدیمی را باطل میکند.
- `validate_production` هفت شرط و فراخوان از **شش** نقطه ورود + گیت CI اختصاصی.
- هشت validator کلاس، از جمله رد صریح `JWT_ALGORITHM=none` (`:467-472`)، الزام `SameSite=None → AUTH_COOKIE_SECURE=true` (`:457-465`)، و ترتیب صدکهای DXY (`:431-438`).
- `_auth_required()` تکمنبع `AUTH_DISABLED` با غلبه env و اصلاح مستند bypass استیجینگ (API-008).
- `BRSAPI_ENABLED=false` switches/کلید قطع کامل HTTP زنده (DB-only) — documented در `brsapi/readiness.py`، `client.py`، `apps/scheduler/app.py`.
- `_get_client_ip()` در `apps/api/endpoints/auth.py:95-115` تنها زمانی `X-Forwarded-For` را باور میکند که peer مستقیم در `TRUSTED_PROXIES` (IP یا CIDR) باشد (SEC-06) — پیادهسازی امن و مستند.

---

## ۱۲. جدول یافتهها

| ID | شدت | خط / فایل | یافته | اثر عملی | جهت اصلاح |
|---|---|---|---|---|---|
| **CFG-01** | 🔴 بحرانی | `docker-compose.production.yml` anchor | استقرار «production» هرگز `ENV=production` ست نمیکند | هفت گیت `validate_production` خاموش، `/docs`+`/openapi.json` باز، WS token قدیمی مجاز، کوکی refresh ناامن، Sentry با برچسب development | `ENV: production` در anchor + تأیید بوت |
| **CFG-02** | 🔴 بحرانی | `docker-compose.production.yml` secrets | ۳ secret به `./secrets/*.txt` اشاره دارند؛ پوشه وجود ندارد و کد هیچ `/run/secrets`ـی نمیخواند | `docker stack deploy` شکست میخورد یا secretها بلااستفاده میمانند و اپ همچنان از env میخواند | ساخت پوشه + خواندن `_FILE` در کد، یا حذف declaration |
| **CFG-03** | 🟠 بالا | `.env*` + `ci.yml:121` | `AUTH_COOKIE_SECURE` (الزامی گیت) و `REGISTRATION_OPEN`, `JOB_QUEUE_TOKEN` حتی در `.env.example` مستند نشدهاند | اپراتور نمیتواند production را از روی مستندات بالا بیاورد؛ CI چون inline پاس میدهد کمبود را پنهان میکند | افزودن سه کلید به `.env.example` |
| **CFG-04** | 🟠 بالا | `.env.production` (۹ کلید) | فاقد `SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS`, `OTLP_ENDPOINT`, `AUTH_COOKIE_SECURE` | با `ENV` درست → بوت با ≥۴ خطا شکست میخورد؛ بدون `ENV` → بوت ناامن (CFG-01) | تکمیل فایل یا حذف و اتکا به secret store |
| **CFG-05** | 🟠 بالا | `core/config/environments.py` + `__init__.py:69` | `ENV_FILE_MAP`/`get_env_file` صفر فراخوان دارند؛ `env_file` ثابت `.env` ریشه است | فایلهای محیطی مردهاند؛ production همان `.env` توسعه را میخواند | وصل کردن `get_env_file()` به `model_config` یا حذف ماژول |
| **CFG-06** | 🟠 بالا | ۱۸ زیرکلاس `BaseSettings` (اسکن AST) | شش مسیر متفاوت `env_file` (یکی لنگرانداخته، چهار CWDنسبی، یکی `dotenv_values`) | اجرای اسکریپت از دایرکتوری دیگر → مقادیر متفاوت؛ `INGESTION_DB_DSN` در compose با نام موردانتظار `IngestionConfig` نمیخواند | تک `env_file` مطلق + تزریق صریح |
| **CFG-07** | 🟠 بالا | `docker-compose.production.yml` healthcheck | پروب روی `/api/v1/health` (liveness همیشه ۲۰۰) نه `/health/ready` | اورکستراتور خرابی DB/Redis را نمیبیند؛ ادامه EX-05 در production | `/api/v1/health/ready` |
| **CFG-08** | 🟡 متوسط | ۱۴ ماژول `core/config/*.py` | صفر مصرفکننده، ولی پیشفرضهای ناامن (`cors_origins=["*"]`, `allowed_hosts=["*"]`, `AdminSettings` فاقد پیشفرض) حمل میکنند | اتصال تصادفی آینده، گیت production را دور میزند | حذف یا تبدیل به re-export از `Settings` |
| **CFG-09** | 🟡 متوسط | `core/config/feature_flags.py` + `core/feature_flags/` | سه سیستم پرچم، دوتا فقط self-import و تست | `ENABLE_SENTRY`/`ENABLE_METRICS`/`USE_CACHE` سه تعریف بیارتباط | حذف دوتای مرده |
| **CFG-10** | 🟡 متوسط | `.env.production` | `ENABLE_MARKET_DATA`, `ENABLE_HEATMAP` هیچ خوانندهای ندارند | توهم پیکربندی؛ با `extra="ignore"` بیسروصدا حذف میشوند | حذف کلیدها |
| **CFG-11** | 🟡 متوسط | `apps/api/middleware.py:544` در برابر `auth.py:95-115` | helper امن `_get_client_ip` (trusted-proxy aware) فقط در login/OTP استفاده شده؛ نرخگیر عمومی از `request.client.host` خام میگیرد | **تأیید HTTP-08 قسمت ۰۲**: نرخگیری ورود محافظت شده، نرخگیری کل API نه | استفاده مشترک از `_get_client_ip` در میانافزار |
| **CFG-12** | 🟡 متوسط | `__init__.py:185,267` | `data_dir`/`ml_model_dir` به `Path.cwd()` وابستهاند در حالی که `.env` به ریشه لنگر انداخته | مسیرهای داده/مدل با تغییر CWD عوض میشوند | `_REPO_ROOT` |
| **CFG-13** | 🟡 متوسط | `__init__.py:547-552` + `ci.yml:121` | singleton قابلتغییر؛ CI `settings.environment` را درون فرایند جهش میدهد | تستها میتوانند state را به سایر تستها نشت دهند | `get_settings()` تازهای بهازای تست یا fixture reset |
| **CFG-14** | 🟢 کم | `.env.example:42,88,165` | پیشفرضهای اعتباری توسعهای committed (`minioadmin`, `change-me-in-production`, `ENCRYPTION_KEY`) | کپی بدون ویرایش → اسرار پیشبینیپذیر | کامنت هشدار قویتر / مقادیر خالی |
| **CFG-15** | 🟢 کم | `.env.bak.1790980646` (۶٫۹ KB) | بکآپ محلی ignored ولی روی دیسک؛ الگوی `.env.*` هر فایل محیطی تازهای را هم پنهان میکند | ریسک افشای محلی و پنهانشدن پیکربندی تازه از review | پاکسازی + استثنای صریح |
| **CFG-16** | 🟢 کم | گزارش ۱۶۰ لایهای، لایه ۱۳/۱۵۸ | «۱۲۸ فایل مصرفکننده `settings`» | عدد کهنه؛ اندازهگیری مجدد: **۲۱۷ ارجاع در ۱۸۷ فایل** | تصحیح شد (بند ۱۴) |
| **CFG-17** | 🟠 بالا | `docker-compose.yml:101-103` در برابر `ingestion/config.py:30,50-52` | سه متغیر `LAKE_*` تزریق میشوند ولی `IngestionConfig` با پیشوند `INGESTION_` دنبال `INGESTION_LAKE_*` است | اعتبار MinIO روی پیشفرض `minioadmin` میماند؛ گارد production چون به `ENV` وابسته است با CFG-01 خاموش میشود | یکسانسازی پیشوندها |
| **CFG-18** | 🟠 بالا | `docker-compose.yml:97`, `.env.example:82`, `ingestion/db/session.py:11-16` | DSN با scheme `postgresql+asyncpg://` بیتبدیل به `asyncpg.create_pool()` داده میشود؛ validator فقط `str(v)` است | بوت سرویس ingestion با `ClientConfigurationError: invalid DSN` شکست میخورد (`ROOT-002`، تأیید مجدد) | حذف `+asyncpg` یا تبدیل scheme پیش از ساخت pool |
| **CFG-19** | 🟢 کم | `apps/currency_service/config.py` در برابر `.env.example`, `docs/env-vars.md` | هجدهمین استک پیکربندی (`CURRENCY_` prefix، شش فیلد، `port=8002`) زنده است ولی هیچ `CURRENCY_*`ای در `.env.example` یا `docs/env-vars.md` مستند نشده؛ compose فقط `CURRENCY_USE_LIVE` را به سرویس `currency` میدهد (درست مصرف میشود: `collector.py:23`). همزمان `CURRENCY_API_URL` در `compose:184` **متغیر فرانتاند** است و `next.config.ts:23` آن را میخواند — یعنی یک پیشوند واحد دو حوزه پیکربندی متفاوت را پوشش میدهد | اپراتور نمیداند `CURRENCY_JITTER_PCT`, `CURRENCY_CACHE_TTL_SECONDS`, `CURRENCY_ENABLE_ALERTS` قابلتنظیماند؛ احتمال برداشت اشتباه از `CURRENCY_API_URL` بهعنوان تنظیم بکاند | مستندسازی شش فیلد + تفکیک صریح کلیدهای فرانتاند |

> CFG-17 تا CFG-19 در بازبینی نهایی، پس از راستیآزمایی دوباره بند ۷ و اسکن AST کل مخزن، به جدول افزوده شدند.

---

## ۱۳. نقاط قوت تأییدشده

1. لنگر انداختن `.env` به ریشه مخزن (خط ۱۱–۱۵) با دلیلنویسی دقیق درباره تستها، اسکریپتها و `WORKDIR` Docker.
2. `_strip_inline_comment` و `_parse_origin_list`: پردازش سه شکل ورودی (JSON، نقلقول، کاما) با پیام خطای گویا.
3. هشت validator، بهویژه رد `JWT_ALGORITHM=none` و قانون `SameSite=None ⇒ Secure`.
4. `validate_production()` در شش نقطه ورود + گیت CI اختصاصی، fail-closed در prod/**staging** (توجه به staging نکتهای است که خیلی جاها فراموش میشود).
5. Fail-fast دومنبعهای salt توکن GoldDesk، با هشدار صریح درباره باطل شدن توکنها.
6. `_get_client_ip()` (SEC-06) الگوی صحیح اعتماد شرطی به `X-Forwarded-For` — فقط کاش در نرخگیر عمومی هم استفاده میشد.
7. `acceptance_loader.py`: اعتبارسنجی اسکیم، `provenance` سهحالته، alias متریکها، `safe_load`، و کش `@lru_cache(maxsize=8)` — **شک اولیه درباره نبود کش با خواندن خط ۲۰۶ رد شد**.
8. فقط `.env.example` tracked؛ `.gitignore` دقیق و با استثناهای معقول.
9. `BRSAPI_ENABLED=false` بهعنوان کلید قطع کامل وابستگی خارجی (DB-only mode).
10. گارد `ingestion/lake/__init__.py:22-32` که اعتبار پیشفرض MinIO را در production **fail-closed** رد میکند و حتی نام متغیرهای صحیح را در پیام خطا میدهد — منطقش درست است، فقط به لطف CFG-01 هرگز اجرا نمیشود.

---

## ۱۴. تصحیحات / تکمیل گزارش ۱۶۰ لایهای

| محل | قبل | بعد |
|---|---|---|
| لایه ۱۳ | «۵۵۴ خط، ~۱۲۰ فیلد، ۱۲۸ فایل مصرفکننده، ۸ validator» | **۵۵۳ خط، ۱۱۸ فیلد، ۶۰ `Field()`، ۸ validator کلاس + ۷ property، ۲۱۷ ارجاع در ۱۸۷ فایل**؛ `validate_production` **هفت** شرط دارد (نه هشت) |
| لایه ۱۵۸ | «دو سیستم تنظیمات» | **۱۸ زیرکلاس `BaseSettings` (اسکن AST، ۱۵ تا در `core/config/`) + هفت فایل YAML + سه سیستم پرچم** |
| لایه ۱۵۱ | «MinIO کامنت شده» | تأیید شد؛ علاوه بر آن `LAKE_SECRET_KEY=minioadmin` در `.env.example` و `${LAKE_*:-minioadmin}` در compose dev |

همچنین **لایه ۱۵۵ / EX-05 تکمیل شد**: علاوه بر compose توسعه، `docker-compose.production.yml` هم از پروب liveness بجای readiness استفاده میکند (CFG-07) — یعنی یافته فقط محدود به dev نیست.

---

## ۱۵. مرز روش / گام بعدی

همه چیز ایستا است: `docker stack deploy` اجرا نشد، `validate_production()` در محیط واقعی فراخوانی نشد، مقادیر اسرار خوانده/نقل نشدند (فقط نام کلیدها، طول `SECRET_KEY` و اینکه آیا برابر placeholder است یا نه بررسی شد). وجودنداشتن پوشه `secrets/` و نبود خواننده `/run/secrets` با جستوجوی فایل و محتوا تأیید شد، ولی ممکن است اسکریپت deploy خارج از مخزن آن پوشه را بسازد؛ CFG-02 بر همان مبنا «در مخزن حاضر» گزارش شده است. HEAD هنگام نگارش `d551242c` (۱۲ کامیت پس از مبنا) بود و worktree همچنان در حال تغییر است — جزئیات در `README.md`.

**دو شک اولیه که رد شدند و ثبت میشوند:**
1. `get_acceptance_config` بدون کش است (حدس از روی نبود decorator روی خود تابع) — بررسی نشان داد `@lru_cache` روی `_load` (خط ۲۰۶) قرار دارد و docstring «cached per path» صحیح است.
2. «`IngestionConfig` دنبال `INGESTION_DATABASE_URL` میگردد، پس نام `INGESTION_DB_DSN` در compose غلط است» — با خواندن `ingestion/config.py:55` (`db_dsn` + `env_prefix="INGESTION_"`) رد شد؛ **نام درست است**. مشکل واقعی از scheme مقدار و از پیشوند `LAKE_*` است (بند ۷ ← CFG-17 / CFG-18).

**قسمت ۰۴:** پایگاه داده و مهاجرتها — `core/database.py` (engine/replica و نگهبان readonly)، `models/base.py`، ۱۴۹ مدل ORM، گراف ۹۴ مهاجرته Alembic با head منفرد `0123`، درخت موازی `migrations_backup_20261030/`، و جاب `needs-db` در CI.

---
*فقط فایل تحلیلی ساخته شد؛ هیچ کدی تغییر نکرد.*
