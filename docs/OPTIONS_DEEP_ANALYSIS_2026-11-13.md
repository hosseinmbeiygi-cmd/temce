# تحلیل عمیق و جامع زیرسیستم آپشن — TEMCE

**تولید:** 2026-11-12 22:46 UTC
**منبع:** PostgreSQL زنده + کد منبع + ۱۵ راستی‌آزمایی عددی مستقل

---

## وضعیت یافته‌ها — به‌روزرسانی 2026-11-16 (DOM-08)

> **هشدار:** متن اصلی این سند وضعیت 2026-11-12 را منعکس می‌کند. اکثر یافته‌ها از آن تاریخ بسته شده‌اند.
> برای تصمیم‌گیری، جدول زیر را مرجع قرار دهید نه خلاصهٔ «۳ باگ CRITICAL» بالا.

| ID | شدت | وضعیت | کامیت |
|----|------|--------|-------|
| OF1 | CRITICAL | ✅ بسته | `ace9339f` |
| OF2 | CRITICAL | ✅ بسته | `ace9339f` |
| OF3 | CRITICAL | ✅ بسته | `ace9339f` |
| OF4 | HIGH | ✅ بسته | `2ef8be2a` |
| OF5 | HIGH | ⚠️ باز (مسیر GoldDesk/services/gold اصلاح نشد) | `ace9339f` فقط domain را لمس کرد |
| OF6 | HIGH | ✅ بسته | `d77d663e` |
| OF7 | HIGH | ✅ بسته | `8831b574` |
| OF8–OF12 | MEDIUM | ✅ بسته | `2d34beba` |
| OF13 | MEDIUM | ✅ بسته | `26660f89` |
| OF14 | MEDIUM | ✅ بسته | `5aaa2d12` |
| OF15 | LOW | ✅ بسته | `26660f89` |

**تنها مورد باز:** OF5 در مسیر `src/gold_desk/black76.py` و `services/gold/black76_engine.py`
(ثبت‌شده به‌عنوان DOM-01 در گزارش حسابرسی اصلی)

---

## امتیاز کلی: ۶/۱۰

هسته ریاضی (Black-Scholes, binomial, MC, IV solver) صحیح است. ولی ۳ باگ CRITICAL، ۵ خانواده schema موازی با جداول نرمال‌شده خالی، ناسازگاری day-count، و Max Pain اشتباه در API زنده وجود دارد.

## خلاصه یافته‌ها

| شدت | تعداد |
|------|-------|
| CRITICAL | 3 |
| HIGH | 4 |
| MEDIUM | 5 |
| LOW | 3 |

## ارقام کلیدی DB

| جدول | ردیف |
|------|------|
| brsapi_option_snapshots | 1,281,678 |
| brsapi_ime_options | 136,163 |
| options (legacy) | 3,225 |
| commodity_options | 476 |
| option_contracts (normalized) | 0 |
| option_snapshots (normalized) | 0 |
| gold_option_iv_history | 0 |

- زیر ارزش ذاتی: 26.8٪ از نمونه
- OI صفر: 567,511 رکورد
- Volume صفر: 830,679 رکورد

## راستی‌آزمایی ریاضی

| آزمون | نتیجه |
|-------|-------|
| Put-Call Parity | PASS (residual=2.27e-13) |
| Greeks vs FD | PASS (Δ err=0.021٪) |
| Higher-Order Greeks | PARTIAL (vomma err=9878٪) |
| IV Round-Trip | PASS (max err=3.23e-06) |
| Binomial Convergence | PASS |
| MC vs Closed Form | PASS |
| Black-76 Parity | PASS |
| **Heston Pricing** | **PARTIAL** (BS=122.56, Heston=0.0) |
| Prob. of Touch | PASS |
| **Max Pain Correctness** | **PARTIAL** (domain wrong, service accidental) |
| VaR Units | PASS |
| Margin Engine | PASS |
| Symbol Parser FP | PARTIAL (15.8٪ false positive) |
| **Validators** | **NO_OP** (validate_expiration always True) |
| Day-Count | PARTIAL (θ gap=44.8٪) |

## یافته‌های CRITICAL

1. **OF1 — باگ /predict:** asdict() سپس دسترسی مشخصه → AttributeError → HTTP 500
2. **OF2 — Max Pain اشتباه:** max OI بهجای کمینهسازی payout در API زنده
3. **OF3 — Heston = 0:** heston_price همیشه 0.0 حتی برای پارامتر کلاسیک

## یافته‌های HIGH

4. **OF4 — ۲۶.۸٪ زیر ارزش ذاتی** در داده آپشن زنده
5. **OF5 — day-count ناسازگار:** 365 تقویمی vs 252 معاملاتی (θ gap=۴۴.۸٪)
6. **OF6 — ۵ schema موازی، normalized خالی** — هیچ writer وجود ندارد
7. **OF7 — higher-order Greeks مقیاس نادرست** — vomma/charm

## تست‌ها

- ۴۱۵ تست عبور، ۰ شکست
- ۳۰ فایل تست، ۳۷۷ تابع
- **نبود:** Greeks vs finite-differences، DB test، validate_expiration test

## ادعاهای رد شده

- SABR calibration: وجود ندارد
- Margin engine YAML-configurable: hardcoded
- OPTIONS_MARKET_REPORT اعداد: stale
- Monte Carlo QE: واقعاً Milstein
- "options.py not mounted": حالا mounted است

---
سلب مسئولیت: تحلیل فنی-مهندسی، مشاوره سرمایه‌گذاری نیست.
