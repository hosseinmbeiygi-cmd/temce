# قسمت ۰۲ — لایه HTTP، Router، احراز هویت و میانافزارها

| | |
|---|---|
| **تاریخ** | ۲۰۲۶-۱۱-۱۴ |
| **کامیت مبنا** | `091fdf31` |
| **روش** | خواندن مستقیم + پارس AST فقطخواندنی + تطبیق با دو گارد تست و `scripts/auth_policy.py` |
| **محدوده** | `apps/api/router.py`, `dependencies.py`, `middleware.py`, `pagination.py`, `auth.py`, `openapi_security.py`, `core/security/`, `core/config/__init__.py` (بخش نرخگیری), `tests/unit/api/test_api05_mount_decisions.py`, `tests/unit/test_api_router_surface_inventory.py` |
| **وابسته به** | قسمت ۰۱ (ترتیب میانافزارها و routeهای درونخطی آنجا بررسی شد) |
| **اعتبار مقابل HEAD** | با وجود ۱۰ کامیت تازه تا `9a100a6f`، هیچیک از فایلهای `router.py`, `dependencies.py`, `middleware.py`, `pagination.py`, `auth.py`, `openapi_security.py`, `core/security/`، تنظیمات نرخگیری یا دو گارد تست تغییر نکردهاند → همه ۱۳ یافته `HTTP-*` زندهاند |

---

## ۱. شمارش دقیق (با اسکریپت، نه مستندات)

| معیار | مقدار | منبع |
|---|---:|---|
| فایل در `apps/api/endpoints/` | **۸۳** | شمارش فایل (بدون `__init__.py`) |
| ماژول importشده در `router.py` | **۷۵** | regex روی `ImportFrom` |
| ماژول importنشده | **۸** | تفاضل |
| `include_router(...)` | **۸۰** | `grep -c` |
| ورودی `_ENDPOINTS` (فهرست اعلامی) | **۴۵** | شمارش `"path":` |
| Router عمداً نصبنشده (API-05) | **۷** | `DECISIONS` و `KNOWN_UNMOUNTED` |
| decorator route در کل endpoints | **۶۶۸** + ۲ WS | گزارش ۱۶۰ لایهای |
| wrapper `get_*_service` در `dependencies.py` | **۳۹** | `grep -c '^def get_.*service'` |
| کلاس میانافزار در `middleware.py` | **۸** | `grep '^class '` |
| کلید `endpoint_rate_limits` | **~۴۰** | `core/config/__init__.py:196+` |
| پیشفرض نرخ مسیرهای پیکربندینشده | **۳۰۰/min** | `provider_rate_limit_per_minute` (خط ۱۹۱) |

هشت ماژول importنشده عبارتاند از:
```
backtest_requests, comprehensive_analysis, ime, monitoring,
proposals, scanner, sentiment, symbol_alerts
```
**تصحیح مهم:** فقط **هفت**تای آنها واقعاً router تعریف میکنند. `backtest_requests.py` (۷۶ خط) حتی یک `APIRouter` هم ندارد — ماژول کمکی/اسکیماست که صرفاً در پوشه `endpoints/` نشسته. بههمیندلیل تست سطح `test_api_router_surface_inventory.py` که دنبال `ast.Assign` با هدف `router` میگردد، آن را «unmounted router» بهحساب نمیآورد. ادعای «۸ ماژول endpoint نصبنشده» درگزارش اصلی دقیق نبود (لایه ۴۱ و R7 اصلاح شدند).

---

## ۲. `Router.setup()` — معماری mount

```python
_ENDPOINTS = [ ... 45 ورودی {"path", "tag", "description"} ... ]   # :23

def setup(self) -> APIRouter:                                       # :169
    router = APIRouter()

    @router.get("", ...)                                            # :172-180
    async def api_root():
        return ApiResponse(success=True, data={"version": "v1",
                                               "endpoints": _ENDPOINTS})

    # API-05 decision: seven routers stay unmounted (2026-10-29)     # :182-200
    # lazy imports of 75 endpoint routers                            # :204+
    ... 80× router.include_router(...) ...
    return router
```

**`_ENDPOINTS` فقط یک فهرست اعلامی است** که `GET /api/v1` آن را برمیگرداند؛ هیچ نقشی در mount کردن ندارد (تنها دو ارجاع در کل فایل: تعریف خط ۲۳ و مصرف خط ۱۷۸). با ۸۰ `include_router` و ۴۵ ورودی، **نمایه رسمی API حدود ۴۴٪ سطح واقعی را معرفی میکند**. همچنین کامنت تنبلی import در خط ۲۰۴ میگوید «all 45 endpoint files (~45s cumulative)» در حالی که ۷۵ ماژول import میشود — عدد ۴۵ از همان فهرست کهنه کپی شده است. فرانتاندی که بخواهد مسیرها را از `GET /api/v1` کشف کند، نیمی از API را نمییابد.

الگوی import تنبل خودش درست است: کامنت توضیح میدهد که import سطحماژول `Router` حدود ۳۰۰ms و import تمام endpointها حدود ۴۵s طول میکشد، پس واردات به درون `setup()` منتقل شده — گرچه `setup()` خودش در `create_app()` و هنگام import اپ فراخوانی میشود، بنابراین صرفهجویی عملاً فقط برای ابزارهایی است که `Router` را بدون ساختن اپ import میکنند (مثل تستها).

**نمونه تصمیمهای mount (از انتهای فایل):**
- `/tests` → `_require_admin` با دلیل صریح: «Running the test-suite spawns a subprocess on the server».
- `/tables` → `_require_admin`: «Table browser exposes arbitrary database metadata/rows».
- `/pre-buy` → `_public_read`: «Reads (catalogue/instruments) stay anonymous; writes still require a JWT».
- `/brsapi` → `_require_user` ولی routeهای `/manage/*` گیت admin جداگانه دارند چون «burn the BrsApi daily quota and can run for hours».
- `/market-info` → `_public_read`، prefix عوض شده تا با `funds_router` تداخل نکند.
- `/system` → **بدون dependency سطح mount**، با توضیح که احراز درون خود router انجام میشود (kill switch + permission check).
- `/ws` و `/ws/precompute` → **بدون هیچ dependency سطح mount**؛ امنیت باید درون هندلر WebSocket باشد.

تصمیمها تقریباً همگی دلیلنویسی شدهاند — این یکی از منضبطترین قسمتهای مخزن است.

---

## ۳. چهار رده دسترسی

```python
from apps.api.dependencies import require_roles as require_any_role   # :5
_public_read     = [Depends(require_user_for_writes)]                  # :14
_require_analyst = [Depends(require_any_role("analyst", "admin"))]    # :19
_require_admin   = [Depends(require_any_role("admin"))]               # :20
_require_user    = [Depends(require_any_role("user", "analyst", "admin"))]  # :21
```

| رده | GET ناشناس | نوشتن ناشناس | کاربر | تحلیلگر | ادمین |
|---|---|---|---|---|---|
| `_public_read` | ✅ | ❌ ۴۰۱ | ✅ | ✅ | ✅ |
| `_require_user` | ❌ | ❌ | ✅ | ✅ | ✅ |
| `_require_analyst` | ❌ | ❌ | ❌ | ✅ | ✅ |
| `_require_admin` | ❌ | ❌ | ❌ | ❌ | ✅ |
| بدون dependency (`/auth`, `/ws`, `/system`) | بسته به هندلر | بسته به هندلر | — | — | — |

`require_any_role` صرفاً **alias** برای `require_roles` است (نه تابع جداگانه) — نکتهای که `scripts/auth_policy.py:22` هم آن را در فهرست factories آورده تا تحلیلگر ایستا گیج نشود.

کامنت خط ۱۱–۱۳ توضیح میدهد چرا `_public_read` جایگزین `_optional_auth` قدیمی شده: «the old `_optional_auth` let anonymous callers through on every method». و هشدار مهم در `:14`: «Read handlers that are user-scoped must not live on such a router» — یعنی امنیت این الگو به **نظم توسعهدهنده** وابسته است، نه به نظام نوعها.

---

## ۴. تصمیم API-05 و دو گارد تست

`router.py:182-200` هفت router نصبنشده را همراه دلیل ثبت کرده:

| ماژول | دلیل ثبتشده |
|---|---|
| `symbol_alerts`, `proposals`, `sentiment` | زیرسامانه فقط از همین router قابلدسترس است (dead code)؛ `/alerts` معادل سختشده و owner-scoped را ارائه میدهد |
| `monitoring` | «no Prometheus scrape is configured» و `/metrics` + `/data-quality` بدون احراز، شمارندهها و تشخیص DB را افشا میکند |
| `scanner` | `POST /scan` اسکن کل بازار، بدون مصرفکننده UI |
| `ime` | تکرار فقطخواندنی سطح `/gold/ime` |
| `comprehensive_analysis` | همپوشانی با `/analysis/overview` |

دو گارد مستقل:
- `tests/unit/api/test_api05_mount_decisions.py` → `DECISIONS` هفت عضو؛ سه تست: ماژول هنوز وجود دارد، هیچکدام mount نشدهاند، و ارجاع به فایل تصمیم در سورس `router.py` باقی مانده.
- `tests/unit/test_api_router_surface_inventory.py` → `KNOWN_UNMOUNTED` هفت عضو؛ `assert unmounted <= KNOWN_UNMOUNTED` (خط ۹۳) یعنی **router تازهای نمیتواند بیصدا نصبنشده بماند**.

هر دو از `ast.parse(...decode("utf-8-sig"))` استفاده میکنند و کامنت صریحاً میگوید «one module carries a UTF-8 BOM; import tolerates it, but ast.parse on the raw text does not» — همان ۵۲ فایل BOMدار گزارش اصلی، اینجا بهدرستی مدیریت شده. **نقطه قوت تأییدشده:** تصمیم معماری → کد → تست، سه لایه همسو.

نکته جالب: دلیل `monitoring` («هیچ Prometheus scrape ای پیکربندی نشده») دقیقاً با قسمت ۰۱ (EX-02: `/metrics` بدون احراز در اپ اصلی) و `config/prometheus.yml` در تضاد ضمنی است — یعنی متریکها **هستند** ولی تصمیم «مصرفکنندهای نیست» همچنان پابرجاست و همان متریکها از route درونخطی اپ اصلی، بدون احراز، در دسترساند.

---

## ۵. `dependencies.py`: تکثر factoryها

| بخش | خط | تعداد | توضیح |
|---|---:|---:|---|
| `get_db_session` / `get_replica_session` | ۳۸ / ۴۶ | ۲ | replica «falls back to primary» |
| `get_replica_*_service` | ۵۸–۷۹ | ۳ | «Audit CFG-05: the replica was configured but never injected» |
| **generic `get_service`** | **۸۱** | **۱** | `get_service("module.path:ClassName")`، import تنبل، memoized |
| `get_*_service` دستنویس | سراسر فایل | **۳۹** | docstring خودش میگوید «Replaces the ~30 one-line wrappers» |
| `_reject_if_revoked` | ۲۱ | ۱ | jti blacklist + session cutoff |
| `get_current_user` / `get_optional_user` | ۲۵۹ / ۲۸۷ | ۲ | — |
| `get_current_active_user` | ۳۰۸ | alias | `= get_current_user` |
| `current_user_id` / `owned_scope` | ۳۱۱ / ۳۲۱ | ۲ | مالکیت: admin → `None` (بدون فیلتر) |
| `require_user_for_writes` | ۳۳۰ | ۱ | GET/HEAD/OPTIONS → optional، بقیه → کامل |
| `require_role` / `require_roles` | ۳۴۲ / ۳۵۵ | ۲ | دومی `__auth_guard__ = True` میگذارد |

`owned_scope` (`:321-327`) قرارداد مهمی دارد: برگرداندن `None` بهمعنای «بدون فیلتر» است و فقط admin مجاز به آن است؛ کاربر عادی `current_user_id()` میگیرد. کامنت `current_user_id` توضیح میدهد که هم `sub` و هم `user_id` پذیرفته میشوند «so a missing field cannot quietly widen an owner filter to the empty string» — دقت خوبی است، ولی همچنان اگر هویت خالی برگردد، فیلتر `""` اعمال میشود (نه ۴۰۳)؛ یعنی رفتار «هیچ ردیفی» بهجای «رد دسترسی»، که از نظر امنیتی معادل است ولی از نظر خطایابی گمراهکننده است.

`generic get_service` و ۳۹ wrapper دستنویس **همزمان** زندهاند؛ docstring میگوید قرار بوده جایگزین ~۳۰ تای آنها شود. مهاجرت نیمهکاره است، نه باگ — ولی دقیقاً همان الگوی «افزودن لایه جدید بدون حذف قدیمی» است که درگزارش اصلی بهعنوان بدهی ساختاری ثبت شد.

---

## ۶. زنجیره کامل احراز هویت یک درخواست

```
Request
 ├─ RequestContextMiddleware      trace_id
 ├─ RateLimitMiddleware           IP bucket + tier bucket  ← JWT decode #1 (بدون بررسی revocation)
 ├─ SecurityMiddleware            اگر مسیر حساس و متد نوشتن:
 │     ├─ فرمت Authorization Bearer                       ← 401 در صورت نبود
 │     ├─ decode_access_token                              ← JWT decode #2
 │     ├─ payload["type"] == "refresh"                     ← 401
 │     └─ is_token_revoked(jti)                            ← 401
 │        ✗ is_user_session_revoked(sub, iat)  بررسی نمیشود
 ├─ CSRFMiddleware                Origin/Referer + Sec-Fetch-Site + double-submit
 ├─ InputSanitizationMiddleware   query + JSON/form
 ├─ Dependency (get_current_user) ← JWT decode #3
 │     ├─ _auth_required()  →  AUTH_DISABLED env/settings
 │     ├─ decode_access_token
 │     ├─ type == refresh → 401
 │     └─ _reject_if_revoked: jti + user-session cutoff
 └─ require_roles(...)  → has_any_role(roles, ...)  → 403
```

**چند نکته:**
- `AUTH_DISABLED` فقط از یک نقطه خوانده میشود (`apps/api/auth.py:18-33` `_auth_required()`): متغیر محیط بر تنظیمات غلبه میکند و `_FALSY = {"0","false","no","off",""}`. کامنت صریحاً میگوید قبلاً گیت روی `is_production` بوده و «a staging box reachable from the network served the full API with no credentials at all» (API-008). اصلاح درست و مستند است.
- **JWT سه بار در هر درخواست احرازشده decode میشود** (tier، middleware، dependency). بدتر اینکه `tier_subject_from_request` (`core/security/saas.py:323-346`) فقط `decode_access_token` میکند و **هیچ بررسی ابطالی** انجام نمیدهد؛ توکن باطلشده همچنان یک سطل tier کامل میگیرد (هرچند `get_current_user` در نهایت ۴۰۱ میدهد). این یک باگ امنیتی نیست، ولی کار تکراری و رفتار گمراهکننده در متریکهاست.
- `SecurityMiddleware` فاقد بررسی `is_user_session_revoked` است؛ یعنی توکنی که با تغییر رمز عبور باطل شده، از گارد میانافزار عبور میکند. خوشبختانه `get_current_user` (`:280`) آن را میگیرد، **مگر** اینکه router مربوطه بدون dependency احراز mount شده باشد (`/system`, `/ws`) — آنجا فقط لایه میانافزار باقی میماند.
- `core/security/tokens.py` توابع کامل دارد: `create/decode_access_token`, `create/decode_refresh_token`, `is_token_revoked`, `revoke_user_access_tokens`, `is_user_session_revoked`, `validate_access_token`, `revoke_access_token`، `create_ws_ticket`/`consume_ws_ticket`. `validate_production` جلوی `WS_ALLOW_LEGACY_TOKEN=true` را در prod/staging میگیرد تا WS حتماً از تیکت یکبارمصرف استفاده کند.

---

## ۷. `SecurityMiddleware` — دفاع در عمق با دامنه محدود

`_SENSITIVE_WRITE_PREFIXES` (`:57-70`) سیزده پیشوند را برای متدهای POST/PUT/PATCH/DELETE گارد میکند: `/api/v1/gold/`, چهار مسیر `backtests`, دو مسیر `ml`, `portfolios`, `alerts`, `watchlist`, `trades`, `data-import`, `signal-insights`. کامنت توضیح میدهد که **اسلش انتهایی `/gold/` عمدی** است تا `/api/v1/golddesk/...` (SaaS با توکن scoped خودش) وارد این چک JWT نشود — ظرافت قابلتوجه.

دو محدودیت:
1. گارد فقط وجود/امضای توکن و `jti` را چک میکند، نه `type` refresh را بهصورت کامل؟ (چک میکند) و نه session cutoff را (چک نمیکند).
2. هدرهای امنیتی (`nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Cache-Control: no-store` و ...) فقط وقتی اضافه میشوند که `not path.startswith(_EXEMPT_PATHS)` — و `_EXEMPT_PATHS` شامل `/docs`, `/redoc`, `/openapi.json`, `/api/v1/health` است. چون در production دو تای اول غیرفعالاند، عملاً فقط مسیرهای health از هدرها معافاند.

ترکیب با قسمت ۰۱ (EX-06): این میانافزار **درونیتر** از CSRF/RateLimit/Logging/Metrics است، پس پاسخ ۴۰۱ خودش هم از هدرهای CORS و هدرهای `X-Trace-Id`؟ (trace توسط بیرونیترین اضافه میشود، پس بله) محروم است ولی هدرهای امنیتیاش روی پاسخهای ۴۰۳/۴۲۹ وجود ندارند.

---

## ۸. `RateLimitMiddleware` — دو لایه و یک باگ cardinality

```python
def _get_limit_for_path(self, path):            # :525-535
    if path in self._endpoint_limits: return ...
    best_match = ""; best_limit = provider_rate_limit_per_minute   # 300
    for pattern, limit in self._endpoint_limits.items():
        if path.startswith(pattern) and len(pattern) > len(best_match):
            best_match, best_limit = pattern, limit
    return best_limit

def _get_key(self, client_ip, path):            # :537-539
    return f"api:{client_ip}:{path}"            # ← مسیر خام، نه الگوی route
```

**`HTTP-08` — ناسازگاری «محدودیت بر اساس endpoint» و «کلید بر اساس مسیر خام».** تمام ~۴۰ کلید `endpoint_rate_limits` **پیشوند**اند (`/api/v1/signals`, `/api/v1/backtests/run`, `/api/v1/auth/login`, ...) و `_get_limit_for_path` با طولانیترین پیشوند تصمیم میگیرد. ولی سطل شمارش با `_get_key` روی `request.url.path` **کامل** ساخته میشود. نتیجه:

- `/api/v1/quotes/AAPL` و `/api/v1/quotes/MSFT` دو سطل جداگانه دارند؛
- یک کلاینت میتواند با چرخش روی نمادها/شناسهها، N برابر سقف موردنظر درخواست بزند؛
- تعداد کلیدها در store نرخگیر با تعداد مسیرهای متمایز رشد میکند (در `MetricsMiddleware` برعکس عمل شده: `_route_template()` از `request.scope["route"].path` استفاده میکند و مسیرهای نامشخص را به `<unmatched>` فرو میکاست — یعنی الگوی درست **در همان codebase موجود است** ولی در نرخگیر بهکار نرفته).

لایه دوم سهمیه tier است: `tier_subject_from_request` → `TIERS[tier_name]` (`free=10 rpm/1000 روزانه`, `pro=120/50٬000`, `institutional=600/نامحدود`) → `TieredTokenBucketLimiter.allow`. کاربر ناشناس فقط سطل IP میگیرد. کامنت `:65` میگوید پیشتر نگاشت نادرست نقشها به `free` باعث ۴۲۹ روی نیمی از ویجتها شده — اصلاحشده.

**دیگر نکات نرخگیری:**
- `dispatch` در `environment == "test"` **کامل bypass** میشود (`:539`)؛ `tests/conftest.py` هم `ENV=test` را ست میکند. پس هیچ تستی رفتار نرخگیری را در شرایط عادی اجرا نمیکند.
- `/metrics` در فهرست معافیت است (`:540`): هم بدون احراز (EX-02) و هم بدون نرخگیری.
- `client_ip = request.client.host` (`:541`) مستقیماً از scope خوانده میشود، بدون `X-Forwarded-For`. پشت پراکسی معکوس (compose در کامنت Bandit میگوید «behind nginx/traefik») اگر uvicorn با `forwarded_allow_ips` متناسب اجرا نشود，**همه کلاینتها یک IP مشترک خواهند داشت** و سطل IP سراسری میشود. این مورد نیازمند راستیآزمایی زماناجراست و بهعنوان **فرضیه قابلآزمون** ثبت میشود، نه یافته قطعی.

---

## ۹. CSRF و پاکسازی ورودی

`CSRFMiddleware` (`:191-309`) الگوی جالبی دارد: چون API عمدتاً JWT bearer و بدون کوکی است، خطای کلاسیک CSRF وجود ندارد؛ پس فقط درخواستهای نوشتن **مرورگری** را محدود میکند:
- `Sec-Fetch-Site: cross-site` بدون Origin → ۴۰۳؛
- Origin/Referer ناهماهنگ با `cors_origins` → ۴۰۳؛
- درخواست بدون Origin و بدون Referer (curl، server-to-server) → **مجاز** («treated as non-browser»)؛
- double-submit توکن فقط برای کلاینتهای کوکیدار.
- مسیرهای `/docs`, `/openapi.json`, `/api/v1/health` معافاند.

تصمیمی معقول و مستند، ولی `tests/conftest.py` متغیر `ENABLE_CSRF=false` را ست میکند چون «httpx test client does not send browser Origin headers, so CSRFMiddleware would 403 every POST». نتیجه: **تمام suites تست، CSRF را خاموش اجرا میکنند** — دقیقاً همان الگوی `ENV=test` در نرخگیری. هیچ تستی رفتار واقعی CSRF را نمیسنجد.

`InputSanitizationMiddleware` (`:311-409`) کوئری و بدنه JSON/form را پاکسازی میکند (`strip_html` + حذف CR/LF/NUL)، فیلدهای `_SANITIZE_RAW_FIELDS` (پسورد، کد، توکن، api_key، ...) را دستنخورده میگذارد تا مقایسه بایتبهبایت خراب نشود، و مقادیر غیررشتهای در فیلد رشتهای را با ۴۰۰ رد میکند. docstring صادقانه اعلام میکند path/query پارامترها «out of scope for a body-level middleware» ولی کد در عمل `query_string` را هم پاکسازی میکند (`:340-342`) — ناهماهنگی جزئی مستند/کد.

`pagination.py` یک سقف سخت `MAX_PAGE_SIZE = 1000` دارد که «absolute last-resort guard against accidental full-table fetches» است؛ `Settings.api_max_page_size` سقف نرمتری برای endpointهاست. `PaginatedResult` چهار computed field تمیز (`total_pages`, `has_next`, `has_prev`) دارد. **نقطه قوت کوچک ولی واقعی.**

---

## ۱۰. حاکمیت ایستای احراز هویت

دو ابزار مکمل:
- `apps/api/openapi_security.py` — چون اپ بهجای `Security(...)` از `Depends` و `Header` استفاده میکند، OpenAPI پیشتر «no auth at all» اعلام میکرد (AUD-API-02). `install_openapi_security` درخت `route.dependant` را پیمایش میکند و برای عملیات دارای `_FULL_AUTH` یا `_WRITE_AUTH`، `security: [{bearerAuth: []}]` تزریق میکند. **راستیآزمایی شد:** closure `_check` حاصل `require_roles()` دارای `Depends(get_current_user)` است، پس `_dependency_names` نام `get_current_user` را پیدا میکند و routeهای نقشدار بهدرستی علامت میخورند — شک اولیه («`require_roles` در `_FULL_AUTH` نیست، پس OpenAPI کماعلام میکند») **رد شد**. برای `require_user_for_writes` هم متدهای GET/HEAD/OPTIONS حذف میشوند.
- `scripts/auth_policy.py` — تحلیلگر ایستا با `AUTH_DEP_ATTR = "__auth_guard__"`؛ وابستگیهای نامدار `{get_current_user, get_current_active_user, require_role}` و factories `{require_roles, require_any_role, api_key_auth}` را جداگانه میشناسد تا closureها را گم نکند.

این دو ابزار نشان میدهند تیم برای « route فراموششده بدون احراز » هم گارد گذاشته است.

---

## ۱۱. جدول یافتهها

| ID | شدت | خط | یافته | اثر عملی | جهت اصلاح |
|---|---|---:|---|---|---|
| **HTTP-01** | 🔴 بحرانی | `app.py:1098`, `router.py:190` | `monitoring` بهدلیل «هیچ scrapeـای پیکربندی نشده / افشای متریک» نصبنشده، در حالی که `/metrics` روی اپ اصلی **بدون احراز** در دسترس است و `prometheus.yml` وجود دارد | همان ریسکی که تصمیم API-05 میخواست حذف کند، از مسیر دیگری زنده است | حذف/محافظت `/metrics` یا بهروزرسانی تصمیم |
| **HTTP-02** | 🟠 بالا | `middleware.py:537-539` | کلید نرخگیری از **مسیر خام** ساخته میشود ولی محدودیتها **پیشوندی**اند | دور زدن سقف با تغییر نماد/شناسه در URL؛ رشد نامحدود کلیدها | `_get_key` از `scope["route"].path` (الگوی موجود در `metrics.py:79`) |
| **HTTP-03** | 🟠 بالا | `middleware.py:51,58-70,216,540`; `app.py:1107-1198` | پیشوند `/api/v1` هاردکد در ۴ نقطه امنیتی + ۶ route | تغییر `API_PREFIX` → خاموشی بیصداگارد نوشتن حساس و معافیتها | ساخت از `settings.api_prefix` |
| **HTTP-04** | 🟠 بالا | `middleware.py:130-178` | گارد `SecurityMiddleware` بررسی `is_user_session_revoked` را ندارد | توکن باطلشده پس از تغییر رمز، از لایه میانافزار عبور میکند؛ روی routerهای بدون dependency (`/system`, `/ws`) لایه دیگری نیست | اضافه کردن همان چک `_reject_if_revoked` |
| **HTTP-05** | 🟠 بالا | `router.py:23,178` | `_ENDPOINTS` فقط ۴۵ ورودی دارد در برابر ۸۰ mount | `GET /api/v1` نیمی از API را معرفی نمیکند | تولید خودکار از `app.routes` |
| **HTTP-06** | 🟡 متوسط | `middleware.py:539`, `conftest.py` | `environment == "test"` نرخگیری را کامل غیرفعال میکند + `ENABLE_CSRF=false` | هیچ تستی رفتار واقعی rate limit / CSRF را نمیسنجد | تست اختصاصی با override صریح |
| **HTTP-07** | 🟡 متوسط | `saas.py:323-346`, `middleware.py` | توکن سه بار decode میشود؛ مسیر tier هیچ بررسی ابطالی ندارد | سهمیه tier برای توکن باطلشده مصرف میشود؛ متریکها گمراهکننده | کش `request.state.user` در یک لایه |
| **HTTP-08** | 🟡 متوسط | `middleware.py:541` | `client_ip` مستقیم از `request.client.host` بدون `X-Forwarded-For` | پشت پراکسی احتمالاً همه کلاینتها یک سطل IP مشترک میگیرند *(فرضیه، نیازمند اجرای زنده)* | بررسی `--proxy-headers` / `forwarded_allow_ips` |
| **HTTP-09** | 🟡 متوسط | `dependencies.py:321-327` | `owned_scope` هویت خالی را به فیلتر `""` تبدیل میکند، نه ۴۰۳ | پاسخ «هیچ ردیفی» بهجای «دسترسی رد شد»؛ خطایابی دشوار | پرتاب ۴۰۱/۴۰۳ در نبود هویت |
| **HTTP-10** | 🟡 متوسط | `dependencies.py:81` در برابر ۳۹ wrapper | generic `get_service` و ۳۹ دستنویس همزمان زندهاند | مهاجرت نیمهکاره؛ دو مسیر DI برای یک مفهوم | تکمیل مهاجرت یا حذف generic |
| **HTTP-11** | 🟡 متوسط | `app.py:1107,1126` | وضعیت/تاریخچه کرون فقط `get_current_active_user` میخواهد | استکتریسها و وضعیت بحران در دسترس هر کاربر واردشده | `require_roles("admin")` |
| **HTTP-12** | 🟢 کم | `router.py:204`, `middleware.py:311-330` | «all 45 endpoint files» در برابر ۷۵ import؛ docstring میگوید query out-of-scope ولی کد آن را پاکسازی میکند | drift مستندات جزئی | بهروزرسانی کامنتها |
| **HTTP-13** | 🟢 کم | `router.py` انتها | `/ws`, `/ws/precompute`, `/system` بدون dependency سطح mount | امنیت کاملاً به هندلر واگذار شده؛ نیازمند بررسی قسمت ۰۶/۱۱ | افزودن dependency یا تست پوشش |

---

## ۱۲. نقاط قوت تأییدشده

1. **API-05**: تصمیم معماری → کامنت دلیلدار در کد → دو گارد AST مستقل (یکی جلوی mount تصادفی، یکی جلوی router تازه نصبنشده) — کاملترین حلقه حاکمیتی مخزن.
2. `_auth_required()` تکمنبع، با اصلاح مستند یک باگ واقعی (bypass staging) و غلبه صریح env بر settings.
3. `_reject_if_revoked` دوبعدی: blacklist `jti` + cutoff سراسری کاربر پس از تغییر رمز (SEC-07).
4. `validate_production` جلوی `WS_ALLOW_LEGACY_TOKEN` را میگیرد و `tokens.py` تیکت WS یکبارمصرف `create_ws_ticket`/`consume_ws_ticket` دارد.
5. `_SANITIZE_RAW_FIELDS` — تشخیص اینکه پاکسازی پسورد/توکن، مقایسه بایتبهبایت را خراب میکند.
6. `MetricsMiddleware._route_template()` از `scope["route"].path` و `<unmatched>` استفاده میکند (bounded cardinality) — الگوی درستی که میتواند مستقیماً HTTP-02 را حل کند.
7. `install_openapi_security` + `scripts/auth_policy.py` — حاکمیت ایستای احراز، با شناخت closureها و `__auth_guard__`.
8. `pagination.py` سقف سخت ۱۰۰۰ در برابر fetch تمام جدول.
9. اسلش انتهایی عمدی `/gold/` برای جدا کردن سطح SaaS توکن scoped از JWT معمولی.

---

## ۱۳. تصحیحات اعمالشده برگزارش ۱۶۰ لایهای

| محل | ادعای قبلی | اصلاح |
|---|---|---|
| لایه ۴۱ | «۸ ماژول router نصبنشده» | ۷ router نصبنشده (مطابق `DECISIONS` و `KNOWN_UNMOUNTED`) + `backtest_requests.py` بدون `APIRouter` |
| R7 ماتریس ریسک | «۸ ماژول endpoint نصبنشده نشده» | همان تصحیح، با تفکیک صریح |

همچنین لایه ۴۲ (پشته میانافزار) از نظر **ترتیب** درست بود ولی پیامد «CORS درونیترین» را نگفته بود → در قسمت ۰۱ بهعنوان EX-06 اضافه شد.

---

## ۱۴. مرز روش / گام بعدی

تحلیل ایستا است: سرور بوت نشد، درخواستی ارسال نشد، تستی اجرا نشد. HTTP-08 صریحاً **فرضیه** علامت خورده (وابسته به پیکربندی uvicorn پشت پراکسی). شک اولیه درباره `install_openapi_security` («`require_roles` را نمیشناسد») با ردیابی درخت وابستگی **رد شد** و در بند ۱۰ ثبت گردید تا دوباره بررسی نشود. اعتبارسنجی هندلرهای WebSocket و `/system` به قسمت ۰۶ (صف/WS) و ۱۱ (فرانتاند) موکول شد.

**قسمت ۰۳:** پیکربندی، اسرار و تولید محیط — `core/config/__init__.py` (۵۵۴ خط، ۶۰ `Field`، ۸ validator، ~۴۰ کلید نرخگیری) در برابر پوشه موازی `core/config/*` کممصرف، `validate_production()`، `.env*`، الزامات `${VAR:?}` در compose، و پرچمهای `BRSAPI_ENABLED` / `JOB_QUEUE_ENABLED` / `NEWS_READ_MODE`.

---
*فقط فایل تحلیلی ساخته شد؛ هیچ کدی تغییر نکرد.*
