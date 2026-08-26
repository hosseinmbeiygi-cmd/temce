# 0-2 — قرارداد مخزن خام (Raw Store) — فاز صفر

> مالک: مالک داده | وابسته به: 0-1 RACI | خروجی: DDL + سیاست نگهداری

## ۱. هدف
هر پاسخ BrsApi/TSETMC/IME به‌صورت **تغییرناپذیر (immutable)** با تمام فراداده لازم ذخیره شود تا هر رکورد تحلیلی تا «پاسخ خام + منبع + زمان» قابل ردیابی باشد (معیار پذیرش فاز صفر سند).

## ۲. DDL — `raw_store` (PostgreSQL + Timescale)

```sql
CREATE TABLE raw_store (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT NOT NULL,          -- 'brsapi.option' | 'brsapi.ime_option' | 'brsapi.ime_future' | 'tsetmc.direct' | ...
    endpoint        TEXT NOT NULL,          -- '/Tsetmc/Option.php'
    http_status     INT  NOT NULL,
    duration_ms     INT  NOT NULL,
    checksum_sha256 TEXT NOT NULL,          -- SHA256(payload)
    schema_version  TEXT NOT NULL,          -- 'ime_option.v1' — از BrsApi page
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),  -- زمان دریافت (سرور)
    market_time     TIMESTAMPTZ,            -- زمان بازار در payload (در صورت وجود)
    params          JSONB,                  -- پارامترهای درخواست (l18, market_type...)
    payload         JSONB NOT NULL,         -- پاسخ خام کامل
    payload_bytes   INT  NOT NULL
);
CREATE INDEX ON raw_store (source, ingested_at DESC);
CREATE INDEX ON raw_store (endpoint, ingested_at DESC);
CREATE INDEX ON raw_store USING GIN (params);
SELECT create_hypertable('raw_store','ingested_at', chunk_time_interval => INTERVAL '7 days');
```

> در `brsapi/repositories/base.py` فعلی فقط `raw_json` در جدول snapshot نگهداری می‌شود — این جدول جدا و append-only است.

## ۳. سیاست نگهداری (Retention)

| داده | نگهداری گرم | آرشیو سرد | حذف |
|------|-------------|-----------|-----|
| `raw_store` | ۹۰ روز (hypertable) | فشرده Timescale تا ۷ سال (الزام ممیزی) | پس از ۷ سال با تأیید مالک داده |
| `market_snapshots` (پس از Normalizer) | ۲ سال | آرشیو Parquet | — |
| لاگ HTTP 4xx/5xx | ۱ سال | — | — |

## ۴. قاعده checksum و هشدار schema
- هر پاسخ: `checksum = sha256(canonical_json(payload))` محاسبه و ذخیره
- در هر sync: اگر `schema_version` تغییر کرد → هشدار `DataQuality` + مسدودسازی ورود به لایه تحلیل تا تأیید مالک داده (جلوگیری از «تغییر بی‌هشدار» ص۲)
- تست CI: فایل نمونه هر endpoint با schema فعلی مقایسه می‌شود

## ۵. نمونه ردیابی (معیار پذیرش)
```sql
-- هر snapshot تا raw قابل join
SELECT s.symbol, s.price_last, r.checksum_sha256, r.http_status, r.ingested_at
FROM option_snapshots s
JOIN raw_store r ON r.id = s.raw_store_id
WHERE s.symbol = 'ضخود8012' AND s.fetched_at > now() - interval '1 day';
```
> پذیرش: ۹۹.۹٪ رکوردهای 24h اخیر باید این join را در <1s پاسخ دهند.

## ۶. پیاده‌سازی
- فایل مهاجرت: `migrations/versions/XXXX_create_raw_store.py`
- تغییر `brsapi/services/sync_service.py`: پس از `client.fetch` بلافاصله `INSERT INTO raw_store` و دریافت `id` برای ارجاع در snapshot
