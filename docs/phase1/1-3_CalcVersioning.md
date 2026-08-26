# 1-3 — نسخه‌گذاری محاسبات — فاز ۱

> هر Greeks/IV/بک‌تست با `calc_version` قابل بازتولید

## فرمت
```json
{
  "git_sha": "a1b2c3d",
  "input_hash": "sha256(params+inputs)",
  "param_version": "pricing.v2",
  "timestamp": "2026-09-01T10:00:00+03:30"
}
```

- `git_sha`: کامیت کد محاسبه
- `input_hash`: هش ورودی‌های مؤثر (S,K,T,r,sigma,قیمت انتخابی)
- `param_version`: نسخه جدول پارامتر (مثلاً `fees.v1`, `risk_free.v3`)
- ذخیره در هر ردیف `greeks_calc`, `iv_calc`, `backtest_run`

## تست تکرارپذیری
- ۱۰ مورد BS با ورودی ثابت → `input_hash` یکسان → خروجی یکسان در دو اجرا
- تغییر `r` از 0.15 به 0.16 → `input_hash` متفاوت → نسخه جدید
