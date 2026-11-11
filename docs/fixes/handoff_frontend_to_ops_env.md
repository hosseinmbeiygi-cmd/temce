# handoff — از دستیار ۳ (frontend-infra) به صاحب محصول / Ops (فایل `.env.example`)

> ## ✅ حل‌شده در مرحلهٔ ۳ — دیگر درخواست نیست
> در مرحلهٔ ۳، `.env.example` به محدودهٔ مالکیت این دستیار اضافه شد و چهار کلید
> خواسته‌شده **همین حالا نوشته شده‌اند** (بدون هیچ مقدار واقعی):
> `DEV_JOB_QUEUE_TOKEN=`، `GOLD_API_TOKEN_SALT=`، `GOLD_BACKUP_DIR=`،
> `GOLD_BACKUP_RETENTION_DAYS=14`.
> این فایل به‌عنوان سابقهٔ تصمیم نگه داشته شده (حذف نمی‌شود؛ سیاست repo: حذف فایل
> با صاحب کار). باقی‌ماندهٔ واقعی این سند فقط **چون‌بَدِل کردن** دو مقدار لو‌رفته است
> که کار من نیست: `docs/security/secret_rotation.md`.
>
> تنها چیزی که از این فایل باقی می‌ماند و **در محدودهٔ من نیست**:
> `docs/analysis/02_backend_infra.md:538` مقدار رمز Redis را در جدول چاپ کرده —
> فایل فقط‌خواندنی. از صاحب گزارش ماسک می‌خواهم. جزئیات:
> `docs/security/secret_scan_report.md §۲` ردیف ۶.

تاریخ: ۲۰۲۶-۱۰-۲۴

## چرا این فایل جداست

`.env.example` در فهرست محدودهٔ مالکیت هیچ‌یک از سه دستیار نیست (محدودهٔ من:
`frontend/` بخش gold، `docs/`، `PLAN_GOLD.md`, `README.md`, `Dockerfile.golddesk`,
`nginx-golddesk.conf`, `docker-compose*.yml`, `monitoring/`, `tests/load/`, و
فایل‌های **جدید** `scripts/` و `.github/workflows/`). طبق قاعدهٔ ۲ تغییرش ندادم و
درخواست را اینجا می‌نویسم.

## تغییر مطلوب

به `.env.example` (کنار `DEV_POSTGRES_PASSWORD` که در خط ۱۹۱ هست) دو کلید اضافه شود:

```
# salt برای هش کردن API tokenهای GoldDesk — اجباری در docker-compose (I3)
GOLD_API_TOKEN_SALT=

# توکن صف jobها — اجباری در docker-compose (بود، ولی فقط به‌عنوان پیش‌فرضِ commit شده)
<REDACTED>=
```

## دلیل

`docker-compose.yml` در این رفع دو چیز شد:

1. **`GOLD_API_TOKEN_SALT` با `:?` اجباری شد** (I3). کد هنوز پیش‌فرض committed دارد
   (`src/gold_desk/api_token.py:28`) که یعنی «اگر ست نشود، همه با یک salt معلوم
   هش می‌کنند». compose حالا نگهبان بیرونی است.
2. دو پیش‌فرضِ **secret واقعی‌نما** که در فایل commit شده بود حذف شد:
   ۱) پیش‌فرض `<REDACTED>` ۲) پیش‌فرض `<REDACTED>`
   (در ۵+ خط compose تکرار شده بودند). مقادیر را این‌جا نمی‌نویسم (قاعدهٔ ۵)؛
   جای دقیقشان در `docs/security/secret_scan_report.md` با file:line آمده است.

## پیامد فوری که باید بدانید

- `docker compose up` روی محیطی که این دو مقدار را در `.env` ندارد، **همان اول
  با خطا می‌ایستد**: `GOLD_API_TOKEN_SALT must be set as a secret`. این رفتار
  عمدی و خواستهٔ I3 است (fail-closed بهتر از بالا آمدن با secret پیش‌فرض است).
- اگر `GOLD_API_TOKEN_SALT` قبلاً ست نشده بود، اولین مقدارِ ست‌شده token های
  صادرشدهٔ قبلی را باطل می‌کند → باید از `/gold/tokens` بازصدور شوند.
- آن دو مقدار لو‌رفته باید **چون‌بَدِل** شوند؛
  حذفشان از فایل، تاریخ commit را پاک نمی‌کند.

## کار مرتبط (اختیاری، ولی توصیه)

- `GOLD_BACKUP_DIR` و `GOLD_BACKUP_RETENTION_DAYS` را هم به `.env.example` اضافه
  کنید تا `scripts/backup_golddesk.sh` قابل کشف باشد
  (راهنما: `docs/golddesk_backup.md`).
