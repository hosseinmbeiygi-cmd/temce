# گزارش قابلیت اتکا — بک‌تست سیگنال ML (نهایی)

## ۱) سنجش با معیارهای پذیرش
- فایل `acceptance.yaml` در ریشه ریپو وجود ندارد (جست‌وجو شد).
- تنها معیارهای پذیرشِ مستندِ پروژه در `docs/quant-signal-goal-assessment.md:32-39` هستند و عیناً نقل می‌شوند. ستون «مقدار فعلی» همان سند است و در این ممیزی مستقل بازسنجی نشده (بک‌تست مقادیر متناظر را تولید نمی‌کند):

| # | معیار | مقدار هدف | مقدار سند | حکم |
|---|---|---|---|---|
| ۱ | دقت جهت سیگنال | >۷۰٪ | ۳۶.۷٪ | ❌ |
| ۲ | میانگین بازده هر سیگنال | مثبت | −۴.۰٪ | ❌ |
| ۳ | Win Rate در Paper Trading | >۵۰٪ | ۲۸.۴٪ | ❌ |
| ۴ | بازده کل Paper Trading | مثبت | −۱۵.۲٪ | ❌ |
| ۵ | نسبت شارپ (بک‌تست‌ها) | >۱ | نامشخص | ⚪ |

- هیچ آستانهٔ دیگری اختراع نشد؛ فقط معیارهای بالا داوری می‌شوند.

## ۲) حکم صریح
**حکم: غیرقابل‌اتکا**

چهار دلیل اصلی:
۱. مسیر واقعی `ml_signal` هیچ سیگنالی تولید نکرد — `step1_run.md` بخش ۳: `No ML model available ... using zero predictions` و `total_trades: 0` در هر ۵ نماد (ارجاع: `step4_numbers.md` جدول مرحله ۱).
۲. استراتژی تصادفی با هزینه مثبت سودآور بود — `step2_robustness.md` آزمایش B: `return_pct: 28.2465` با `total_cost: 21079467.9`؛ قاعده صریح حکم، «قابل‌اتکا» را رد می‌کند.
۳. buy-and-hold (`36.6254%`) از آینده‌بینی کامل (`34.1354`) و همه سیگنال‌ها بالاتر است (`step2_robustness.md` + `step4_numbers.md`) — سودها دریفت بازارند نه مهارت سیگنال.
۴. مسیر رسمی بک‌تست سیگنال (`POST /signal-insights/backtest`) با `AttributeError` می‌شکند، حتی با دورزدن خطا `total_signals: 0` می‌دهد، و موتور آن معاملهٔ ساختگی `+786.2%` با `profit_factor: Infinity` می‌سازد (`step1_run.md` بخش ۵ + `step2_tests.md` بخش ۵).

به‌علاوه ۹ مورد بحرانی باز در `step3_criticals.md` (C1 تا C9).

## ۳) اصلاحات لازم قبل از اعتماد به نتیجه
۱. فایل: `services/backtest_service.py` (`_inject_ml_predictions`) — ثبت مدل `xgboost_<symbol>` در `ArtifactManager`؛ آزمون: `total_trades > 0` در تکرار مرحله ۱.
۲. فایل: گزارش‌ساز بک‌تست — افزودن ستون‌های اجباری `bh_return_pct` و `random_return_pct`؛ آزمون: `return_strategy - return_bh > 0` و `return_strategy - return_random > 0`.
۳. فایل: `repositories/backtest_repository.py` / مدل `BacktestRun` — رفع خطای `current_value`؛ آزمون: نبود هشدار `Failed to get result from DB` در لاگ.
۴. فایل: `backtesting/metrics/drawdown_metrics.py` — بررسی MDD یکسان `38.73` در رفتارهای متفاوت (C6)؛ آزمون: تفکیک MDD یا مستندسازی علت.
۵. فایل: `apps/api/endpoints/signal_insights.py:120` (و کلاس `MarketSignal`) — رفع `AttributeError: 'MarketSignal' object has no attribute 'to_dict'`؛ آزمون: endpoint مسیر رسمی با `200` و `total_signals > 0` پاسخ دهد.
۶. فایل: `services/signal_backtest_engine.py` — صفر/None کردن `profit_factor` به‌جای `Infinity` و بازبینی نگاشت تاریخ؛ آزمون: `json.dumps(result)` بدون `allow_nan=True` موفق شود.
۷. فایل: `services/signal_backtest_engine.py:124-132, :228` — استفاده از `domain/trading/iran_costs.py` به‌جای نرخ ثابت `0.003`؛ آزمون: نرخ سهام برابر رفت‌وبرگشت SSOT (`0.0147`) شود.
۸. ثبت `acceptance.yaml` با همان آستانه‌های بند ۱ تا داوری خودکار شود؛ آزمون: هر آستانه به بخش مشخصی از خروجی خام ارجاع دهد.

## ۴) بررسی نشد
- `acceptance.yaml` — ندیدم.
- هزینه کل تفکیکی کمیسیون/لغزش در مرحله ۱ — فیلد جدا ندیدم (صفر معامله → هزینه صفر).
- سرمایه نهایی مرحله ۱ به‌تفکیک نماد — ندیدم.
- تکرار تصادفی با seedهای بیشتر و نمادهای دیگر — انجام نشد.
- `step2_tests.md` بخش ۱–۳ روی داده مصنوعی اجرا شده است و فقط بخش ۵ آن (بازهٔ واقعی مرحله ۱) در این گزارش لحاظ شده.
- انجام شد: `step1_run.md`، `step2_robustness.md`، `step2_tests.md` (بخش ۵)، `step3_criticals.md`، `step4_numbers.md`.
- کپی پایدار شواهد خام (مستقل از پوشه موقت): `audit_out/_tmp/opencode/` (`step1_raw.json`، `step2_raw.json`، `step1.py`، `step2.py`، `bh.py`) — یکسان‌بودن با نسخهٔ پوشه موقت با `cmp` تأیید شد؛ عددهای `step4_numbers.md` و `step2_robustness.md` با همین JSON تطبیق داده شدند (PASS).
- شواهد مرحله ۱ (مسیر ML) و بخش ۵: `audit_out/_logs/step1_run.log`، `step1_run_b.log`، `step1_rerun1.log`، `step1_rerun2.log`، `step2_real_window.out`.

## ۵) خلاصه ده‌خطی: اگر فقط یک چیز را اصلاح کنم، چه باشد؟
۱. مسیر واقعی ML اجرا شد ولی مدل وجود ندارد: صفر معامله در هر ۵ نماد.
۲. با پروکسی هیوریستیک هم سود (`28.76%`) از شانس (`28.25%`) جدا نشد.
۳. و هر دو از نگهداری ساده (`36.63%`) کمترند.
۴. حتی دانستن آینده (`34.14%`) بازار صعودی را نبرد.
۵. پس مشکل، تنظیم آستانه نیست — سیگنال ارزشی روی دریفت ندارد.
۶. اگر فقط یک چیز: مدل واقعی آموزش‌دیده در `ArtifactManager` بگذار.
۷. جای تغییر: `_inject_ml_predictions` در `services/backtest_service.py`.
۸. بعد همان دستور مرحله ۱ را تکرار کن تا `total_trades > 0` شود.
۹. سپس هر گزارش را با buy-and-hold و baseline تصادفی مقایسه کن.
۱۰. تا آن زمان به هیچ عدد بک‌تست ML اعتماد نکن.
