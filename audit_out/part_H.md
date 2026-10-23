# بخش H — امنیت و حقوقی داده

> فقط مسیر و نوع گزارش می‌شود؛ هیچ مقدار رمزی در خروجی نوشته نشده (مقدارها `***`). [خوانده‌شده+اجراشده] برای اسکن فایل/گیت.

## H1) کلید/رمز/توکن

| محل | نوع یافته | مسیر | وضعیت |
|---|---|---|---|
| `.env` | ۶ کلید حساس **حاضر** (نام‌ها): `SECRET_KEY`, `ENCRYPTION_KEY`, `DB_PASSWORD`, `BRSAPI_API_KEY`, `SMTP_PASSWORD`, `SENTRY_DSN` (مقادیر `***`) | `.env` | در گیت **tracked نیست** (در `.gitignore` خطوط ۱۹-۲۳) |
| `.env.bak.1790980646` | نسخهٔ پشتیبان env (احتمالاً همان کلیدها) | `.env.bak.1790980646` | tracked نیست |
| `.env.production` | env تولیدی | `.env.production` | tracked نیست |
| `crawler_state.json` | **بدون رمز** — فقط شمارنده (`current_day`, `requests_today`, `hits_today`) | `crawler_state.json` | **tracked است** (بی‌خطر) |
| `docker-compose.yml` | هیچ کلید ثابت inline دیده نشد (احتمالاً `env_file`) | `docker-compose.yml` | — |
| کد پایتون (services/core/brsapi/ml/scripts) | هیچ کلید ثابت (grep الگوی `sk-…`/`api_key="…"` بدون نتیجه) | — | ✅ |
| `openrouter/deepseek/deepseek-chat` | **فایل ۰ بایتی** (خالی)؛ کلید ثابت ندارد | `openrouter/deepseek/deepseek-chat` | ✅ |
| زیرساخت امنیت | workflow اسکن رمز + مستندات چرخش | `.github/workflows/secrets-scan.yml`, `docs/secrets-management.md`, `docs/SECRETS_ROTATION_2026-09-16.md`, `core/security/secrets.py`, `integrations/secrets.py` | ✅ موجود |
| تاریخچهٔ گیت | اسکن کاملِ همهٔ کامیت‌ها **انجام نشد** (خارج از بودجه) | — | **بررسی‌نشده** |

**نتیجهٔ H3:** پوشهٔ `openrouter/deepseek` **وجود دارد** ولی `deepseek-chat` یک فایل **۰ بایتی** است؛ **کلید ثابتی ندیدم**.

## H2) منبع داده‌های اسکرپ‌شده و شرایط استفاده

| منبع | مسیر مستند/کد | شرایط استفاده |
|---|---|---|
| BrsApi (سهام/طلا/ارز/کریپتو/IME/کدال) | `docs/brsapi-data-sources.md`، `brsapi/` | **نامشخص** (سند فقط اندپوینت‌ها را فهرست می‌کند) |
| TGJU (اسکرپ) | `docs/CODEBASE_DISCOVERY_OPTIONS_2026-09-16.md` + `src/gold_desk/secondary_source.py` | **نامشخص** |
| Nobitex / TSE / Codal | اسناد `docs/` | **نامشخص** |

هیچ سند «Terms of Service / مجوز بازتوزیع / سیاست robots.txt» برای منابع اسکرپ‌شده پیدا نکردم ⇒ **نامشخص**.

## جمع‌بندی H

| id | شرح | شدت | اقدام |
|---|---|---|---|
| H-01 | `.env` و بکاپ‌ها در گیت نیستند (خوب)؛ اما ۶ کلید حساس روی دیسک هستند | متوسط | اطمینان از عدم اشتراک‌گذاری |
| H-02 | هیچ کلید ثابتی در کد/`openrouter`/`docker-compose` پیدا نشد | — | — |
| H-03 | شرایط استفادهٔ منابع اسکرپ‌شده (BrsApi/TGJU) مستند نشده | متوسط | افزودن سند ToS |
| H-04 | اسکن تاریخچهٔ گیت انجام نشد | اطلاعاتی | اجرای `gitleaks`/workflow موجود |
