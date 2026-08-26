# 2-4 — CI: parity / Greeks / داده ناقص — فاز ۲

> مالک: QA

## 20 تست جدید به CI
- 5 parity: put-call با r/q مختلف
- 5 Greeks: delta/gamma/vega با BS vs درخت
- 5 داده ناقص: کهنه، spread باز، حجم صفر، تقسیم سود، تعطیلی
- 5 limit price: نزدیک ±۱۹%

## اجرا
- هر PR → `pytest tests/unit/options -q` + `npm run build`
- شکست هر تست → PR قرمز
