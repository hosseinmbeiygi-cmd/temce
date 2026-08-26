# 1-1 — سند واسط Broker (مستقل از BrsApi) + PoC Paper — فاز ۱

> مالک: تیم Trading + حقوقی | تأیید: مالک ریسک | پیش‌نیاز حقوقی قبل از هر ارسال واقعی

## ۱. اصل معماری (ص۱ سند)
> «اجرای واقعی باید از طریق Adapter Broker مستقل و پس از کنترل‌های ریسک انجام شود» — BrsApi فقط داده.

## ۲. قرارداد واسط (Broker Port)

```python
class BrokerAdapter(Protocol):
    async def send_order(self, proposal: ProposalOrder, idempotency_key: str) -> BrokerResult: ...
    async def cancel_order(self, broker_order_id: str, idempotency_key: str) -> BrokerResult: ...
    async def get_order(self, broker_order_id: str) -> OrderStatus: ...
    async def get_positions(self) -> list[Position]: ...
```

- **پروتکل:** REST (فعلاً Paper) — آماده برای FIX بعداً
- **احراز:** توکن کارگزاری در Vault (نه .env)، چرخش ۹۰ روزه
- **Idempotency:** هر درخواست با `idempotency_key = sha256(proposal.id)` — ارسال دوباره بی‌اثر، پاسخ قبلی برگردانده می‌شود
- **حالات:** `accepted | rejected | partial | filled | cancelled | failed` — هر تغییر در `order_audit` ثبت append-only
- **بازیابی:** `get_order` برای جبران قطعی شبکه (poll تا `filled`)

## ۳. PoC Paper (بدون پول واقعی)

پیاده‌سازی: `services/broker/paper_broker.py` — دفتر داخلی در `paper_positions/paper_orders`

- ۱۰ سفارش paper (۵ option، ۳ future، ۲ certificate) با `ProposalOrder` واقعی از Risk
- شبیه‌سازی fill با تأخیر ۱s + کارمزد واقعی از جدول 1-5
- تست: `pytest tests/unit/broker/test_paper_broker.py` — ۱۰ سفارش بدون bypass

## ۴. تفکیک حقوقی
- قرارداد کارگزاری جداگانه (مجوز سازمان بورس) — تیم حقوقی تا هفته ۳ تأیید کتبی می‌دهد
- داده BrsApi هرگز برای ارسال سفارش استفاده نمی‌شود (تست نفوذ: فراخوانی مستقیم Broker بدون Approval → 403)

## ۵. معیار پذیرش
- سند واسط امضا + PoC ۱۰ سفارش paper + لاگ audit کامل + تأیید حقوقی
