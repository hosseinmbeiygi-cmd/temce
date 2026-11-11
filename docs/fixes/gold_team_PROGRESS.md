# GoldDesk — PROGRESS

## فاز ۰ (۲۰۲۶-۱۱-۰۹)
- **وضعیت:** ✅ کامل — منتظر تأیید مالک
- **worktree:** `../temce_goldteam` → `fix/gold-team` ← `integration/golddesk-fixes @ 095cc98f`
- **تست‌های سبز (مرجع fix/zero-errors):** 454 passed, 1 skipped
- **تست‌های worktree (پایهٔ شکسته):** 5 failed, 336 passed (ImportError: phase1 missing)
- **گزارش:** `docs/fixes/gold_team_PHASE0.md`

### یافته‌های مهم فاز ۰
1. base branch (`integration/golddesk-fixes`) فاقد phase1/phase2/snapshot_service → باید از `fix/zero-errors` fork کرد
2. Registration کاملاً عمومی + first-user-admin — CRITICAL blocker
3. `docker-compose.production.yml` فاقد GOLD_API_TOKEN_SALT
4. `conftest.py` بدون GOLD_TEST_DATABASE_URL guard
5. `/docs` و `/openapi.json` در production باز

---

## فاز ۱ (۲۰۲۶-۱۱-۰۹)
- **وضعیت:** ✅ کامل — commit `675482a9` روی `fix/gold-team`
- **suite:** 465 passed, 1 skipped (needs_db), 0 failed
- **frontend:** 29 passed (vitest proxy.test.ts)
- **secrets scan:** no real secrets found

### آیتم‌های رفع‌شده

| # | آیتم | فایل | تست |
|---|------|------|-----|
| 2 | admin gate برای /gold/tokens با require_roles("admin") | `src/gold_desk/api.py` | `test_phase1_admin_gate.py` |
| 3 | مرگ کد `isPublic` در proxy.ts + /gold بدون محافظت | `frontend/src/proxy.ts` | `proxy.test.ts` (+5 test) |
| 4 | pnl_pct صفر کاذب → None برای holdings بدون قیمت | `src/gold_desk/portfolio.py` | `test_phase1_pnl_null.py` |
| 7 | GOLD_API_TOKEN_SALT در docker-compose.production.yml | `docker-compose.production.yml` | `test_phase1_docker_salt.py` |
| 8 | GOLD_TEST_DATABASE_URL allowlist guard در conftest.py | `tests/conftest.py` | `test_phase1_db_allowlist.py` |
| 9 | Bounded retry (≤3, backoff) برای snapshot_ready | `src/gold_desk/ws_hub.py` | `test_phase1_snapshot_retry.py` |

### آیتم‌های به‌دلیل نبود تست رد شده (نیاز به بررسی بیشتر)
- آیتم ۵ (FIFO sell): نیاز به تست اثبات‌کننده‌ی باگ قبل از رفع
- آیتم ۶ (token lifecycle): نیاز به تست اثبات‌کننده‌ی باگ قبل از رفع

---

## فاز ۱.۵a (۲۰۲۶-۱۱-۰۹)
- **وضعیت:** ✅ کامل — منتظر تأیید D1–D4 از مالک
- **نوع:** طراحی-فقط (بدون تغییر کد/migration/داده)
- **گزارش:** `docs/fixes/gold_team_PHASE1_5a.md`

### یافته‌های مهم فاز ۱.۵a
- API-layer ownership کامل است (۱۲+ endpoint از `owned_scope()` استفاده می‌کنند)
- Schema-layer بدون NOT NULL constraint — ریسک G-1 (ردیف‌های legacy با `user_id=NULL`)
- ریسک G-3: `allow_any_owner` ممکن است `trade.user_id=admin` را ثبت کند نه `user_id=user123`
- ریسک G-4: composite unique در `gold_portfolio_history` با NULL user_id مشکل‌ساز

### نقاط تصمیم (D1–D4)
- **D1:** ردیف‌های legacy `user_id=NULL` به چه user_id‌ای backfill شوند؟
- **D2:** آیا `allow_any_owner` باید `trade.user_id` را از holding بگیرد؟
- **D3:** آیا حذف سخت holding توسط admin مجاز بماند؟
- **D4:** آیا انتقال holding/trade بین کاربران مورد نیاز است؟

---

## فاز ۱.۵b (۲۰۲۶-۱۱-۰۹)
- **وضعیت:** ✅ کامل — commit `ee85e1b2` روی `fix/gold-team`
- **suite:** 472 passed, 1 skipped, 0 failed (gold_desk)

### تغییرات
| فایل | تغییر |
|------|-------|
| `src/gold_desk/portfolio.py` | G-3: `_record_sell` با `allow_any_owner=True` user_id را از holding می‌گیرد |
| `src/gold_desk/portfolio.py` | `get_active_holding` holding با `user_id=NULL` را reject می‌کند |
| `src/gold_desk/api.py` | `delete_holding` با `force=True` audit WARNING log می‌نویسد |
| `migrations/versions/0122_gold_desk_ownership_enforce.py` | backfill NULL→admin + SET NOT NULL روی ۶ جدول |
| `tests/gold_desk/test_phase1_5b_code.py` | ۵ تست TDD |
| `tests/gold_desk/test_phase1_5b_migration.py` | ۲ تست بررسی migration |
| `tests/gold_desk/test_holding_soft_delete_reject.py` | رفع regression: user_id=None در fixture |

## آیتم‌های ۵ و ۶ (۲۰۲۶-۱۱-۰۹)
- **وضعیت:** ✅ کامل — commit قبلی روی `fix/gold-team`
- آیتم ۵: FIFO sell — دو باگ در `_consume_lots_by_symbol()` رفع شد (loop counter + unit_cost formula)
- آیتم ۶: token lifecycle — `cache.set(ttl=None)` → `cache.set_persistent()` در `save_token` و `verify_token`
- **تست:** `tests/gold_desk/test_phase1_items5_6.py` (5 تست، همه سبز)

---

## Security Hardening (۲۰۲۶-۱۱-۰۹)
- **وضعیت:** ✅ کامل — commit `c8110289` روی `fix/gold-team`
- **suite:** 481 passed, 1 skipped, 0 failed

### تغییرات
| فایل | تغییر |
|------|-------|
| `core/config/__init__.py` | اضافه کردن `registration_open: bool` (REGISTRATION_OPEN، پیش‌فرض True) |
| `apps/api/endpoints/auth.py` | چک `settings.registration_open` در ابتدای `register()` → HTTP 403 اگر بسته باشد |
| `apps/api/app.py` | `docs_url=None if settings.is_production else "/docs"` و همین برای `openapi_url` |
| `docker-compose.production.yml` | `REGISTRATION_OPEN=false` برای محیط production |
| `tests/gold_desk/test_security_hardening.py` | ۴ تست TDD (red ثبت‌شده، همه ۴ سبز) |

### ریسک‌های رفع‌شده
- **CRITICAL**: `/auth/register` کاملاً عمومی بود؛ اولین کاربر ثبت‌شده admin می‌شد
- **HIGH**: `/docs` و `/openapi.json` در production بدون محافظت

---

---

## WS1: BrsApi Resilience (۲۰۲۶-۱۱-۰۹)
- **وضعیت:** ✅ کامل — commit `923003df` روی `fix/gold-team`
- **suite:** 491 passed, 1 skipped, 0 failed (gold_desk + brsapi unit)
- **secrets scan:** هیچ مورد واقعی پیدا نشد

### تغییرات

| فایل | تغییر |
|------|-------|
| `brsapi/config.py` | `circuit_recovery_timeout: float = Field(default=120.0, ge=10.0)` اضافه شد |
| `brsapi/client.py` | `import random` + `_circuit_breaker()` از `brsapi_settings.circuit_recovery_timeout` می‌خواند (به‌جای hardcoded 30.0) + `±10%` jitter روی هر دو مسیر retry |
| `brsapi/services/sync_service.py` | `SYNC_OP_TIMEOUT_SECONDS=180.0` + هر عملیات در `sync_all()` با `asyncio.wait_for(timeout=SYNC_OP_TIMEOUT_SECONDS)` ایزوله شد |
| `tests/unit/test_ws1_brsapi_resilience.py` | ۵ تست TDD (همه سبز) |

### ریسک‌های رفع‌شده
- **HIGH**: `sync_all()` بدون timeout — یک fetch معلق تمام ۱۱ عملیات را مسدود می‌کرد
- **MEDIUM**: `circuit_recovery_timeout=30s` hardcoded — خیلی کوتاه برای یک provider production
- **MEDIUM**: jitter نداشتن retry — thundering herd هنگام retry همزمان چند درخواست

---

## WS2: FX Source (۲۰۲۶-۱۱-۰۹)
- **وضعیت:** ✅ کامل — commit `8863c3ee` روی `fix/gold-team`
- **suite:** 15/15 (secondary_source + snapshot_service + ws1)
- **secrets scan:** clean

### تغییرات

| فایل | تغییر |
|------|-------|
| `src/gold_desk/secondary_source.py` | `RIAL_TO_TOMAN = Decimal("0.1")` ثابت نام‌دار + TGJU_SYMBOLS از `_R2T` استفاده می‌کند |
| `src/gold_desk/snapshot_service.py` | `import is_available as tgju_available` حذف + `TGJU_FALLBACK_TIMEOUT_SECONDS=15.0` + `asyncio.wait_for` روی `fetch_tgju_prices()` |
| `tests/unit/test_ws2_fx_source.py` | ۶ تست TDD |

### ریسک‌های رفع‌شده
- **MEDIUM**: ثابت `0.1` ناشناس در TGJU_SYMBOLS — ریسک خطای تبدیل واحد
- **MEDIUM**: `tgju_available()` یک round-trip اضافه قبل از `fetch_prices()` — تاخیر اضافه در حالت fallback
- **MEDIUM**: بدون timeout روی fallback TGJU — `fetch_prices()` معلق می‌توانست کل snapshot را بلاک کند

---

## WS3: Macro Adapter (۲۰۲۶-۱۱-۰۹)
- **وضعیت:** ✅ کامل — commit `afc24963` روی `fix/gold-team`
- **suite:** 39/39 (WS1+WS2+WS3 + test_macro_news.py)
- **secrets scan:** clean

### تغییرات

| فایل | تغییر |
|------|-------|
| `src/gold_desk/macro_news.py` | `import asyncio` اضافه شد |
| `src/gold_desk/macro_news.py` | بلوک تکراری (import logging, logger, REDIS_KEY_MACRO, REDIS_KEY_MACRO_CACHE_DAYS) حذف شد |
| `src/gold_desk/macro_news.py` | `SCRAPE_TIMEOUT_SECONDS: float = 20.0` اضافه شد |
| `src/gold_desk/macro_news.py` | `refresh_macro_events_cache(scraper=scrape_cbi_news, cache=None)` اضافه شد |
| `tests/unit/test_ws3_macro_adapter.py` | ۶ تست TDD |

### ریسک‌های رفع‌شده
- **MEDIUM**: تعریف تکراری `REDIS_KEY_MACRO` و `logger` — باگ copy-paste، تغییر یک بلوک دیگری را آپدیت نمی‌کرد
- **MEDIUM**: بدون timeout روی scraper — stall در CBI تمام caller را بلاک می‌کرد
- **MEDIUM**: `fetch_macro_events()` و `scrape_cbi_news()` جدا بودند — cache هرگز از طریق این ماژول پر نمی‌شد

---

## فازهای بعدی (نیازمند بررسی/تأیید)
- **WS4–WS9**: نیاز به تأیید مالک در هر gate
- آیتم‌های ۱۰ و ۱۱ (gold_fund_nav staleness, BrsApi unit): نیاز به DB زنده
