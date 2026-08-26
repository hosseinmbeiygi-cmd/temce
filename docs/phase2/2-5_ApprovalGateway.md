# 2-5 — Approval Gateway MVP — فاز ۲

> مالک: مالک محصول/UX | تأیید: مالک ریسک

## فلو
```
Proposal (pending) → Gateway UI → [تأیید | رد | انقضا] → Broker / آرشیو
```

## UI
- کارت: استراتژی، legs، قیمت، هزینه (ناخالص/خالص)، ریسک (max_loss/margin/var)، سناریوها (5 نقطه pnl)، TTL شمارش معکوس
- دکمه‌ها: تأیید (MFA) / رد (دلیل) / انصراف
- پس از تأیید: نمایش `broker_order_id` + وضعیت

## API
- `POST /proposals/{id}/approve` (MFA + RBAC)
- `POST /proposals/{id}/reject`
- `GET /proposals?status=pending`

## لاگ
- هر تصمیم: `who, when, why, calc_version` در `proposal_audit` append-only

## تست کاربر
- 5 کاربر → نرخ خطای تأیید <5%
