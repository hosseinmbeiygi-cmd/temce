# ۲۵ — API-05: موجودی سطح Router و routerهای mount‌نشده

**تاریخ:** 2026-10-29
**دامنه:** `apps/api/router.py`, تمام `apps/api/endpoints/*.py`
**وضعیت:** DONE (شناسایی + گاردِ رگرسیون؛ تصمیم mount/حذف = محصولی و باز)
**نسخه:** run1 — گزارش‌های قبلی بازنویسی نشدند.

---

## ۱. Git

| فیلد | مقدار |
|---|---|
| HEAD | `252b5ea5` (شروع مرحله) |
| snapshot | `_snapshots/t21-api05.txt` |

## ۲. روش

تحلیل AST:
- همهٔ ماژول‌های `apps/api/endpoints/*.py` که یک نام `router` را تعریف می‌کنند.
- تمام `router.include_router(...)` در `apps/api/router.py` و نگاشت `from apps.api.endpoints.X import router as y`.
- مجموعهٔ تفاضل = ماژول‌های دارای router که *هرگز* mount نمی‌شوند.

## ۳. یافتهٔ اصلی — ۷ router mount‌نشده

مجموع ۸۲ ماژول router-دار؛ ۷۵ mount‌شده؛ **۷ mount‌نشده**:

| ماژول | مسیرهای تعریف‌شده | mount شده؟ | مصرف‌کنندهٔ فرانت‌اند | import در کد بیزنس |
|---|---|---|---|---|
| `comprehensive_analysis` | `GET /{symbol}/comprehensive-analysis` | خیر | ندارد | ندارد |
| `ime` | ۶ مسیر GET (فهرست IME) | خیر | ندارد | ندارد |
| `monitoring` | `GET /metrics`, `GET /data-quality` | خیر | ندارد | ندارد |
| `proposals` | `POST/GET ""`, `POST /{id}/approve`, `POST /{id}/reject` | خیر | ندارد | ندارد |
| `scanner` | `POST /scan`, `GET /scan/status`, `GET /scan/results`, `POST /scan/extract-relations` | خیر | ندارد | ندارد |
| `sentiment` | `POST /analyze`, `POST /batch`, `POST /train`, `GET /stats` | خیر | ندارد | ندارد |
| `symbol_alerts` | `GET ""`, `POST ""`, `DELETE /{alert_id}`, `GET /{symbol}/decision-hub` | خیر | ندارد | ندارد |

**شواهد:** `rg "from apps.api.endpoints.<m> import"` برای هیچ‌یک نتیجه نداد؛ هیچ مسیر `/proposals`, `/scanner/scan`, `/sentiment/analyze`, `/monitoring/metrics`, `/comprehensive-analysis` در `tests/` یا `frontend/src` ارجاع نشده؛ در `docker-compose*.yml` هیچ scrape/paths به `/metrics` وجود ندارد.

**نتیجه:** سطح این ۷ router از طریق API عمومی **غیرقابل‌دسترس** است؛ کد مرده محسوب می‌شود (نه خطای زندهٔ کاربر). شدت P3.

## ۴. یافتهٔ جانبی (کشف‌شده در جریان تحلیل) — BOM در `ime.py`

- فایل `apps/api/endpoints/ime.py` با یک UTF-8 BOM (`EF BB BF`) شروع می‌شد.
- اثر: import پایتون تحمل می‌کند، اما ابزارهایی که منبع را به‌عنوان متن UTF-8 خام می‌خوانند (مثل `ast.parse(text)`) شکست می‌خورند — دقیقاً همین موضوع باعث شد `ime` در اولین پاس تحلیل نادیده بماند (۱۳→۱۴ ماژول اشتباه شمرده شد و ime گم شد).
- **اصلاح:** حذف BOM با بازنویسی بایت‌به‌بایت (۳ بایت اول؛ بدون تغییر دیگری در فایل). ۷۴۰۸→۷۴۰۵ بایت.

## ۵. اصلاحات انجام‌شده

1. `apps/api/endpoints/ime.py` — حذف BOM (hygiene، بدون تغییر منطق).
2. تست جدید `tests/unit/test_api_router_surface_inventory.py`:
   - `test_no_endpoint_module_has_utf8_bom` (RED قبل از حذف BOM → GREEN بعد).
   - `test_new_unmounted_router_is_not_introduced` — عدم‌برابری زیرمجموعه‌ای با allowlist (اگر کسی یکی را mount کند، Superset می‌شود و تست سبز می‌ماند؛ فقط انباشت router مردهٔ *جدید* را می‌گیرد).

**توجه:** تصمیم «mount با نقش مناسب یا حذف کد» برای ۷ ماژول، محصولی/امنیتی است (بند D در §۱۰.۱ طرح مادر) و به‌صورت یک‌طرفه انجام نشد.

## ۶. معیارهای پذیرش

| معیار | نتیجه |
|---|---|
| فهرست دقیق routerهای mount‌نشده با شاهد | PASS (۷ مورد، بالا) |
| تست RED قبل / GREEN بعد برای BOM | PASS |
| گارد جلوگیری از انباشت router مردهٔ جدید | PASS (`test_new_unmounted_router_is_not_introduced`) |
| ruff روی فایل‌های تغییریافته | PASS |

## ۷. شواهد آزمون

| فرمان | نتیجه |
|---|---|
| `python -m pytest tests/unit/test_api_router_surface_inventory.py -q` | قبل از حذف BOM: 1 failed, 1 passed؛ بعد: **2 passed**، exit 0 |
| `python -m ruff check apps/api/endpoints/ime.py tests/unit/test_api_router_surface_inventory.py` | exit 0 |

## ۸. باقی‌مانده

- ۷ ماژول mount‌نشده → منتظر تصمیم محصولی: mount با `Depends(require_roles(...))` یا حذف.
- دامنه‌های باز دیگر طبق §۱۰.۱ طرح مادر (دسته‌های B/C/D/E).
