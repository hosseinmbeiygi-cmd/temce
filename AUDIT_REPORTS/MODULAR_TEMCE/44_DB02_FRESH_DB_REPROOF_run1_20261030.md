# ۴۴ — اثبات مجدد DB-02 روی DB کاملاً تازه — ۳۰ اکتبر ۲۰۲۶

**هدف:** فایل `0004b_core_baseline.py` پس از پاک‌سازی W291 بازتولید شد؛ این گزارش
نشان می‌دهد نسخهٔ نهاییِ فایل هنوز روی یک دیتابیس کاملاً خالی به `head` می‌رسد.

**وضعیت:** **PASS**. تغییرات commit نشده‌اند.

---

## ۱) محیط

- DB جدید: `tse_quant_verify` روی همان کانتینر audit (`localhost:15432`)،
  مالک `quant_dev`.
- DB قبلی `tse_quant` دست‌نخورده ماند.
- `.env` تغییر نکرد؛ DSN به‌صورت inline و رمز redact شده.

## ۲) اجرا

```
alembic upgrade head      (روی tse_quant_verify)
  -> exit 0
  -> 90 migration از 0001 تا 0119

alembic current
  -> 0119_service_private_tables (head)

alembic upgrade head      (اجرای دوم)
  -> exit 0
  -> 0 migration (idempotent)
```

## ۳) وضعیت schema

| مورد | مقدار |
|---|---|
| `alembic_version` | `0119_service_private_tables` |
| جدول‌های `public` | **۲۰۳** |
| جدول‌های `brsapi_*` | **۲۷** |
| ردیف‌های `dual_date_columns` | **۷۴** |
| ستون‌های کلیدی افزوده‌شده | **۱۴/۱۴** حاضر: `users.totp_secret/totp_enabled/totp_confirmed_at/mfa_method/telegram_chat_id` (۵)، `brsapi_codal_announcements.audit_status/content_hash` (۲)، `brsapi_sync_log.created_at/outcome` (۲)، `brsapi_raw_payloads.receive_time/market_time/response_latency_ms/schema_version/checksum_sha256` (۵) |

> شمارش اولیهٔ ۹ فقط دامنهٔ کوئری بود (۳ ستون users + ۲ + ۲ + ۲)؛ بررسی مستقیم
> همهٔ ستون‌های `totp*` و پنج ستون v5، حضور ۱۴/۱۴ را تأیید کرد.

## ۴) نکته

DB `tse_quant_verify` عمداً **حذف نشد**؛ حذف دیتابیس یک اقدام مخرب است و نیاز به دستور
صریح مالک دارد. در صورت نیاز، با تأیید می‌توان `DROP DATABASE tse_quant_verify` را اجرا کرد.

## ۵) وضعیت

| مورد | وضعیت |
|---|---|
| `upgrade head` روی DB تازه | **PASS** (exit 0) |
| Idempotency | **PASS** (اجرای دوم: ۰) |
| Schema نهایی | **PASS** (۲۰۳ جدول / ۲۷ brsapi / ۷۴ dual) |
| DB تست | باقی‌مانده (بدون حذف) |
| commit | **BLOCKED** |
