# 1-2 — قرارداد Risk Engine (۱۲ کنترل غیرقابل دور زدن) — فاز ۱

> مالک: مالک ریسک (A) | مجری: معمار + تیم Trading | هر سفارش باید از `RiskEngine.check()` عبور کند

## ۱. فهرست ۱۲ کنترل (ترتیب اجرا = اولویت)

| # | کنترل | آستانه اولیه (قابل تنظیم توسط مالک ریسک) | اقدام در fail |
|---|-------|--------------------------------------------|---------------|
| 1 | سقف سرمایه هر سفارش | ≤ ۲٪ پورتفو | reject + لاگ |
| 2 | زیان روزانه تجمیعی | ≤ ۵٪ پورتفو/روز | circuit breaker — توقف کل ارسال تا فردا |
| 3 | اندازه موقعیت (position size) | ≤ ۱۰٪ در یک نماد | reject |
| 4 | نقدشوندگی | حجم ۵روزه < ۱۰× سفارش → thin/illiquid | reject اگر illiquid |
| 5 | کهنگی داده | `now - fetched_at > 5m` → stale → reject | reject |
| 6 | تمرکز (concentration) | ≤ ۲۵٪ در یک صنعت | reject |
| 7 | وجه تضمین (margin) | کافی بودن موجودی + مارجین نگهداری | reject |
| 8 | محدودیت قیمت (price limit ±۱۹٪) | قیمت پیشنهادی خارج بازه → reject | reject |
| 9 | اعتبار نماد (allowlist) | فقط نمادهای allowlist | reject |
| 10 | TTL سفارش | `now > expires_at` → expired | reject |
| 11 | تطابق دفتر (position vs proposal) | مغایرت > ۱٪ → هشدار | هشدار + مسدود |
| 12 | Idempotency تکراری | کلید تکراری → بازگردانی نتیجه قبلی | replay بدون ارسال جدید |

> تست نفوذ: فراخوانی `BrokerAdapter.send_order` بدون عبور از `RiskEngine.check()` باید 403 شود (Gateway اجباری).

## ۲. واسط

```python
@dataclass
class RiskResult:
    passed: bool
    failed_checks: list[str]
    warnings: list[str]

class RiskEngine:
    def check(self, proposal: ProposalOrder, portfolio: Portfolio) -> RiskResult: ...
    def check_with_bypass_attempt(self, ...) -> Never:  # وجود ندارد — bypass غیرممکن
```

## ۳. معیار پذیرش
- ۱۲ کنترل پیاده + تست هر کنترل با ۲ سناریو (pass/fail)
- تست bypass: تلاش مستقیم به Broker → 403
- لاگ هر عبور/رد در `risk_audit` (append-only)
