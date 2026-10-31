# ۴۳ — پاس کیفیت روی دیف‌های آدیت — ۳۰ اکتبر ۲۰۲۶

**وضعیت:** **PASS** — همهٔ فایل‌های تغییر‌یافته ruff-clean هستند و ۳۹۹ تست مرتبط پاس شد.
تغییرات commit نشده‌اند.

---

## ۱) یافته‌های lint روی دیف خودمان

`ruff check` روی ۳۰ فایل تغییر‌یافته: **۵۷۷ خطا → ۰**.

| کد | تعداد | علت | اصلاح |
|---|---|---|---|
| W291 | ۵۷۰ | فاصلهٔ انتهایی داخل DDL تولیدشدهٔ baseline | بازتولید `0004b` با `rstrip` هر خط |
| F821 | ۵ | `Any` در `event_builder.py` بعد از انتقال `MarketEvent` حذف شده بود | بازگرداندن `from typing import Any` |
| F401 | ۱ | `_AGG_TOKEN_TTL` به‌عنوان re-export برای تست نگه داشته شده | `# noqa: F401` با توضیح |
| I001 | ۱ | ترتیب import در `apps/api/app.py` | `ruff --fix` |

## ۲) تأیید

```
ruff check <changed files>     -> All checks passed!
py_compile <changed py files>  -> compile_ok
alembic heads                  -> 0119_service_private_tables (head)  [تک‌سر]
pytest test_no_import_cycles + test_core_tables_migration + tests/unit/backtesting
  -> 399 passed, 1 skipped in 31.72s, exit 0
```

## ۳) نکتهٔ baseline

بازتولید `0004b_core_baseline.py` فقط فاصله‌های انتهایی خطوط SQL را حذف کرده است؛
DDL معنایی تغییری نکرده. اثبات `upgrade head` از گزارش ۳۴ (exit 0، ۲۰۳ جدول) معتبر
می‌ماند، اما اگر برای commit اطمینان کامل لازم است، می‌توان پیش از commit یک DB خالی
دیگر ساخت و دوباره اجرا کرد (نیازمند تأیید ساخت/حذف DB).

## ۴) وضعیت

| مورد | وضعیت |
|---|---|
| ruff روی دیف آدیت | **PASS** (۰ خطا) |
| تست‌های مرتبط | **PASS** (۳۹۹/۴۰۰، ۱ skip) |
| تک‌سری زنجیرهٔ migration | **PASS** |
| commit | **BLOCKED** (درخت مشترک) |
