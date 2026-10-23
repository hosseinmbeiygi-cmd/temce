# مرحله ۲ — حساسیت، آینده‌بینی، baseline تصادفی (خودرو، ۲۰۲۴)

## دستور [خوانده‌شده+اجراشده]
- اسکریپت موقت: `C:\Users\Iran\AppData\Local\Temp\opencode\step2.py`
- دستور: `venv/Scripts/python.exe C:\Users\Iran\AppData\Local\Temp\opencode\step2.py` (از ریشه ریپو)
- نماد: خودرو، `239` بار از `brsapi_historical_daily`، بازه `2024-01-01` تا `2024-12-29`، سرمایه `1000000000`
- موتور: `BacktestSimulator` مستقیم + `MlSignalStrategy` با `sizing_method="percent"`, `sizing_value=90.0`؛ کارمزد/لغزش پیش‌فرض بروکر (کمیسیون `0.4%` هر سمت، عین سطر `backtesting/engine/broker.py:42`: `commission_pct: float = BROKER_PCT  # 0.4% per side (canonical)`)
- خروجی خام: `C:\Users\Iran\AppData\Local\Temp\opencode\step2_raw.json`
- مبنای خرید-و-نگهداری (اسکریپت `bh.py`): اول `2744.0`، آخر `3749.0`، بازده `36.6254%`

## خروجی خام (عین JSON، بدون خلاصه‌سازی)

- A_heuristic_proxy (پنجره رو به رشد، بدون آینده‌بینی؛ برچسب: پروکسی چون مدل ML واقعی ندیدم):
  `return_pct: 28.7617`، `sharpe: 0.2129`، `mdd_pct: 38.73`، `trades: 29`، `n_fills: 29`، `total_cost: 21207265.6`، `final_capital: 1287616825.434212`، `failed_blocks: []`
- B_random_seed7 (تصادفی با هزینه روشن):
  `return_pct: 28.2465`، `sharpe: 0.201`، `mdd_pct: 38.73`، `trades: 93`، `n_fills: 93`، `total_cost: 21079467.9`، `final_capital: 1282465157.0996327`، `failed_blocks: []`
- C_perfect_foresight_lookahead (علامت بازده روز بعد):
  `return_pct: 34.1354`، `sharpe: 0.3497`، `mdd_pct: 38.73`، `trades: 86`، `n_fills: 86`، `total_cost: 21102843.6`، `final_capital: 1341353702.3528063`، `failed_blocks: []`
- D_lagged_foresight (شیفت یک‌روزه، بدون آینده‌بینی):
  `return_pct: 32.4624`، `sharpe: 0.3083`، `mdd_pct: 38.73`، `trades: 86`، `n_fills: 86`، `total_cost: 21081070.3`، `final_capital: 1324624249.732907`، `failed_blocks: []`
- E_sensitivity روی پروکسی هیوریستیک:
  - `th_0.5`: `return_pct: 28.7617`، `trades: 29`، `total_cost: 21207265.6`
  - `th_1.0`: `return_pct: 28.7617`، `trades: 29`، `total_cost: 21207265.6`
  - `th_2.0`: `return_pct: 0.0`، `sharpe: 0.0`، `mdd_pct: 0.0`، `trades: 0`، `total_cost: 0`، `final_capital: 1000000000.0`

## خوانش فنی (فقط حقایق)
۱. استراتژی تصادفی با هزینه مثبت سودآور بود (`B: return_pct 28.2465` با `total_cost 21079467.9`) — قاعده رد «قابل‌اتکا» فعال است.
۲. خرید-و-نگهداری (`36.6254%`) بالاتر از هر استراتژی فعال است، از جمله آینده‌بینی کامل (`C: 34.1354`) — دریفت بازار بر هر سیگنالی غلبه دارد.
۳. فاصله آینده‌بینی کامل تا پروکسی فقط `5.3737` واحد درصد است و نسخه lagged (`32.4624`) نزدیک نسخه lookahead است — سیگنال، مهارت جداکننده نشان نداد.
۴. `mdd_pct: 38.73` در هر ۵ آزمایش (A تا D) یکسان است — با وجود تفاوت تعداد معامله (`29` تا `93`).
۵. حساسیت آستانه: `0.5` و `1.0` خروجی یکسان دادند، `2.0` صفر معامله — پرتگاه آستانه‌ای.
۶. هشدار ADV در هر اجرا تکرار شد، عین لاگ: `No ADV resolved for 'خودرو' — using fallback 1000000 for slippage.`
