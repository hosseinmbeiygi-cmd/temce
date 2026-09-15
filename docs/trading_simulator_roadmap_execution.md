# نقشه راه اجرایی شبیه‌ساز معاملاتی
# Trading Simulator Execution Roadmap

## وضعیت فعلی (Current Status)
تاریخ: 2026-09-05
همه فازهای ۱ تا ۸ پیاده‌سازی شده‌اند. زیرساخت قبلی (Screener، Paper Trading، Cost Models)
از قبل وجود داشت. ماژول‌های جدید در این دور اضافه شده‌اند.

## خلاصه فازهای تکمیل‌شده

### Phase 2: Trading Costs (مدل هزینه معاملات واقعی)
- **مدل هزینه ایران** (`backtesting/costs/iran_costs.py`): کارمزد 0.4%, مالیات فروش 0.5%, هزینه سپرده‌گذاری 0.085%
- **مدل هزینه FX** (`backtesting/costs/fx_costs.py`): اسپرد پویا با ضریب نوسان
- **مدل هزینه طلا** (`backtesting/costs/gold_costs.py`): اسپرد 0.5% پایه
- **تخمین‌گر اسپرد Corwin-Schultz** (NEW - `backtesting/costs/spread_estimator.py`): تخمین اسپرد از OHLC
- **مدل اسلیپیج پویا** (`backtesting/slippage.py`): مبتنی بر حجم و نوسان
- **تحلیل حساسیت تأخیر** (NEW - `backtesting/execution/latency_sensitivity.py`): ۵ سناریو
- **مدل تراکنش کامل** (`backtesting/costs/transaction_cost_model.py`): ۷ مؤلفه هزینه

### Phase 3: Data Quality (کیفیت داده)
- **اعتبارسنج تیک** (`backtesting/data_quality/tick_validator.py`): تشخیص تیک‌های بد، رانش زمانی، ناهنجاری
- **خط‌مشی داده گمشده** (NEW - `backtesting/data_quality/missing_data_policy.py`): تشخیص و حذف، بدون پرکردن ساختگی

### Phase 4: Scoring & Regime (امتیازدهی و رژیم)
- **تشخیص رژیم بازار** (`backtesting/regime/regime_detector.py`): ۶ رژیم (عادی/روند/وحشت/نقدینگی‌کم/صف/بازگشت)
- **امتیاز اطمینان** (`services/confidence_scorer.py`): ۷ عامل وزنی
- **تحلیل همبستگی** (NEW - `backtesting/analytics/correlation.py`): پیرسون، اسپیرمن، بتا، آلفا
- **Walk-Forward Validator** (`services/walk_forward_validator.py`): اعتبارسنجی چندپنجره‌ای

### Phase 5: Statistical Tests (آزمون‌های آماری)
- **بوت‌استرپ برای Expectancy** (NEW - `backtesting/analytics/significance_tests.py`)
- **آزمون Sign** برای میانه PnL
- **آزمون Wilcoxon Signed-Rank**
- **درگاه پذیرش آماری** (`services/statistical_acceptance_gate.py`): ۴ شرط §7.2

### Phase 6: Phase Exit Criteria (معیارهای خروج فاز)
- **معیارهای کمی خروج** (NEW - `backtesting/analytics/phase_exit_criteria.py`)
- پشتیبانی از ۸ فاز با آستانه‌های مشخص
- قابلیت ارزیابی برنامه‌ریزی‌شده

### Phase 8: Stress Scenarios (سناریوهای استرس)
- **سناریوهای بازار** (`backtesting/scenarios/`): صعودی، نزولی، پرنوسان، کم‌نقدینگی
- **سناریو اسلیپیج** (NEW - `backtesting/scenarios/slippage_stress.py`): 2x تا 5x
- **تست استرس آلفا** (`backtesting/alpha/stress_testing.py`): ۵ سناریوی مرکب
- **ارکستراتور استرس یکپارچه** (NEW - `backtesting/scenarios/stress_test_orchestrator.py`)

## مسیر ادامه (Next Steps)

### 1. تست واحد برای ماژول‌های جدید
فایل‌های تست زیر باید ایجاد شوند:
- `tests/unit/backtest/test_spread_estimator.py`
- `tests/unit/backtest/test_latency_sensitivity.py`
- `tests/unit/backtest/test_missing_data_policy.py`
- `tests/unit/backtest/test_correlation.py`
- `tests/unit/backtest/test_significance_tests.py`
- `tests/unit/backtest/test_phase_exit_criteria.py`
- `tests/unit/backtest/test_slippage_stress.py`

### 2. یکپارچه‌سازی با Pipeline موجود
- لینک `UnifiedStressTestOrchestrator` به `paper_trading_service.py`
- اضافه کردن `evaluate_phase` به گزارش‌های روزانه Pipeline

### 3. Paper Trading واقعی
- استفاده از `paper_trading_service.py` با حداقل ۳۰ معامله
- مقایسه هفتگی نتایج Paper با بک‌تست

## نحوه اجرا
```bash
# تست همه ماژول‌های جدید
python -m pytest tests/unit/backtest/ -v

# اجرای ارکستراتور استرس
python -c "from backtesting.scenarios.stress_test_orchestrator import UnifiedStressTestOrchestrator; o=UnifiedStressTestOrchestrator(); r=o.run_all([]); print(r)"

# بررسی معیارهای خروج فاز
python -c "from backtesting.analytics.phase_exit_criteria import evaluate_phase, ALL_PHASES; print(ALL_PHASES.keys()); r=evaluate_phase(2, {'spread_estimator_ready':1.0,'slippage_dynamic':1.0,'latency_sensitivity':1.0,'partial_fill_model':1.0}); print(r.summary)"
```
