# تکمیل بخش ۷ (موتور استراتژی — Strategy Engine)

> ادامه‌ی همان شماره‌گذاری سند اصلی؛ این نسخه جایگزین/الحاقی بخش ۷ است.

---

## ۷.۱ کتابخانه استراتژی‌ها — گسترش‌یافته

علاوه بر استراتژی‌های جدول اصلی (Covered Call، Protective Put، Straddle، Bull/Bear Spread، Iron Condor، Naked)، موارد زیر برای پوشش کامل‌تر نیاز کاربران حرفه‌ای اضافه می‌شود:

| استراتژی | ساختار | کاربرد اصلی |
|---|---|---|
| Iron Butterfly | Short Straddle (K) + Long Put(K−Δ) + Long Call(K+Δ) | مشابه Iron Condor ولی با نقطه اوج سود در یک قیمت واحد؛ مناسب انتظار نوسان بسیار کم |
| Calendar Spread | Short نزدیک‌سررسید + Long دورسررسید (هم Strike) | بهره‌برداری از Theta Decay سریع‌تر قرارداد نزدیک‌تر؛ به Term Structure نوسان حساس است |
| Diagonal Spread | مانند Calendar ولی Strikeهای متفاوت | ترکیب دیدگاه جهت‌دار با بهره از Theta |
| Ratio Spread | Long ۱ واحد + Short ۲ واحد (Strike بالاتر/پایین‌تر) | دیدگاه جهت‌دار محدود با هزینه‌ی پایین یا اعتبار اولیه، ریسک نامتقارن |
| Collar | Long سهم + Long Put + Short Call | محافظت پرتفوی سهام موجود با هزینه‌ی خالص نزدیک صفر |
| Strangle (Long/Short) | Long/Short Call(K2) + Long/Short Put(K1<K2) | مشابه Straddle با هزینه/اعتبار کمتر و بازه‌ی سود/ضرر پهن‌تر |
| Jade Lizard | Short Put(K1) + Short Call(K2) + Long Call(K3>K2) | حذف ریسک سمت بالا با نگه‌داشتن اعتبار دریافتی در صورت K2−K1 کافی |

هر استراتژی در کد به‌صورت الگوی از پیش‌تعریف‌شده (Template) با پارامترهای قابل تنظیم (Strike Offset، تعداد روز تا سررسید، نسبت پایه‌ها) ذخیره می‌شود تا هم در `Strategy Builder` و هم در `Backtest Lab` قابل استفاده باشد.

## ۷.۲ معماری موتور — گسترش‌یافته

معماری پایه‌ی `StrategyLeg` و `StrategyBuilder` در سند اصلی حفظ می‌شود؛ لایه‌های زیر به آن اضافه می‌شوند:

```
StrategyEngine
├── StrategyTemplateLibrary
│     └── تعریف الگوهای آماده (جدول ۷.۱) به‌صورت پارامتریک، قابل نمونه‌سازی با یک کلیک
│
├── StrategyBuilder (موجود در سند اصلی)
│     └── payoff() / breakeven_points()
│
├── GreeksAggregator
│     └── محاسبه‌ی Delta/Gamma/Vega/Theta/Rho ترکیبی برای کل استراتژی
│         (نه فقط Payoff در سررسید، بلکه پروفایل ریسک لحظه‌ای پیش از سررسید)
│
├── SignalGenerator (موجود در سند اصلی، تکمیل در ۷.۳)
│
├── PositionSizer (موجود در سند اصلی، تکمیل در ۷.۴)
│
├── RuleEngine (موجود در سند اصلی، تکمیل در ۷.۵)
│
├── MultiLegOrderCoordinator
│     └── ارسال/لغو هم‌زمان چند پایه با کنترل All-or-None (هماهنگ با OMS بخش ۱۱)
│
├── AdjustmentEngine
│     └── منطق تنظیم/رول کردن استراتژی باز (۷.۶)
│
└── StrategyLifecycleTracker
      └── وضعیت هر استراتژی: PROPOSED → PENDING_APPROVAL → ACTIVE → ADJUSTED → CLOSED
```

### پروفایل ریسک لحظه‌ای (پیش از سررسید)

برخلاف `payoff()` که فقط ارزش ذاتی در سررسید را محاسبه می‌کند، برای نمایش نمودار زنده در `Strategy Builder` باید ارزش فعلی هر پایه (با فرض گذر زمان و نوسان فعلی) هم محاسبه شود:

```python
class GreeksAggregator:
    def __init__(self, pricer: "OptionPricer"):
        self.pricer = pricer

    def portfolio_value_and_greeks(self, legs, S, T, r, sigma_by_leg):
        """
        legs: لیست StrategyLeg
        sigma_by_leg: دیکشنری {leg_index: implied_vol} - هر پایه ممکن است IV متفاوت داشته باشد
        """
        total_value, total_greeks = 0.0, {"delta": 0, "gamma": 0, "vega": 0, "theta": 0, "rho": 0}
        for i, leg in enumerate(legs):
            if leg.option_type == "STOCK":
                sign = 1 if leg.position == "LONG" else -1
                total_value += sign * leg.quantity * S
                total_greeks["delta"] += sign * leg.quantity
                continue

            sigma = sigma_by_leg[i]
            price = self.pricer.black_scholes(S, leg.strike, T, r, sigma, leg.option_type.lower())
            greeks = self.pricer.greeks(S, leg.strike, T, r, sigma, leg.option_type.lower())
            sign = 1 if leg.position == "LONG" else -1
            total_value += sign * leg.quantity * price
            for g in total_greeks:
                total_greeks[g] += sign * leg.quantity * greeks[g]
        return total_value, total_greeks
```

### نمودار Payoff دوگانه در UI

`Strategy Builder` باید دو خط هم‌زمان نشان دهد: (۱) Payoff نهایی در سررسید (خط شکسته، از `payoff()`)، و (۲) ارزش فعلی استراتژی قبل از سررسید با گذر زمان فرضی (خط منحنی، از `GreeksAggregator`) — این تفاوت برای درک اثر Theta روی استراتژی‌های اعتباری بسیار مهم است و در پلتفرم‌های داخلی موجود (صحرا، ایزی‌تریدر) وجود ندارد.

## ۷.۳ SignalGenerator — تکمیل‌شده

منطق تولید سیگنال باید از قوانین ساده (آستانه‌ی IV Rank) به یک امتیازدهی ترکیبی ارتقا یابد:

```python
class SignalGenerator:
    def __init__(self, weights=None):
        self.weights = weights or {"iv_rank": 0.3, "skew": 0.2, "trend": 0.25, "term_structure": 0.15, "dte": 0.1}

    def score(self, market_state: dict) -> dict:
        """
        market_state شامل: iv_rank (0-100)، skew، trend_strength (-1..1)،
        term_structure_slope، days_to_expiry
        خروجی: امتیاز کلی + دسته‌بندی استراتژی پیشنهادی
        """
        s = 0.0
        s += self.weights["iv_rank"] * (market_state["iv_rank"] / 100)
        s += self.weights["skew"] * np.tanh(market_state["skew"])
        s += self.weights["trend"] * market_state["trend_strength"]
        s += self.weights["term_structure"] * np.tanh(market_state["term_structure_slope"])
        dte_factor = 1.0 if 15 <= market_state["days_to_expiry"] <= 45 else 0.5
        s *= dte_factor

        if market_state["iv_rank"] > 70:
            suggestion = "SELL_PREMIUM"   # مثلاً Iron Condor / Short Strangle
        elif market_state["iv_rank"] < 30 and abs(market_state["trend_strength"]) > 0.5:
            suggestion = "BUY_DIRECTIONAL"  # مثلاً Long Call/Put یا Debit Spread
        else:
            suggestion = "NEUTRAL_WAIT"

        return {"score": round(s, 3), "suggestion": suggestion}
```

خروجی این ماژول در فاز اول، فقط **پیشنهاد** است (طبق الزام رگولاتوری Decision Support در سند اصلی) و کاربر باید آن را تأیید یا رد کند؛ ورودی مدل ML (بخش ۹) هم می‌تواند به‌عنوان یکی از فیچرهای این امتیازدهی وارد شود (نه جایگزین آن).

## ۷.۴ PositionSizer — تکمیل‌شده

```python
class PositionSizer:
    def __init__(self, method="fractional_fixed", risk_per_trade_pct=1.0, kelly_cap_pct=25):
        self.method = method
        self.risk_per_trade_pct = risk_per_trade_pct
        self.kelly_cap_pct = kelly_cap_pct

    def size(self, capital, max_loss_per_contract, win_rate=None, win_loss_ratio=None):
        if self.method == "fractional_fixed":
            risk_budget = capital * (self.risk_per_trade_pct / 100)
            return max(int(risk_budget / max_loss_per_contract), 0)

        if self.method == "kelly":
            if win_rate is None or win_loss_ratio is None:
                raise ValueError("Kelly نیازمند win_rate و win_loss_ratio است")
            kelly_fraction = win_rate - (1 - win_rate) / win_loss_ratio
            kelly_fraction = max(min(kelly_fraction, self.kelly_cap_pct / 100), 0)
            risk_budget = capital * kelly_fraction
            return max(int(risk_budget / max_loss_per_contract), 0)

        raise ValueError("روش نامعتبر")
```

نکته‌ی مهم برای بازار ایران: برای استراتژی‌های با ریسک نامحدود (Naked Short)، `max_loss_per_contract` باید بر اساس **Stress Test** (شوک ۲۰٪± سهم پایه، بخش ۱۰ سند اصلی) محاسبه شود، نه صرفاً فاصله تا نزدیک‌ترین Strike، چون در نبود سقف قیمتی نظری، فرض ضرر نامحدود عملاً حجم صفر می‌دهد.

## ۷.۵ RuleEngine — تکمیل‌شده

فراتر از JSON schema ساده‌ی سند اصلی، قوانین باید امکان ترکیب شرط‌های چندگانه (AND/OR) و اقدامات خروج پلکانی را پشتیبانی کنند:

```json
{
  "entry": {
    "all_of": [
      {"iv_rank": {"gt": 70}},
      {"days_to_expiry": {"between": [20, 45]}},
      {"underlying_trend": {"eq": "RANGE_BOUND"}}
    ]
  },
  "exit": {
    "any_of": [
      {"profit_target_pct": 50},
      {"stop_loss_pct": 100},
      {"days_to_expiry": {"lt": 5}},
      {"portfolio_delta_breach": true}
    ],
    "scale_out": [
      {"at_profit_pct": 30, "close_fraction": 0.5},
      {"at_profit_pct": 50, "close_fraction": 1.0}
    ]
  }
}
```

پیاده‌سازی ارزیاب قوانین به‌صورت بازگشتی روی `all_of`/`any_of` تا امکان ترکیب دلخواه شرط‌ها بدون تغییر کد مرکزی فراهم شود.

## ۷.۶ AdjustmentEngine (رول کردن و تعدیل استراتژی) — بخش جدید

قابلیتی که در هیچ‌کدام از پلتفرم‌های داخلی بررسی‌شده وجود ندارد:

- **Rolling**: بستن پایه‌ی نزدیک‌به‌سررسید و باز کردن پایه‌ی مشابه در سررسید دورتر (یا Strike متفاوت)، وقتی قیمت به نزدیکی Short Strike می‌رسد یا DTE به آستانه‌ی خروج می‌رسد.
- **Delta Hedging نیمه‌خودکار**: پیشنهاد خرید/فروش سهم پایه برای خنثی کردن Delta تجمیعی پرتفوی وقتی از حد مجاز کاربر عبور کند (خروجی صرفاً پیشنهاد، اجرا با تأیید کاربر — منطبق با محدودیت رگولاتوری).
- **Defend/Repair پیشنهادی**: برای Iron Condor که یک سمت آن تهدید شده، پیشنهاد خودکار تبدیل به Iron Butterfly یا بستن سمت سالم برای کاهش ریسک.

```python
class AdjustmentEngine:
    def evaluate(self, strategy_state: dict, market_state: dict) -> list[dict]:
        suggestions = []
        if strategy_state["days_to_expiry"] <= 5 and strategy_state["unrealized_pnl_pct"] > 0:
            suggestions.append({"action": "ROLL_FORWARD", "reason": "نزدیکی سررسید با سود جزئی"})

        threatened_leg = strategy_state.get("threatened_leg")
        if threatened_leg and strategy_state["distance_to_threatened_strike_pct"] < 2:
            suggestions.append({
                "action": "DEFEND_SIDE",
                "leg": threatened_leg,
                "reason": "قیمت سهم پایه به Strike تهدیدشده نزدیک شده"
            })

        if abs(strategy_state["portfolio_delta"]) > strategy_state["user_delta_limit"]:
            suggestions.append({"action": "DELTA_HEDGE", "reason": "عبور از حد مجاز Delta تجمیعی"})

        return suggestions
```

## ۷.۷ StrategyLifecycleTracker

هر استراتژی طی چرخه‌ی مشخصی دنبال می‌شود تا هم در داشبورد و هم برای Audit Log قابل ردیابی باشد:

```
PROPOSED → (تأیید کاربر) → PENDING_EXECUTION → (پرشدن همه پایه‌ها) → ACTIVE
ACTIVE → (رویداد AdjustmentEngine + تأیید کاربر) → ADJUSTED → ACTIVE
ACTIVE → (سررسید یا خروج کاربر) → CLOSED
```

وضعیت `PENDING_EXECUTION` مهم است چون در `MultiLegOrderCoordinator` با کنترل All-or-None، ممکن است فقط بخشی از پایه‌ها پر شوند؛ در این حالت سیستم باید بین دو گزینه تصمیم بگیرد: لغو خودکار پایه‌های پرشده (Unwind) یا نگه‌داشتن به‌عنوان موقعیت ناقص با هشدار به کاربر — این رفتار باید در تنظیمات کاربر قابل انتخاب باشد.

## ۷.۸ اتصال به ماژول‌های دیگر

- **به Risk Management (بخش ۱۰)**: `GreeksAggregator` خروجی هر استراتژی را به `Portfolio Greeks` تجمیعی می‌فرستد؛ محدودیت‌های Concentration Limit پیش از تأیید نهایی هر استراتژی جدید بررسی می‌شود (پیشگیری، نه فقط هشدار پس از وقوع).
- **به Backtesting Engine (بخش ۸)**: دقیقاً همان نمونه از `StrategyBuilder`/`RuleEngine`/`AdjustmentEngine` در `StrategyRunner` بک‌تست فراخوانی می‌شود تا Parity کامل بین بک‌تست و اجرای زنده حفظ شود.
- **به ML/Forecasting (بخش ۹)**: خروجی احتمالاتی مدل به‌عنوان یک فیچر اضافه در `SignalGenerator.score()` وارد می‌شود، با وزن قابل تنظیم، نه به‌عنوان تصمیم مستقل.

---

اگر بخواهید، می‌توانم کتابخانه‌ی کامل الگوهای استراتژی (۷.۱) را هم به‌صورت فایل JSON/Python آماده و قابل بارگذاری در `StrategyTemplateLibrary` تولید کنم.
