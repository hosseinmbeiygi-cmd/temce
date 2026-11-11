# GoldDesk — فاز ۰: آدیت خواندنی (Read-Only Audit)

**تاریخ:** ۲۰۲۶-۱۱-۰۹  
**worktree:** `../temce_goldteam` → branch `fix/gold-team`  
**base:** `integration/golddesk-fixes` @ `095cc98f`  
**main dev:** `fix/zero-errors` @ `5f9da6bf`  
**ناظر:** Claude Sonnet 4.6

---

## الف) وضعیت Git

### شاخه‌ها و HEAD
```
branch: fix/gold-team (← integration/golddesk-fixes @ 095cc98f)
main dev: fix/zero-errors @ 5f9da6bf
```

### آخرین ۸ commit در integration/golddesk-fixes
```
095cc98f fix(audit): publish X-Data-As-Of on /stocks/v2 history CSV
6383b6a9 docs(audit): record stocks_v2 envelope commit 9a4bfe93
9a4bfe93 fix(audit): publish data_as_of envelope on /stocks/v2 (API-05 follow-up)
46946947 fix(audit): disable scheduled no-op job gold_daily_history (R2)
fc51c74b docs(audit): classify API-05 unmounted routers (dead subsystem vs unique)
```

### worktree list (خلاصه)
```
C:/Users/Iran/Desktop/temce            [fix/zero-errors]  — اصلی (uncommitted changes دارد)
C:/Users/Iran/Desktop/temce_goldteam   [fix/gold-team]    — این worktree
+ چندین worktree عامل (billowy-crowberry, goldfix، ...)
```

### ⚠️ یافتهٔ بحرانی برای worktree: branch divergence
`integration/golddesk-fixes` حداقل ۹۵ commit از `fix/zero-errors` عقب است. فایل‌های زیر در worktree وجود **ندارند** ولی در `fix/zero-errors` هستند:
- `src/gold_desk/phase1.py`
- `src/gold_desk/phase1_schemas.py`
- `src/gold_desk/phase2.py`
- `src/gold_desk/phase2_schemas.py`
- `src/gold_desk/snapshot_service.py`

نتیجه: `src/gold_desk/api.py` (که در worktree نسخهٔ قدیمی‌تر دارد و به phase1/phase2 import می‌کند) در worktree کامپایل‌نمی‌شود.

**دلالت:** تمام کد، تست و گزارش‌های فعلی روی `fix/zero-errors` هستند. worktree فعلی پایهٔ شکسته دارد. فاز ۱ باید بر روی `fix/zero-errors` یا یک merge مناسب بنا شود.

---

## ب-۰) بررسی ایمنی تست پیش از اجرا

### بررسی `tests/conftest.py` — needs_db gate

**کد فعلی (`_db_url()`):**
```python
def _db_url() -> str:
    override = os.environ.get("DATABASE_URL")
    if override:
        return override
    try:
        from core.config import settings
        return settings.database_url_async
    except Exception:
        return "postgresql+asyncpg://market:market@localhost:5432/market_test"
```

**مشکل — آیتم ۸ تأیید شد:**
- هیچ بررسی `GOLD_TEST_DATABASE_URL` وجود ندارد
- هیچ allowlist برای host یا نام دیتابیس وجود ندارد
- هیچ چکی که نام دیتابیس حاوی "test" باشد وجود ندارد
- اگر `DATABASE_URL` روی دیتابیس production باشد، `needs_db` تست‌ها روی آن اجرا می‌شوند
- **این یک نقص امنیتی است** طبق EXECUTION GATES AND SAFETY

**وضعیت عملی الان:** دیتابیس روی این دستگاه در دسترس نیست → تمام `needs_db` تست‌ها skip می‌شوند. فعلاً ایمن است ولی باید قبل از هر DB-test اصلاح شود.

---

## ب) baseline تست‌ها

### worktree (integration/golddesk-fixes — پایهٔ شکسته)
```
$ cd temce_goldteam && python -m pytest tests/gold_desk -m "not needs_db" -q -p no:cacheprovider
ERROR tests/gold_desk/test_api_contract_fields.py
ERROR tests/gold_desk/test_holding_soft_delete_reject.py
ERROR tests/gold_desk/test_metrics_scope.py
ImportError: cannot import name 'phase1' from 'src.gold_desk'

FAILED tests/gold_desk/test_api_token_boot.py::test_api_module_import_is_lazy_without_salt
FAILED tests/gold_desk/test_api_token_boot.py::test_api_and_api_token_import_with_salt
FAILED tests/gold_desk/test_phase0_mount.py::test_frontend_critical_gold_routes_are_mounted
FAILED tests/gold_desk/test_phase0_snapshot_integration.py::test_snapshot_returns_200_with_required_fields
FAILED tests/gold_desk/test_phase0_snapshot_integration.py::test_snapshot_has_valid_data_structure_when_data_available
5 failed, 336 passed, 1 skipped
```
علت: فایل‌های `phase1`, `phase2`, `snapshot_service` در این branch وجود ندارند.

### fix/zero-errors (شاخهٔ توسعهٔ اصلی — مرجع)
```
$ cd temce && python -m pytest tests/gold_desk -m "not needs_db" -q -p no:cacheprovider
454 passed, 1 skipped, 2 deselected
WARNING: feedparser not installed — RSS news fetching disabled
```
**همهٔ تست‌ها سبز هستند.**

### scripts/check_router_auth.py (روی fix/zero-errors)
```
Audited 714 router operations and 8 app-level routes.
Router auth audit OK — every operation is authenticated or on the documented allowlist.
exit code: 0
```

---

## ج) نقشهٔ جریان داده (Data-Flow Map)

```
BrsApi (خارجی)
   ↓ [brsapi/services/sync_service.py — central worker, only caller]
   ↓ Fetch → Pydantic validate → DB insert
   ↓ PostgreSQL: brsapi_gold_currency_pro_prices / _daily_history / gold_fund_nav / ...
   ↓
src/gold_desk/snapshot_service.py::build_snapshot(session)
   ├── pricer.py → قیمت‌های طلا/سکه (از DB)
   ├── bubbler.py → حباب نرمال/ذاتی
   ├── scorer.py → سیگنال کلی
   ├── hard_stops.py → حد توقف با دادهٔ کلان
   ├── nav_checker.py → NAV صندوق‌ها
   └── secondary_source.py → TGJU (fallback وقتی BrsApi قطع است)
   ↓
   ↓ [cache: core/cache.py::get_cache() — Redis]
   ↓ hotpath.py::get_hot_snapshot() → polling endpoint /gold/hot (سبک)
   ↓
src/gold_desk/api.py (FastAPI router prefix /gold)
   ├── GET /snapshot → build_snapshot() مستقیم (DB-bound)
   ├── GET /hot → hotpath, Redis-first
   ├── GET /terminal → phase1 data
   ├── WebSocket /ws → ws_hub.py fan-out
   └── ... (۵۰+ endpoint)
   ↓
frontend/src/components/gold/ → polling REST + WebSocket
```

### نقاط شکست (Single Points of Failure)
| نقطه | خطر | fallback موجود |
|------|-----|----------------|
| BrsApi قطع | قیمت‌ها کهنه می‌شوند | TGJU (secondary_source.py) — تنها یک fallback |
| Redis قطع | hot-path برمی‌گردد None | get_hot_snapshot() خطا را می‌بلعد و None برمی‌گرداند |
| DB قطع | snapshot کار نمی‌کند | هیچ — 503 |
| Workers قطع | داده‌ها به‌روز نمی‌شوند | Last-Known-Good از cache تا TTL |

### حجم call به BrsApi
- فقط worker مرکزی BrsApi می‌زند (کلاینت‌ها از cache می‌خوانند) — مطابق قاعدهٔ PRODUCT SCOPE ✓
- polling interval: نامشخص از کد (hardcoded یا config؟) — نیاز به تأیید

---

## د) جدول وضعیت ۱۱ آیتم

| # | موضوع | وضعیت | مدرک | توضیح |
|---|-------|---------|------|--------|
| 1 | Service Worker reload loop | **FIXED** | `frontend/public/golddesk-sw.js` v3; `frontend/public/sw.js` | golddesk-sw.js v3: navigations شبکه-اول؛ loop رفع‌شده. دو SW با scope جداگانه (/gold و /) ثبت می‌شوند — طراحی عمدی |
| 2 | /admin role gate + brsapi/sync-status | **PARTIAL** | `src/gold_desk/api.py:80`; `apps/api/endpoints/brsapi.py:38-40` | token endpoints: `_require_admin_user` (بررسی `has_role("admin")`). brsapi/manage/*: `_manage_admin = [Depends(require_roles("admin"))]`. اما `_require_admin_user` در `AUTH_NAMES` نیست (تنها از subgraph تشخیص داده می‌شود) |
| 3 | frontend middleware isPublic unused | **PARTIAL** | `frontend/src/proxy.ts:131` | `isPublic` محاسبه می‌شود ولی در شرط redirect **استفاده نمی‌شود** (فقط `isProtectedPath()` چک می‌شود). API پشتیبان ۴۰۱ برمی‌گرداند. متغیر dead code است |
| 4 | /live-prices ← 0.0 / portfolio -100% | **PARTIAL** | `src/gold_desk/portfolio.py:499`; `compute_returns:231` | endpoint `/live-prices` وجود ندارد (احتمالاً `/snapshot` است). `total_pnl_pct=0` وقتی `priced_cost=0` (نه -100%). `pnl_pct=None` وقتی contributions=0. برخی فیلدها با `0.0` default هستند نه `None` — نیاز به بررسی دقیق‌تر |
| 5 | Sell inventory reduction / FIFO | **PARTIAL** | `src/gold_desk/portfolio.py:786-884`; `tests/gold_desk/test_sell_consumes_holdings.py` | `_consume_lots()` و `_consume_lots_by_symbol()` موجودند. تست‌ها وجود دارند ولی DB-dependent — نیاز به DB برای تأیید کامل |
| 6 | API token lifecycle | **PARTIAL** | `src/gold_desk/api.py:986-1050`; `src/gold_desk/api_token.py` | create/list/delete endpoint با admin gate. انقضا: نامشخص. rotation: نامشخص. بررسی `api_token.py` ناقص است |
| 7 | docker-compose.production.yml بدون GOLD_API_TOKEN_SALT | **NOT DONE** | `docker-compose.yml:66,119`; `docker-compose.production.yml` | `docker-compose.yml` دارای `:?` برای `GOLD_API_TOKEN_SALT` است. `docker-compose.production.yml` این متغیر را **اصلاً** تعریف نمی‌کند (فقط `env_file: .env.production`). اگر `.env.production` salt نداشته باشد، سرویس‌ها با salt پیش‌فرض ناامن شروع می‌شوند |
| 8 | conftest needs_db gate بی‌توجه به GOLD_TEST_DATABASE_URL | **NOT DONE** | `tests/conftest.py:56-71` | `_db_url()` فقط `DATABASE_URL` را چک می‌کند. هیچ allowlist برای host یا نام دیتابیس وجود ندارد. بدون این محافظ، DB-tests می‌توانند روی دیتابیس production اجرا شوند |
| 9 | snapshot_ready گم می‌شود وقتی cache client init نشده | **UNVERIFIED** | `src/gold_desk/ws_hub.py:243`; `src/gold_desk/live_signals.py` | `ws_hub.py` subscriber به `snapshot_ready` وجود دارد. اما publisher در کدبیس پیدا نشد (نه در live_signals.py، نه در hotpath.py). احتمالاً در scheduler یا worker است که در این branch وجود ندارد |
| 10 | gold_fund_nav staleness / overlap ETF-funds | **UNVERIFIED** | `src/gold_desk/freshness.py:82` | آخرین ردیف NAV: نیاز به DB. endpoint `/gold/funds` یا `/gold/etf` **وجود ندارد** — `/gold/fund-map` هست. history endpoint مجزا برای NAV پیدا نشد. `oos_max_drawdown_pct` مثبت (convention: درصد افت — نه منفی) |
| 11 | BrsApi unit (toman/rial) / brsapi_gold_currency_pro_* | **PARTIAL** | `src/gold_desk/phase2.py:803`; `src/gold_desk/freshness.py:82` | `_toman_to_rial` وجود دارد و اعمال می‌شود. `constants.py:54` sanity check دارد. ستون `ins_id` در api.py و brsapi.py استفاده می‌شود. `bid_volume_1` در freshness.py ارجاع دارد. تأیید واقعی نیاز به DB دارد |

---

## ه) موجودی قابلیت‌ها برای workstream‌ها

| Workstream | وجود دارد | کمبود | وابستگی BrsApi | ریسک | نیاز تأیید مالک |
|-----------|-----------|-------|----------------|------|----------------|
| WS1: BrsApi resilience | `brsapi/services/sync_service.py` | circuit breaker، backoff محدود، pipeline رسمی | ✓ | بالا | خیر |
| WS2: FX source | `secondary_source.py` (TGJU) | normalize ریال/تومان در یک جا، secondary sources | جزئی | بالا | نیاز به verify terms |
| WS3: Macro adapter | `macro_news.py` (CBI scraper) | provider swappable، async، TimescaleDB جداگانه | نه (DXY نامشخص) | متوسط | بله (terms) |
| WS4: News | `macro_news.py` (بدون feedparser) | feedparser نصب نیست، sentiment برای فارسی | نه | متوسط | بله (licensing) |
| WS5: Event calendar | نه | هیچ | نه | متوسط | بله |
| WS6: Fund analytics | `nav_checker.py`، `freshness.py` | microstructure، fee matrix | جزئی | متوسط | بله (fields) |
| WS7: Derivatives | `black76.py` | تأیید options chain از BrsApi | نامشخص | بالا | بله |
| WS8: Signal engine | `signal_engine.py`، `scorer.py` | journal، revoke events | ✓ | متوسط | خیر |
| WS9: Paper trading | `portfolio.py` (real) | paper account جداگانه، team view | ✓ | متوسط | خیر |

---

## و) موجودی احراز هویت و exposure

### Registration و first-admin
```
# services/user_service.py:111-114
is_first_user = bool(getattr(_settings, "bootstrap_first_admin", True)) and (
    (total_users or 0) == 0
)
initial_role = "admin" if is_first_user else "user"
```
⚠️ **URGENT**: endpoint `/auth/register` کاملاً عمومی است (فقط rate-limit، نه admin-only). اگر مهاجم قبل از مدیر واقعی ثبت‌نام کند، admin می‌شود. برای استقرار روی اینترنت عمومی این یک **انسداد حیاتی** است.

### نقش‌ها
- در کد: `admin`, `user`, `analyst`, `viewer` (در `/auth/users/{id}/role`)
- در PRODUCT SCOPE: فقط `admin` و `member` — ناسازگاری

### Sessions
- JWT access token + httpOnly refresh cookie (SameSite=Lax)
- CSRF middleware موجود است
- MFA: **پیدا نشد**

### CORS
- `settings.cors_origins` (env-driven)
- `.env.bak` نشان می‌دهد گاهی `["*"]` استفاده شده
- production باید با allowlist صریح باشد

### مستندسازی API
- `/docs`, `/redoc`, `/openapi.json`: همیشه فعال (بدون guard برای production)
- هیچ `docs_url=None` برای محیط production وجود ندارد

### WebSocket
- `ws_hub.py` توکن می‌خواهد
- Origin check: از `settings.cors_origins` (apps/api/endpoints/websocket.py:101)

### Rate limit
- Login: پیاده‌سازی شده (`auth.py:43`)
- Register: پیاده‌سازی شده (3 per 60s per IP)

### اسرار commit شده
- `.env.bak` با `CORS_ORIGINS=["*"]` در تاریخچهٔ repo موجود است (نیاز به rotation اگر secret داشت)

---

## ز) یافته‌های امنیتی اورژانسی

| اولویت | یافته | فایل | اقدام |
|--------|-------|------|-------|
| **CRITICAL** | Registration عمومی + first-user-admin race | `services/user_service.py:111` | قفل registration یا bootstrap با secret مشخص — **قبل از هر استقرار اینترنتی** |
| HIGH | `/docs` و `/openapi.json` در production باز | `apps/api/app.py:1068` | `docs_url=None` در production |
| HIGH | `docker-compose.production.yml` فاقد GOLD_API_TOKEN_SALT | `docker-compose.production.yml` | افزودن `:?` syntax |
| MEDIUM | conftest بدون GOLD_TEST_DATABASE_URL guard | `tests/conftest.py` | افزودن allowlist قبل از DB tests |
| MEDIUM | `isPublic` dead code در proxy.ts | `frontend/src/proxy.ts:131` | حذف یا استفاده — API پشتیبان امن است |

---

## متوقف — منتظر تأیید مالک برای شروع فاز ۱

طبق EXECUTION GATES:
> Do not begin Phase 1 without the owner's explicit approval.

**سؤالات نیازمند تصمیم مالک پیش از فاز ۱:**

1. **پایهٔ worktree:** آیا فاز ۱ باید از `fix/zero-errors` (پایهٔ سالم، ۴۵۴ تست سبز) ادامه یابد نه از `integration/golddesk-fixes` (پایهٔ شکسته)؟ پیشنهاد: بله.

2. **Urgent security blockers:** آیا قبل از فاز ۱ باید registration قفل شود؟ (Critical برای هر استقرار اینترنتی)

3. **GOLD_API_TOKEN_SALT در production:** آیا `docker-compose.production.yml` هم‌اکنون باید اصلاح شود؟

4. **Nیاز DB:** آیتم‌های ۵، ۹، ۱۰، ۱۱ برای تأیید کامل به DB نیاز دارند — کدام نمونهٔ DB-test برای مالک قابل دسترس است؟

5. **Legacy data:** تست‌های موجود holdings و trades باید حفظ شوند. پس از تأیید طراحی ownership (فاز ۱.۵a)، چه رویکردی برای ردیف‌های legacy انتخاب می‌شود؟

---

*گزارش فاز ۰ کامل شد. هیچ تغییری در کد application یا database اعمال نشده.*
