# 2-1 — Normalizer + Reference DB — فاز ۲

> مالک: معمار داده | وابسته به: 0-2 Raw Store

## ۱. هدف
هر منبع (5 سرویس IME/TSETMC) پس از ذخیره خام، به مدل مشترک نرمال شود تا لایه Research یک API واحد ببیند.

## ۲. جداول مرجع (Reference DB)

```sql
CREATE TABLE instruments (
  id SERIAL PRIMARY KEY,
  symbol TEXT UNIQUE NOT NULL,
  isin TEXT,
  market TEXT, -- TSE/IME
  asset_class TEXT, -- equity/commodity/certificate
  contract_size INT DEFAULT 1000
);
CREATE TABLE contracts (
  id SERIAL PRIMARY KEY,
  instrument_id INT REFERENCES instruments(id),
  expiry DATE,
  strike NUMERIC,
  option_type TEXT -- call/put/future/physical
);
CREATE TABLE market_snapshots (
  contract_id INT REFERENCES contracts(id),
  ts TIMESTAMPTZ,
  price NUMERIC, volume BIGINT, oi BIGINT,
  bid NUMERIC, ask NUMERIC,
  raw_store_id BIGINT REFERENCES raw_store(id),
  PRIMARY KEY (contract_id, ts)
);
CREATE TABLE orderbook_levels (
  contract_id INT, ts TIMESTAMPTZ, side TEXT, level INT, price NUMERIC, qty BIGINT
);
CREATE TABLE trades (
  contract_id INT, ts TIMESTAMPTZ, price NUMERIC, qty BIGINT, side TEXT
);
```

## ۳. Normalizer

`services/normalizer/base.py` — هر Adapter (`ImeOptionAdapter.normalize(raw) -> NormalizedRecord`) ISIN/واحد/اندازه/سررسید را یکسان می‌کند.

- تست: 20 نماد نمونه (10 اختیار + 5 آتی + 5 گواهی) → ISIN یکسان‌سازی 95%+
