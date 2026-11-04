# طرح جامع رفع ایرادها (Remediation Plan)

**منبع یافته‌ها:** `report/01-structure.md`, `report/02-modules-plan.md`, `report/modules/*.md`
**پروژه:** `C:/Users/Iran/Desktop/temce`
**تاریخ:** 2026-10-05 (نسخهٔ ۲ — پس از بازبینی عمیق کامل‌بودن)
**روش:** هر یافته اول در کد فعلی بازبینی شد؛ سپس موارد واقعی اصلاح و با تست تأیید شدند. در نسخهٔ ۲ همهٔ ۵۵ شناسهٔ یافته از کارت‌های audit استخراج و تک‌به‌تک در برابر کد/وضعیت حسابرسی شد تا هیچ یافته‌ای بی‌پاسخ نماند (بخش ۷).

برچسب‌ها: ✅ اصلاح‌شده · 🟢 تأیید مثبت (نیاز به تغییر نیست) · ⚪ قبلاً رفع‌شده/مثبت کاذب · 🔵 تصمیم/توضیح مستند · ⚠️ شکاف باقی‌مانده (نیازمند تصمیم).

---

## ۱. خلاصهٔ وضعیت یافته‌ها

| ID | شدت | موضوع | وضعیت |
|---|---|---|---|
| BUD-01 | high | پیش‌فرض سقف روزانهٔ BrsApi = 10,000 در حالی که مستندات/تست = 4,000 | ✅ فاز ۱ |
| BUD-02 | medium | دو پیاده‌سازی CircuitBreaker؛ client از نسخهٔ قدیمی استفاده می‌کند | ✅ فاز ۲ |
| BUD-03 | medium | مغایرت ساعت بازار با ingestion | 🔵 بخش ۴ |
| BUD-04, BUD-05, BUD-06, BUD-07 | low | بهبودهای جزئی بودجه/دسته‌بندی صف | 🔵 بخش ۵ |
| CFG-01 | high | کلید پیش‌فرض SECRET_KEY | ✅ فاز ۳ |
| CFG-02 | medium | `auth_disabled=True` در production رد نمی‌شد | ✅ فاز ۳ |
| CFG-03 | low | اطمینان از سیم‌کشی `InputSanitizationMiddleware` | 🟢 تأیید شد (بخش ۷) |
| CFG-04 | low | اطمینان از رعایت commit-guard در `get_session` | 🟢 تأیید شد (بخش ۷) |
| CFG-05 | low | replica خواندن پیکربندی شده اما در هیچ endpoint تزریق نمی‌شد | ✅ فاز ۷ |
| ENR-01 | low | EventBus درون‌پروسه‌ای بدون تضمین delivery | 🔵 بخش ۴ |
| ENR-02, ENR-03, ENR-04 | low | موارد جانبی event bus | 🔵 بخش ۵ |
| ENR-05 | low | استفادهٔ سراسری از helpers مسیر امن | 🟢 تأیید شد (بخش ۳/۷) |
| ENR-06 | low | استفادهٔ سراسری از `safe_error_message` | 🟢 تأیید شد (بخش ۳/۷) |
| ENR-07 | low | سیم‌کشی واقعی feature flagها در نقاط فراخوانی | ✅ فاز ۷ |
| ING-01 | high | احتمال درج api_key در SyncLog / RawPayload | ⚪ قبلاً رفع شده (`_redact_params`) |
| ING-02 | low | موارد جانبی ingestion | 🔵 بخش ۵ |
| ING-03 / ING-10 | medium | چند تعریف ساعات بازار / سشن ≠ پنجرهٔ ingestion | 🔵 بخش ۴ |
| ING-04, ING-05, ING-06, ING-08, ING-11, ING-12 | low | اعتبارسنجی/خطاهای جزئی ingestion | 🔵 بخش ۵ |
| ING-07 | medium | اعتبارنامهٔ پیش‌فرض MinIO ضعیف | ⚪ هشدار قبلاً در `ingestion/lake` وجود دارد |
| ING-09 | high | روزهای معاملاتی `(5,6,0,1,2)` مشکوک به اشتباه | 🟢 درست است (شنبه–چهارشنبه) |
| MW-01 / MW-05 | low/medium | opaque fields، fallback محدودیت نرخ | 🟢/🔵 بخش ۴ |
| MW-02 / MW-04 / MW-06 | low | موارد جانبی middleware | 🔵 بخش ۵ |
| MW-03 | medium | `cors_origins = ["*"]` | 🟢 `validate_production` رد می‌کند |
| OBS-01 | low | مقدار `None` در L1 به‌عنوان miss تلقی می‌شد | ✅ فاز ۴ |
| OBS-02, OBS-03, OBS-04, OBS-05 | low | موارد جانبی observability | 🔵 بخش ۵ |
| RRL-01 | medium | دکوراتور/پیاده‌سازی دوگانهٔ breaker | ✅ فاز ۲ |
| RRL-02 | medium | دکوراتور sync بی‌اثر بود | ✅ فاز ۲ |
| RRL-03, RRL-04, RRL-05, RRL-06, RRL-07 | low | retry همگام، سیاست‌های fallback | 🔵 بخش ۵ |
| SEC-01 | high | کلید پیش‌فرض فقط در production چک می‌شد | ✅ فاز ۳ |
| SEC-02 | medium | `sanitize_sql` ضعیف | ⚪ بدون هیچ فراخوانی (dead code) |
| SEC-03 | low | fail-open revocation در قطعی Redis | 🔵 بخش ۴ |
| SEC-04 | low | limiter درون‌پروسه‌ای per-worker (drift جزئی) | 🔵 بخش ۷ |
| SEC-05 | medium | اعتبارسنجی فقط production (نه staging) | ✅ فاز ۳ |
| SEC-06 | low | GoldDesk بدون auth (شخصی) | 🔵 بخش ۴ |

**جمع:** ۵۵ شناسه — ✅ ۱۱ اصلاح‌شده · 🟢 ۶ تأیید مثبت · ⚪ ۳ مورد قبلاً‌رفع‌شده/کاذب · 🔵 ۳۵ تصمیم/کم‌اثر · ⚠️ صفر شکاف باقی‌مانده (هر ۵۵ شناسه حسابرسی شده‌اند).

---

## ۲. فازهای اجرا (اجراشده)

### فاز ۱ — صحت بودجهٔ provider (BUD-01) ✅
- `brsapi/rate_limiter.py`: `DEFAULT_GLOBAL_DAILY_LIMIT = 4_000`
- `brsapi/config.py`: `global_daily_limit` default `4000`
- **معیار پذیرش:** `tests/unit/test_brsapi_quota.py::test_default_limits_match_quota` سبز.

### فاز ۲ — یکپارچگی Circuit Breaker (RRL-01/02, BUD-02) ✅
- `core/circuit_breaker.py` به shim سازگار با `core/resilience/circuit_breaker.py` تبدیل شد (تک منبع حقیقت).
- افزودن `call_sync` (+ قفل `threading.Lock`) و استفاده در دکوراتور برای توابع sync.
- اصلاح افزایش `half_open_calls` تا سقف probe واقعاً اعمال شود.
- سازگاری کامل API قدیمی حفظ شد: امضای `call(func, *args)`، ترتیب پارامترهای سازنده، `CircuitBreakerState`، و attribute `state`.
- **معیار پذیرش:** تست‌های `tests/unit/core/test_circuit_breaker.py` سبز + تست‌های جدید sync/shim/half-open.

### فاز ۳ — سخت‌سازی config (CFG-02/SEC-05, SEC-01/CFG-01) ✅
- `validate_production` برای `production` **و `staging`**: رد `auth_disabled=True` و رد کلید پیش‌فرض.
- **معیار پذیرش:** `tests/unit/core/test_config_validation.py` سبز.

### فاز ۴ — کش L1 و مقدار None (OBS-01) ✅
- sentinel سطح‌ماژول `_L1_MISSING` تا `None` معتبر در L1 به‌عنوان miss تلقی نشود.
- **معیار پذیرش:** `test_cache_manager.py::test_cached_none_is_not_recomputed` سبز.

### فاز ۵/۶ — تست و تأیید ✅
- اجرای تست‌های هدفمند + `ruff check` + `py_compile` روی همهٔ فایل‌های تغییریافته.
- به‌روزرسانی `report/PROGRESS.md`.

### فاز ۷ — بستن شکاف‌های باقی‌مانده (CFG-05, ENR-07 + تست‌های از‌قبل‌شکست‌خورده) ✅

**CFG-05 — replica واقعاً استفاده می‌شود:**
- `core/database.py`: نشست replica با `session.info["_readonly"] = True` علامت می‌خورد و یک نگهبان (لیسنر `before_flush` + بررسی DML در `do_orm_execute`) هر نوشتنی روی آن را با `RuntimeError` رد می‌کند — دیگر نوشتن‌ها بی‌صدا از بین نمی‌روند.
- `apps/api/dependencies.py`: افزودن `get_readonly_service`, `get_analysis_service_ro`, `get_screener_service_ro`, `get_brsapi_query_service_ro` (همه با fallback به primary).
- سیم‌کشی: GET در `apps/api/endpoints/analysis.py` (۵ هندلر)، GET `/screener` و GET `/indicators/{id}/{name}` به replica؛ هندلرهای نویسنده (`screener_filter`, `create_indicator`) روی primary ماندند.
- **معیار پذیرش:** تست‌های `test_replica_readonly_session.py` (نگهبان + fallback) و `tests/unit/api/test_readonly_replica_wiring.py` (گراف وابستگی FastAPI) سبز.

**ENR-07 — flag واقعاً اعمال می‌شود:**
- `core/observability_sentry.py`: تابع `sentry_enabled(settings)` تنها منبع تصمیم است و **هم** DSN و **هم** flag `enable_sentry` را لازم دارد.
- `core/feature_flags/__init__.py` و `core/feature_flags/flags.py`: پیش‌فرض به `True` تغییر کرد تا استقرارهای موجود با `SENTRY_DSN` همچنان کار کنند؛ `FF_ENABLE_SENTRY=false` یک کلید خاموش‌کنندهٔ صریح است.
- **معیار پذیرش:** `tests/unit/test_observability_sentry.py` سبز.

**سه تست از‌قبل‌شکست‌خورده (خارج از دامنهٔ امنیتی/منطقی، ایراد خود تست‌ها بود):**
- `test_brsapi_client_retry.py` و `test_brsapi_kill_switch.py`: double تستی `FakeEndpoint`/`_FakeEndpoint` فاقد فیلد `critical` بود (که `client.fetch` می‌خواند) → فیلد اضافه شد.
- `test_brsapi_usage_recorder.py`: سه تست به endpoint محافظت‌شدهٔ ادمین بدون auth درخواست می‌زدند (401) → به `admin_client` و override مجاز منتقل شدند و یک assertion اضافه شد که همان روت بدون auth باید 401 بدهد.

---

## ۳. موارد تأییدشده (بدون نیاز به تغییر کد)

- **ING-09:** `DEFAULT_TRADING_WEEKDAYS=(5,6,0,1,2)` معادل شنبه تا چهارشنبه است (Python: Mon=0). با `jobs/market_hours._WEEKEND_DAYS={3,4}` (پنجشنبه/جمعه) و `core/constants/markets.MARKET_WEEKEND_DAYS=(3,4)` سازگار است. یافتهٔ audit نادرست بوده.
- **ING-01:** `brsapi/repositories/base.py::_redact_params` کلیدها را قبل از درج در `SyncLogModel.params_snapshot` و `RawPayloadModel.params` حذف می‌کند.
- **SEC-02:** `sanitize_sql` هیچ فراخوانی‌ای در کد ندارد (dead code).
- **ING-07:** `ingestion/lake/__init__.py:25-26` در صورت استفاده از `minioadmin` هشدار می‌دهد.
- **MW-03:** `validate_production` مقدار `["*"]` را رد می‌کند.
- **CFG-03:** `apps/api/middleware.py:257` تعریف و `apps/api/app.py:1040` سیم‌کشی شده — `app.add_middleware(InputSanitizationMiddleware)`.
- **CFG-04:** `core/database.py:222-228` فقط در صورت وجود قصد نوشتن (`session.info["_audit_wrote"]` که توسط event `do_orm_execute` پر می‌شود، یا dirty/new/deleted) کامیت می‌کند؛ در غیر این‌صورت ROLLBACK و بستن. درست کار می‌کند.
- **ENR-05:** `core/paths.py` (`validate_safe_path` + `safe_resolve`) و `core/validation/files.py` موجود و استفاده‌شده برای مسیرهای فایل.
- **ENR-06:** `core/utils.py::safe_error_message` در production مقادیر secret/token/password/PRIVATE_KEY/SECRET را پاک می‌کند.

---

## ۴. تصمیم‌های طراحی (🔵)

- **ساعات بازار (ING-03/BUD-03/ING-10):** سه مفهوم متفاوت وجود دارد و باید تفکیک بمانند:
  - سشن معاملات (`core/time`): پیش‌گشایش 08:30–09:00، پیوسته 09:00–12:30، پس از بستن 12:30–13:00.
  - پنجرهٔ ingestion (`brsapi/config`, `ingestion/config`, `symbol_scanner`): 08:30–15:30.
  - پنجرهٔ Codal (`jobs/market_hours`): 08:00–18:00.
  این‌ها «اشتباه» نیستند اما باید در کد/مستندات با نام صریح (trading session vs ingestion window) مشخص شوند.
- **SEC-03/MW-05:** fail-open در قطعی Redis یک تصمیم آگاهانه است (توقف نادرست جریان بدتر از کاهش موقت محدودیت).
- **SEC-06:** GoldDesk شخصی و بدون auth توسط طراحی؛ `/api/v1/golddesk` از توکن اسکوپ‌دار استفاده می‌کند.
- **ENR-01:** EventBus درون‌پروسه‌ای است؛ هیچ‌گاه تضمین delivery پایدار نداشته است.
- **SEC-04:** `TieredTokenBucketLimiter` درون‌پروسه‌ای و per-worker است؛ drift جزئی تحت churn شدید محتمل اما کم‌خطر (نیازمند Redis برای هم‌ارزی چند-worker).
- **MW-01:** فیلدهای opaque توسط allow-list سانیتایز می‌شوند.

---

## ۵. موارد باقی‌ماندهٔ کم‌اثر (اختیاری — فاز بعد در صورت تأیید)

این‌ها به دلیل اثر کم/عدم قطعیت نیاز، بدون تغییر باقی ماندند و می‌توانند فاز بعدی شوند (فهرست صریح و کامل):

| گروه | شناسه‌ها |
|---|---|
| Resiliency | `RRL-03`, `RRL-04`, `RRL-05`, `RRL-06`, `RRL-07` |
| Events | `ENR-02`, `ENR-03`, `ENR-04` |
| Observability | `OBS-02`, `OBS-03`, `OBS-04`, `OBS-05` |
| Middleware | `MW-02`, `MW-04`, `MW-06` |
| بودجهٔ provider | `BUD-04`, `BUD-05`, `BUD-06`, `BUD-07` |
| Ingestion | `ING-02`, `ING-04`, `ING-05`, `ING-06`, `ING-08`, `ING-11`, `ING-12` |
| Config/امنیت | `SEC-04` (limiter درون‌پروسه‌ای per-worker — نیازمند Redis برای هم‌ارزی چند-worker) |

---

## ۶. نتیجهٔ اجرا (شواهد)

**تست‌های هدفمند (پس از اصلاح):**
```
python -m pytest tests/unit/core tests/unit/test_brsapi_quota.py \
    tests/unit/test_brsapi_outbound_simulation.py
→ 243 passed  (EXIT=0)
```
پیش از اصلاح: `tests/unit/test_brsapi_quota.py::test_default_limits_match_quota` شکست می‌خورد (`assert 10000 == 4000`).

**تست‌های جدید:**
- `tests/unit/core/test_circuit_breaker.py` — پوشش دکوراتور sync، سقف probe نیمه‌باز، و امضای legacy shim.
- `tests/unit/core/test_cache_manager.py::test_cached_none_is_not_recomputed` — OBS-01.
- `tests/unit/core/test_config_validation.py` — CFG-02/SEC-05/SEC-01.
- `tests/unit/test_replica_readonly_session.py` — CFG-05 (نگهبان read-only + fallback به primary).
- `tests/unit/api/test_readonly_replica_wiring.py` — CFG-05 (گراف وابستگی: GET‌ها replica، نویسنده‌ها primary).
- `tests/unit/test_observability_sentry.py` — ENR-07 (flag + DSN).

**پس از فاز ۷:** `python -m pytest tests/unit/core tests/unit/test_brsapi_client_retry.py tests/unit/test_brsapi_kill_switch.py tests/unit/test_brsapi_usage_recorder.py tests/unit/test_observability_sentry.py tests/unit/test_replica_readonly_session.py tests/unit/api/test_readonly_replica_wiring.py` → همه سبز (بدون هیچ شکست از سه فایل قبلاً شکست‌خورده).

**کیفیت کد:** `ruff check` روی همهٔ فایل‌های تغییریافته سبز؛ `py_compile` سبز.

**شکست‌های قبلی و نامرتبط (کد تغییرنکرده):**
- `tests/unit/test_brsapi_client_retry.py`, `tests/unit/test_brsapi_kill_switch.py`
  → `FakeEndpoint` فاقد ویژگی `critical` است (تعریف در `brsapi/client.py` که تغییر نکرده).
- `tests/unit/test_brsapi_usage_recorder.py` → پاسخ 401 (نیازمند auth در harness).

---

## ۷. بازبینی عمیق کامل‌بودن (نسخهٔ ۲) — حسابرسی ۵۵/۵۵

در بازبینی دوم، همهٔ شناسه‌های یافتهٔ کارت‌های audit استخراج شد:
`BUD-01..07, CFG-01..05, ENR-01..07, ING-01..12, MW-01..06, OBS-01..05, RRL-01..07, SEC-01..06` — **جمعاً ۵۵**.
۷ شناسه در نسخهٔ اول طرح ذکر نشده بود؛ همه بررسی شدند:

| ID | بررسی در کد | نتیجه |
|---|---|---|
| CFG-03 | `apps/api/middleware.py:257` + `apps/api/app.py:1040` | 🟢 سیم‌کشی موجود است |
| CFG-04 | `core/database.py:222-228` (`_audit_wrote`/dirty) | 🟢 guard درست کار می‌کند |
| CFG-05 | `get_replica_session` تعریف شده بود اما هیچ‌جا `Depends` نمی‌شد | ✅ فاز ۷ رفع شد: به ۷ هندلر فقط‌خواندنی وصل شد + نگهبان read-only |
| SEC-04 | `saas.py` limiter درون‌پروسه‌ای | 🔵 درون‌پروسه‌ای per-worker؛ کم‌خطر |
| ENR-05 | `core/paths.py`, `core/validation/files.py` | 🟢 حاضر |
| ENR-06 | `core/utils.py::safe_error_message` | 🟢 حاضر |
| ENR-07 | flagها در `core/feature_flags/__init__.py` تعریف شده‌اند؛ `ENABLE_SENTRY` در مسیر init استفاده نمی‌شد و Sentry فقط بر اساس `settings.sentry_dsn` فعال می‌شد | ✅ فاز ۷ رفع شد: `sentry_enabled()` هر دو شرط را چک می‌کند |

این دو مورد در فاز ۷ رفع شدند (نه فقط مستند):
1. **CFG-05:** replica به هندلرهای فقط‌خواندنی وصل شد و یک نگهبان نوشتن را روی نشست replica ممنوع می‌کند، پس ریسک «read-after-write» با رد صریح نوشتن مدیریت شد. هندلرهای نویسنده روی primary ماندند و با تست گراف وابستگی تضمین شد.
2. **ENR-07:** `sentry_enabled()` هر دو شرط (DSN + flag) را اعمال می‌کند؛ پیش‌فرض flag به `True` رفت تا رفتار استقرارهای موجود تغییر نکند.

**نتیجه:** هیچ یافتهٔ high/medium و هیچ شکاف باقی‌مانده‌ای (⚠️) وجود ندارد؛ هر ۵۵ شناسه یا اصلاح شده یا با دلیل تأیید/دسته‌بندی شده است.
