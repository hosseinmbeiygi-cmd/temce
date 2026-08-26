# 1-4 — قانون انتخاب قیمت برای IV — فاز ۱

> مالک: سرپرست پژوهش

## قانون (به ترتیب اولویت)
1. **Mid** = `(Bid+Ask)/2` اگر `Ask-Bid >0`, `spread = (Ask-Bid)/Mid < 2%` و `age < 60s` → flag `fresh`
2. **Bid/Ask** اگر Mid نامعتبر ولی `Bid>0` یا `Ask>0` و `age < 60s` → flag `thin` (استفاده با احتیاط)
3. **Last** فقط اگر `age < 5m` و `spread` قبلی نامعتبر — flag `stale` و IV با هشدار
4. در غیر این صورت → **نامعتبر** — IV محاسبه نمی‌شود، لاگ `price_unavailable`

## پیاده‌سازی
```python
def select_price_for_iv(bid, ask, last, fetched_at) -> (price, flag):
    age = now - fetched_at
    mid = (bid+ask)/2 if bid and ask else None
    spread = (ask-bid)/mid if mid else None
    if mid and spread < 0.02 and age < 60:
        return mid, "fresh"
    if (bid or ask) and age < 60:
        return bid or ask, "thin"
    if last and age < 300:
        return last, "stale"
    return None, "unavailable"
```

## تست
- ۵ سناریو: Mid معتبر، spread باز، کهنه ۱۰m، فقط Last، هیچکدام
