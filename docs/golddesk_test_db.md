# دیتابیس تست GoldDesk (`golddesk_test`)

تست‌های `tests/gold_desk/test_holding_soft_delete.py` و `@pytest.mark.needs_db` فقط روی یک دیتابیس تست ایزوله اجرا می‌شوند. هرگز روی `my_first_db` (دیتابیس برنامه) نوشته نمی‌شود.

## شرایط اجرا

- متغیر محیطی `GOLD_TEST_DATABASE_URL` باید ست شده باشد.
- نام دیتابیس باید حاوی «test» باشد (مثال: `golddesk_test`).
- اگر آدرس برابر `settings.database_url_async` باشد، تست skip می‌شود.
- اگر `GOLD_TEST_DATABASE_URL` ست نشده باشد، ماژول با پیام روشن skip می‌شود.

## راه ۱: ساخت با psql

```bash
# به دیتابیس postgres وصل شو و دیتابیس تست بساز
psql -U postgres -c "CREATE DATABASE golddesk_test;"

# در یک ترمینال دیگر متغیر را فقط برای همین session ست کن (هیچ credential در فایل ثبت نشود)
$env:GOLD_TEST_DATABASE_URL = "postgresql+asyncpg://USER:PASSWORD@localhost:5432/golddesk_test"

# تست را اجرا کن
python -m pytest tests/gold_desk/test_holding_soft_delete.py -q -p no:cacheprovider
```

> «USER» و «PASSWORD» placeholder هستند؛ هرگز مقدار واقعی را در این مستند یا در کد ثبت نکن.

## راه ۲: ساخت با docker exec

```bash
# نام کانتینر postgres را پیدا کن
docker ps --filter name=postgres --format "{{.Names}}"

# داخل کانتینر دیتابیس بساز
docker exec -i <POSTGRES_CONTAINER> psql -U postgres -c "CREATE DATABASE golddesk_test;"

# متغیر را برای همین shell ست کن (فقط این session)
$env:GOLD_TEST_DATABASE_URL = "postgresql+asyncpg://USER:PASSWORD@localhost:5432/golddesk_test"

python -m pytest tests/gold_desk/test_holding_soft_delete.py -q -p no:cacheprovider
```

## نوشتهNormalization

کد تست `postgresql://` و `postgres://` را به `postgresql+asyncpg://` تبدیل می‌کند تا با درایور asyncpg هم‌خوانی داشته باشد.

## اگر دیتابیس در دسترس نباشد

تست با پیام «اجرا نشد» skip می‌شود و هیچ Rowی در دیتابیس برنامه نوشته نمی‌شود.

## preserving ایزوله‌سازی

تنظیمات `pytestmark = pytest.mark.needs_db` در `tests/conftest.py` هر تستی که به دیتابیس نیاز دارد را skip می‌کند وقتی PostgreSQL قابلRSI نیست.
