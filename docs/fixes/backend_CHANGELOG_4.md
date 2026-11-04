# Backend CHANGELOG 4 — GoldDesk WS pub/sub، تست soft-delete، ممیزی salt

شاخه: `integration/golddesk-fixes` — HEAD زمان شروع: `c18b616b`

## خلاصهٔ وضعیت

| کار | وضعیت | فایل‌ها | تست |
|---|---|---|---|
| ۱) Redis Pub/Sub برای رویدادهای WS (job → API) | fixed | `src/gold_desk/ws_hub.py`، `src/gold_desk/live_signals.py`، `brsapi/jobs/gold_desk_jobs.py`، `tests/gold_desk/test_ws_pubsub.py`، `tests/gold_desk/test_ws_hub.py` | `tests/gold_desk/test_ws_pubsub.py` (۱۵ تست) + به‌روزرسانی تست lifecycle در `test_ws_hub.py`؛ همه پاس |
| ۲) تست soft-delete قابل اجرا و ایمن | fixed | `tests/gold_desk/test_holding_soft_delete.py`، `docs/golddesk_test_db.md` | روی `golddesk_test` واقعی: `2 passed in 9.06s` |
| ۳-الف) ممیزی salt اجباری (فقط‌خواندنی) | fixed (گزارش) | بدون تغییر کد | subprocess probe واقعی |
| ۳-ب) fail-fast در startup بدون `GOLD_API_TOKEN_SALT` | fixed | `apps/api/app.py`، `tests/gold_desk/test_api_token_boot.py` | ۵ تست subprocess؛ `import apps.api.app` بدون salt شکست می‌خورد |
| ۳-ج) راستی‌آزمایی تزریق salt در production | fixed (گزارش) — شکاف دارد | بدون تغییر deployment | بررسی compose/Dockerfile/k8s/CI |

---

## کار ۱ — Redis Pub/Sub

### الگوی اتصال (فقط‌خواندنی، بدون وابستگی جدید)

`hotpath.py` و بقیهٔ GoldDesk از `core.cache.get_cache()` (کلاینت `redis.asyncio`
با `decode_responses=True` و همان `settings.redis_url`) استفاده می‌کنند. همین
مسیر در `ws_hub.py` به کار رفته است: `get_cache().client` برای `publish` و
`client.pubsub()` برای subscribe. هیچ کلاینت/کانفیگ دوم یا وابستگی تازه اضافه نشد.

### تغییرها

- `src/gold_desk/ws_hub.py`
  - ثابت `GOLD_WS_CHANNEL = "golddesk:ws_events"` (و `SUBSCRIBER_BACKOFF_SECONDS=1`،
    سقف `30`).
  - `publish_ws_event(payload)`: با `with_as_of` فیلد `as_of` را تضمین می‌کند و
    پیام JSON را روی کانال publish می‌کند. نبود Redis، نبود `as_of` یا خطای
    publish فقط `warning`/`False` است و استثنا بالا نمی‌آید.
  - `_subscriber_loop()` در `ensure_started` به‌عنوان task سوم (نام
    `golddesk-ws-subscriber`) اضافه شد؛ `stop()` همان مسیر همه را cancel می‌کند.
    قطع اتصال با backoff نمایی (۱ → ۲ → ۴ … تا ۳۰ ثانیه) دوباره وصل می‌شود.
  - `_handle_pubsub_message()`: فقط پیام‌های `message` را می‌پذیرد؛ `bytes` را
    decode می‌کند؛ JSON خراب را `warning` و رد می‌کند؛ پیام بدون `as_of` را رد
    می‌کند. `signal` مستقیم `broadcast` می‌شود؛ `snapshot_ready` با
    `_snapshot_message()` از همان مسیر Redis/hotpath یک snapshot تازه با
    `as_of` واقعی می‌سازد و push می‌کند. `snapshot_ready` هرگز به مرورگر
    نمی‌رود.
- `src/gold_desk/live_signals.py`
  - فقط همان یک فراخوانی: `get_hub().broadcast(...)` جای خود را به
    `publish_ws_event({"type": "signal", "data": s.to_dict()})` داد. منطق
    تشخیص سیگنال، cooldown و ذخیرهٔ prev دست نخورد.
- `brsapi/jobs/gold_desk_jobs.py`
  - `cache_snapshot` + `broadcast` قدیمی حذف شد. بعد از ساخت/ذخیرهٔ snapshot،
    رویداد `{"type": "snapshot_ready", "as_of": snap.snapshot_at.isoformat()}`
    publish می‌شود. دادهٔ ذخیره‌شده در `REDIS_KEY_SNAPSHOT` تغییر نکرد.
  - `get_hub().client_count()` از لاگ حذف شد (دیگر `get_hub` در job import نمی‌شود).

### قرارداد فریم‌ها (خوانده‌شده از frontend، قبل از تغییر)

`frontend/src/lib/goldApi.ts` → `GoldWSManager.onmessage` فقط `msg.type` را
می‌شناسد:

- `snapshot` → `msg.data` به‌عنوان `Snapshot` کامل ذخیره می‌شود؛
- `hot` → `msg.data` در `lastHot` (کلیدهای `GoldHotPayload`)؛
- `signal` → فقط `lastMessageAt` را تازه می‌کند (بدنه تفسیر نمی‌شود)؛
- فریم غیر-JSON (مثل `pong`) نادیده گرفته می‌شود.

کلیدهای مورد انتظار که شکلشان **تغییر نکرد**:

```text
signal:   { "type": "signal", "as_of": "<ISO UTC>", "data": {
            "symbol", "signal_type", "severity", "title", "description",
            "current_value", "threshold", "change_pct", "ts" } }
hot:      { "type": "hot", "as_of": "<ISO UTC>", "data": {
            "status", "timestamp",
            "refs": { "xau_usd", "usd_irt", "aed_gap_pct" },
            "score": { "total", "decision" },
            "signal": { "action", "confidence", "reason" },
            "coin_emami": { "market", "fair", "bubble_pct", "implied_usd" },
            "top_funds": [ { "symbol", "name", "nav", "bubble_pct", "bpr" } ] } }
snapshot: { "type": "snapshot", "as_of": "<ISO UTC>", "data": <Snapshot کامل> }
```

`useGoldWS.ts` فقط همین سه `type` را از `GoldWSInfo` می‌خواند؛ `as_of` را مصرف
نمی‌کند ولی قرارداد hub آن را الزامی می‌داند.

### تست (Redis جعلی، بدون Redis واقعی)

`tests/gold_desk/test_ws_pubsub.py`:

- publish از job (شامل مسیر واقعی `detect_and_broadcast` با کش جعلی) و حفظ
  کلیدها + افزودن `as_of`؛
- رد payload بدون `as_of`؛
- دریافت `signal` در subscriber و broadcast به کلاینت محلی؛
- `snapshot_ready` → فریم `snapshot` فوری با `as_of` واقعی snapshot؛
- نادیده‌گرفتن JSON خراب (با لاگ `warning`) و پیام غیر-object؛
- backoff در اتصال دوباره (`[1.0, 2.0]`)؛
- توقف تمیز task با `stop()` (سه task، همه cancel/done)؛
- خطای Redis در publish و در `detect_and_broadcast` job را نمی‌شکند؛
- پیام `bytes` و نام ثابت کانال.

`tests/gold_desk/test_ws_hub.py` تنها انتظار `len(tasks) == 2` را به ۳ تغییر
داد و کش را در آن تست جعلی کرد تا subscriber به Redis واقعی دست نزند.

---

## قرمزی قبل از رفع (ثبت‌شده)

تست جديد `tests/gold_desk/test_ws_pubsub.py` قبل از پیاده‌سازی اجرا شد:

```text
=================================== ERRORS ====================================
_____________ ERROR collecting tests/gold_desk/test_ws_pubsub.py ______________
ImportError while importing test module '...\tests\gold_desk\test_ws_pubsub.py'.
...
tests\gold_desk\test_ws_pubsub.py:20: in <module>
    from src.gold_desk.ws_hub import (
E   ImportError: cannot import name 'GOLD_WS_CHANNEL' from 'src.gold_desk.ws_hub'
=========================== short test summary info ============================
ERROR tests/gold_desk/test_ws_pubsub.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 7.08s
```

بعد از پیاده‌سازی:

```text
34 passed in 24.12s
```

(۳۴ = تست‌های pub/sub + hub + subprocess salt.)

---

## کار ۲ — تست soft-delete

`tests/gold_desk/test_holding_soft_delete.py`:

- بدون `GOLD_TEST_DATABASE_URL` → `pytest.skip(..., allow_module_level=True)` با
  پیام روشن.
- اگر آدرس بعد از normalization با `settings.database_url_async` یکی باشد →
  skip؛ اگر نام دیتابیس شامل `test` نباشد → skip. `postgresql://` و
  `postgres://` به `postgresql+asyncpg://` تبدیل می‌شوند؛ `postgresql+asyncpg://`
  دست‌نخورده می‌ماند.
- اگر جدول‌های `GoldDeskBase.metadata` نباشند، فقط روی engine همین تست
  `metadata.create_all` اجرا می‌شود (checkfirst؛ بدون migration).
- teardown فقط ردیف‌های دو نماد یکتای همین اجرا (`_TD_A_<run>`/`_TD_B_<run>`) را
  پاک می‌کند؛ هیچ `LIKE` یا assert سراسری نیست.

تأییدهای واقعی (بدون اتصال به دیتابیس):

```text
# بدون env
SKIPPED [1] tests\gold_desk\test_holding_soft_delete.py:33: GOLD_TEST_DATABASE_URL is not set;
skipping the soft-delete DB test so the application database is never touched
1 skipped in 5.60s

# با آدرس دیتابیس غیر test
SKIPPED [1] tests\gold_desk\test_holding_soft_delete.py:76: test database name 'my_first_db'
does not contain 'test'; refusing to run against a non-test database
1 skipped in 5.66s

# با آدرس برابر settings.database_url_async
app-db guard fired: True
skipped: True
```

`docs/golddesk_test_db.md` روش ساخت `golddesk_test` (psql و docker exec با
placeholder)، ست‌کردن `GOLD_TEST_DATABASE_URL` فقط در session پاورشل و دستور
اجرا را توضیح می‌دهد و تأکید می‌کند نباید `my_first_db` باشد.

> **اجرای واقعی:** دیتابیس `golddesk_test` ساخته شد (بدون دست‌زدن به داده‌های
> `my_first_db`) و تست با `GOLD_TEST_DATABASE_URL` همان دیتابیس اجرا شد:
>
> ```text
> 2 passed in 9.06s
> ```
>
> جدول‌ها با `create_all` در همان دیتابیس تست ساخته شدند و teardown فقط دو
> نماد یکتای همان اجرا را پاک کرد.

---

## کار ۳ — ممیزی salt اجباری (بدون تغییر کد)

`src.gold_desk.api_token` در سطح ماژول `GOLD_API_TOKEN_SALT` را می‌خواند و بدون
آن `RuntimeError` می‌دهد. تنها مصرف‌کنندهٔ مستقیم آن `src/gold_desk/api.py` است
(خطوط ۷۵۲، ۷۷۹، ۸۰۰، ۱۴۲۱ — همه **داخل تابع**، نه سطح ماژول) و تست‌ها.

نتیجهٔ probe واقعی روی import زنجیرهٔ entrypointها بدون salt:

قبل از تغییر (پروب اولیه):

```text
src.gold_desk.api_token: import=FAIL (RuntimeError: GOLD_API_TOKEN_SALT is not set ...)
src.gold_desk.api:       import=OK  api_token_loaded=False
apps.api.router:         import=OK  api_token_loaded=False
apps.api.app:            import=OK  api_token_loaded=False
apps.worker.app:         import=OK  api_token_loaded=False
apps.scheduler.app:      import=OK  api_token_loaded=False
apps.currency_service.app: import=OK  api_token_loaded=False
apps.admin.app:          import=OK  api_token_loaded=False
ingestion.main:          import=OK  api_token_loaded=False
```

بعد از تغییر (fail-fast در entrypoint):

```text
$ python -c "import apps.api.app"   # بدون GOLD_API_TOKEN_SALT
RuntimeError: GOLD_API_TOKEN_SALT is not set; API token hashing needs an explicit salt
```

| کاندید | entrypoint | api_token را در import لود می‌کند؟ | `GOLD_API_TOKEN_SALT` |
|---|---|---|---|
| compose `backend` | `uvicorn apps.api.app:app` | **بله** (guard سطح ماژول) | بله، اجباری با `:?` (`docker-compose.yml:59`) |
| compose `worker` | `python -m apps.worker.app` | خیر | بله، اجباری با `:?` (`docker-compose.yml:86`) |
| compose `currency` | `uvicorn apps.currency_service.app:currency_app` | خیر | تعریف نشده (نیازی هم نیست) |
| compose `frontend` / `timescaledb` / `redis` | — | خیر | — |
| `docker-compose.production.yml` (`api`/`admin`/`worker`/`scheduler`) | همان imageها | **بله** برای `api`/`admin` (همان `apps.api.app`) | **شکاف:** فقط `env_file: .env.production`؛ هیچ `:?` یا secret صریحی وجود ندارد |
| `Dockerfile.golddesk` | `python -m apps.scheduler.app --only gold_desk` | خیر (scheduler توکن hash نمی‌کند) | در image/compose مرجعی پیدا نشد؛ باید در deployment تزریق شود |
| k8s | فقط manifestهای decision-engine (API/worker/GoldDesk وجود ندارد) | — | تعریف نشده |
| `scripts/` | — | هیچ import از `gold_desk.api`/`api_token` یافت نشد | — |
| `jobs/` (worker) | `apps.worker.app` | خیر | در compose worker بله |
| CI | `.github/workflows/ci.yml:289` | — | بله (`ci-only-salt-not-a-real-secret`) |
| pytest | `tests/conftest.py:80` | فقط تست‌های token | `test-salt-for-pytest` |

### تست subprocess

`tests/gold_desk/test_api_token_boot.py`:

- بدون env، `import src.gold_desk.api_token` → کد خروج غیرصفر و پیام
  `GOLD_API_TOKEN_SALT is not set`؛
- بدون env، `import apps.api.app` (entrypoint واقعی) هم با همان پیام شکست
  می‌خورد → process API بالا نمی‌آید؛
- با env، هم `api_token`، هم `src.gold_desk.api` و هم `apps.api.app` import
  می‌شوند؛
- بدون env، `import src.gold_desk.api` تنها **موفق** است و `api_token` را لود
  نمی‌کند؛ به همین دلیل guard در `apps/api/app.py` (entrypoint) گذاشته شد، نه در
  `api.py`.

> **تغییر نسبت به گزارش قبلی:** فرض اولیه («import `src.gold_desk.api` بدون
> salt شکست می‌خورد») درست نبود. حالا با درخواست صریح «fail-fast در startup»،
> `apps/api/app.py` ماژول `api_token` را در سطح ماژول import می‌کند و بدون salt
> کل process API شکست می‌خورد. `api.py` و `apps/api/router.py` دست نخوردند.

### راستی‌آزمایی production (بدون تغییر deployment)

- `docker-compose.yml` (dev): هر دو سرویس `backend` و `worker` با `:?` نمک را
  اجباری می‌کنند.
- `docker-compose.production.yml`: همهٔ سرویس‌ها با لنگر `*app-prod` فقط
  `env_file: .env.production` دارند؛ **هیچ `GOLD_API_TOKEN_SALT` صریح یا `:?`
  وجود ندارد.** اگر آن فایل کلید را نداشته باشد، API با fail-fast جدید در
  startup می‌میرد (که خوب است) ولی scheduler/GoldDesk image بدون بررسی بالا
  می‌آید.
- `k8s/` فقط manifestهای decision-engine را دارد؛ هیچ deploymentای برای API،
  worker یا GoldDesk scheduler نیست، پس تزریق salt در k8s قابل بررسی نیست.
- `.env.example` فقط `GOLD_API_TOKEN_SALT=` خالی دارد؛ CI مقدار تستی
  `ci-only-salt-not-a-real-secret` را می‌دهد.
- **نتیجه:** تزریق salt در production **تضمین‌شده نیست**؛ صاحب پروژه باید در
  `docker-compose.production.yml` (یا secret manager) آن را با `:?`/secret
  اجباری کند.

---

## تأیید نهایی

دستور درخواستی (خروجی عیناً):

```text
$ python -m pytest tests/gold_desk -q -p no:cacheprovider
...
323 passed, 1 skipped, 1 warning in 49.66s
```

- ۱ skip همان `test_holding_soft_delete.py` است (بدون `GOLD_TEST_DATABASE_URL`).
- همان تست با `GOLD_TEST_DATABASE_URL` روی `golddesk_test` جداگانه اجرا شد:
  `2 passed in 9.06s`.
- انتظار «حداقل ۳۰۳ پاس» برآورده شد (۳۲۳).
- `metrics.py`، `hotpath.py` و `tests/conftest.py` در محدوده بودند ولی تغییری
  لازم نداشتند.

## سؤالات باز

1. ~~fail-fast در startup~~ — انجام شد: `apps/api/app.py` بدون salt بالا نمی‌آید.
2. `docker-compose.production.yml` هیچ `GOLD_API_TOKEN_SALT` صریحی ندارد و به
   `.env.production` تکیه می‌کند؛ محتوای env بررسی نشد، پس تزریق production
   تضمین‌شده نیست (شکاف باز).
3. `tests/conftest.py` برای گیت `needs_db` فقط دیتابیس برنامه را probe می‌کند،
   نه `GOLD_TEST_DATABASE_URL`. اگر دیتابیس برنامه در دسترس نباشد ولی دیتابیس
   تست بالا باشد، تست soft-delete با گیت session skip می‌شود (سریع و ایمن، ولی
   «اجرا نشدن»).
4. در scheduler، `get_cache().initialize()` به‌صورت task جدا شروع می‌شود؛ اگر
   job در همان لحظه publish کند و کلاینت هنوز آماده نباشد، فقط warning ثبت
   می‌شود و رویداد از دست می‌رود (بدون retry). بعد از ۵ دقیقهٔ اول معمولاً
   بی‌اثر است.

## کارهایی که فقط صاحب پروژه می‌تواند

1. یک `GOLD_API_TOKEN_SALT` واقعی در محیط production (`.env.production` یا
   secret manager) ست و در صورت تغییر، توکن‌های قبلی را بازصدور کند.
2. در `docker-compose.production.yml` (یا manifestهای deployment) نمک را با
   `:?`/secret اجباری کند تا fail-fast فقط موقع درخواست token دیده نشود.
3. مطمئن شود API و scheduler/worker به **همان** Redis و کانال
   `golddesk:ws_events` دسترسی دارند.
4. (اختیاری) گیت `needs_db` در `tests/conftest.py` را به
   `GOLD_TEST_DATABASE_URL` هم وصل کند تا وقتی DB برنامه پایین است ولی DB تست
   بالاست، تست soft-delete الکی skip نشود.
