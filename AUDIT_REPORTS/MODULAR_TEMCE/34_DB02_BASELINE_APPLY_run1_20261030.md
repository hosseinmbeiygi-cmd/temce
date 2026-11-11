# ۳۴ — DB-02: اجرای baseline و اثبات پذیرش — run1، ۳۰ اکتبر ۲۰۲۶

**وضعیت DB-02:** **FIXED** (روی `localhost:15432/tse_quant`) — تغییرات در درخت کاری است و
هنوز commit نشده.
**دامنه:** فقط دیتابیس audit؛ ۵۴۳۲/۶۳۷۹ دست نخورد؛ `.env` تغییر نکرد؛ رمزها redact شده‌اند.

---

## ۱) تغییرات اعمال‌شده

| فایل | تغییر | چرا |
|---|---|---|
| `migrations/versions/0004b_core_baseline.py` | **جدید** — ۳۴ جدول + ۷۶ ایندکس با `IF NOT EXISTS` | ۸ جدول هسته از DDL فریز ۰۱۱۸ (منهای ۶ ستون users)، ۲۵ جدول `brsapi_*` از درخت یتیم، و `dual_date_columns` |
| `0005_add_performance_indexes.py` | `down_revision = "0004b_core_baseline"` | تنها ویرایش مجاز در فایل موجود |
| `0006_add_missing_updated_at.py` | `contextlib.suppress` → `ALTER TABLE IF EXISTS … ADD COLUMN IF NOT EXISTS` | suppress روی جدول ناموجود، تراکنش Postgres را abort می‌کرد |
| `0011_add_price_volume_columns.py` | `NULLIF(col::text, '')::…` | cast رشتهٔ خالی به double روی DB تازه می‌شکست |
| `0012_saved_filters.py` | حذف `create_index` تکراری `ix_saved_filters_user_id` | `index=True` خودش همان ایندکس را می‌سازد |
| `0099_signal_arch_align.py` | suppress → `ADD COLUMN IF NOT EXISTS` | همان الگوی ۰۰۰۶ |
| `migrations/env.py` | (۱) تضمین `alembic_version VARCHAR(255)`؛ (۲) `commit()` صریح | شناسه‌های >۳۲ کاراکتر جا نمی‌شدند؛ بدون commit کل اجرا rollback می‌شد |

**انحراف از طراحی ۳۳:** علاوه بر ۰۰۰۵، پنج فایل دیگر حداقلی اصلاح شد و baseline به کل
۲۵ جدول یتیم گسترش یافت. دلیل: آزمون پذیرش، پنج بلاکر دیگرِ همان کلاس را آشکار کرد
(هر کدام در لاگ خام با exit code ثبت شده است).

---

## ۲) نتیجهٔ آزمون پذیرش

| مورد | نتیجه |
|---|---|
| `alembic upgrade head` روی DB خالی | **exit 0**؛ ۹۰ migration از `0001` تا `0119` |
| `alembic current` | `0119_service_private_tables (head)` — exit 0 |
| اجرای دوبارهٔ `upgrade head` | exit 0 و **۰** migration (idempotent) |
| `alembic_version` | موجود؛ مقدار `0119_service_private_tables` |
| جدول‌ها | **۲۰۳** جدول در `public` |
| `brsapi_*` | **۲۷** جدول |
| `dual_date_columns` | **۷۴** ردیف (از ۰۰۲۵) |
| ستون‌های افزوده‌شده | `users.totp_secret/totp_enabled/totp_confirmed_at/mfa_method/telegram_chat_id`، `brsapi_codal_announcements.audit_status/content_hash`، `brsapi_sync_log.created_at/outcome`، `brsapi_raw_payloads.receive_time/checksum_sha256` — همه حاضر |
| `tests/unit/test_core_tables_migration.py` | **۳ passed** |
| ۷ تست gold که قبلاً محیطی‌بلوکه بودند | **۵۶ passed / ۰ failed** (قبلاً ۴۹ passed / ۷ failed) |

---

## ۳) یافتهٔ مهم حین اجرا: «موفقیت کاذب»

در تلاش نهم، `alembic upgrade head` با **exit 0** تمام شد اما دیتابیس خالی ماند.
علت: `env.py` هیچ‌وقت commit نمی‌کرد؛ SQLAlchemy 2.0 در بستن اتصال rollback می‌زند و
`context.begin_transaction()` وقتی تراکنش باز است no-op می‌شود. با `await connection.commit()`
(و `connection.commit()` در مسیر SQLite) این بلاکر بسته شد. **درس:** exit 0 بدون
بازبینی schema، اثبات نیست.

---

## ۴) قیدهای باقی‌مانده (خارج از این مأموریت)

- حالت آفلاین `alembic upgrade head --sql`: ۰۰۰۷ (`sa.inspect`) و ۰۰۲۶ (pg_indexes) هنوز
  introspection دارند ⇒ نیازمند approval جدا.
- `README.md:362` و `migrations/README.md` هنوز مسیر DB خالی را با baseline جدید توضیح
  نمی‌دهند.
- درخت `brsapi/migrations` هنوز خارج از زنجیره است؛ baseline آن را فریز کرده اما منبع
  رسمی نشده.
- تغییرات commit نشده‌اند؛ درخت مشترک است و باید با صاحب پروژه هماهنگ شود.

---

## ۵) وضعیت

| مورد | وضعیت |
|---|---|
| DB-02 | **FIXED** (روی audit DB؛ uncommitted) |
| پذیرش `upgrade head` | **PASS** (exit 0 + schema) |
| Idempotency | **PASS** (اجرای دوم: ۰ migration) |
| Drift test | **PASS** |
| تست‌های gold | **PASS** (۵۶/۵۶) |
| ۰۰۰۷/۰۰۲۶ آفلاین | **BLOCKED** |
| مستندات DB خالی | **BLOCKED** |

خروجی خام: `AUDIT_REPORTS/MODULAR_TEMCE/evidence/DB02_BASELINE_APPLY_20261030.log`
