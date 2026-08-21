# 📋 گزارش ممیزی مجدد — وضعیت رفع یافته‌های معماری

> تاریخ تهیه: ۲۰۲۶-۰۸-۱۳ — بر اساس **بررسی مستقیم کد** و **اجرای سوت‌های تست** در این جلسه.
> مرجع کامل یافته‌ها: [ARCHITECTURE_AUDIT.md](ARCHITECTURE_AUDIT.md)

## ۱. خلاصه وضعیت

| وضعیت | تعداد |
|-------|-------|
| یافته‌های بحرانی/بالا (ردیف P0/P1) | ۸ |
| ✅ رفع‌شده | **۸/۸** |
| ⬜ باز | ۰ |
| باقی‌مانده ردیف P2 (غیربحرانی) | ۸ |

**نتیجه:** تمام یافته‌های بحرانی و بالا بسته شده‌اند؛ هیچ یافته بازِ P0/P1 وجود ندارد.

---

## ۲. جدول رفع یافته‌ها (با تأیید کد)

| شناسه | یافته | مصنوع کلیدی (تأییدشده) | وضعیت |
|-------|-------|------------------------|--------|
| **F1** | ۶+ مدل کارمزد تکراری با نرخ‌های متناقض | `backtesting/costs/iran_costs.py` — تک‌منبع نرخ‌ها | ✅ |
| **F2** | مسیرهای بک-تست با `commission=0.0` سخت‌کد | `tests/unit/backtesting/test_cost_parity.py` + گارد CI | ✅ |
| **F3** | اخذ مالیات از سمت خرید | `iran_costs.py` — `SELL_TAX_PCT = 0.005` فقط فروش | ✅ |
| **S1** | تک-نقطه وابستگی به BrsApi (ریسک مسدودی کلید) | `brsapi/budget.py::BrsApiBudgetGovernor` + `brsapi/usage_recorder.py` | ✅ |
| **F6** | R² درون‌نمونه + look-ahead در بهینه‌ساز وزن‌ها | `ml/weight_validator.py::PurgedWeightValidator` (OOS R² + purged WF + پرچم provisional) | ✅ |
| **F8** | قرارداد هم‌ترازی برچسب نادقیق | `prepare_training_data(feature_sequence, closes=..., targets=...)` + assert هم‌ترازی | ✅ |
| **D1** | ۶ موتور بک-تست هم‌پوشان | `backtesting/runner.py::BacktestRunner` + deprecation موتورهای یتیم | ✅ |
| **F4** | PnL گردش بدون کارمزد خرید | `cost_basis` در `backtesting/analytics/engine.py` + `backtesting/metrics/trade_metrics.py` (deque FIFO) | ✅ |
| **F5** | ADV پیش‌فرض ۱ میلیون برای همه نمادها | `backtesting/engine/adv.py::AdvResolver` + `OrderEvent.daily_volume` + fail-fast | ✅ |
| **S2** | شکست‌های صامت در دقت‌سنجی | `services/accuracy_outcome_queue.py` + متریک‌های Prometheus + fail-fast خارج production | ✅ |

---

## ۳. سوت‌های تست (اجرای واقعی)

| سوت | نتیجه |
|------|-------|
| `tests/unit/backtesting/` | ✅ ۲۷۳ پاس |
| `tests/unit/ml/` | ✅ ۴۷ پاس |
| brsapi (گاورنر، kill-switch، readiness، quota، sync-fixes، client-retry، job-registry) | ✅ ۸۴ پاس |
| brsapi usage-recorder | ✅ ۱۰ پاس |
| تست‌های راه‌حل‌ها (ADV، cost-basis، برچسب، صف outcome، رانر) | ✅ ۴۹ پاس |
| ruff — فایل‌های تغییرداده‌شده در این روند | ✅ پاک |

> خطاهای ruff موجود در `backtesting/engine|analytics|metrics` **پیش از این روند** وجود داشتند (فایل‌هایی که در ممیزی تغییر نکرده‌اند) — رگرسیون lint نیستند.

---

## ۴. گاردهای CI فعال

| گارد | هدف |
|------|-----|
| **Backtest integrity guard** (`test_cost_parity.py` + `test_engine_runner.py`) | هر تغییر نرخ هزینه یا `commission=0.0` یا ناهماهنگی موتورها در CI fail می‌شود |
| **چک Mermaid مستندات** (`scripts/check_mermaid_blocks.py`) | سینتکس همه دیاگرام‌های `docs/` در CI اعتبارسنجی می‌شود |
| Lint / Typecheck / Build | ruff، mypy، Docker و فرانت‌اند |

---

## ۵. باقی‌مانده‌ها (ردیف P2 — غیربحرانی)

| مورد | شناسه | شدت | اولویت پیشنهادی |
|------|-------|------|-----------------|
| سیاست چرخه حیات و پاکسازی خودکار `ml_artifacts` (۳۶۰ پوشه، ۱۶۳۵ فایل) | **M2** | 🟠 بالا | ۱ |
| متادیتا + هش مدل‌های pickle (RCE/تعداد ویژگی) | M1 | 🟡 | ۲ |
| تک‌منبع‌سازی منطق صندوق در backend | D6 | 🟡 | ۳ |
| پکیج screener یکپارچه | D7 | 🟡 | ۴ |
| EvaluationSuite مشترک در CI | M3 | 🟡 | ۵ |
| رادیولوژی تصمیم دروازه‌ها | M4 | 🟡 | ۶ |
| حذف `.bak` + قانون CI | D3 | 🟡 | ۷ |
| قطع وابستگی چرخه‌ای watchlist↔symbol_catalog | D4 | 🟡 | ۸ |

---

## ۶. جمع‌بندی

پروژه برای همه یافته‌های ممیزی بحرانی/بالا در **وضعیت سبز** است:

1. **لایه هزینه/اجرا**: مدل هزینه یکپارچه ایران (F1/F2/F3) + دیسپچر یکتای موتورها (D1) + cost-basis PnL (F4) + لغزش با ADV واقعی هر نماد (F5) — همگی با تست پاریتی fail-fast.
2. **لایه ML**: R² برش OOS با purged walk-forward (F6) + قرارداد برچسب بدون نشت (F8) + lazy loader با LRU.
3. **لایه داده**: بودجه‌بان BrsApi ضد-مسدودی (S1) + ثبت مصرف روزانه در دیتابیس.
4. **لایه عملیات**: شکست‌های صامت به متریک + صف تبدیل شدند (S2).

اولویت بلافصل بعدی: **M2** — سیاست چرخه حیات و پاکسازی خودکار `ml_artifacts`.
