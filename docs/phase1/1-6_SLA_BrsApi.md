# 1-6 — SLA داخلی BrsApi + بافر — فاز ۱

> مالک: مالک داده

## سهمیه (از brsapi/config.py)
- TSETMC: 18 req/min | IME: 12 req/min | سهمیه روزانه 4000 (BrsApiSettings)
- هر ۵ دقیقه در ساعات بازار (cron 300s)

## Runbook
- **retry:** ۳ بار با backoff 1s/2s/4s + jitter 0.5s
- **بافر:** صف DB `brsapi_buffer` — در قطعی، درخواست‌ها بافر و پس از بازیابی replay
- **هشدار کهنگی:** `now - max(fetched_at) > 30m` در ساعات بازار → هشدار Slack/ایمیل + بنر «داده کهنه»
- **Degraded Mode:** نمایش بنر + توقف سیگنال (Risk کنترل ۵)

## معیار
- ۷ روز بدون از دست‌رفتگی + هشدار کهنگی در <1m
