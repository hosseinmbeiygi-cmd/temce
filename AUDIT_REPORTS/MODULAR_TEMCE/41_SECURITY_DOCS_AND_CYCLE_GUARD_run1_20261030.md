# ۴۱ — AUD-SEC-01 + گارد چرخه — run1، ۳۰ اکتبر ۲۰۲۶

**AUD-SEC-01:** **DECIDED/FIXED** — گیت salt حفظ شد و مستند/قابل‌کشف شد.
**گارد import-linter:** با یک تست AST بدون dependency جدید جایگزین شد و **PASS** است.
تغییرات commit نشده‌اند.

---

## ۱) AUD-SEC-01 — الزام `GOLD_API_TOKEN_SALT`

این رفتار عمدی است: `src/gold_desk/api_token.py` در import بدون salt خطا می‌دهد تا هیچ
هش پیش‌فرضی وجود نداشته باشد. مشکل عملیاتی این بود که ابزارها/توسعه‌دهنده پیام روشنی
برای رفع آن نداشتند.

**اقدام:**

- `docs/env-vars.md` → ردیف جدید در جدول «متغیرهای الزامی»:
  `GOLD_API_TOKEN_SALT` با توضیح «بدون آن `apps.api.app` با RuntimeError بالا نمی‌آید».
- `README.md` → بلوک `.env` نمونه با توضیح و مقدار نمونه.
- پیام `RuntimeError` در `src/gold_desk/api_token.py` به `docs/env-vars.md` ارجاع می‌دهد.

گیت امنیتی تغییر نکرد (هیچ salt پیش‌فرضی اضافه نشد).

## ۲) گارد دائمی چرخه (جایگزین import-linter)

`tests/unit/test_no_import_cycles.py` (جدید، بدون dependency):
- تمام فایل‌های ۱۲ بستهٔ بک‌اند را AST-parse می‌کند؛
- یال‌های import را در سطح دو‌سطحی می‌سازد (شامل importهای داخل تابع)؛
- هر چرخه‌ای پیدا شود تست fail می‌شود.

این همان الگوریتمی است که در گزارش‌های ۳۷/۳۸ برای رسیدن به صفر استفاده شد؛ بنابراین
اگر کسی وارونگی `brsapi.services → apps.api` یا چرخه‌های `backtesting` را برگرداند،
CI فوراً قرمز می‌شود.

**اثبات:**

```
pytest tests/unit/test_no_import_cycles.py tests/unit/test_core_tables_migration.py -q
  -> 4 passed in 15.71s, exit 0
```

## ۳) فایل‌ها

```
docs/env-vars.md                     + GOLD_API_TOKEN_SALT (REQUIRED)
README.md                            + نمونهٔ env و هشدار
src/gold_desk/api_token.py           + ارجاع به مستند در پیام خطا
tests/unit/test_no_import_cycles.py  جدید (گارد AST)
```

## ۴) وضعیت

| مورد | وضعیت |
|---|---|
| AUD-SEC-01 | **FIXED** (DECIDED: gate حفظ شد) |
| گارد چرخه | **PASS** |
| import-linter | جایگزین شد (dependency جدید لازم نیست) |
| commit | **BLOCKED** (درخت مشترک) |
