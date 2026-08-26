# 1-8 — Kill Switch + Circuit Breaker — فاز ۱

> مالک: مدیر امنیت + مالک ریسک | آزمون فصلی الزامی

## Kill Switch (دستی)
- **محل:** پنل جدا از سیستم اصلی (out-of-band) + کلید فیزیکی/توکن
- **اثر:** قطع فوری تمام `send_order` + لغو سفارش‌های باز
- **مالک:** تنها مالک ریسک می‌تواند فعال/احیاء کند (حتی مدیرعامل بدون او نمی‌تواند)
- **احیاء:** نیاز به امضای دوباره + بررسی لاگ

## Circuit Breaker (خودکار)
- زیان روزانه >۵٪ → توقف خودکار تا فردا ۹ صبح
- خطای BrsApi >۱۰ در ۵m → توقف سیگنال
- مغایرت دفتر >۱٪ → مسدود + هشدار

## تست
- تست فصلی: فعال‌سازی واقعی + اندازه‌گیری زمان قطع (<30s) + گزارش

## پیاده‌سازی
```python
# services/kill_switch.py
class KillSwitch:
    def is_killed(self) -> bool: ...
    def kill(self, by: str, reason: str) -> None: ...  # only مالک ریسک
    def revive(self, by: str) -> None: ...
```
Gateway قبل از هر `send_order` چک می‌کند: `if kill_switch.is_killed(): raise Blocked`
