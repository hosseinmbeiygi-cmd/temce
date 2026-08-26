# 2-3 — بک‌تست با هزینه واقعی — فاز ۲

> مالک: تیم Research

## مدل هزینه
- هر معامله: `commission = price*qty*fee_version` + `slippage = spread*0.5` (از orderbook_levels)
- تأخیر: 1s بین سیگنال و اجرا
- نقدشوندگی: اگر حجم سفارش >10% حجم 5روزه → لغزش 2×

## گزارش
- خروجی هر بک‌تست: `pnl_gross, pnl_net, commission_total, slippage_total, max_drawdown`
- تست 6 ماهه روی 20 نماد آپشن → گزارش کارمزد/لغزش اجباری

## پیاده‌سازی
- `services/backtest/cost_model.py` — تابع `apply_costs(trades, fee_version)`
