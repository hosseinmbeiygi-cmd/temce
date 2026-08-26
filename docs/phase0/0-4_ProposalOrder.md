# 0-4 — سفارش پیشنهادی (Proposal Order) — فاز صفر

> مالک: معمار نرم‌افزار | تأیید: مالک ریسک | فایل اسکیما: `0-4_ProposalOrder.schema.json`

## ۱. چرخه عمر
```
Signal → Risk (۱۲ کنترل) → Proposal (TTL) → Approval Gateway → Broker (idempotent) → دفتر
         ↓ fail                ↓ expired/rejected
         لاگ + هشدار          لاگ + آرشیو
```

- هیچ مسیری از Signal به Broker بدون Risk و Approval وجود ندارد (تست نفوذ: تلاش مستقیم باید 403 شود).
- پس از `expires_at` تأیید نامعتبر است.

## ۲. حالات
`draft → pending_approval → approved/rejected/expired → sent → accepted/partial/filled/cancelled/failed`

## ۳. Idempotency
- هر Proposal یک `idempotency_key = sha256(proposal.id + legs + price)` دارد
- ارسال دوباره با همین کلید به Broker بی‌اثر است (پاسخ قبلی برگردانده می‌شود)

## ۴. نمونه
```json
{
  "id": "b3e1...",
  "market": "option",
  "strategy": "covered_call",
  "legs": [{"type":"call","side":"sell","quantity":1,"strike":2500,"premium":120}],
  "proposed_price": 120,
  "cost": {"gross":120000,"commission":1500,"net":118500,"slippage_bps":15},
  "risk": {"max_loss":500000,"margin":0,"var_95":80000,"liquidity_flag":"ok","staleness_flag":"fresh"},
  "idempotency_key": "a1b2...",
  "expires_at": "2026-09-01T10:05:00+03:30"
}
```
