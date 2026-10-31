# پیشرفت رفع خطاهای طلا (GoldDesk)

| فاز | کار | وضعیت | فایل‌ها | تست | commit |
|----|-----|------|--------|-----|--------|
| ۱ | Redis pub/sub برای signal (job → hub → browser) | fixed | `src/gold_desk/live_signals.py`, `src/gold_desk/ws_hub.py`, `brsapi/jobs/gold_desk_jobs.py` | `tests/gold_desk/test_ws_pubsub.py`, `tests/gold_desk/test_ws_hub.py` | `12be887f` |
| ۱ | تست soft-delete ایمن (بدون دیتابیس skip) | fixed | `tests/gold_desk/test_holding_soft_delete.py`, `docs/golddesk_test_db.md` | `test_holding_soft_delete.py` (needs_db) | `12be887f` |
| ۱ | ممیزی salt اجباری API token (فقط‌خواندنی گزارش) | fixed | `src/gold_desk/api_token.py`, `tests/gold_desk/test_api_token_salt.py`, `tests/gold_desk/test_api_token_boot.py` | ۴ تست salt/boot | `12be887f` |
| ۱ | ماژول‌های غایب phase1/phase2/phase1_schemas (import api.py) | fixed | `src/gold_desk/phase1.py`, `src/gold_desk/phase1_schemas.py`, `src/gold_desk/phase2.py` | `tests/gold_desk/test_api_contract_fields.py`, `test_metrics_scope.py`, `test_holding_soft_delete_reject.py` | `12be887f` |
| ۱ | اصلاح تکرار مسیر در `test_metrics_scope.py` | fixed | `tests/gold_desk/test_metrics_scope.py` | `test_metrics_route_sits_on_the_token_gated_router` | `12be887f` |
| ۲ | لول ریلود SW: حذف `skipWaiting()`/`clients.claim()` از هر دو SW | fixed | `frontend/public/sw.js`, `frontend/public/golddesk-sw.js` | `tests/gold_desk/...` (SW) + `src/__tests__/sw_reload_loop.test.ts` | `dca31ab8` |
| ۲ | ثبت SW یک‌بار با guard در `PWAProvider.tsx` و `providers.tsx` | fixed | `frontend/src/components/gold/PWAProvider.tsx`, `frontend/src/app/providers.tsx` | `src/__tests__/sw_reload_loop.test.ts` | `dca31ab8` |
| ۲ | دسترسی /admin (W5-01): `/markets/gold` (کاربر عادی) از `sync-status` استفاده می‌کند ⇒ endpoint محافظت نشد |報告 شده | — | — | `dca31ab8` |
| ۳ | W4-01: فروش مقدار موجودی را کم می‌کند، فروش بیش از موجودی ValueError | fixed | `src/gold_desk/portfolio.py` | `tests/gold_desk/test_w401_inventory_sale.py` | pending |
| ۳ | W4-02: چرخهٔ حیات توکن (save/index/verify/revoke/list) | fixed | `src/gold_desk/api_token.py` | `tests/gold_desk/test_w402_token_lifecycle.py` | pending |
| ۳ | null-safety فرانت: pnl_pct/current_value/pnl_irt/priced_cost null → «—» | قبلاً پیاده شده | `frontend/src/app/gold/portfolio/page.tsx` | `tests/gold_desk/...` + `src/__tests__/GoldPortfolioSafety.test.tsx` | pending |
| ۳ | حذف دارایی گروه‌شده: holding_ids، ConfirmDialog، 409→قبلاً حذف شده، refetch، force نه | قبلاً پیاده شده | `frontend/src/app/gold/portfolio/page.tsx` | `src/__tests__/GoldPortfolioSafety.test.tsx` | pending |

**بازوهای باز:**
- `/admin/page.tsx` بررسی `hasRole("admin")` ندارد (خارج از دامنه مجاز `app/gold`، `components/gold`، `lib/goldApi.ts`، `types/gold.ts`، `hooks/useGoldWS.ts`، `__tests__`)
- `tests/gold_desk/test_phase0_mount.py` و `test_phase0_snapshot_integration.py` بدون PostgreSQL شکست می‌خورند (غيرقابل‌اجتناب در این محیط)
