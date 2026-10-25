# اولین راه‌اندازی GoldDesk (S2 — bootstrap)

مخاطب: کسی که برای اولین بار این repo را روی یک ماشین بالا می‌آورد، یا کسی که
`.env` ندارد و `docker compose up` اش خطا می‌دهد.

---

## ۰) چرا عمداً بالا نمی‌آید

`docker-compose.yml` سه متغیر را با سینتکس `${VAR:?message}` می‌خواند. یعنی اگر
تعریف نشده باشند، compose **همان اول** با پیام خطا می‌ایستد و هیچ کانتینری
بالا نمی‌آید. این باگ نیست، خواستهٔ I3 است:

| متغیر | چرا اجباری است |
|---|---|
| `DEV_POSTGRES_PASSWORD` | رمز دیتابیس dev؛ قبلاً دوبار با پیش‌فرض commit شده منتشر شد |
| `DEV_REDIS_PASSWORD` | به‌صورت پیش‌فرضِ commit‌شده در `REDIS_URL` بود (حذف شد) |
| `DEV_JOB_QUEUE_TOKEN` | به‌صورت پیش‌فرضِ commit‌شده در backend/worker بود (حذف شد) |
| `GOLD_API_TOKEN_SALT` | salt هش API tokenهای طلا؛ `api_token.py:28` هنوز پیش‌فرض hard-code دارد و این نگهبان بیرونی آن است |

نکته: پیش از این رفع، نبودِ این مقادیر یعنی بالا آمدن با رمزهای معلوم. حالا نبودشان
یعنی ایستادن. **پیام خطا بهتر از اجرای بی‌صدا با secret پیش‌فرض است.**

## ۱) ساخت مقادیر تصادفی

```bash
# برای هر چهار متغیر، یک مقدار تصادفی ۶۴ کاراکتری بسازید
openssl rand -hex 32        # رمزها و توکن‌ها
openssl rand -hex 32        # salt توکن‌های API
```

اگر `openssl` ندارید:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## ۲) پر کردن `.env`

```bash
cp .env.example .env
```

سپس در `.env` این چهار خط را با مقدارهای تازه پر کنید (در `.env.example` عمداً
خالی‌اند — قاعدهٔ repo: هیچ مقدار واقعی commit نمی‌شود):

```
DEV_POSTGRES_PASSWORD=<خروجی openssl rand -hex 32>
DEV_REDIS_PASSWORD=<خروجی openssl rand -hex 32>
DEV_JOB_QUEUE_TOKEN=<خروجی openssl rand -hex 32>
GOLD_API_TOKEN_SALT=<خروجی openssl rand -hex 32>
```

دو مورد زیر اختیاری‌اند و پیش‌فرض معقول دارند:

```
GOLD_BACKUP_DIR=./backups/golddesk
GOLD_BACKUP_RETENTION_DAYS=14
```

## ۳) بالا آوردن و بررسی

```bash
docker compose --env-file .env up -d
docker compose ps                       # همه healthy
curl -fsS http://localhost:8000/api/v1/gold/health | head -c 400
```

`/health` باید ۲۰۰ بدهد. اگر **۵۰۳** گرفتید یعنی Redis یا DB قطع است (C8) — آن
۵۰۳ اطلاعات کاملی در بدنه دارد (`redis_ok`, `db_ok`, …) و صفحهٔ `/gold/health`
نشان می‌دهد کدام وابستگی خوابیده.

## ۴) مسیر غیر-داکر (dev مستقیم)

اگر بدون compose اجرا می‌کنید (`uvicorn apps.api.main:app`)، هیچ چیزی شما را از
مقادیر پیش‌فرض منع نمی‌کند — `GOLD_API_TOKEN_SALT` در `api_token.py:28` هنوز
پیش‌فرض hard-code دارد. تا قبل از رفع آن (درخواست در
`docs/fixes/handoff_frontend_to_backend.md §۵`)، **خودتان** متغیر را ست کنید:

```bash
export GOLD_API_TOKEN_SALT=$(openssl rand -hex 32)
export DEV_JOB_QUEUE_TOKEN=$(openssl rand -hex 32)
```

## ۵) بعد از بالا آمدن

- UI: `http://localhost:3000/gold`
- اولین snapshot ممکن است ۱–۲ دقیقه طول بکشد؛ تا قبلش عدد اصلی `NO_DATA` است.
- توکن خارجی: از `/gold/tokens` بسازید (scope `read` برای Sheets/ربات).
- پشتیبان: `docs/golddesk_backup.md` — و تا اولین بازگردانی **موفق** روی همان
  ماشین، نسخه‌گیری را تأییدشده حساب نکنید.

## ۶) اگر موجودی از قبل token داشته و salt را عوض کردید

هر API token صادرشده با salt قبلی دیگر معتبر نیست. چک‌لیست کامل
چون‌بَدِل‌کردن (رمزها، توکن صف، salt، بازصدور توکن‌ها) در
`docs/security/secret_rotation.md` است.
