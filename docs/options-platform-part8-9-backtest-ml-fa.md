# تکمیل بخش ۸ (موتور بک‌تست) و بخش ۹ (موتور پیش‌بینی)

> این فایل نسخه‌ی گسترده‌تر بخش‌های ۸ و ۹ سند اصلی «معماری کامل پلتفرم معاملات آپشن بورس تهران» است. شماره‌گذاری زیربخش‌ها ادامه‌ی همان سند است تا بتوانید مستقیم جایگزین یا الحاق کنید.

---

## ۸. موتور بک‌تست (Backtesting Engine) — نسخه تکمیلی

### ۸.۱ اصول طراحی (تکمیلی)

علاوه بر اصول ذکرشده در سند اصلی (Event-Driven، شبیه‌سازی هزینه‌ها، محدودیت نقدشوندگی، Walk-Forward)، نکات زیر باید در پیاده‌سازی رعایت شود:

- **عدم نشتی داده (No Data Leakage) به‌صورت سخت‌گیرانه**: هر Feature یا قیمتی که در تصمیم لحظه `t` استفاده می‌شود باید timestamp انتشار واقعی‌اش `≤ t` باشد؛ این شامل داده‌های تعدیل‌شده (Adjusted) هم می‌شود — تعدیل قیمت اعمال به‌خاطر افزایش سرمایه باید فقط از لحظه‌ی انتشار رسمی اطلاعیه به بعد در بک‌تست اعمال شود، نه با فرض قبلی.
- **شبیه‌سازی سررسید واقعی**: قراردادهایی که به سررسید می‌رسند باید طبق نوع تسویه (نقدی/فیزیکی) در همان لحظه بسته شوند؛ در حالت تسویه فیزیکی، موقعیت به خرید/فروش سهم پایه در پرتفوی تبدیل می‌شود (نه صرفاً صفر شدن).
- **جداسازی کامل کد استراتژی از کد بک‌تست**: همان کلاس `StrategyBuilder` / `RuleEngine` که در Live استفاده می‌شود، بدون تغییر در بک‌تست هم فراخوانی شود؛ این تضمین می‌کند نتیجه‌ی بک‌تست واقعاً معرف رفتار سیستم زنده است (Parity بین Backtest و Live).
- **تعیین صریح فرض‌های اجرا**: هر بک‌تست باید صراحتاً مشخص کند سفارش‌ها با چه فرضی پر شده‌اند (Fill at Mid / Fill at Worst-of-Bid-Ask / با تأخیر N ثانیه)، چون در بازار کم‌عمق ایران این فرض تأثیر زیادی روی نتیجه دارد.

### ۸.۲ معماری کامل موتور

```
BacktestEngine
├── MarketReplaySource
│     ├── UnderlyingPriceStream   (کندل/تیک سهم پایه)
│     ├── OptionChainSnapshot     (bid/ask/last/OI هر گام زمانی)
│     └── CorporateActionStream   (افزایش سرمایه، سود نقدی، توقف نماد)
│
├── ExecutionSimulator
│     ├── OrderMatcher            (تطبیق سفارش با bid/ask لحظه)
│     ├── SlippageModel           (تابعی از حجم سفارش / عمق بازار)
│     ├── CommissionModel         (کارمزد کارگزاری + سازمان بورس، پلکانی)
│     └── LiquidityConstraint     (رد/اجرای جزئی بر اساس حجم موجود)
│
├── StrategyRunner
│     └── فراخوانی مستقیم SignalGenerator + RuleEngine (کد یکسان با Live)
│
├── PortfolioSimulator
│     ├── PositionLedger          (موقعیت‌های باز، PnL شناور/محقق‌شده)
│     ├── MarginEngine            (وجه تضمین اولیه/متغیر، Margin Call)
│     └── CorporateActionHandler  (تعدیل موقعیت‌های باز پس از اطلاعیه)
│
├── RiskGuard
│     └── همان قوانین ماژول Risk Management (Circuit Breaker، Concentration Limit)
│       — برای اطمینان از این‌که استراتژی در دنیای واقعی هم زیر همین محدودیت‌ها اجرا می‌شد
│
└── ReportGenerator
      ├── EquityCurve + DrawdownChart
      ├── PerformanceMetrics (بخش ۸.۴)
      ├── TradeLog (ورود/خروج هر معامله با دلیل سیگنال)
      └── SensitivityReport (اثر نرخ بهره / IV فرضی روی نتیجه)
```

### ۸.۳ مدل‌سازی اجرای سفارش (Execution Model)

برای بازار کم‌نقدشوندگی ایران، فرض «اجرای کامل در قیمت درخواستی» واقع‌بینانه نیست. مدل پیشنهادی:

```python
class ExecutionSimulator:
    def __init__(self, slippage_bps_per_lot=5, max_participation_rate=0.2):
        self.slippage_bps_per_lot = slippage_bps_per_lot
        self.max_participation_rate = max_participation_rate

    def simulate_fill(self, order, market_snapshot):
        """
        order: شامل side, quantity, order_type, limit_price
        market_snapshot: شامل bid, ask, bid_size, ask_size, last, volume_this_bar
        """
        available_volume = market_snapshot.volume_this_bar * self.max_participation_rate
        filled_qty = min(order.quantity, available_volume)

        if filled_qty <= 0:
            return {"status": "REJECTED", "filled_qty": 0, "avg_price": None}

        base_price = market_snapshot.ask if order.side == "BUY" else market_snapshot.bid
        # اسپرد + اسلیپیج متناسب با نسبت حجم سفارش به عمق بازار
        depth = market_snapshot.ask_size if order.side == "BUY" else market_snapshot.bid_size
        impact_factor = min(filled_qty / max(depth, 1), 1.0)
        slippage = base_price * (self.slippage_bps_per_lot / 10000) * impact_factor
        fill_price = base_price + slippage if order.side == "BUY" else base_price - slippage

        if order.order_type == "LIMIT":
            if order.side == "BUY" and fill_price > order.limit_price:
                return {"status": "REJECTED", "filled_qty": 0, "avg_price": None}
            if order.side == "SELL" and fill_price < order.limit_price:
                return {"status": "REJECTED", "filled_qty": 0, "avg_price": None}

        status = "FILLED" if filled_qty == order.quantity else "PARTIAL"
        return {"status": status, "filled_qty": filled_qty, "avg_price": round(fill_price, 2)}
```

### ۸.۴ مدیریت رویدادهای شرکتی و سررسید طی بک‌تست

- `CorporateActionHandler` باید در همان لحظه‌ی زمانی که اطلاعیه در تاریخ گذشته منتشر شده، قیمت اعمال و اندازه‌ی قرارداد را تعدیل کند — با استفاده از همان منطق `Corporate Actions Handler` سیستم زنده، نه یک نسخه‌ی جدا.
- در سررسید، برای موقعیت‌های In-the-Money با تسویه فیزیکی، `PortfolioSimulator` باید به‌صورت خودکار موقعیت سهام معادل ایجاد کند و آن را در ادامه‌ی همان بازه‌ی بک‌تست (اگر استراتژی شامل نگهداری سهم است) دنبال کند.
- برای موقعیت‌های Out-of-the-Money، بستن با ارزش صفر و ثبت ضرر کامل پرمیوم پرداختی به‌عنوان نتیجه‌ی معامله.

### ۸.۵ متریک‌های خروجی گسترده‌تر (علاوه بر موارد سند اصلی)

| متریک | فرمول / توضیح |
|---|---|
| Calmar Ratio | بازده سالانه / \|Max Drawdown\| — برای سنجش بازده به‌ازای ریسک دنباله |
| Omega Ratio | نسبت مجموع بازده‌های بالای آستانه به مجموع بازده‌های زیر آستانه |
| Expectancy | (Win Rate × میانگین سود) − (Loss Rate × میانگین ضرر) به‌ازای هر معامله |
| Average Holding Period | میانگین مدت نگهداری موقعیت تا خروج |
| Margin Utilization | نسبت میانگین وجه تضمین مصرف‌شده به کل سرمایه در طول دوره |
| Tail Ratio | نسبت پرسنتایل ۹۵ بازده‌ها به قدرمطلق پرسنتایل ۵ |

### ۸.۶ اعتبارسنجی آماری نتایج (فراتر از Walk-Forward ساده)

برای جلوگیری از استنتاج نادرست از یک مسیر تاریخی واحد:

- **Block Bootstrap روی equity curve**: نمونه‌گیری مجدد بلوک‌های زمانی بازده (نه تک‌روزها، برای حفظ خودهمبستگی) جهت ساخت بازه‌ی اطمینان برای شارپ و Max Drawdown.
- **Monte Carlo Trade Reshuffling**: چیدمان تصادفی ترتیب معاملات ثبت‌شده برای بررسی حساسیت نتیجه به توالی خاص معاملات.
- **Deflated Sharpe Ratio**: تعدیل شارپ محاسبه‌شده بر اساس تعداد ترکیب‌های پارامتری آزموده‌شده، برای کاهش اثر Overfitting ناشی از جست‌وجوی گسترده‌ی پارامتر (مهم چون `RuleEngine` امکان تنظیم آزادانه‌ی پارامتر را می‌دهد).

```python
def deflated_sharpe_ratio(observed_sharpe, n_trials, n_obs, skew=0, kurt=3):
    from scipy.stats import norm
    import numpy as np
    # تخمین شارپ مورد انتظار تحت فرض صفر با n_trials آزمایش مستقل
    expected_max_sharpe = (1 - np.euler_gamma) * norm.ppf(1 - 1 / n_trials) \
        + np.euler_gamma * norm.ppf(1 - 1 / (n_trials * np.e))
    sr_std = np.sqrt((1 - skew * observed_sharpe + (kurt - 1) / 4 * observed_sharpe**2) / (n_obs - 1))
    return norm.cdf((observed_sharpe - expected_max_sharpe) / sr_std)
```

---

## ۹. موتور پیش‌بینی (ML / Forecasting) — نسخه تکمیلی

### ۹.۱ فیچرهای ورودی — لیست کامل‌تر

| دسته | فیچرها |
|---|---|
| قیمتی/تکنیکال | RSI(14)، MACD، Bollinger Band Width، ATR، بازده لگاریتمی ۱/۵/۲۰ روزه، نسبت حجم به میانگین ۲۰ روزه |
| ساختار آپشن | IV Rank / IV Percentile (۵۲ هفته)، Put/Call Volume Ratio، Put/Call OI Ratio، Term Structure Slope (تفاوت IV بین دو سررسید نزدیک)، Skew (IV اوت‌آف‌مانی پوت منهای کال)، تغییر روزانه‌ی Open Interest |
| میکروساختار بازار | اسپرد نسبی bid/ask، عمق صف در بهترین قیمت، تعداد معاملات در بازه |
| کلان/بین‌بازاری | بازده شاخص کل و شاخص هم‌وزن، نرخ ارز (برای صنایع صادرات‌محور)، نرخ بهره بین‌بانکی، نرخ تورم نقطه‌به‌نقطه (به‌صورت فیچر کم‌فرکانس) |
| تقویمی | روزهای مانده به سررسید، فاصله تا مجمع/برگزاری DPS، فصل مالی |

نکته: فیچرهای مبتنی بر داده‌های رسمی/کدال باید با تأخیر انتشار واقعی (Publication Lag) وارد شوند، نه تاریخ رویداد.

### ۹.۲ مدل‌ها با جزئیات بیشتر

**GARCH(1,1) برای نوسان آتی:**

```
σ²_t = ω + α·ε²_(t-1) + β·σ²_(t-1)
```

خروجی به‌صورت نوسان پیش‌بینی‌شده برای افق `T` (روزهای تا سررسید) با استفاده از فرمول تجمیع نوسان (Volatility Term Structure) به‌کار می‌رود و به‌عنوان baseline در کنار Implied Volatility بازار مقایسه می‌شود تا سیگنال گران/ارزان بودن آپشن تولید شود.

**LightGBM/XGBoost برای پیش‌بینی جهت/بازه‌ی حرکت سهم پایه:**

- خروجی به‌صورت طبقه‌بندی سه‌کلاسه (صعود معنادار / خنثی / نزول معنادار) به‌جای رگرسیون مستقیم قیمت — پایدارتر و برای تولید سیگنال مناسب‌تر است.
- Early Stopping بر اساس اعتبارسنجی Walk-Forward، نه k-fold تصادفی معمولی (چون داده‌ی مالی توالی‌محور است).

```python
import lightgbm as lgb

def train_direction_model(X_train, y_train, X_val, y_val):
    train_set = lgb.Dataset(X_train, label=y_train)
    val_set = lgb.Dataset(X_val, label=y_val, reference=train_set)
    params = {
        "objective": "multiclass",
        "num_class": 3,
        "learning_rate": 0.03,
        "num_leaves": 31,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "min_data_in_leaf": 50,   # جلوگیری از overfit روی داده کم‌حجم بازار ایران
    }
    model = lgb.train(
        params, train_set, num_boost_round=1000,
        valid_sets=[val_set], callbacks=[lgb.early_stopping(50)]
    )
    return model
```

### ۹.۳ اعتبارسنجی صحیح سری‌های زمانی (Purged & Embargoed Walk-Forward)

اعتبارسنجی معمولی k-fold برای داده‌ی مالی نشتی ایجاد می‌کند چون نمونه‌های نزدیک به هم در زمان همبسته‌اند. روش پیشنهادی (بر اساس رویکرد López de Prado):

1. داده به بازه‌های زمانی متوالی (Fold) تقسیم می‌شود.
2. بین مجموعه‌ی آموزش و آزمون یک **Purge Gap** به‌اندازه‌ی طول افق پیش‌بینی حذف می‌شود (برای جلوگیری از هم‌پوشانی برچسب‌ها).
3. یک **Embargo Period** کوتاه بعد از مجموعه‌ی آزمون هم حذف می‌شود تا اثر خودهمبستگی باقی‌مانده وارد فولد بعدی نشود.
4. مدل روی هر فولد به‌صورت مستقل آموزش داده و روی فولد آزمون بعدی (که کاملاً در آینده است) ارزیابی می‌شود.

### ۹.۴ کالیبراسیون احتمال و بازه‌ی اطمینان

چون سیستم طبق الزام رگولاتوری باید خروجی احتمالی/بازه‌ای بدهد نه سیگنال قطعی:

- **کالیبراسیون**: استفاده از Platt Scaling یا Isotonic Regression روی خروجی خام مدل برای اطمینان از این‌که «احتمال ۷۰٪» واقعاً معادل نرخ وقوع ۷۰٪ در داده‌ی تاریخی باشد.
- **Conformal Prediction**: برای تولید بازه‌ی اطمینان با پوشش تضمین‌شده (مثلاً بازه‌ای که ۹۰٪ اوقات مقدار واقعی را در بر می‌گیرد) بدون فرض توزیع خاص — مناسب برای بازار با رفتار غیرنرمال مثل بورس تهران.

### ۹.۵ Ensemble پویا با وزن‌دهی Rolling

```python
class DynamicEnsemble:
    def __init__(self, models: dict, lookback_window=60):
        self.models = models          # {"garch": ..., "lgbm": ..., "xgb": ...}
        self.lookback_window = lookback_window
        self.recent_performance = {name: [] for name in models}

    def update_weights(self):
        scores = {
            name: max(np.mean(perf[-self.lookback_window:]), 1e-6)
            for name, perf in self.recent_performance.items() if perf
        }
        total = sum(scores.values())
        return {name: score / total for name, score in scores.items()} if total > 0 else \
            {name: 1 / len(self.models) for name in self.models}

    def predict(self, X):
        weights = self.update_weights()
        combined = sum(weights[name] * model.predict_proba(X) for name, model in self.models.items())
        return combined
```

معیار عملکرد اخیر برای هر مدل می‌تواند Log Loss یا Brier Score معکوس‌شده باشد تا مدل‌هایی که اخیراً بهتر کالیبره بوده‌اند وزن بیشتری بگیرند.

### ۹.۶ ارزیابی مدل — متریک‌های اضافه بر دقت طبقه‌بندی

| متریک | کاربرد |
|---|---|
| Brier Score | کیفیت کالیبراسیون احتمال (پایین‌تر بهتر) |
| Log Loss | جریمه‌ی احتمالات اطمینان‌بیش‌ازحد اشتباه |
| Directional Accuracy | درصد تطابق جهت پیش‌بینی‌شده با جهت واقعی |
| Nested Backtest عملکرد سیگنال | اجرای `BacktestEngine` روی سیگنال‌های خروجی مدل (نه صرفاً دقت آماری) برای سنجش سودآوری واقعی پس از کسر هزینه |

### ۹.۷ پایش Drift و بازآموزی در Production

- **Data Drift**: مقایسه‌ی توزیع فیچرهای ورودی روزانه با توزیع دوره‌ی آموزش (مثلاً با آزمون Kolmogorov–Smirnov)؛ هشدار خودکار در صورت انحراف معنادار.
- **Performance Drift**: پایش رولینگ Log Loss/Brier Score مدل روی داده‌ی واقعی؛ افت مستمر → فعال‌سازی بازآموزی.
- **زمان‌بندی بازآموزی**: پیش‌فرض هفتگی برای مدل جهت‌یابی (به‌دلیل تغییر رژیم بازار)، ماهانه برای GARCH (پارامترهای نوسان کندتر تغییر می‌کنند).
- تمام نسخه‌های مدل و پارامترهای‌شان با شماره‌ی نسخه در دیتابیس ثبت شوند (Model Registry) تا قابلیت Rollback وجود داشته باشد.

### ۹.۸ تفسیرپذیری (Explainability)

استفاده از **SHAP values** برای هر پیش‌بینی، تا در `Forecast Panel` داشبورد نشان داده شود کدام فیچرها (مثلاً IV Rank بالا، یا Skew منفی شدید) بیشترین سهم را در سیگنال تولیدشده داشته‌اند. این هم برای اعتماد کاربر و هم برای انطباق رگولاتوری (توضیح‌پذیری تصمیم‌یار) مهم است.

### ۹.۹ حاکمیت مدل و انطباق رگولاتوری

- هر خروجی مدل که به `SignalGenerator` می‌رود باید همراه با: نسخه‌ی مدل، بازه‌ی اطمینان، و فیچرهای اصلی مؤثر، در `Audit Log` ثبت شود.
- خروجی مدل هرگز مستقیماً سفارش تولید نمی‌کند؛ فقط به‌عنوان یکی از ورودی‌های `RuleEngine` در کنار سیگنال‌های قاعده‌محور (IV Rank، Skew و...) مورد استفاده قرار می‌گیرد، و تصمیم نهایی و تأیید اجرا با کاربر است — منطبق با محدودیت رگولاتوری معاملات کاملاً خودکار که در سند اصلی ذکر شد.

---

اگر بخواهید، در ادامه می‌توانم کد اسکلت کامل و اجراپذیر Python برای این دو ماژول (`backtesting_engine/` و `forecasting_engine/`) را به‌صورت پروژه‌ی چندفایلی هم آماده کنم.
