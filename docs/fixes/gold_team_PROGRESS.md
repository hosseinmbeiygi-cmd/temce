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

## فازهای بعدی (نیازمند تأیید)
- فاز ۱.۵b: پیاده‌سازی ownership (backfill + NOT NULL + رفع G-3) — پس از تأیید D1–D4
- ...
