# 3-1 — Allowlist + سقف‌ها — فاز ۳ (اجرای محدود)

> مالک: مالک ریسک (A) | تأیید کتبی الزامی قبل از هر سفارش واقعی

## Allowlist اولیه (۱۰ نماد کم‌حجم، نقدشونده)
```
خودرو, خساپا, شستا, فولاد, فملی, ذوب, وبملت, وتجارت, پالایش, شپنا
```
- خارج allowlist → Risk کنترل ۹ → reject خودکار

## سقف‌ها (قابل تنظیم توسط مالک ریسک، ثبت نسخه‌دار)
| سقف | مقدار اولیه | اعمال |
|-----|-------------|-------|
| هر سفارش | ≤ ۲٪ پورتفو | Risk #1 |
| هر نماد | ≤ ۱۰٪ پورتفو | Risk #3 |
| هر صنعت | ≤ ۲۵٪ | Risk #6 |
| زیان روزانه | ≤ ۵٪ → Circuit Breaker تا فردا | Risk #2 |
| تعداد سفارش/روز | ≤ ۲۰ | کنترل جدید |

## پیاده‌سازی
```sql
CREATE TABLE risk_limits (version TEXT PRIMARY KEY, payload JSONB, approved_by TEXT, approved_at TIMESTAMPTZ);
INSERT INTO risk_limits VALUES ('v1', '{"max_order_pct":0.02, ...}', 'risk_owner', now());
```
- هر Proposal با `risk_limits.version` ثبت می‌شود

## معیار
- تست: سفارش ۳٪ → reject + لاگ `order_size`
