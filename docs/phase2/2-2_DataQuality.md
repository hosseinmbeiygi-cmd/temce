# 2-2 — Data Quality + مانیتورینگ — فاز ۲

> مالک: DevOps + مالک داده

## چک‌لیست کیفیت
- null_check: قیمت/حجم تهی نباشد
- checksum: تطابق SHA256
- staleness: `now - fetched_at > 5m` در بازار → fail
- price_limit: خارج ±۱۹% → flag

## مانیتورینگ
- Prometheus: `brsapi_requests_total{status}`, `data_staleness_seconds`, `raw_store_lag`
- Grafana: داشبورد 3 پنل (کهنگی، 5xx، تعداد قرارداد/روز)
- هشدار: کهنگی>30m یا 5xx>10/5m → Slack

## معیار
- داشبورد زنده + هشدار در <1m
