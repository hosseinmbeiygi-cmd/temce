# core/ — قراردادهای مشترک

## `dbcompat.py` — سه دام تکرارشونده پایگاه داده

الگوی اجباری برای کد جدید که با Postgres (asyncpg) کار می‌کند. مستند
شده از باگ‌های واقعی جلسه ۲۰۲۶-۰۹-۱۹ (`docs/SESSION_REPORT_2026-09-19.md` §6).

### ۱. PK پلی‌مورف — `as_bigint_id` / `as_text_id`

جدول‌های هم‌خانواده idهای ناهمگون دارند: `symbols.id` = BIGINT،
`funds.id` = VARCHAR، ستون‌های پلی‌مورف مثل `news_tag_symbol_map.resolved_id` = TEXT.

```python
from core.dbcompat import as_bigint_id, as_text_id

# asyncpg برای هر ستون type پایتون native می‌خواهد — SQL-side CAST کافی نیست:
{"i": as_bigint_id(raw_id)}        # ستون BIGINT (int پایتونی، نه str)
{"i": as_text_id(raw_id)}          # ستون TEXT/VARCHAR (str)
```

`as_bigint_id` برای ورودی غیرعددی `ValueError` می‌دهد → در endpoint به 422
نگاشت کنید، نه 500.

JOIN پلی‌مورف به BIGINT هم باید TEXT-cast باشد:
`LEFT JOIN symbols s ON CAST(s.id AS TEXT) = m.resolved_id`

### ۲. datetime ناوی — `naive_utc`

بیشتر ستون‌های زمانی اسکیما `timestamp without time zone`اند (UTC به‌صورت
قراردادی). asyncpg پارامتر aware را به ستون naive نمی‌دهد:

```python
from core.dbcompat import naive_utc

{"from": naive_utc(date_from)}     # در مرز repo/service، قبل از execute
```

نکته مشابه: برای مقدار «الان» روی ستون‌های naive از `core.time.utc_now_naive()`
استفاده کنید نه `datetime.utcnow()` (که منسوخ است و از ساعت سرور پیروی می‌کند).

### ۳. کامیت بعد از پاسخ — `commit_now`

`core.database.get_session` در teardown **بعد از ارسال پاسخ** کامیت می‌کند.
هر mutation که کلاینت انتظار دارد در درخواستِ بعدی‌اش ببیند باید قبل از
پاسخ durable باشد:

```python
from core.dbcompat import commit_now

await commit_now(session)          # قبل از return در handlerهای mutation
```

## وضعیت مهاجرت

| لایه | وضعیت |
|------|-------|
| news (mapper، دو ریپو، admin endpoints) | ✅ delegate شده |
| fund services (۷ سرویس، ۳۴ commit) | عمداً باقی است — `commit()`های خودشان تراکنش‌های چند مرحله‌ای درست‌کارند و اپ پشت FLG/داخلی است؛ مهاجرت باید تست‌به‌تست با تمرکز روی مسیرهای API-محور انجام شود |
| `datetime.utcnow` در fund services (۶ مورد) | کاندیدای بعدی: جایگزینی با `core.time.utc_now_naive` |
