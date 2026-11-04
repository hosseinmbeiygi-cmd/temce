# ۳۲ — DB-02 baseline: مرحلهٔ ۲ متوقف شد (ویرایش هم‌زمان عامل دیگر) — ۳۰ اکتبر ۲۰۲۶

**وضعیت مأموریت: BLOCKED** — طبق قاعدهٔ «دو snapshot با ۳۰ ثانیه فاصله / تغییر فایل‌ها توسط عامل دیگر»،
پس از تأیید مرحلهٔ ۱، شواهد نشان می‌دهد عامل هم‌زمان **همان مسیر DB-02 را در حال پیاده‌سازی** است.
هیچ فایلی ویرایش، stage، commit، reset، stash یا clean نشد؛ هیچ migration/تستی اجرا نشد.

## ۱) شواهد تغییر هم‌زمان

| مورد | مقدار |
|---|---|
| HEAD | `095cc98f` (بدون تغییر در بازه) |
| گزارش مرحلهٔ ۱ | mtime `2026-10-30T01:50:40` |
| `migrations/versions/0005_add_performance_indexes.py` | mtime `2026-10-30T02:31:14` — **پس از** ثبت مرحلهٔ ۱ |
| `migrations/versions/0004b_core_baseline.py` | mtime `2026-10-30T03:40:47` — **جدید و untracked** |
| snapshot مرحلهٔ ۱ | ۳۵۶ ورودی `git status` |
| snapshot شروع مرحلهٔ ۲ | ۴۱۹ ورودی (تفاوت فقط فایل‌های موقت خودِ بررسی در بازهٔ ۳۰ثانیه‌ای نبود؛ تفاوت اصلی بین دو مرحله است) |

`git status` مسیر migrations:

```
 M migrations/versions/0005_add_performance_indexes.py
 M migrations/versions/0006_add_missing_updated_at.py
 M migrations/versions/0011_add_price_volume_columns.py
 M migrations/versions/0012_saved_filters.py
 M migrations/versions/0099_signal_arch_align.py
?? migrations/versions/0004b_core_baseline.py
?? migrations/versions/0118_core_tables_backfill.py
?? migrations/versions/0119_service_private_tables.py
```

diff فایل ۰۰۰۵ (تنها تغییر مشاهده‌شده در آن):

```diff
 revision = "0005_add_performance_indexes"
-down_revision = "0004_ml_symbol_results"
+down_revision = "0004b_core_baseline"
```

## ۲) محتوای baseline جدید (فقط خوانده شد، تأیید/اجرا نشد)

`0004b_core_baseline.py` (۳۵٬۰۴۷ بایت، untracked):

- `revision = "0004b_core_baseline"`, `down_revision = "0004_ml_symbol_results"` ⇒ دقیقاً بین 0004 و 0005.
- **۳۴ بلوک `CREATE TABLE IF NOT EXISTS`**: ۸ جدول هسته (`users, instruments, trades, quotes,
  news_articles, signals, alerts, ml_model_versions`) + **۲۵ جدول `brsapi_*`** + `dual_date_columns`.
- **۷۶ بلوک `CREATE INDEX`**.
- `downgrade()` خالی (no-op) با دلیل در docstring: «DBهای ≥0005 هرگز این revision را اجرا نمی‌کنند».
- در docstring صریح آمده که ستون‌های MFA کاربر (`totp_*`, `mfa_method`, `telegram_chat_id`) عمداً حذف شده‌اند
  تا 0022/0023/0024 بدون guard آن‌ها را اضافه کنند؛ و brsapi‌ها شکل «پیش از 0016» دارند.
- فایل‌های 0006/0011/0012/0099 هم تغییر کرده‌اند (ماهیت تغییرات بررسی نشد؛ برای مرحلهٔ ۳ لازم است).

این طرح با گزینهٔ A درخواستی هم‌راستاست، اما **بدون اجرا و بدون تست تأیید نشده** است.

## ۳) چرا BLOCKED (و نه ادامه)

- قاعدهٔ مأموریت صریح است: اگر فایل‌ها هم‌زمان توسط عامل دیگری تغییر می‌کنند، توقف و گزارش BLOCKED.
- درخت فعلی ناپایدار است (۵ فایل migration تغییرکرده + ۳ فایل untracked)؛ نوشتن baseline دوم یا تست‌های
  drift روی این درخت می‌تواند با کار هم‌زمان تداخل/دوباره‌کاری ایجاد کند.
- اجرای `alembic upgrade head` یا تست‌ها در این وضعیت، نتیجه‌ای قابل‌انتساب به طرح من نمی‌دهد.

## ۴) کارهای باقی‌ماندهٔ من پس از رفع تعارض

1. بازبینی مستقل baseline هم‌زمان (بدون ویرایش): تک‌head، پوشش ۱۸ جدول مرحلهٔ ۱، سازگاری DDL با
   0118/درخت orphan/ORM، عدم بازنویسی ستون‌های دیرتر اضافه‌شده، no-op بودن downgrade.
2. تست‌های ساختاری درخواستی (تک‌head؛ «هر جدول ۱۸گانه قبل از اولین مصرف‌کننده ساخته شود»؛ drift با
   0118/ORM/orphan؛ امکان `--sql` تا 0005).
3. پیشنهاد جداگانه (بدون ویرایش) برای 0007 و 0026 در حالت offline (بخش جدا در گزارش نهایی).
4. در صورت اختلاف، ارائهٔ diff جایگزین — نه نوشتن هم‌زمان.

## ۵) وضعیت

| مورد | وضعیت |
|---|---|
| مرحلهٔ ۱ | **PASS** (تأییدشده) |
| مرحلهٔ ۲ طراحی/انتشار diff | **BLOCKED** (ویرایش هم‌زمان migrationها) |
| DB-02 | **FAIL** (رفع‌نشده/تأییدنشده) |
| baseline هم‌زمان `0004b_core_baseline` | **PARTIAL** — محتوا وجود دارد، اجرا/تست نشده |
| 0007/0026 offline | **BLOCKED** (پیشنهاد جدا، بدون ویرایش) |
