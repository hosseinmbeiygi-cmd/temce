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

### اقدام بعدی
**منتظر تأیید مالک برای فاز ۱.۵a (طراحی ownership)**

## فازهای بعدی (نیازمند تأیید)
- فاز ۱.۵a: طراحی ownership (نه کد)
- ...
