# بخش D — ردیابی اعداد و ادعاهای پروژه

> [خوانده‌شده+اجراشده] برای اعداد DB (اسکریپت `audit_out/_tmp/partD_db.py`، SELECT فقط) و [خوانده‌شده] برای متن اسناد.
> DB فعلی: `2026-10-10` روی `localhost:5432/my_first_db`.

---

## D1) جدول اعداد/ادعاها

| # | عدد | عین جمله | فایل:خط | منبع ادعا | تاریخ سند | داده | قابل‌بازتولید؟ | وضعیت |
|---|---|---|---|---|---|---|---|---|
| 1 | ۳۶.۷٪ | `دقت کل: 36.73%` | `docs/quant-signal-goal-assessment.md:117` | `signal_accuracy` | 2026-08-12 | DB | نه دقیقاً (اکنون ۳۸.۴۳٪) | **قابل‌ردیابی** |
| 2 | −۴.۰٪ | `میانگین بازده هر سیگنال: -4.03%` | `:119` | `signal_accuracy` | 2026-08-12 | DB | نه دقیقاً (اکنون −۳.۷۳٪) | **قابل‌ردیابی** |
| 3 | ۲۸.۴٪ | `برد (pnl > 0): 860 → Win Rate = 28.4%` | `:149` | `paper_trades` | 2026-08-12 | DB | بله (۸۶۱/۳۰۲۸=۲۸.۴۳٪) | **قابل‌ردیابی** |
| 4 | −۱۵.۲٪ | `سرمایه: 1,000,000,000 → 847,475,349 (−15.2%)` | `:152` | `paper_trades` | 2026-08-12 | DB | بله (−۱۵.۲۵٪) | **قابل‌ردیابی** |
| 5 | ۳۵۹ مدل | `۳۵۹ مدل ذخیره‌شده` | `:96` | `ml_models` | 2026-08-12 | DB | بله (۳۵۹) | **قابل‌ردیابی** |
| 6 | ۳٫۶۹۵ سیگنال | `مجموع سیگنال‌های ارزیابی‌شده: 3,695` | `:112` | `signal_accuracy` | 2026-08-12 | DB | خیر (اکنون ۳۷۰۵) | **قابل‌ردیابی (کهنه)** |
| 7 | ۱٫۹٪ کاتastroفی | `commodity | ۱,۴۴۹ | ۱.۹٪` | `:134` | `signal_accuracy` | 2026-08-12 | DB | بازسنجی نشد | **بی‌منبع در این ممیزی** |
| 8 | ۲۷۵ ماژول بک‌تست | `ماژول موتور بک‌تست (backtesting/) | ۲۷۵` | `README.md:24` | — | شمارش فایل | `find backtesting -name '*.py'` = **۲۹۸** | **بی‌منبع/ناسازگار** |
| 9 | ۱۱۸ ماژول ML | `ماژول ML (ml/) | ۱۱۸` | `README.md:25` | — | شمارش فایل | `find ml -name '*.py'` = **۱۱۸** | **قابل‌ردیابی** |
| 10 | ۱۰۳ فایل سرویس | `فایل سرویس تجاری (services/) | ۱۰۳` | `README.md:23` | — | شمارش | `ls services/*.py` = **۱۶۲** | **بی‌منبع/ناسازگار** |
| 11 | ۱۱۵+ ویژگی | `محاسبه ۱۱۵+ ویژگی (۸ بلوک)` | `docs/PROJECT_GUIDE.md:90` | `feature_engine.py` | — | کد | grep = **۱۰۱** کلید یکتای `f[...]` | **تقریبی/نامشخص** |
| 12 | ۶۲.۹٪ سهام | `stock (سهام) | ۱,۳۷۶ | ۶۲.۹٪` | `docs/quant-signal-goal-assessment.md:131` | `signal_accuracy` | 2026-08-12 | DB | بازسنجی نشد | **ردیابی‌نشده** |
| 13 | `PRICE_LIMIT 5%`/`OPTION_LIMIT 19%` | عین سطر | `audit_out/_src/OPTIONS_MARKET_REPORT.md:97` | کد | — | — | دیده شد (در کد `options` — بخش C) | **قابل‌ردیابی (سند کپی‌شده)** |
| 14 | `Hard stop ... >5% / >3%` | `PLAN_GOLD.md:52` | طرح (plan) | — | — | بی‌اجرا | **بی‌منبع (طرح، نه نتیجه)** |

> توجه: `AUDIT_REPORT.md` و `OPTIONS_MARKET_REPORT.md` فقط داخل `audit_out/_src/` موجودند (نسخهٔ ریشه دیده نشد).

---

## D2) بازاجرای سه عدد مهم

| عدد | سند | مقدار فعلی DB | اختلاف |
|---|---|---|---|
| دقت جهت سیگنال | ۳۶.۷۳٪ | **۳۸.۴۳٪** (۱۴۲۴/۳۷۰۵) | **+۱.۷۰ pp** |
| میانگین بازده هر سیگنال | −۴.۰۳٪ | **−۳.۷۲۸٪** | **+۰.۳۰ pp** |
| Win Rate پیپر | ۲۸.۴٪ | **۲۸.۴۳٪** (۸۶۱/۳۰۲۸) | **+۰.۰۳ pp** |

خروجی خام (`audit_out/_tmp/partD_db.json`):
```json
"signal_accuracy_stats": {"total": 3705, "correct": 1424, "accuracy_pct": 38.43, "avg_return_pct": -3.728}
"paper stats": {"total": 3028, "wins": 861, "avg_pnl_pct": -5.0319, "sum_pnl": -152524650.92}
```
نتیجه: اعداد سند «کهنه» شده‌اند (پایگاه داده از ۱۴۰۳/۰۸/۱۰ جلو رفته)؛ فاصلهٔ کوچک ولی **غیرصفر**. عدد پیپر دقیقاً بازتولید می‌شود.

---

## D3) بازتولید اعداد خاص این سند

| ادعا | نتیجهٔ واقعی | حکم |
|---|---|---|
| دقت جهت ۳۶.۷٪ | ۳۸.۴۳٪ (۱۴۲۴/۳۷۰۵) | **بازتولید نشد** (کهنه؛ روند مثبت کم) |
| میانگین بازده −۴.۰٪ | −۳.۷۲۸٪ | **بازتولید نشد** (کهنه) |
| Win Rate پیپر ۲۸.۴٪ | ۸۶۱/۳۰۲۸ = **۲۸.۴۳٪** | **بازتولید شد** |
| بازده پیپر −۱۵.۲٪ | sum_pnl = −۱۵۲٬۵۲۴٬۶۵۰.۹۲ ⇒ **−۱۵.۲۵٪** از ۱B | **بازتولید شد** |
| «۱۱۵ ویژگی» | ۱۰۱ کلید یکتای `f[...]` در `services/feature_engine.py` (۸ بلوک A-H) | **نزدیک؛ دقیقاً ۱۱۵ تأیید نشد** |
| «۲۷۵ ماژول بک‌تست» | `find backtesting -name '*.py'` = **۲۹۸** | **ناسازگار** |
| «۱۱۸ ماژول ML» | `find ml -name '*.py'` = **۱۱۸** | **تأیید شد** |

---

## D4) وضعیت فعلیِ ۶ مورد از ۱۸ مورد `AUDIT_REPORT.md`

| # | ادعای سند | عین سطر فعلی | رفع شده؟ |
|---|---|---|---|
| **#5** | عدم احتساب هزینه در بک‌تست — `services/signal_backtest_engine.py` — ✅ اصلاح شد | `costs_pct = self.DEFAULT_TRANSACTION_COSTS.get(market_type, 0.003)` و `cost_adjusted_return = outcome.actual_return_pct - (costs_pct * 100)` | **نیمه‌رفع** — هزینه کسر می‌شود ولی نرخ ۰.۰۰۳ ثابت و **۴.۹× کم** نسبت به SSOT (`0.0147`) |
| **#8** | Sharpe بدون annualization — ✅ اصلاح شد | `result.sharpe = period_sharpe * (252 ** 0.5)` (در `_aggregate_results`) | **رفع شده** |
| **#9** | Max Drawdown با cumsum — ✅ اصلاح شد (cumprod) | `cumulative = np.cumprod(1.0 + np.array(returns) / 100.0)` سپس `peak = np.maximum.accumulate(cumulative)` | **رفع شده** |
| **#11** | Profit Factor floor 0.001 — ✅ اصلاح شد | `result.profit_factor = total_profit / total_loss if total_loss > 0 else (float("inf") if total_profit > 0 else 0.0)` (signal engine) **در برابر** `ar.profit_factor = sum(wins) / max(abs(sum(losses)), 1.0)` (AnalyticsEngine) | **ناسازگاری**: یکی `inf` می‌دهد یکی floor ۱.۰ |
| **#6** | عدم Walk-Forward در آموزش ML — ✅ اصلاح شد | `services/ml_signal_connector.py:528-585` (`WalkForwardValidator`, `walk_forward_results`) | **رفع شده** (اما validator purge/embargo ندارد — بخش C7) |
| **#1** | Default Release در خطا — ✅ اصلاح شد (Fail-closed) | `services/quant_signal_orchestrator.py:1253-1261`: `# Gate 9 fix: ... default to allowed with a warning (fail-open) ... portfolio_approved = True` | **رفع نشده — دروازهٔ ۹ Fail-OPEN است** |

**تناقض‌های خواسته‌شده:**
- **#5 در برابر «نرخ 0.003»:** سند مدعی است هزینه «اصلاح شد»، اما نرخ سخت‌کدشدهٔ `0.003` هنوز از SSOT جدا است و ممیزی C9/A5 آن را ۴.۹× کم‌برآورد نشان داد ⇒ «هزینه کسر می‌شود» ولی «درست کسر نمی‌شود».
- **#11 در برابر `profit_factor=Infinity`:** «floor» در `AnalyticsEngine` به `1.0` تغییر کرده، اما `SignalBacktestEngine` هنوز `float("inf")` برمی‌گرداند؛ همان چیزی که در ممیزی قبلی به‌صورت `"profit_factor": Infinity` و شکست `json.dumps` دیده شد ⇒ «اصلاح #11» فقط در یک مسیر اعمال شده است.

---

## جمع‌بندی بخش D

| id | شرح | شدت | فایل:خط | اقدام |
|---|---|---|---|---|
| D-01 | ادعای «ماژول بک‌تست ۲۷۵» با شمارش واقعی ۲۹۸ ناسازگار؛ «فایل سرویس ۱۰۳» با ۱۶۲ | پایین | `README.md:23-24` | به‌روزرسانی شمارش |
| D-02 | اعداد goal-assessment کهنه‌اند (۳۶.۷٪→۳۸.۴۳٪، −۴.۰٪→−۳.۷۳٪) | متوسط | `docs/quant-signal-goal-assessment.md` | تاریخ‌گذاری/بازسنجی |
| D-03 | #1 «Fail-closed» در واقع Fail-open (دروازهٔ ۹) | بحرانی | `services/quant_signal_orchestrator.py:1253-1261` | fail-closed واقعی |
| D-04 | #11 در دو موتور ناسازگار (`inf` در برابر floor 1.0) | بالا | `services/signal_backtest_engine.py`, `backtesting/analytics/engine.py` | یکسان‌سازی |
| D-05 | #5 نرخ هزینه `0.003` سخت‌کد (۴.۹× کم) | بالا | `services/signal_backtest_engine.py` | SSOT |
