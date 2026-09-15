# 🗃️ migrations/ — لایه مهاجرت دیتابیس (Alembic)

> مدیریت نسخه‌بندی اسکیمای دیتابیس با **Alembic**. هر فایل یک ریویژن است و زنجیره‌ای خطی از `<base>` تا `head` را تشکیل می‌دهد. اجرا: `alembic upgrade head`

---

## 📑 فهرست مطالب

- [نقش و جایگاه](#نقش-و-جایگاه)
- [زنجیره ریویژن‌ها](#زنجیره-ریویژنها)
- [ساختار فایل‌ها](#ساختار-فایلها)
- [نحوه اجرا](#نحوه-اجرا)
- [قوانین و Convention ها](#قوانین-و-convention-ها)
- [اشکالات رفع‌شده](#اشکالات-رفعشده)

---

## نقش و جایگاه

```
models/ (SQLAlchemy)  ──►  migrations/ (Alembic)  ──►  PostgreSQL
   ساختار ORM                 نسخه‌بندی DDL              اسکیمای واقعی
```

- `models/` توصیف ORM است؛ **منبع حقیقت** اسکیمای دیتابیس `migrations/` است.
- هر ریویژن باید `upgrade()` و `downgrade()` داشته باشد (قابل بازگشت).
- در production هرگز از `create_all()` استفاده نمی‌شود — فقط `alembic upgrade head`.

---

## زنجیره ریویژن‌ها

زنجیره کامل (خطی، تک‌سر):

```
<base>
  └─ 0001_initial_schema ................ ۱۹ جدول اولیه BrsApi (symbols, snapshots, ...)
      └─ 0002_codal_financial_statements . صورت‌های مالی کدال
          └─ 0003_codal_analysis_models .. مدل‌های تحلیلی کدال (Star Schema, SCD2)
              └─ 0004_ml_symbol_results .. نتایج ML هر نماد
                  └─ 0005_add_performance_indexes ..... ایندکس‌های کارایی
                      └─ 0006_add_missing_updated_at .. افزودن updated_at به ۵۲ جدول
                          └─ 0007_signal_accuracy ...... جدول دقت سیگنال
                              └─ 0008_screener_tables .. جداول غربالگری ۱۱۰ ستونه
                                  └─ 0009_rechain_stub ──► (ترمیم زنجیره)
                                      └─ 0010_rechain_stub ──► (ترمیم زنجیره)
                                          └─ 0011_add_price_volume_columns ... ۸ ستون قیمت/حجم
                                              └─ 0012_saved_filters
                                                  └─ 0013_decision_engine_tables
                                                      └─ 0014_queue_analysis_results
                                                          └─ 0015_funds_table
                                                              └─ 0016_add_codal_audit_status
                                                                  └─ 0017_add_sync_log_created_at
                                                                      └─ 0018_add_codal_content_hash
                                                                          └─ 0019_codal_attachments
                                                                              └─ 0020_brsapi_snapshots_unique
                                                                                   (head)
```

### کنترل زنجیره

```bash
alembic history   # کل زنجیره را نشان می‌دهد
alembic heads     # سرهای زنجیره (باید فقط یک head باشد)
alembic current   # ریویژن فعلی دیتابیس
alembic upgrade head
```

> ⚠️ اگر `alembic history` خطای «Revision X referenced from ... is not present» بدهد یعنی زنجیره شکسته است و `upgrade head` کار نخواهد کرد.

---

## ساختار فایل‌ها

هر فایل در `migrations/versions/` الگوی استاندارد Alembic دارد:

```python
revision: str = "0015"
down_revision: str | None = "0014"
branch_labels = None
depends_on = None

def upgrade() -> None: ...
def downgrade() -> None: ...
```

- **`revision`** — شناسه یکتای ریویژن (مهم: باید دقیقاً با `down_revision` فایل بعدی یکی باشد).
- **`down_revision`** — ریویژن والد؛ `None` فقط برای اولین فایل.
- **`env.py`** — پیکربندی Alembic؛ مسیر پروژه را به `sys.path` اضافه می‌کند و بسته به نوع دیتابیس (sqlite/async postgres) موتور مناسب را می‌سازد.

---

## نحوه اجرا

```bash
# توسعه محلی (sqlite یا postgres با DATABASE_URL در .env)
alembic upgrade head

# CI — fund-service.yml و decision-engine.yml
alembic upgrade head --raiseerr

# ساخت مهاجرت جدید (بعد از تغییر مدل‌ها)
alembic revision --autogenerate -m "describe change"
```

---

## قوانین و Convention ها

1. **یک سر (head)**: زنجیره باید خطی و تک‌سر باشد — `alembic heads` باید فقط یک ریویژن برگرداند.
2. **هماهنگی revision/down_revision**: `revision` هر فایل باید دقیقاً برابر `down_revision` فایل بعدی باشد.
3. **بازگشت‌پذیری**: همه مهاجرت‌ها `downgrade()` دارند (ایندکس‌ها قبل از جدول حذف می‌شوند).
4. **ایندکس‌های مشخص**: هر جدول time-series با `create_hypertable()` (TimescaleDB) و ایندکس‌های کوئری‌های پرکاربرد ساخته می‌شود.
5. **ایمنی idempotent**: در مهاجرت‌های الحاقی از `IF NOT EXISTS`/`contextlib.suppress` استفاده می‌شود تا روی دیتابیس‌های موجود هم اجرا شوند.
6. **نوع ستون‌ها**: `BigInteger` برای حجم/تعداد، `Numeric` برای قیمت (دقت اعشار)، `DateTime(timezone=True)` برای تایم‌استمپ‌ها.

---

## اشکالات رفع‌شده

1. **🔴 شکستگی زنجیره (بحرانی)** — ریویژن `0011` به `down_revision="0010"` اشاره می‌کرد اما هیچ فایل `0010` وجود نداشت → `alembic history`/`heads`/`upgrade head` همگی کرش می‌کردند. با دو مهاجرت no-op (`0009_rechain_stub`, `0010_rechain_stub`) زنجیره ترمیم شد: `0008 → 0009 → 0010 → 0011`.
2. **🔴 down_revision ناهماهنگ** — `0019` به `"0018_add_codal_content_hash"` اشاره می‌کرد در حالی که `revision` واقعی فایل 0018 فقط `"0018"` است (و `0020` هم به `"0019_codal_attachments"` به‌جای `"0019"`) → اصلاح شد تا زنجیره کامل در `alembic history` نمایش داده شود.
3. **تأیید نهایی** — `alembic history` حالا کل زنجیره را سالم نشان می‌دهد و `alembic heads` دقیقاً یک سر (`0020_brsapi_snapshots_unique`) برمی‌گرداند.
