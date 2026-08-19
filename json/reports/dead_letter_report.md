# 📊 گزارش صف Dead-Letter (job:dead)

- **تاریخ تولید:** 2026-08-10T15:20:26.211699+00:00
- **تعداد کل پیام‌ها:** 5
- **پیام‌های malformed:** 0

## 📋 توزیع job_name ها

| job_name | تعداد |
|----------|-------|
| `SyncCodalJob` | 2 |
| `SyncQuotesJob` | 2 |
| `NewsFetchJob` | 1 |

## 🐛 دسته‌بندی خطاها

| دسته | تعداد |
|------|-------|
| db_error | 2 |
| timeout | 2 |
| parse_error | 1 |

## 🔁 خطاهای خام پرتکرار (top)

| خطا | تعداد |
|-----|-------|
| TimeoutError: timed out waiting for codal.ir after 30s | 2 |
| DBError: SQLAlchemy OperationalError: connection refused to postgres at localhost:5432 | 1 |
| DBError: psycopg2.OperationalError: server closed the connection unexpectedly | 1 |
| JSONDecodeError: Expecting value: json decode failed at line 1 column 1 | 1 |

## 🔄 پیام‌های تکراری (job_id مشترک)

| job_name | job_id | تعداد کپی |
|----------|--------|-----------|
| `SyncCodalJob` | `sync-c-20260810-003` | 2 |

**تعداد پیام‌های تکراری:** 1
