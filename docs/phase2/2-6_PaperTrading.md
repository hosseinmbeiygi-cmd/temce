# 2-6 — Paper Trading + دفتر داخلی — فاز ۲

> مالک: تیم Trading

## دفتر
```sql
CREATE TABLE paper_positions (symbol TEXT PRIMARY KEY, qty INT, avg_price NUMERIC);
CREATE TABLE paper_orders (id TEXT PRIMARY KEY, proposal_id TEXT, status TEXT, filled_qty INT, price NUMERIC);
```

- هر Proposal تأییدشده → PaperBroker (فاز1) → دفتر به‌روز
- انطباق روزانه: `sum(paper_orders) == paper_positions` (۱۰۰%)

## اجرا
- 28 روز paper بدون bypass (Risk 12 کنترل فعال)
- گزارش روزانه: تعداد سفارش، PnL، زیان

## معیار خروج
- 28 روز + 0 bypass + انطباق 100%
