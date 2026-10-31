# ۳۶ — AUD-TEST-01 و مستندات DB خالی — run1، ۳۰ اکتبر ۲۰۲۶

**AUD-TEST-01:** **PARTIAL** — collection بدون DB تمیز شد؛ اجرای تست‌های DB همچنان به
`DATABASE_URL` نیاز دارد (مستند شد).
**مستندات DB-02:** **FIXED**.
تغییرات commit نشده‌اند.

---

## ۱) AUD-TEST-01 — خطای collection روی DB ناموجود

**قبل:**

```
pytest tests --collect-only -q
  -> exit 2
  -> 8158/8207 collected (49 deselected), 2 errors in 46.53s
  -> ERROR tests/test_screener_flow.py - RuntimeError: Cannot connect to PostgreSQL
  -> ERROR tests/test_sync_2.py - asyncpg.InvalidPasswordError
```

**ریشه:** هر دو فایل اسکریپتی‌اند و در انتهای ماژول `asyncio.run(test())` داشتند؛
pytest برای خواندن markerها ماژول را import می‌کند و اجرای سطح‌ماژول قبل از هر
skip/collection hook به DB وصل می‌شد. `pytestmark = needs_db` در `test_sync_2.py`
هم بی‌اثر بود، چون import اول انجام می‌شود.

**اصلاح:**

- `async def test()` → `async def _run()` در هر دو فایل؛
- `asyncio.run(...)` زیر `if __name__ == "__main__":` منتقل شد.

**بعد:**

```
pytest tests --collect-only -q
  -> exit 0
  -> 8158/8207 tests collected (49 deselected) in 52.58s
  -> no errors
```

**باقی‌مانده:** تست‌هایی که واقعاً DB می‌خواهند (از جمله ۷ تست gold) بدون
`DATABASE_URL` روی `localhost:5432/market` شکست می‌خورند. این دیگر خطای collection
نیست؛ در README دستور اجرا با DSN استک audit اضافه شد. وضعیت: **PARTIAL** تا CI
متغیر را تنظیم کند.

---

## ۲) مستندات DB خالی (باقی‌ماندهٔ DB-02)

| فایل | تغییر |
|---|---|
| `migrations/README.md` | یادداشت `0004b_core_baseline` بین 0004/0005؛ مسیر DB خالی؛ هشدار که `contextlib.suppress` دور `op.add_column` تراکنش را abort می‌کند؛ ورودی DB-02 در «اشکالات رفع‌شده» |
| `README.md` | بخش مهاجرت: baseline خودکار و انتظار `current = 0119`؛ بخش تست: دستور اجرای تست‌های DB با `DATABASE_URL` روی ۱۵۴۳۲ |

---

## ۳) فایل‌ها

```
tests/test_screener_flow.py        (asyncio.run زیر __main__، تابع _run)
tests/test_sync_2.py               (همان)
migrations/README.md               (زنجیره، مسیر DB خالی، هشدار suppress، DB-02)
README.md                          (مهاجرت + دستور تست DB)
```

## ۴) وضعیت

| مورد | وضعیت |
|---|---|
| Collection بدون DB | **PASS** (exit 0، ۰ خطا) |
| AUD-TEST-01 | **PARTIAL** (اجرای DB نیازمند DSN) |
| مستندات DB خالی | **FIXED** |
| commit | **BLOCKED** (درخت مشترک؛ منتظر دستور) |
