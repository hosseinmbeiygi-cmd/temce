# مرحله ۳ — موارد بحرانی

## C1. مدل ML وجود ندارد؛ مسیر ml_signal همیشه صفر است [خوانده‌شده+اجراشده]
- شاهد: لاگ مرحله ۱، عین: `No ML model available for <symbol>, using zero predictions` (هر ۵ نماد) + عین کد `services/backtest_service.py:798-800` (`b["predicted_change_pct"] = 0.0`)؛ گارد در `:797`.
- اثر: `total_trades: 0` در هر ۵ نماد؛ هر ادعای عملکرد ML روی این مسیر، ادعای روی «هیچ» است.
- رفع پیشنهادی: ثبت مدل `xgboost_<symbol>` در `ArtifactManager`؛ آزمون: `total_trades > 0` پس از تکرار دستور مرحله ۱.

## C2. استراتژی تصادفی با هزینه مثبت سودآور است [خوانده‌شده+اجراشده]
- شاهد: `audit_out/step2_robustness.md` آزمایش B — `return_pct: 28.2465` با `total_cost: 21079467.9`.
- اثر: سودآوری، مهارت سیگنال را ثابت نمی‌کند؛ قاعده: حکم نمی‌تواند «قابل‌اتکا» باشد.
- رفع پیشنهادی: گزارش اجباری اختلاف بازده نسبت به buy-and-hold و baseline تصادفی در هر گزارش بک‌تست؛ آزمون: `return_strategy - return_random > 0` و `return_strategy - return_bh > 0`.

## C3. هیچ استراتژی فعالی buy-and-hold را نبرد، حتی آینده‌بینی کامل [خوانده‌شده+اجراشده]
- شاهد: buy-and-hold `36.6254%` در برابر `C_perfect_foresight_lookahead: 34.1354` و `A: 28.7617`.
- اثر: هزینه‌ها (`~21M` در هر اجرا) بازده فعال را زیر نگهداری ساده بردند؛ سیگنال ارزش افزوده ندارد.
- رفع پیشنهادی: افزودن ستون buy-and-hold به خروجی `_summarize` در `backtesting/runner.py`؛ آزمون: هر گزارش شامل `bh_return_pct` باشد.

## C4. خطای لایه ذخیره نتیجه (`current_value`) [خوانده‌شده+اجراشده]
- شاهد: عین لاگ مرحله ۱: `Failed to get result from DB: 'BacktestRun' object has no attribute 'current_value'`.
- اثر: خوانش `get_result(run_id)` از DB شکست می‌خورد؛ نتایج قابل‌بازیابی/حسابرسی نیستند.
- رفع پیشنهادی: هم‌خوان‌سازی مدل `BacktestRun` با کد خوانش در `repositories/backtest_repository.py`؛ آزمون: نبود این هشدار در لاگ مرحله ۱.

## C5. افت ADV به مقدار پیش‌فرض (slippage غیرواقعی) [خوانده‌شده+اجراشده]
- شاهد: عین لاگ مرحله ۲: `No ADV resolved for 'خودرو' — using fallback 1000000 for slippage.`
- اثر: لغزش با حجم generic محاسبه شد، نه نقدشوندگی واقعی نماد؛ هزینه‌ها تقریبی‌اند.
- رفع پیشنهادی: pre-warm کردن `AdvResolver` (همان‌طور که `backtest_service.py:239` انجام می‌دهد) در اجراهای مستقیم؛ آزمون: نبود هشدار fallback در لاگ.

## C6. MDD یکسان (`38.73`) در هر ۵ آزمایش با تعداد معامله متفاوت [خوانده‌شده+اجراشده]
- شاهد: `audit_out/step2_robustness.md` — آزمایش‌های A تا D با `trades` از `29` تا `93` همگی `mdd_pct: 38.73`.
- اثر: یا اکوییتی همیشه در معرض بازار است (سایز ۹۰٪ + ورود سریع) یا محاسبه دراودان به سیگنال حساس نیست — نیازمند بررسی، نه اعتماد.
- رفع پیشنهادی: بازبینی `backtesting/metrics/drawdown_metrics.py` + ثبت equity_curve در خروجی خام؛ آزمون: MDD دو استراتژی با رفتار متفاوت، متفاوت شود یا علت مستند گردد.

## C7. مسیر رسمی `POST /signal-insights/backtest` با خطای سریال‌سازی می‌شکند [خوانده‌شده+اجراشده]
- شاهد: عین لاگ `audit_out/_logs/step1_run.log:97`: `"exception": "AttributeError: 'MarketSignal' object has no attribute 'to_dict'"`؛ کد فراخوان `apps/api/endpoints/signal_insights.py:120`: `signals=[s.to_dict() for s in signals],`.
- اثر: مسیر رسمی بک‌تست سیگنال (که `signal_accuracy` را هم تغذیه می‌کند) بالا نمی‌آید؛ با دورزدن خطا (`dataclasses.asdict`) هم نتیجه `total_signals: 0` بود (`step1_run.md` بخش ۵-۱).
- رفع پیشنهادی: افزودن `to_dict()` به `MarketSignal` یا جایگزینی با `dataclasses.asdict` در endpoint؛ آزمون: endpoint با `200` و `total_signals > 0` پاسخ دهد.

## C8. موتور بک‌تست سیگنال معاملهٔ ساختگی و `profit_factor: Infinity` تولید می‌کند [خوانده‌شده+اجراشده]
- شاهد: عین لاگ `audit_out/_logs/step1_run.log:164,170`: `"profit_factor": Infinity` و `"best_trade_pct": 786.2`؛ معاملهٔ عین JSON: نماد `آ س پ3`، ورود `3163.0` → خروج `28040.0` ⇒ `+786.2%` با `entry_date 2026-10-03` و `exit_date 2026-10-08` (`step1_run.md` بخش ۵-۲).
- اثر: خروجی با `json.dumps` استاندارد می‌شکند (`ValueError: Out of range float values are not JSON compliant`) و نگاشت تاریخ جلالی↔میلادی در ورود/خروج ناسازگار است.
- رفع پیشنهادی: صفر/None کردن `profit_factor` وقتی مخرج صفر است + بازبینی نگاشت تاریخ؛ آزمون: `json.dumps(result)` بدون `allow_nan=True` موفق شود.

## C9. نرخ هزینهٔ موتور سیگنال ~۴.۹ برابر کم‌برآورد است [خوانده‌شده+اجراشده]
- شاهد: `services/signal_backtest_engine.py:124-132`: `DEFAULT_TRANSACTION_COSTS = {"stock": 0.003, ...}` و کسر در `:228`؛ SSOT `domain/trading/iran_costs.py`: `BROKER_PCT=0.004` + `CLEARING_FEE_PCT=0.00085` + `SELL_TAX_PCT=0.005` ⇒ رفت‌وبرگشت سهام `0.0147` (۱.۴۷٪).
- اثر: سود خالص بک‌تست سیگنال خوش‌بینانه است (نرخ موتور نسبت به SSOT حدود ۴.۹ برابر کم).
- رفع پیشنهادی: در `SignalBacktestEngine` از `domain/trading/iran_costs.py` استفاده شود؛ آزمون: نرخ سهام برابر رفت‌وبرگشت SSOT شود.
