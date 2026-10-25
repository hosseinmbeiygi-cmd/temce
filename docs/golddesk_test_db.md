# دیتابیس تست GoldDesk

تست `tests/gold_desk/test_holding_soft_delete.py` واقعاً روی PostgreSQL می‌نویسد.
پس **هرگز** نباید به دیتابیس برنامه (`my_first_db`) وصل شود. این تست فقط وقتی
اجرا می‌شود که متغیر `GOLD_TEST_DATABASE_URL` در همان session ترمینال تنظیم شده
باشد و آدرسش از دو حفاظ عبور کند:

1. با `settings.database_url_async` یکی نباشد؛
2. نام دیتابیسش شامل `test` باشد (مثلاً `golddesk_test`).

اگر متغیر تنظیم نشود، تست با پیام روشن skip می‌شود. هیچ مقدار پیش‌فرض یا فایل
commit‌شده‌ای برای آدرس تست وجود ندارد.

## ۱) ساخت دیتابیس خالی

هر دو راه فقط یک دیتابیس خالی می‌سازند؛ هیچ جدول یا داده‌ای از `my_first_db`
کپی نمی‌شود. مقدارهای `<...>` را با مقادیر محیط خودت جایگزین کن (رمز را در
گزارش/فایل ننویس).

### الف) با `psql`

```bash
psql -h localhost -p 5432 -U <db_user> -c "CREATE DATABASE golddesk_test;"
```

### ب) با `docker exec`

نام کانتینر PostgreSQL را از `docker ps` بردار:

```bash
docker exec -it <postgres_container> psql -U <db_user> -c "CREATE DATABASE golddesk_test;"
```

اگر دیتابیس از قبل هست، خطای `already exists` طبیعی است؛ نیازی به حذف آن نیست.

## ۲) تنظیم آدرس فقط در همان PowerShell session

در PowerShell (نه cmd و نه فایل `.env`):

```powershell
$env:GOLD_TEST_DATABASE_URL = "postgresql://<db_user>:<db_password>@localhost:5432/golddesk_test"
```

- این متغیر فقط تا بسته‌شدن همان پنجره معتبر است و در فایل ذخیره نمی‌شود.
- کد، `postgresql://` را خودش به `postgresql+asyncpg://` نرمال می‌کند.
- برای پاک‌کردنش: `Remove-Item Env:\GOLD_TEST_DATABASE_URL`

> تذکر: این آدرس نباید به `my_first_db` یا هر دیتابیس برنامه/تولید اشاره کند.

## ۳) اجرای تست

```powershell
python -m pytest tests/gold_desk/test_holding_soft_delete.py -q -m needs_db -p no:cacheprovider
```

- `-m needs_db` لازم است چون `pyproject.toml` به‌طور پیش‌فرض
  `-m "not needs_db"` را به `addopts` اضافه می‌کند و در غیر این صورت تست
  deselect می‌شود.
- برای دیدن دلیل skip: `-rs` را هم اضافه کن.

```powershell
python -m pytest tests/gold_desk/test_holding_soft_delete.py -q -m needs_db -rs -p no:cacheprovider
```

## ۴) رفتار تست روی دیتابیس تست

- اگر جدول‌های GoldDesk در `golddesk_test` نباشند، فقط روی engine همین تست و با
  `GoldDeskBase.metadata.create_all` ساخته می‌شوند (بدون migration).
- دادهٔ تست با دو نماد یکتا (`_TD_A_<run>`، `_TD_B_<run>`) در setup و teardown
  پاک می‌شود؛ هیچ `LIKE` یا پاک‌سازی سراسری وجود ندارد.
- هیچ assertion یا شمارشی روی کل جدول انجام نمی‌شود، بنابراین اجرای هم‌زمان با
  دادهٔ دیگران آن را نمی‌شکند.
