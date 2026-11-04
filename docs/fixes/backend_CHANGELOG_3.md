# Backend batch 3 — گزارش نهایی (GoldDesk)

شاخه: `integration/golddesk-fixes` · محیط: Windows + bash (Git Bash) + `venv/Scripts/python.exe` (Python 3.11.9، pytest 9.1.1)

هیچ commit/stash/checkout/reset/clean/push انجام نشد. فقط فایل‌های محدودهٔ مجاز تغییر کردند
(فهرست کامل: `docs/fixes/backend_paths_3.txt`). موتور، `frontend/`، `migrations/`،
Docker/nginx، `docs/analysis/`، `brsapi/jobs/`، `scripts/` و `apps/api/router.py` دست نخوردند.
هیچ ردیفی به دیتابیس جاری (`my_first_db`) اضافه/حذف/ویرایش نشد.

## جدول کارها

| # | کار | وضعیت | فایل‌ها | تست |
|---|---|---|---|---|
| 1 | `ws_hub` (C10): دو حلقهٔ جدا، `as_of`، timeout، lifecycle، snapshot از Redis | fixed | `src/gold_desk/ws_hub.py` | `tests/gold_desk/test_ws_hub.py` (۱۵ تست) |
| 2 | `api_token` (C9): حذف salt پیش‌فرض و fail-fast بدون `GOLD_API_TOKEN_SALT` | fixed | `src/gold_desk/api_token.py`, `tests/conftest.py` (از قبل مقدار تست را می‌گذاشت) | `tests/gold_desk/test_api_token_salt.py` (۴ تست) |
| 3 | `/metrics` (C9): فقط Bearer API-token با scope `metrics` | fixed | `src/gold_desk/api.py` | `tests/gold_desk/test_metrics_scope.py` (۷ تست) |
| 4 | `deleted_at`: رد دارایی soft-delete‌شده در مسیرهای id‌محور | fixed | `src/gold_desk/portfolio.py`, `src/gold_desk/api.py` | `tests/gold_desk/test_holding_soft_delete_reject.py` (۹ تست) |
| 5 | تست soft-delete روی دیتابیس تست ایزوله | fixed (اجرا نشد — env تنظیم نیست) | `tests/gold_desk/test_holding_soft_delete.py` | همان فایل؛ `1 skipped` با پیام روشن |
| 6 | `snapshot_service`: حذف `hasattr` + بررسی H1 | fixed (hasattr) / already-fixed (H1) | `src/gold_desk/snapshot_service.py` | `tests/gold_desk/test_snapshot_score_fields.py` (۳ تست) |
| 7 | `api.py`: telegram JSON-only، `/portfolio` (id, priced_cost, null)، `oos_*` | fixed | `src/gold_desk/api.py`, `src/gold_desk/portfolio.py` | `tests/gold_desk/test_api_contract_fields.py` (۷ تست) |
| 8 | اجرای `tests/gold_desk` بدون DB و فایل `test_contract_no_data.py` | done | — | `303 passed, 1 skipped`؛ فایل قرارداد وجود ندارد |

## یافته‌های فاز اول (فقط‌خواندنی، با شواهد واقعی)

### ۱) `ws_hub.py` — وضعیت قبل

- یک حلقهٔ واحد `start_broadcast_task`: `sleep(10)` → hot، `sleep(20)` → snapshot؛ یعنی snapshot هر ۳۰ ثانیه (نه ۳۰۰).
- hot از `self._last_snapshot` ساخته می‌شد و اگر خالی بود `{}` می‌فرستاد (`self._last_snapshot or {}`).
- `broadcast` ارسال‌ها را **داخل `self._lock`** و سریال انجام می‌داد؛ یک کلاینت کند همه را بلاک می‌کرد.
- هیچ timeout روی `send_json` نبود.
- `get_hub()` داخل خودش `asyncio.create_task(...)` می‌ساخت — `metrics.py::ws_client_count()` و هر فراخوان خارج از event loop باعث `RuntimeError: no running event loop` می‌شد (که در metrics با `except Exception` به `0` تبدیل می‌شد).
- کامنت آلمانی: `# Produkt پیام از client (ping/pong)`.

### ۲) فراخوان‌های `cache_snapshot` و `get_hub` (کجا و کدام process)

| محل | فراخوانی | process |
|---|---|---|
| `brsapi/jobs/gold_desk_jobs.py:99-100` | `hub.cache_snapshot(snap_dict)` + `await hub.broadcast({...})` | scheduler/worker (job با `cron=300`) — **process جدا از API** |
| `brsapi/jobs/gold_desk_jobs.py:132` | `get_hub().client_count()` (لاگ) | scheduler/worker |
| `src/gold_desk/live_signals.py:232` | `get_hub().broadcast({"type": "signal", ...})` | job process (از snapshot job صدا زده می‌شود) |
| `src/gold_desk/metrics.py:96` | `get_hub().client_count()` | API (و هر جا /metrics رندر شود) |
| `src/gold_desk/api.py` (`/gold/ws` → `ws_endpoint`) | `get_hub()`، `register`/`unregister` | API |

نتیجهٔ عملی: `cache_snapshot` در **process دیگر** اجرا می‌شد، پس `_last_snapshot` در API همیشه `None` بود و کلاینت‌های WS پیام `{"type":"hot","data":{}}` می‌گرفتند. اصلاح: حلقه‌ها snapshot را از Redis (`hotpath.get_hot_snapshot()`) می‌خوانند و حافظهٔ محلی فقط fallback است. فایل job تغییر نکرد چون `broadcast` خودش `as_of` را از `data.snapshot_at` استخراج می‌کند.

### ۳) گیت احراز هویت مسیرهای gold

- `apps/api/router.py:291` — `anonymous_router` (فقط `/gold/health`, `/gold/assistant-rules`, `/gold/ws`) بدون هیچ dependency.
- `apps/api/router.py:295-298` — `src.gold_desk.api.router` با `dependencies=_require_user` (JWT) مانت می‌شود؛ همین گیت `/api/v1/gold/metrics` را ۴۰۱ می‌کرد.
- شاهد واقعی در لاگ موجود: `baseline_api.txt:213` → `GET /api/v1/gold/metrics -> 401`.
- `apps/api/middleware.py` فقط نوشتن‌ها را روی `/api/v1/gold/` گیت می‌کند و `/metrics` را در rate-limit مستثنی می‌کند؛ برای GET مانعی نبود.

### ۴) `portfolio.py:553` و `api.py:976` (شماره خط‌ها جابه‌جا شده‌اند)

- قبل: `portfolio.py:552-555` → `record_trade(...)`: `if action == "sell" and holding_id: h = await session.get(GoldHoldingModel, holding_id); if h: pnl = ...`. اگر ردیف نبود یا `deleted_at` داشت، **بدون خطا** با `pnl_irt = 0` ثبت می‌شد.
- `api.py:976` در درخت فعلی دیگر «گرفتن holding با id» نیست؛ آن خط اکنون `new_h = GoldHoldingModel(**h.model_dump())` در `add_holding` (ساخت، نه خواندن) است. مسیرهای واقعی id‌محور:
  - `api.py:1159` `post_trade` → `record_trade(..., holding_id=...)`
  - `api.py:1003` `delete_holding` → `session.get(GoldHoldingModel, holding_id)`

## تغییرات (خلاصهٔ پیاده‌سازی)

1. **`ws_hub.py` (بازنویسی)**
   - `HOT_INTERVAL_SECONDS = 10`, `SNAPSHOT_INTERVAL_SECONDS = 300`؛ دو حلقهٔ مستقل `_hot_loop` / `_snapshot_loop` (هیچ چرخهٔ ۳۰ثانیه‌ای نمانده).
   - hot از `hotpath.get_hot_snapshot()` و `build_hotpath_response` ساخته می‌شود (نه از `_last_snapshot`).
   - هر پیام فیلد `as_of` (ISO UTC) دارد؛ `payload_as_of` از `as_of`/`snapshot_at` ریشه یا `data.snapshot_at|as_of|ts` (epoch) استخراج می‌کند. پیام بدون زمان داده **فرستاده نمی‌شود** (`None` ⇒ skip)، `{}` هم فرستاده نمی‌شود.
   - `broadcast`: کپی کلاینت‌ها زیر قفل، سپس `asyncio.gather` + `asyncio.wait_for(send_json, 5s)` بیرون از قفل؛ کلاینت timeout/خطادار حذف می‌شود.
   - `get_hub()` دیگر `create_task` نمی‌سازد؛ `ensure_started()` (async، پس loop حتمی است) دو task می‌سازد و `stop()` آن‌ها را cancel می‌کند. `ws_endpoint` هم `ensure_started` را صدا می‌زند.
   - `register` نسخهٔ cache‌شده را با همان timeout می‌فرستد.
2. **`api_token.py`**: `GOLD_API_TOKEN_SALT` اجباری است و **در هر محیطی** (نه فقط production) import بدون آن `RuntimeError` می‌دهد؛ هیچ salt پیش‌فرضی باقی نمانده. `has_scope()` اضافه شد و `metrics` به scopeهای مجاز `POST /gold/tokens` اضافه شد. `tests/conftest.py` از قبل `os.environ.setdefault("GOLD_API_TOKEN_SALT", "test-salt-for-pytest")` را داشت و دست نخورد.
   - **هشدار مهاجرت:** تغییر/تعیین salt، hash همهٔ توکن‌های قبلی را عوض می‌کند و آن‌ها را **باطل** می‌کند؛ کاربر باید توکن بسازد.
3. **`/metrics`**: مسیر از `router` (پشت JWT) به `anonymous_router` منتقل شد و dependency `api_key_auth` گرفت: `Authorization: Bearer <api-token>` با scope دقیقاً `metrics` وگرنه `401` + `WWW-Authenticate: Bearer`. `admin` جای `metrics` را نمی‌گیرد. این تنها «راه عبور» ساخته‌شده از گیت JWT است و کوچک/دقیق: همان یک route، همان یک dependency؛ بقیهٔ ۶۲ عملیات `router` دست‌نخورده.
   - نام تابع عمداً `api_key_auth` است چون `scripts/check_router_auth.py` فقط نام‌های شناخته‌شدهٔ `AUTH_NAMES` را «auth» می‌شمارد؛ `scripts/` تغییر نکرد و گیت با exit 0 پاس می‌شود (خروجی پایین).
4. **`deleted_at`**: تابع مشترک `portfolio.get_active_holding()` با دو خطای `HoldingNotFoundError` (→ 404) و `HoldingDeletedError` (→ 409). `record_trade` هر `holding_id` (خرید یا فروش) را اعتبارسنجی می‌کند؛ `post_trade` استثناها را به 404/409 نگاشت می‌کند. `DELETE /portfolio/holdings/{id}` روی ردیف soft-delete‌شده بدون `?force=true` اکنون **409** می‌دهد (قبلاً `200 {"deleted": false}`).
5. **تست soft-delete**: فقط با `GOLD_TEST_DATABASE_URL`؛ در نبود آن skip سطح ماژول با پیام روشن. نمادها یکتا (`_TD_A_<run8>`/`_TD_B_<run8>`) و پاک‌سازی setup+teardown فقط با `symbol IN (دو نماد)`؛ هیچ `like("_TD%")` و هیچ assert روی کل جدول. اثبات مستقیم: ردیف A می‌ماند با `deleted_at` غیر null، ردیف B دست‌نخورده، و tupleهای (id, symbol, quantity, amount_irt, holding_id) معامله‌ها قبل/بعد یکی هستند. assertion متناقض قبلی (روی خروجی فیلترشده) حذف شد.
6. **`snapshot_service`**: `hasattr(...)` حذف و `raw_total` / `available_weight` / `data_coverage_pct` مستقیم خوانده می‌شوند.
   - H1 (`reversed(closes[-days:])` که جدیدترین ردیف‌ها را دور می‌ریخت) قبلاً در `signal_engine.py` (`_newest_window_ascending`, E-H1) رفع شده و در `snapshot_service.py:146,177` فقط مصرف می‌شود؛ تست جدید ثابت می‌کند مصرف‌کننده دو نقطهٔ **جدیدتر** را مقایسه می‌کند (`[90,100,110] → +10%`). کد این بخش تغییری لازم نداشت.
7. **`api.py`**:
   - `POST /gold/telegram/test`: `request: Request` به امضا اضافه شد (قبلاً `request` تعریف‌نشده بود و `NameError` را هم `except Exception` می‌بلعید)؛ فقط `json.JSONDecodeError` گرفته می‌شود.
   - `GET /gold/portfolio`: `priced_cost` + `id` (فقط وقتی گروه یک ردیف دارد) و `holding_ids` (همیشه) برای هر دارایی؛ `pnl_pct`/`current_value`/`pnl_irt` برای دارایی بی‌قیمت `null` می‌مانند.
   - `GET /gold/backtest/strategy`: پنج فیلد `oos_start` (ISO یا `null`), `oos_total_return_pct`, `oos_buy_hold_return_pct`, `oos_alpha_pct`, `oos_max_drawdown_pct` از `StrategyMetrics` منتقل شد (موتور از قبل محاسبه می‌کرد).
8. **`schemas.py` (ضروری، یک خط)**: درخت کار یک ویرایش commit‌نشده داشت که `class DCARequest` را داخل کامنت همان خط گذاشته بود (`# ── DCA ───class DCARequest(BaseModel):`) و **import کل `src.gold_desk.api` را می‌شکست** (`ImportError: cannot import name 'DCARequest'`). خط به دو خط تقسیم شد تا ماژول import شود؛ هیچ تغییری در مدل داده نبود.

## خروجی واقعی تست‌ها

### قرمزی قبل از رفع (baseline = HEAD `23a44ba9` در worktree موقت `_red_base`، همان ۶ فایل تست جدید)

```
$ ../venv/Scripts/python.exe -m pytest tests/gold_desk/test_ws_hub.py \
    tests/gold_desk/test_api_token_salt.py tests/gold_desk/test_metrics_scope.py \
    tests/gold_desk/test_holding_soft_delete_reject.py tests/gold_desk/test_api_contract_fields.py \
    tests/gold_desk/test_snapshot_score_fields.py -q --continue-on-collection-errors

ERROR tests/gold_desk/test_ws_hub.py
  ImportError: cannot import name 'HOT_INTERVAL_SECONDS' from 'src.gold_desk.ws_hub'
ERROR tests/gold_desk/test_holding_soft_delete_reject.py
  ImportError: cannot import name 'HoldingDeletedError' from 'src.gold_desk.portfolio'
FAILED tests/gold_desk/test_api_token_salt.py::test_import_fails_without_salt
FAILED tests/gold_desk/test_api_token_salt.py::test_no_builtin_default_salt_remains
FAILED tests/gold_desk/test_api_token_salt.py::test_metrics_scope_is_recognised
FAILED tests/gold_desk/test_metrics_scope.py::test_metrics_accepts_bearer_token_with_metrics_scope
FAILED tests/gold_desk/test_metrics_scope.py::test_metrics_rejects_missing_token
FAILED tests/gold_desk/test_metrics_scope.py::test_metrics_rejects_unknown_token
FAILED tests/gold_desk/test_metrics_scope.py::test_metrics_rejects_jwt_session_token
FAILED tests/gold_desk/test_metrics_scope.py::test_metrics_rejects_tokens_with_another_scope[read-token]
FAILED tests/gold_desk/test_metrics_scope.py::test_metrics_rejects_tokens_with_another_scope[admin-token]
FAILED tests/gold_desk/test_metrics_scope.py::test_metrics_route_sits_on_the_token_gated_router
FAILED tests/gold_desk/test_snapshot_score_fields.py::test_score_coverage_fields_come_straight_from_the_engine
  AttributeError: 'ScoreBlock' object has no attribute 'raw_total'
FAILED tests/gold_desk/test_snapshot_score_fields.py::test_score_without_coverage_fields_is_not_silently_defaulted
  pydantic ValidationError (ScoreBlock.decision بدون NO_DATA در آن رفرنس)
ERROR tests/gold_desk/test_api_contract_fields.py (۷ مورد — fixture: PortfolioSummary بدون priced_cost)
12 failed, 2 passed, 1 warning, 9 errors in 8.88s
```

دو تستی که از قبل سبز بودند: `test_salt_comes_from_env_and_hashes_with_it` و
`test_daily_changes_use_the_newest_two_closes` (دومی تأیید می‌کند H1 قبلاً در موتور رفع شده است).

### بعد از رفع (درخت کاری، ۶ فایل تست جدید + کل مجموعهٔ gold_desk)

```
$ ./venv/Scripts/python.exe -m pytest tests/gold_desk -q -p no:cacheprovider
303 passed, 1 skipped, 1 warning in 10.21s
```

جزئیات skip (با جمع‌آوری needs_db):

```
$ ./venv/Scripts/python.exe -m pytest tests/gold_desk -q -p no:cacheprovider \
    --override-ini="addopts=" -rs
SKIPPED [1] tests\gold_desk\test_holding_soft_delete.py:27: GOLD_TEST_DATABASE_URL is not set;
  skipping the soft-delete DB test so the application database is never touched
303 passed, 1 skipped, 1 warning in 10.28s
```

قبل از این batch همین مجموعه `258 passed, 1 deselected in 9.58s` بود؛ ۴۵ تست جدید اضافه شده است.

### گیت CI احراز هویت مسیرها

```
$ ./venv/Scripts/python.exe scripts/check_router_auth.py
Audited 703 router operations and 8 app-level routes.
Router auth audit OK — every operation is authenticated or on the documented allowlist.
exit=0
```

### تست‌های واحد موجود که به این سطح API وابسته‌اند (خارج از محدودهٔ ویرایش، فقط اجرا)

```
$ ./venv/Scripts/python.exe -m pytest tests/unit/api/test_gold_personal_surface_auth.py \
    tests/unit/api/test_golddesk_portfolio_returns.py -q -p no:cacheprovider
48 passed, 2 warnings in 50.66s
$ ./venv/Scripts/python.exe -m pytest tests/unit/test_gold_portfolio_history.py -q -p no:cacheprovider
20 passed in 5.78s
```

### `tests/gold_desk/test_contract_no_data.py`

وجود ندارد (`ls` → `No such file or directory`؛ `find tests -name "test_contract*"` → خروجی خالی)، بنابراین اجرا نشد.

## سؤالات باز

1. **`409` برای حذف دوباره:** آیا کلاینتی به پاسخ قبلی `200 {"deleted": false, "reason": "already_deleted"}` وابسته است؟ رفتار اکنون `409` + راهنمای `?force=true` است.
2. **scope `metrics` و `admin`:** عمداً `admin` جای `metrics` را نمی‌گیرد. اگر اپراتور انتظار دارد توکن admin برای scrape کافی باشد، باید صریح تصمیم گرفته شود.
3. **شروع حلقه‌های WS:** lazy است (اولین اتصال WS). اگر بک‌گراند بدون کلاینت هم باید snapshot/hot را publish کند، یک lifespan در `apps/api/app.py` لازم است (خارج از محدودهٔ این batch).
4. **چند worker API:** هر process حلقه‌های خودش را دارد؛ چون کلاینت‌ها per-process هستند پیام تکراری به یک کلاینت نمی‌رسد، ولی تعداد خواندن Redis با تعداد workerها بالا می‌رود.
5. **`GOLD_TEST_DATABASE_URL` در CI:** بدون آن تست soft-delete همیشه skip می‌شود؛ یک Postgres تستی اختصاصی لازم است.
6. **`as_of` روی فرانت:** فرانت فعلاً `as_of` را نمی‌خواند (از `timestamp` استفاده می‌کرد)؛ افزودن `as_of` سازگار است ولی استفاده از آن در UI تصمیم جداست.
