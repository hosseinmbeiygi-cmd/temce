# چرخش Secrets — راهنما و گزارش اجرا (۲۰۲۶-۰۹-۱۶)

## چرا؟

فایل `.env.production` (شامل `SECRET_KEY` واقعی و credentials دیتابیس) از **initial commit در تاریخچه git** وجود داشته — یعنی هر secret ای در آن لو رفته فرض می‌شود حتی بعد از untrack شدن فایل (کامیت `51e9bebc`). همچنین رمزهای dev هاردکد (`securepassword123`، `redissecure456`، `dev-shared-queue-token`) در `docker-compose.yml` در تاریخچه مانده‌اند.

## چه چیزی rotate شد

| Secret | قبل | بعد | محل |
|--------|-----|-----|------|
| `SECRET_KEY` | placeholder `change-me-in-production` (۵۴ کاراکتر) | ۶۴ کاراکتر hex تصادفی (`secrets.token_hex(32)`) | `.env` محلی (untracked) |
| رمز Postgres محلی (`DB_PASSWORD`/`PG_PASSWORD`/`DATABASE_URL`) | `1343` (۴ کاراکتر!) | ۲۷ کاراکتر urlsafe تصادفی | `.env` + **خود Postgres** (`ALTER USER`) |
| رمز Postgres کانتینر dev | `securepassword123` هاردکد | `${DEV_POSTGRES_PASSWORD:-qT7vR2mXe9LpZ4kD}` | `docker-compose.yml` |
| رمز Redis کانتینر dev | `redissecure456` هاردکد | `${DEV_REDIS_PASSWORD:-rD8wN5sYh2JqX6vB}` | `docker-compose.yml` |
| `JOB_QUEUE_TOKEN` dev | `dev-shared-queue-token` هاردکد | `${DEV_JOB_QUEUE_TOKEN:-jK3nQ8vTz5WmR7xC}` | `docker-compose.yml` |

## راستی‌آزمایی انجام‌شده

1. **Postgres واقعی:** اتصال با رمز قدیمی → `ALTER USER hossein WITH PASSWORD '...'` → اتصال مجدد با رمز جدید ✅
2. **لایه DB اپ:** `init_database()` + `SELECT 1` با تنظیمات جدید ✅
3. **JWT:** توکن با کلید جدید sign/verify ✅ — توکن امضاشده با کلید قبلی → `InvalidSignatureError` (دقیقاً رفتار موردانتظار چرخش؛ همه access/refresh tokenهای قبلی باطل شدند) ✅
4. **`docker compose config`** بعد از تغییرات: معتبر ✅
5. **`.env` همچنان untracked** (`.gitignore:19`) ✅

## ⚠️ اقدام دستی باقی‌مانده: stale env در ترمینال

ترمینال/IDE جاری سه متغیر **Process-level** با مقادیر قدیمی تزریق کرده: `SECRET_KEY=change-me...`، `DB_PASSWORD=1343`، `PG_PASSWORD=1343`. چون pydantic-settings اولویت env واقعی را بر `.env` می‌دهد، **پروسه‌های بازشده از همین ترمینال فعلی تا ری‌استارت، مقادیر قدیمی می‌گیرند.**

→ ترمینال را ببندید و باز کنید (یا `unset SECRET_KEY DB_PASSWORD PG_PASSWORD`). مقادیر جدید از `.env` خوانده می‌شوند.

## چیزهایی که فقط خودتان می‌توانید انجام دهید

| مورد | چرا اینجا ممکن نیست |
|------|---------------------|
| رمز Postgres **production** (`market@postgres` در `.env.production` قدیمی) | سرور واقعی از اینجا قابل دسترسی نیست |
| `BRSAPI_API_KEY` | در فایل لو-رفته نبود؛ اگر در جای دیگری لو رفته، از پنل BrsApi بگیرید |
| Secretهای سرویس‌های دیگر (Telegram bot token و...) | خارج از دامنه این ریپو |

## procedure — چرخش در آینده

```bash
# 1. کلید جدید بسازید
python -c "import secrets; print(secrets.token_hex(32))"

# 2. در .env محلی جایگزین کنید (هرگز commit نکنید)

# 3. رمز را داخل خود دیتابیس عوض کنید
psql -U hossein -d my_first_db -c "ALTER USER hossein WITH PASSWORD '<new>';"

# 4. همه پروسه‌ها را ری‌استارت کنید (ترمینال + سرویس‌ها)
```

## یادآوری نهایی

این چرخش، تاریخچه git را تمیز نمی‌کند — فقط secretهای قبلی را بی‌ارزش می‌کند. پاکسازی history (`git filter-repo`) همچنان به‌عنوان گام مکمل برای ریپوهای public توصیه می‌شود.
