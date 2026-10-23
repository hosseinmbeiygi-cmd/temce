# بخش A — ناهنجاری هزینه و MDD در `BacktestSimulator` (اولویت اول)

> برچسب‌ها: [خوانده‌شده] = فقط کد خوانده شد | [خوانده‌شده+اجراشده] = کد اجرا و خروجی دیده شد | [حدس از نام] = فقط از نام.
> ماشین: Windows (bash/Git Bash) | مفسر: `Python 3.11.9` (venv پروژه) | DB: PostgreSQL `localhost:5432/my_first_db` (فقط SELECT؛ هیچ نوشتنی روی DB زنده انجام نشد).
> اسکریپت‌های موقت (جدید، بدون تغییر هیچ فایل موجودی): `audit_out/_tmp/partA_probe.py`، `audit_out/_tmp/partA_run.py`، `audit_out/_tmp/partA5_run.py`.
> خروجی خام: `audit_out/_tmp/partA_raw.json`، `audit_out/_tmp/partA5.json`، منحنی‌های اکوییتی: `audit_out/equity_A..D.csv`، جدول fillها: `audit_out/fills_B.csv`.

---

## A1) فرمول واقعی هزینه در `backtesting/engine/broker.py` و `simulator.py` [خوانده‌شده]

مسیر هزینه در `BacktestSimulator` این است: `simulator.run` → `broker.submit_order_sync(order)` → `Broker._compute_commission` → `self.cost_model.compute(side, price, qty)`.

عین سطر `backtesting/engine/broker.py` (شیء `cost_model` که منبع واحد است):

```python
# backtesting/engine/broker.py — در __init__
self.cost_model = IranTransactionCosts(
    broker_pct=commission_pct if commission_pct is not None else BROKER_PCT,
    sell_tax_pct=self.config.sell_tax_pct,
    clearing_fee_pct=self.config.clearing_fee_pct,
)
```

```python
# backtesting/engine/broker.py — _compute_commission
return self.cost_model.compute(side, exec_price, quantity)
```

عین سطر `backtesting/costs/iran_costs.py` (پیاده‌سازی `compute`):

```python
def buy_cost(self, price: float, quantity: int) -> float:
    principal = max(float(price), 0.0) * max(int(quantity), 0)
    broker = max(principal * self.broker_pct, self.min_commission)
    return broker + principal * self.clearing_fee_pct

def sell_cost(self, price: float, quantity: int) -> float:
    principal = max(float(price), 0.0) * max(int(quantity), 0)
    broker = max(principal * self.broker_pct, self.min_commission)
    return broker + principal * self.sell_tax_pct + principal * self.clearing_fee_pct
```

نرخ‌های کانونیک، عین سطر `domain/trading/iran_costs.py:8-10`:

```python
BROKER_PCT = 0.004
CLEARING_FEE_PCT = 0.00085
SELL_TAX_PCT = 0.005
```

**پاسخ صریح:** هر سه جزء اعمال می‌شود — نه فقط کمیسیون ۰.۴٪. خرید = `0.4% + 0.085% = 0.00485` و فروش = `0.4% + 0.5% + 0.085% = 0.00985`. (این با ادعای ممیزی قبلی که می‌گفت «فقط کمیسیون ۰.۴٪» **مغایر** است؛ در مسیر `BacktestSimulator` مالیات و کارمزد تسویه اعمال **می‌شوند**.)

مالیات فروش در `sell_cost` فقط وقتی `normalize_side(side)=="sell"` باشد اعمال می‌شود — عین سطر `backtesting/costs/iran_costs.py`:

```python
def compute(self, side: Any, price: float, quantity: int) -> float:
    """Total transaction cost for a single fill. Tax only on sell (F3)."""
    if normalize_side(side) == "sell":
        return self.sell_cost(price, quantity)
    return self.buy_cost(price, quantity)
```

### لغزش (slippage) — `broker.py::_compute_slippage`
```python
participation_rate = min(quantity / adv, 1.0)  # Cap at 100%
total_slippage_bps = self.config.base_slippage_bps + (
    self.config.volume_impact_factor * participation_rate * 10_000
)
total_slippage_bps = max(
    self.config.min_slippage_bps,
    min(total_slippage_bps, self.config.max_slippage_bps)
)
slippage_per_share = price * (total_slippage_bps / 10_000)
```
پیکربندی پیش‌فرض `IRAN_MARKET_COSTS`: `base_slippage_bps=5.0`، `volume_impact_factor=0.15`، `min_slippage_bps=3.0`، `max_slippage_bps=150.0`.
`exec_price = order.price + slippage` (خرید) یا `order.price - slippage` (فروش)؛ عین سطر `broker.py`.

نکته مهم: `ADV` از `order.daily_volume` می‌آید و اگر نبود از `AdvResolver`؛ در نبود هر دو، `average_daily_volume=1_000_000` (پیش‌فرض کلاس) استفاده و هشدار داده می‌شود.

---

## A2) جدول هر fill برای `B_random_seed7` و تطبیق با `total_cost = 21079467.9` [خوانده‌شده+اجراشده]

همان بازه/نماد ممیزی قبلی: خودرو، ۲۳۹ بار، `2024-01-01..2024-12-29`، سرمایه `1_000_000_000`، `sizing_method="percent"`, `sizing_value=90.0`، استراتژی `MlSignalStrategy`، seed=7 و `preds=random.choice([1.5,-1.5,0,0])`.

خلاصه B: `return_pct=28.2465`, `n_fills=93`, `total_cost=21079467.9` — **دقیقاً بازتولید شد** (تطبیق کامل با `audit_out/step2_robustness.md`).

جدول ۱۵ fill اول (ستون‌ها عین `audit_out/fills_B.csv`؛ `derived_*` از روی `principal = exec_price×qty` و نرخ‌های SSOT محاسبه شد):

| تاریخ | سمت | تعداد | قیمت اجرا | ارزش اسمی | کمیسیون | لغزش | broker (مشتق) | تسویه (مشتق) | مالیات (مشتق) |
|---|---|---|---|---|---|---|---|---|---|
| 1402-10-16 | buy | 315,678 | 2893.765 | 913,497,947.67 | 4,430,465.05 | 13,499,969.67 | 3,653,991.79 | 776,473.26 | 0.0 |
| 1402-10-19 | sell | 26,054 | 2822.503 | 73,537,494.11 | 724,344.32 | 325,595.89 | 294,149.98 | 62,506.87 | 367,687.47 |
| 1402-10-20 | buy | 47,935 | 2930.3632 | 140,466,962.24 | 681,264.77 | 1,071,982.24 | 561,867.85 | 119,396.92 | 0.0 |
| 1402-10-23 | sell | 4,161 | 2967.6602 | 12,348,433.89 | 121,632.07 | 13,897.11 | 49,393.74 | 10,496.17 | 61,742.17 |
| 1402-10-24 | buy | 7,815 | 2995.0 | 23,405,925.21 | 113,518.74 | 39,075.21 | 93,623.70 | 19,895.04 | 0.0 |
| 1402-10-26 | sell | 765 | 2872.2332 | 2,197,258.40 | 21,643.00 | 1,351.60 | 8,789.03 | 1,867.67 | 10,986.29 |
| 1402-10-30 | buy | 1,473 | 2824.0345 | 4,159,802.85 | 20,175.04 | 2,996.85 | 16,639.21 | 3,535.83 | 0.0 |
| 1402-11-01 | sell | 143 | 2753.5634 | 393,759.57 | 3,878.53 | 205.43 | 1,575.04 | 334.70 | 1,968.80 |
| 1402-11-02 | buy | 276 | 2701.4618 | 745,603.45 | 3,616.18 | 403.45 | 2,982.41 | 633.76 | 0.0 |
| 1402-11-03 | sell | 27 | 2616.6804 | 70,650.37 | 695.91 | 35.63 | 282.60 | 60.05 | 353.25 |
| 1402-11-04 | buy | 50 | 2656.3474 | 132,817.37 | 644.16 | 67.37 | 531.27 | 112.89 | 0.0 |
| 1402-11-08 | sell | 5 | 2662.666 | 13,313.33 | 131.14 | 6.67 | 53.25 | 11.32 | 66.57 |
| 1402-11-09 | buy | 10 | 2663.335 | 26,633.35 | 129.17 | 13.35 | 106.53 | 22.64 | 0.0 |
| 1402-11-10 | sell | 1 | 2610.6936 | 2,610.69 | 25.72 | 1.31 | 10.44 | 2.22 | 13.05 |
| 1402-11-11 | buy | 1 | 2613.3064 | 2,613.31 | 12.67 | 1.31 | 10.45 | 2.22 | 0.0 |

جمع کل B (عین `audit_out/_tmp/partA_raw.json` → `B_totals`):

```json
"B_totals": {
  "n_fills": 93,
  "sum_commission": 6123756.97,
  "sum_slippage": 14955710.93,
  "total_cost_comm_plus_slip": 21079467.9,
  "derived_broker": 4684869.78,
  "derived_clearing": 995534.83,
  "derived_tax": 443352.35,
  "derived_sum_broker_clear_tax": 6123756.97,
  "gross_notional": 1171217445.63,
  "cost_as_pct_of_notional": 1.7998
}
```

### تطبیق با `total_cost = 21079467.9`
- **کاملاً می‌خورد.** `total_cost` در اسکریپت ممیزی = `sum(commission) + sum(slippage)`:
  `6,123,756.97 + 14,955,710.93 = 21,079,467.90` ✅
- `sum_commission` خودش = `broker + clearing + tax` مشتق:
  `4,684,869.78 + 995,534.83 + 443,352.35 = 6,123,756.97` ✅ (پس مالیات و تسویه واقعاً اعمال شده‌اند.)

### چرا هزینه کل با تعداد fill متناسب نیست؟
شاهد عددی (عین `partA_raw.json`):

| آزمایش | تعداد fill | هزینه کل | ارزش اسمی کل (gross notional) | هزینه/اسمی |
|---|---|---|---|---|
| A_heuristic | 29 | 21,207,265.6 | 1,170,753,354.81 | 1.81% |
| B_random | 93 | 21,079,467.9 | 1,171,217,445.63 | 1.80% |
| C_foresight | 86 | 21,102,843.6 | 1,171,152,093.61 | 1.80% |
| D_lagged | 86 | 21,081,070.3 | 1,171,197,444.61 | 1.80% |

تعداد fill سه‌برابر تفاوت دارد (۲۹ ↔ ۹۳) ولی هزینه کل فقط ~۰.۶٪ تفاوت دارد. علت: **ارزش اسمی کل تقریباً ثابت است** (~۱.۱۷ میلیارد برای همه) و هزینه نسبت به «ارزش اسمی» است نه «تعداد سفارش». ارزش اسمی توسط **یک خرید غول‌آسای اول** (~۹۱۳ میلیون = ~۷۸٪ کل اسمی) تعیین می‌شود و بقیه fillها به‌سرعت به ۱ سهم می‌رسند (دنبالهٔ هندسی ۳۱۵٬۶۷۸ → ۲۶٬۰۵۴ → ۴۷٬۹۳۵ → ۴٬۱۶۱ → ۷۸۱۵ → … → ۱). پس ۶۴٪ هزینه هم روی همان یک fill اول است (لغزش ۱۳.۵M از ۲۱.۱M).

---

## A3) سایز واقعی هر سفارش؛ `sizing_value=90` چیست؟ [خوانده‌شده+اجراشده]

**پاسخ: `sizing_value=90` = ۹۰٪ «نقدینگی فعلی» (`ctx.cash`) است، نه درصدی از NAV یا سرمایه اولیه.**

عین سطر `backtesting/sizing.py`:

```python
elif self.method == "percent":
    return (capital * self.value / 100.0) / price
```

و اینکه `capital` از کجا می‌آید، عین سطر `backtesting/strategies/base.py`:

```python
def _compute_quantity(self, price: float, **kwargs: Any) -> int:
    if self.ctx:
        qty = self.sizer.calculate(capital=self.ctx.cash, price=price, **kwargs)
```
و `StrategyContext.cash` عین سطر `backtesting/strategies/context.py`:
```python
@property
def cash(self) -> float:
    return self.portfolio.get_cash()
```

**بحرانی‌تر:** سمت **فروش** هم از همین `_compute_quantity(price)` استفاده می‌کند (نه از اندازهٔ پوزیشن). عین سطر `backtesting/strategies/ml_based/ml_signal_strategy.py` (شاخهٔ فروش):

```python
elif predicted_change <= self.sell_threshold:
    if self._position > 0:
        # Close long position
        qty = self._compute_quantity(price)
```

پس «بستن پوزیشن» عملاً فقط ~۱۰٪ پوزیشن را می‌فروشد، چون بعد از خرید اول `cash ≈ 0.09×C` می‌ماند.

**شاهد عددی:** خرید اول ۳۱۵٬۶۷۸ سهم روی قیمت بستهٔ ~۲۸۵۱ (چون `0.9×1e9/2851 ≈ 315,678`) با ارزش اسمی ۹۱۳.۵M؛ بعد از آن cash ≈ ۸۲M و فروش بعدی ۲۶٬۰۵۴ سهم (`0.9×82M/2822 ≈ 26,150` — مطابق). بنابراین سری fillها به ۱ سهم می‌رسد. مقدار واقعی fillها در جدول A2 آمده است. علت اینکه MDD همهٔ آزمایش‌ها یکی است همین است: استراتژی هیچ‌وقت واقعاً از بازار خارج نمی‌شود.

---

## A4) منحنی اکوییتی و چرا MDD = 38.73 [خوانده‌شده+اجراشده]

منحنی‌های کامل در `audit_out/equity_A.csv` … `equity_D.csv` ذخیره شد (۲۳۹ نقطه، ستون‌های `i,timestamp,nav,cash,positions_value`).

MDD محاسبه‌شده از خود فایل‌ها (پیاده‌سازی مستقل):

| آزمایش | NAV اول | NAV آخر | MDD از فایل | min NAV |
|---|---|---|---|---|
| A | 1,000,000,000 | 1,287,616,825.43 | **38.7299%** | 703,055,639.45 |
| B | 1,000,000,000 | 1,282,465,157.10 | **38.7309%** | 700,243,476.12 |
| C | 1,000,000,000 | 1,341,353,702.35 | **38.7307%** | 732,396,537.81 |
| D | 1,000,000,000 | 1,324,624,249.73 | **38.7308%** | 723,262,342.27 |

MDD **خود قیمت خام خودرو** در همان بازه (پیاده‌سازی مستقل روی سری close):

```
price_first = 2744.0
price_last  = 3749.0
raw_price_mdd_pct      = 38.7309
buy_and_hold_mdd_pct   = 38.7309
const_90pct_invested   = 35.492
```

**تأیید می‌شود: MDD 38.73 دقیقاً برابر MDD خود قیمت (buy-and-hold) است** (`38.7309`). علت: استراتژی پس از اولین خرید عملاً همیشه ~۹۰٪ در بازار می‌ماند (بند A3) و NAV آن تقریباً مضربی از قیمت خودرو است؛ لذا افت آن همان افت قیمت است و به سیگنال حساس نیست. `max_drawdown_pct` در `_compute_metrics` مقدار `abs(max_drawdown)` از `DrawdownMetrics` است (عین سطر `services/backtest_service.py`):
```python
all_metrics.setdefault("max_drawdown_pct", round(abs(all_metrics.get("max_drawdown", result.max_drawdown)), 2))
```
پس `38.73` یک کمیت «بازار» است، نه «مهارت استراتژی». این به‌تنهایی اندازه‌گیری MDD را برای مقایسهٔ استراتژی‌ها **بی‌اعتبار** می‌کند.

---

## A5) یک نماد، یک بازه، سه موتور، یک مدل هزینه [خوانده‌شده+اجراشده]

اسکریپت `audit_out/_tmp/partA5_run.py` | خروجی `audit_out/_tmp/partA5.json`. سیگنال یکسان: `random seed7`، مبنای long/flat (`pos=1 if pred>0`، ۹۳ تغییر موقعیت). نرخ هزینه از SSOT: خرید `0.00485`، فروش `0.00985`.

| موتور | بازده | هزینه کل | تعداد معامله | منبع هزینه |
|---|---|---|---|---|
| `BacktestSimulator` (شبیه‌ساز رویدادمحور) | **+28.2465%** | 21,079,467.9 | 93 | SSOT بومی + لغزش (ADV fallback) |
| `VectorizedBacktest` (ناخالص) | **−20.94%** | 0 (بدون قلاب هزینه) | 93 تغییر | ندارد |
| `VectorizedBacktest` + هزینه SSOT (هارنس بیرونی) | **−60.17%** | — | 93 تغییر | هارنس (نه خود موتور) |
| `SignalBacktestEngine` | اجرا نشد (بدون قلاب هزینه) | نرخ سهام `0.003` | — | ثابت در کد |

**نتیجه‌ها هم‌خوان نیستند و علت با خط کد:**

۱. **`VectorizedBacktest` هیچ پارامتر هزینه ندارد.** امضای متد عین سطر `services/backtest_framework.py`:
```python
def run(self, close_prices: list[float], signals: list[int],
        initial_capital: float = 1_000_000_000) -> dict[str, Any]:
```
و نگاشت سیگنال→بازده عین سطر همان فایل:
```python
strategy_returns.append(signals[i - 1] * returns[i])
```
پس «یک مدل هزینه یکسان» اصلاً قابل تزریق نیست؛ بدون هزینه `−20.94%` می‌دهد و با هزینه‌ای که ما بیرون از موتور اعمال کردیم `−60.17%`.

۲. **`SignalBacktestEngine` نرخ را در دیکشنری ثابت نگه می‌دارد و راه تزریق ندارد.** عین سطر `services/signal_backtest_engine.py`:
```python
DEFAULT_TRANSACTION_COSTS = {
    "stock": 0.003,
    ...
```
و مصرف: `costs_pct = self.DEFAULT_TRANSACTION_COSTS.get(market_type, 0.003)`. نسبت به SSOT: رفت‌وبرگشت SSOT = `0.0147`، موتور = `0.003` ⇒ **۴.۹ برابر کم‌برآورد** (`signal_backtest_engine_ratio = 4.9`).

۳. **`BacktestSimulator` با استراتژی یکسان با Vectorized هم‌خوان نیست** چون: (الف) سایز سفارش از cash است و پوزیشن را کامل نمی‌بندد (بند A3) ⇒ عملاً ~۹۰٪ در بازار می‌ماند، در حالی که Vectorized موقعیت‌ها را ۰/۱ می‌چرخاند؛ (ب) لغزش ۱.۵٪ روی خرید اول اعمال می‌شود (زیرا `qty/ADV=315678/1e6=0.316` ⇒ `5 + 0.15×0.316×10000 = 478bps` که به سقف `max_slippage_bps=150` می‌خورد). این دو، تفاوت +28% و −21% را توضیح می‌دهند.

**حکم A5:** سه موتور «همسان‌سازی‌شده» **نیستند**. برای مقایسهٔ معتبر، `VectorizedBacktest` باید ستون هزینه بگیرد و `SignalBacktestEngine` باید از `domain/trading/iran_costs.py` استفاده کند؛ و باگ سایز فروش در `MlSignalStrategy` باید اصلاح شود.

---

## جمع‌بندی بخش A (یافته‌های جدید، همه [خوانده‌شده+اجراشده] جز A1 که [خوانده‌شده] است)

| id | شرح | شدت | فایل:خط | اقدام پیشنهادی |
|---|---|---|---|---|
| A-01 | مالیات فروش و کارمزد تسویه در `BacktestSimulator` **اعمال می‌شوند** (نه فقط کمیسیون ۰.۴٪) | اطلاعاتی (رد ادعای قبلی) | `backtesting/engine/broker.py` __init__ + `backtesting/costs/iran_costs.py` | اصلاح گزارش قبلی |
| A-02 | هزینه کل ~ثابت (۲۱.۰۸–۲۱.۲۱M) چون ارزش اسمی ~ثابت (~۱.۱۷B) است؛ ۶۴٪ هزینه = یک خرید اول | بالا | `partA_raw.json` | گزارش هزینه باید به حجم معامله نرمال شود |
| A-03 | `sizing_value=90` = درصدِ «cash فعلی»؛ سمت فروش هم از cash سایز می‌گیرد ⇒ پوزیشن هرگز کامل بسته نمی‌شود | بحرانی | `backtesting/sizing.py` + `ml_signal_strategy.py` (شاخهٔ sell) | فروش باید از `position` سایز بگیرد |
| A-04 | MDD = 38.73 = MDD خود قیمت (buy-and-hold)؛ حساس به استراتژی نیست | بحرانی | `backtesting/metrics/drawdown_metrics.py` + `services/backtest_service.py` | MDD نسبی به buy-and-hold گزارش شود |
| A-05 | لغزش خرید اول به سقف ۱.۵٪ می‌خورد چون ADV fallback = 1,000,000 و سفارش ~۹۱۳M است | بالا | `backtesting/engine/broker.py::_compute_slippage` | ADV واقعی resolve شود |
| A-06 | سه موتور با یک سیگنال و یک مدل هزینه، نتایج ناهم‌خوان می‌دهند (+28.25% در برابر −20.94%) | بحرانی | `services/backtest_framework.py` / `services/signal_backtest_engine.py` | هزینه به موتورها تزریق شود |
| A-07 | `SignalBacktestEngine` نرخ ۰.۰۰۳ ثابت دارد (۴.۹× کم‌برآورد نسبت به SSOT) | بالا | `services/signal_backtest_engine.py` (DEFAULT_TRANSACTION_COSTS) | استفاده از SSOT |
