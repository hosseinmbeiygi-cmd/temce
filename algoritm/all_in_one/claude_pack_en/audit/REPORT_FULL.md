# گزارش کامل ممیزی قابلیت‌اتکا — تک‌فایل (A تا J)

> **حکم نهایی: غیرقابل‌اتکا** — اعتبار اندازه‌گیری خراب است، مسیر ML عملاً صفر است، و یکپارچگی داده/کنترل‌ها معیوب است.
>
> این فایل همهٔ ممیزی را در **یک فایل** جمع می‌کند: ۱۰ بخش (`part_A.md` … `part_J.md`)، جدول کامل **۴۹ یافته**، شواهد خام و بندهای انجام‌نشده.
>
> توزیع یافته‌ها: ۱۰ بحرانی، ۱۹ بالا، ۷ متوسط، ۶ پایین، ۷ اطلاعاتی.
>
> قواعد: هیچ عدد/نام فایل/شماره خطی ساخته نشده؛ هر ادعا با عین سطر/عین خروجی پشتیبانی شده؛ هیچ فایل موجود پروژه تغییر/حذف نشده؛ هیچ نوشتنی روی DB زنده انجام نشده (فقط SELECT).

## فهرست مطالب

۱. بخش A — ناهنجاری هزینه و MDD در `BacktestSimulator` (اولویت اول)
۲. بخش B — آزمون‌های درست‌ساخته‌شده (جایگزین آزمون‌های ضعیف قبلی)
۳. بخش C — هشت منبع بی‌اعتباری (جدول کامل)
۴. بخش D — ردیابی اعداد و ادعاهای پروژه
۵. بخش E — تست‌ها
۶. بخش F — ML
۷. بخش G — داده
۸. بخش H — امنیت و حقوقی داده
۹. بخش I — ساختار مخزن
۱۰. بخش J — جمع‌بندی
۱۱. پیوست الف — جدول کامل یافته‌ها
۱۲. پیوست ب — شواهد خام و بازتولید

---

# MISSING_ITEMS_REPORT — ممیزی کامل بخش‌های A تا J

> گردآوری‌شده از `audit_out/part_A.md` تا `audit_out/part_J.md`.
> قواعد رعایت‌شده: هیچ عدد/نام فایل/شماره خطی از خود ساخته نشده؛ هر ادعا با عین سطر/عین خروجی پشتیبانی شده؛ هیچ فایل موجودی تغییر/حذف نشده؛ هیچ نوشتنی روی DB زنده انجام نشده (فقط SELECT)؛ رمز/توکن فقط با مسیر و نوع ذکر شده‌اند.
> برچسب‌ها: [خوانده‌شده] / [خوانده‌شده+اجراشده] / [حدس از نام].
> فایل یافته‌ها: `audit_out/findings_new.csv` (۴۹ یافته) | وضعیت هر بخش: `audit_out/progress.md`.

---


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

---

# بخش B — آزمون‌های درست‌ساخته‌شده (جایگزین آزمون‌های ضعیف قبلی)

> [خوانده‌شده+اجراشده] مگر خلافش ذکر شود. اسکریپت: `audit_out/_tmp/partB_run.py`؛ خروجی: `audit_out/_tmp/partB.json`؛ لاگ: `audit_out/_logs/partB.log`.
> ۵ نماد روی بازهٔ واقعی `2024-01-01..2024-12-29` (وپترو ۲۳۸، وساخت ۲۳۹، خودرو ۲۳۹، وسپه ۲۳۸، خبهمن ۲۳۹ بار). هزینه = SSOT (`buy=0.00485`, `sell=0.00985`).
> دو مسیر اجرا شد: (الف) **Simulator واقعی پروژه** با `MlSignalStrategy`، (ب) یک **هارنس long/flat تمیز** که پوزیشن را کامل می‌چرخاند (چون موتور پروژه این کار را نمی‌کند — بخش A).

---

## B1) تصادفی هم‌نوسان (۲۰۰ seed، نسبت حضور = نسبت استراتژی مرجع)

نسبت حضور بازار از پروکسی هیوریستیک خودِ پروژه گرفته شد (ستون `heuristic_in_market_frac`). ۲۰۰ seed، در هر seed دقیقاً `k` کندل تصادفی long.

| نماد | کندل | buy&hold % | frac حضور | k | هارنس تمیز: میانگین | انحراف | صدک۵ | صدک۹۵ | مثبت از ۲۰۰ | Simulator پروژه: میانگین | انحراف |
|---|---|---|---|---|---|---|---|---|---|---|---|
| وپترو | 238 | +45.12 | 0.496 | 118 | **−49.46** | 9.54 | −64.15 | −33.74 | **0/200** | **+42.40** | 2.26 |
| وساخت | 239 | −28.37 | 0.402 | 96 | **−62.42** | 7.47 | −73.35 | −48.95 | **0/200** | −29.37 | 1.24 |
| خودرو | 239 | +36.63 | 0.456 | 109 | **−51.68** | 7.56 | −63.93 | −38.92 | **0/200** | **+33.85** | 2.56 |
| وسپه | 238 | +18.20 | 0.567 | 135 | **−53.42** | 8.19 | −65.46 | −38.08 | **0/200** | **+17.42** | 0.76 |
| خبهمن | 239 | −2.53 | 0.494 | 118 | **−59.26** | 6.87 | −69.32 | −47.06 | **0/200** | −3.36 | 0.81 |

**خوانش:**
۱. با هزینه SSOT، استراتژی تصادفی long/flat در **۱۰۰۰ مورد از ۱۰۰۰** منفی است (میانگین ~−۵۱٪ تا −۶۲٪). پس «تصادفی با هزینه سودآور نباشد» ✅ برقرار است.
۲. اما **Simulator واقعی پروژه** روی همان الگوی موقعیت، میانگین **مثبت** می‌دهد و تقریباً برابر buy&hold (وپترو +42.4 در برابر BH +45.1؛ خودرو +33.9 در برابر BH +36.6). یعنی «baseline تصادفی» در `step2_robustness.md` (آزمایش B = 28.25%) **یک baseline تصادفی نیست، بلکه buy&hold با اهرم ۹۰٪ است** — علتش باگ سایز (بند A3). این آزمون بنیادی سنجش‌ناپذیر می‌شود.

---

## B2) تصادفی روی سری بدون روند

سری با تفریق دریفت روزانه (`r_i − mean(r)`) ساخته شد؛ همان آزمون B1.

| نماد | دریفت حذف‌شده (روزانه) | buy&hold بی‌روند % | هارنس تمیز: میانگین | انحراف | صدک۵ | صدک۹۵ |
|---|---|---|---|---|---|---|
| وپترو | +0.001828 | −5.89 | **−59.12** | 7.42 | −69.65 | −45.63 |
| وساخت | −0.001089 | −7.14 | **−57.47** | 8.59 | −69.21 | −42.54 |
| خودرو | +0.001509 | −4.59 | **−59.57** | 6.69 | −69.69 | −48.52 |
| وسپه | +0.000922 | −5.01 | **−58.70** | 7.28 | −68.82 | −44.84 |
| خبهمن | +0.000086 | −4.51 | **−59.45** | 7.40 | −70.84 | −45.70 |

**نتیجهٔ واقعی:** مطابق انتظار، بازده خالص strongly منفی است و در همهٔ ۵ نماد حول **−۵۸٪ تا −۶۰٪** می‌چرخد؛ این همان «کشش هزینه» است (تعداد زیاد تغییر موقعیت × هزینهٔ رفت‌وبرگشت). پس آزمون روی سری بی‌روند **پاس** می‌شود.

---

## B3) آینده‌بین هم‌تراز با قیمت اجرا

**قاعدهٔ اجرای واقعی موتور:** `BacktestSimulator` سفارشِ `on_bar(bar_t)` را با `order.price = bar_t["close"]` می‌فرستد و `Broker.submit_order_sync` **بی‌درنگ روی همان close** پر می‌کند؛ mark-to-market هم روی همان close. پس برای «هم‌ترازی»، سیگنال باید `close[t+1]` را بخواند (یک‌روز جلوتر از قیمت تصمیم). این دقیقاً همان `preds_c` آزمایش C است.

| نماد | Simulator + استراتژی پروژه % | Simulator + full-flip % | Vectorized ناخالص % | Vectorized Sharpe | مرجع تمیز (ایده‌آل) ناخالص % | مرجع تمیز خالص SSOT % |
|---|---|---|---|---|---|---|
| وپترو | 44.69 | 137.41 | **634.71** | 10.61 | — | 288.60 |
| وساخت | −27.78 | 46.51 | **771.72** | 10.26 | — | 387.16 |
| خودرو | 34.17 | 10.81 | **658.24** | 10.54 | **658.24** | **304.12** |
| وسپه | 17.28 | −13.35 | **263.85** | 8.97 | — | 127.43 |
| خبهمن | −1.27 | −5.94 | **439.79** | 9.13 | — | 205.25 |

`partB.json` عیناً: `"vectorized_gross_pct": 634.71`.

**نتیجه:**
- **در Vectorized: بله، آینده‌بین کاملاً قابل‌سنجش است** (+۲۶۴٪ تا +۷۷۲٪ با Sharpe ~۹–۱۰). مرجع تمیز هم دقیقاً همین را می‌دهد (خودرو: ناخالص `658.24` مطابق کامل).
- **در `BacktestSimulator` با استراتژی خود پروژه: نه** — فقط ۴۴.۷٪ تا −۱.۳٪، یعنی تقریباً buy&hold (دوباره باگ سایز).
- حتی **فول‌فلیپ اصلاح‌شده در Simulator** فقط +۱۳۷٪ … −۵.۹٪ می‌دهد، چون لغزش سقف‌خوردهٔ **۱.۵٪ در هر سمت** روی ۸۶ flip، کل سود را می‌خورد (بند A5 + علت ADV).

---

## B4) آیا `VectorizedBacktest` بررسی «منشأ سیگنال» دارد؟ [خوانده‌شده]

**خیر.** کل متد `run` عیناً:

```python
def run(self, close_prices: list[float], signals: list[int],
        initial_capital: float = 1_000_000_000) -> dict[str, Any]:
    if len(close_prices) < 2 or len(close_prices) != len(signals):
        return {"error": "Data length mismatch"}
    ...
    strategy_returns.append(signals[i - 1] * returns[i])
```

هیچ شرطی روی زمان ساخت سیگنال، هم‌ترازی، یا دادهٔ آینده وجود ندارد؛ تنها اعتبارسنجی، هم‌طول‌بودن آرایه‌هاست.

**پیشنهاد (فقط پیشنهاد) گارد:** «سیگنال باید از داده تا `t-1` ساخته شده باشد». عملی‌ترین پیاده‌سازی، **اجرای مجدد روی دادهٔ بریده (truncated)** است: سیگنال روی `data[:t]` بازساخته و مسیر اکوییتی قبل از `t` مقایسه شود؛ اگر تغییر کرد ⇒ نشت. تست پیشنهادی نوشته شد (خارج از `tests/`):

- فایل: `audit_out/_proposed_tests/test_vectorized_signal_origin.py`
- اجرا: `venv/Scripts/python.exe -m pytest audit_out/_proposed_tests/test_vectorized_signal_origin.py -q`
- نتیجهٔ واقعی: **`2 failed in 1.19s`** (هر دو تست) — یعنی گارد **وجود ندارد**:
```
E  assert 1207113848.0 == 1115143269.0
   ... engine result depends on data beyond the evaluated window — no truncation guard exists
```

---

## B5) شیفت‌تست درست (پروکسی هیوریستیک، چون ML خالی است) [برچسب: پروکسی]

سیگنال پروکسی هیوریستیک با شیفت `+1` و `−1` روی Simulator:

| نماد | base | شیفت +۱ | شیفت −۱ | معاملات base/+1/−1 |
|---|---|---|---|---|
| وپترو | 33.55 | 36.82 | 32.27 | 21/21/22 |
| وساخت | −33.97 | −32.19 | −35.92 | 22/22/22 |
| خودرو | 28.76 | 28.31 | 26.53 | 29/29/30 |
| وسپه | 16.18 | 17.94 | 15.78 | 31/31/32 |
| خبهمن | −1.32 | +0.30 | −1.85 | 27/27/28 |

**خوانش:** مقادیر base با buy&hold هم‌راستا هستند (وپترو BH=+45.1 در برابر base=+33.6؛ خودرو BH=+36.6 در برابر base=+28.8) ⇒ استراتژی عملاً بازار است، نه یک سیگنال جداکننده. اختلاف شیفت‌ها ~۲ واحد درصد و در حد نویز است ⇒ آزمون با پروکسی **نامعین** می‌ماند (مثل ممیزی قبلی). هیچ شاهدی از نشت در این مسیر دیده نشد.

---

## B6) D_lagged_foresight (32.46%) چرا نزدیک C (34.14%)؟ [خوانده‌شده+اجراشده]

عین سطر شیفت در `audit_out/_tmp/opencode/step2.py`:

```python
# D) lagged foresight (shift by 1, no lookahead): yesterday's perfect signal
preds_d = [0.0] + preds_c[:-1]
```

یعنی `preds_d[i] = preds_c[i-1] = sign(close[i] − close[i-1])`. در بار `i`، این سیگنال فقط از `close[i]` (معلوم در همان بار) و `close[i-1]` استفاده می‌کند و موتور روی `close[i]` پر می‌کند ⇒ **نسبت به قاعدهٔ پرکردن همین موتور، آینده‌بینی ندارد.** پس D «واقعاً بدون آینده‌بینی» است.

**اما نزدیک‌بودن D به C تصادفی نیست و نشت هم نیست — مصنوعِ باگ سایز است.** چرا: هر دو C و D در Simulator عملاً ~۹۰٪ در بازار می‌مانند (بند A3)، پس هر دو ≈ buy&hold هستند. روی مسیر **تمیز** (فول‌فلیپ/vectorized) فاصلهٔ C و D بسیار بزرگ می‌شود:

| نماد | C ایده‌آل (خالص SSOT) | D ایده‌آل (خالص SSOT) | فاصله |
|---|---|---|---|
| خودرو | **+304.12%** | **+18.59%** | ~۱۶× |
| وپترو | **+288.60%** | **+47.07%** | ~۶× |

**حکم B6:** D بدون آینده‌بینی است (تأیید)، ولی «D≈C» شاهدی بر مهارت یا بر بی‌خطر بودن نیست؛ مصنوعِ باگ سایزِ A3 است که هر استراتژی را به buy&hold تبدیل می‌کند. اصلاح پیشنهادی: همان اصلاح سایز (A3) + گارد Vectorized (B4)، و سپس تکرار C/D.

---

## جمع‌بندی بخش B

| id | شرح | شدت | فایل:خط | اقدام |
|---|---|---|---|---|
| B-01 | «baseline تصادفی» پروژه (Simulator) در واقع buy&hold است؛ هیچ seed‌ای منفی نمی‌شود | بحرانی | `backtesting/sizing.py` + `ml_signal_strategy.py` | اصلاح سایز + گزارش هزینه |
| B-02 | با هزینه SSOT، تصادفی long/flat در ۱۰۰۰/۱۰۰۰ مورد منفی (هارنس تمیز) | تأییدی | `partB.json` | گزارش اجباری |
| B-03 | سری بی‌روند → خالص ~−۵۹٪ (کشش هزینه) | تأییدی | `partB.json` | — |
| B-04 | آینده‌بین در Vectorized کاملاً قابل‌سنجش (+۲۶۴٪..+۷۷۲٪) ولی در Simulator نه | بحرانی | `services/backtest_framework.py` | گارد (B4) |
| B-05 | `VectorizedBacktest` هیچ بررسی منشأ سیگنال ندارد؛ تست پیشنهادی fail می‌شود | بالا | `services/backtest_framework.py` (run) | افزودن گارد truncation |
| B-06 | لغزش سقف‌خوردهٔ ۱.۵٪/سمت، سود آینده‌بین را در Simulator می‌خورد | بالا | `backtesting/engine/broker.py::_compute_slippage` | ADV واقعی |
| B-07 | D≈C مصنوعِ باگ سایز است، نه نشت | اطلاعاتی | `step2.py` (شیفت) | پس از رفع A3 تکرار شود |

---

# بخش C — هشت منبع بی‌اعتباری (جدول کامل)

> هر ردیف چهار ستون: «وجود دارد؟ | شدت | شواهد (مسیر:خط + عین سطر) | راه‌حل».
> برچسب‌ها: [خوانده‌شده] / [خوانده‌شده+اجراشده] / [حدس از نام].
> ابزارها: `audit_out/_tmp/partC_db.py` (SELECT فقط)، خواندن کد.

---

## C1) قیمت اجرا: آیا سفارش با قیمت همان کندلِ تصمیم پر می‌شود؟

**وجود دارد؟ بله — و بین موتورها ناسازگار.** | شدت: بحرانی

| موتور | پرکردن | شواهد |
|---|---|---|
| `BacktestSimulator` | **همان کندل، روی close** | `simulator.py`: `orders = strategy.on_bar(bar)` سپس `fill = self.broker.submit_order_sync(order)`؛ و `ml_signal_strategy.py` قیمت سفارش را `price = bar.get("close", 0)` می‌گذارد. ⇒ سفارش بار `t` روی `close[t]` پر می‌شود. [خوانده‌شده+اجراشده: `fills_B.csv`] |
| `BacktestEngine` (رویدادمحور) | **کندل بعدی، روی open** | `backtesting/engine/backtest_engine.py`: کامنت `Orders queue and are executed on bar t + 1 at that bar's open price` و کد `fill = self.execution.execute(order, ..., fill_price=bar["open"])` |
| `VectorizedBacktest` | غیرمستقیم: `signals[i-1] * returns[i]` ⇒ موقعیت از `t-1` روی بازده `t` | `services/backtest_framework.py`: `strategy_returns.append(signals[i - 1] * returns[i])` |
| `SignalBacktestEngine` | روز بعد: `entry = hist_data[0].get("open", ...)` | `services/signal_backtest_engine.py` |

**راه‌حل:** یک قاعدهٔ اجرای واحد (همه روی open کندل `t+1`) انتخاب و در همهٔ موتورها اعمال شود؛ آزمون: برای یک استراتژی ثابت، `fill_price` در دو مسیر برابر شود.

---

## C2) ثابت‌های بازار در کد

**وجود دارد؟ بله، با نرخ‌های SSOT ولی «زمان‌دار» فقط در کد مرده.** | شدت: بالا

| مورد | مقدار | مسیر:خط (عین سطر) | زمان‌دار؟ |
|---|---|---|---|
| کمیسیون کارگزار | `0.004` | `domain/trading/iran_costs.py`: `BROKER_PCT = 0.004` | خیر |
| کارمزد تسویه | `0.00085` | `domain/trading/iran_costs.py`: `CLEARING_FEE_PCT = 0.00085` | خیر |
| مالیات فروش | `0.005` | `domain/trading/iran_costs.py`: `SELL_TAX_PCT = 0.005` | خیر |
| لغزش پایه/سقف | `5bps` / `150bps` | `backtesting/engine/broker.py`: `base_slippage_bps: float = 5.0` / `max_slippage_bps: float = 150.0` | خیر |
| ADV پیش‌فرض | `1_000_000` | `backtesting/engine/broker.py`: `average_daily_volume: int = 1_000_000` | خیر |
| حد نوسان روزانه | `0.03` برای ۲۰۲۴! | `backtesting/data/price_limits.py`: `LimitRule("2024-01-01", None, 0.03, "3pct_current")  # example, update with real rule` | **دارد ولی placeholder/احتمالاً غلط** |
| tick | `base_tick=1.0` (ریال) | `backtesting/market/rule_versioning.py`: `tick_size: float = 1.0  # Rial` | خیر |
| تسویه | `T+2` | `backtesting/market/rule_versioning.py`: `t_plus: int = 2  # T+2 for stocks` | خیر |
| سشن‌ها | `08:45 / 09:00 / 12:30` | `backtesting/market/rule_versioning.py`: `preopen="08:45"`, `open="09:00"`, `close="12:30"` | خیر |
| حجم مبنا | — | در `rule_versioning.py`: `volume_base_enabled: bool = True` (فقط پرچم؛ پیاده‌سازی عددی ندیدم) | — |

**مکانیزم `rule_at`:** بله وجود دارد — `backtesting/market/rule_versioning.py` (`MarketRuleSet.is_active(on_date)`، `effective_from/effective_to`) و `backtesting/data/price_limits.py` (`limit_for_date`, `IRAN_LIMIT_HISTORY`).

**اما [خوانده‌شده+اجراشده]:** تابع‌های `tag_bars`/`limit_for_date` **هیچ‌جا فراخوانی نمی‌شوند** (grep در `backtesting services domain api apps` فقط خودِ تعریف را یافت؛ `pipeline` بک‌تست از `BacktestService._load_historical_data` می‌خواند که این تگ را اضافه نمی‌کند). یعنی حد نوسانِ زمان‌دار **کد مرده** است.

**راه‌حل:** فعال‌سازی واقعی `tag_bars` در لود بارها + بازنویسی `IRAN_LIMIT_HISTORY` با قاعدهٔ درست ۲۰۲۴ (نه `0.03` «مثال»)؛ آزمون: هر بار `price_limit_pct` غیرصفر داشته باشد و برای ۲۰۲۴ برابر قاعدهٔ واقعی باشد.

---

## C3) قیمت خام یا تعدیل‌شده

**وجود دارد؟ ترجیح خام.** | شدت: بالا

ستون‌های `brsapi_historical_daily` (از `information_schema.columns`, ۲۳ ستون) [خوانده‌شده+اجراشده]:
```
symbol varchar | date varchar | time varchar | trade_count int | trade_volume bigint |
trade_value float | price_min float | price_max float | price_yesterday float |
price_first float | price_last float | price_last_change float | price_last_change_pct float |
price_close float | price_close_change float | price_close_change_pct float |
created_at timestamp | ins_id varchar | instrument_id varchar | updated_at timestamp |
gregorian_date date | shamsi_date varchar
```
⇒ **هیچ ستون قیمت تعدیل‌شده یا ضریب تعدیل در این جدول نیست.** جدول جدا `daily_adjust_factors(symbol_id, trade_date, adj_factor, computed_at)` با **۶۲۱٬۸۱۸** ردیف و ویو `vw_daily_history_adjusted` وجود دارد (`services/adjusted_price_reader.py`).

**بک‌تست کدام را می‌خواند؟ خام.** عین سطر `services/backtest_service.py::_load_historical_data`:
```python
SELECT date, price_first, price_max, price_min, price_close,
       trade_volume, trade_value
FROM brsapi_historical_daily
WHERE symbol = :symbol AND date >= :start AND date <= :end ...
```
هیچ join‌ای به `daily_adjust_factors` یا `vw_daily_history_adjusted` ندارد ⇒ **بک‌تست ML/Signal از قیمت خام استفاده می‌کند.**

`tests/unit/services/test_adjusted_price_reader.py` [خوانده‌شده]: مسیر جدا و مستقل `adjusted_price_reader` را آزمون می‌کند (نگاشت `jalali↔gregorian`، اسکیل ضرایب، یک کندل در هر روز معاملاتی). دربارهٔ «۱ شکست»: در اجرای ممیزی قبلی یکی از تست‌های DB-backed شکست خورد؛ من در این بخش تک‌تک اجرا نکردم — در بخش E دوباره اجرا می‌شود.

**خودرو در ۲۰۲۴ رویداد شرکتی داشت؟** [خوانده‌شده+اجراشده، `audit_out/_tmp/partC_db.json`]: رویدادهای `corporate_action_events` خودرو:
```
2011-07-23 capital_increase 0.063796
2011-10-31 capital_increase 0.400457
2013-01-08 capital_increase 0.043233
2014-03-17 capital_increase 0.142487
2015-07-21 capital_increase 0.005229
2015-11-24 capital_increase 0.113917
2020-03-24 capital_increase 18.718910
2025-04-22 capital_increase 7.501099
```
⇒ **در ۲۰۲۴ هیچ رویداد شرکتی برای خودرو نیست** (بعدی: ۲۰۲۵-۰۴-۲۲). ضریب تعدیل در بازهٔ اطراف ۲۰۲۴ ثابت است (`0.1176318497` در همهٔ ۲۸۱ ردیف 2023-12-02..2025-01-29) ⇒ درون بازهٔ ۲۰۲۴ اثر ex-date وجود ندارد، پس بک‌تست ۲۰۲۴ خودرو از این جهت آلوده نیست.

نکتهٔ جانبی مهم: `action_type` تنها `capital_increase` است (۵۸۶ ردیف/۱۴۵ نماد) و **همهٔ `dps = 0.00`** ⇒ **رویداد سود نقدی (DPS) ثبت نشده**؛ `corporate_actions` هم **۰ ردیف** دارد. پس تعدیل سود نقدی پوشش داده نشده است.

**راه‌حل:** `_load_historical_data` به `adjusted_price_reader.load_daily_candles(adjusted=True)` وصل شود؛ آزمون: قیمت‌های بک‌تست با `vw_daily_history_adjusted` برابر شوند.

---

## C4) برچسب‌ها (target)

**وجود دارد؟ بله، ولی تعریف واحد نیست.** | شدت: بالا

| محل | تعریف برچسب | افق | قیمت پایه | شواهد |
|---|---|---|---|---|
| `ml/datasets/labeling.py::LabelGenerator.future_return` | `prices.shift(-horizon)/prices - 1` | `horizon=5` پیش‌فرض | **close همان روز `t`** | عین سطر `future = prices.shift(-horizon) / prices - 1` |
| `ml/datasets/labeling.py::binary_direction` | `(shift(-h) > prices)` | h | close `t` | `direction = (future > prices).astype(int)` |
| `ml/datasets/builders.py::DatasetBuilder.load` | `future_return(df["close"] or df["price_close"], horizon=config.get("horizon",5))` | ۵ | close | — |
| `services/signal_backtest_engine.py` | خروجی `_tracker.evaluate_signal` (return از entry=open روز بعد تا exit=close آخر) | `days_forward=30` | **open روز بعد** | `entry_price = hist_data[0].get("open", signal_price)` |

**مشکل:** برچسب ML با close روز `t` ساخته می‌شود، ولی اجرای موتور رویدادمحور روی open روز `t+1` است ⇒ شکاف یک‌روزه؛ روز قفل خرید/فروش و نماد متوقف‌شده در برچسب لحاظ نمی‌شود (در `labeling.py` هیچ اشاره‌ای به session/قفل/توقف نیست).

**راه‌حل:** برچسب بر پایهٔ «قیمت قابل‌اجرای بعدی» (`open[t+1]`→`open[t+1+h]`) ساخته شود و روزهای بی‌معامله/قفل صریحاً مدیریت شوند؛ آزمون: بازده برچسب با بازده معاملهٔ مرجع هم‌خوان باشد.

---

## C5) فیچرها و knowledge_time + دو باگ ثبت‌شده

**وجود دارد؟ بله (کد)، ولی زمان‌آگاهی نامشخص.** | شدت: بالا

`services/feature_engine.py` → ۸ بلوک (IDs 1-115):

| بلوک | IDها | نمونه فیچرها | پنجره | مرجع |
|---|---|---|---|---|
| A: Identity & Data Quality | 1-10 | — | — | `:199` |
| B: Fundamental | 11-25 | — | — | `:228` |
| C: Valuation & Macro | 26-35 | — | — | `:287` |
| D: Daily Trading & Technical | 36-50 | `avg_volume_50`, `volume_spike`, `float_turnover_pct`, `sma_20`, `rsi_14`, `macd_signal`, `atr_14`, `breakout_flag`, `trend_20d` | ۲۰/۵۰ روز | `:325` |
| E: Money Flow | 51-60 | `inst_buy_volume`, `net_inst_volume`, `net_inst_ratio`, `retail_to_inst_ratio` | روز | `:402` |
| F: Microstructure & Queue | 61-75 | — | — | `:437` |
| G: Events & Qualitative | 76-95 | — | — | `:493` |
| H: Scores/Penalty/Decision | 96-115 | — | — | `:521` |

**knowledge_time:** برای حقیقی/حقوقی (`brsapi_historical_real_legal`) و بنیادی/کدال، در کد `feature_engine` هیچ ارجاعی به `knowledge_time`/`published_at`/`created_at` ندیدم؛ `computed_at` فقط در `daily_adjust_factors` است. نرمال‌سازی مقطعی روزانه/کل‌بازه: در این ماژول (که فیچرهای هر نماد را روزانه می‌سازد) ندیدم — [حدس از نام] یکسان‌سازی احتمالاً بالادست انجام می‌شود. winsorize و مقدار گمشده: `_ff = min(max(free_float_pct, 0.0), 100.0)` تنها clamp دیده‌شده است؛ برای گمشده `0.0` جایگزین می‌شود (نه NaN صریح).

**دو باگ `HIDDEN_ERRORS_REPORT`** (`reports/audits/2026-08-25_audit_hidden-errors-report.md` §2.2/§2.3):

- `float_turnover_pct` ۱۰۰× غلط — **رفع شده.** عین سطر فعلی (`services/feature_engine.py`):
```python
float_shares_count = shares_count * _ff / 100.0 if shares_count > 0 else 0
_denom = float_shares_count * last_price
if _denom > 1e-9:
    f["float_turnover_pct"] = round(100 * f["trade_value"] / _denom, 2)
```
- `net_inst_ratio` مخرج غلط — **رفع شده.** عین سطر فعلی:
```python
if float_shares_count > 1e-9:
    f["net_inst_ratio"] = round(f["net_inst_volume"] / float_shares_count * 100, 2)
```
(هر دو اکنون از `shares_count × free_float_pct/100` استفاده می‌کنند، نه از pct خام.) [خوانده‌شده]

---

## C6) survivorship

**وجود دارد؟ احتمالاً بله.** | شدت: بالا | [خوانده‌شده+اجراشده]

`audit_out/_tmp/partC_db.json`:
```json
"survivorship": {
  "distinct_symbols_last_90d": 2407,
  "distinct_symbols_all_time": 2407,
  "symbols_table_rows": 511,
  "symbols_only_before_90d": 0
}
```
⇒ **هیچ نمادی نیست که در تاریخچه داده داشته باشد ولی در ۹۰ روز گذشته نداشته باشد** (`0`). یعنی نماد حذف‌شده/تغییرنام‌یافته در جدول تاریخی **دیده نمی‌شود** — نشانهٔ survivorship bias. جدول `symbols` فقط ۵۱۱ ردیف دارد در برابر ۲۴۰۷ نماد تاریخی ⇒ universe ثبت‌شده هم کامل نیست.

**راه‌حل:** universe آموزش/بک‌تست از snapshot تاریخ‌دار ساخته شود (شامل نمادهای حذف‌شده)؛ آزمون: `distinct_symbols_last_90d < distinct_symbols_all_time`.

---

## C7) تنظیم هایپرپارامتر و شمارش آزمایش

**وجود دارد؟ بله، ولی DSR/PBO به پایپ‌لاین وصل نیست.** | شدت: بالا [خوانده‌شده]

- `ml/models/sweeper.py::HyperparamSweeper`: `GridSearchCV(..., cv=5)` و `RandomizedSearchCV(..., cv=5)` ⇒ **CV پنج‌تایی معمولی (نه purged/embargo، نه walk-forward)** روی سری زمانی ⇒ ریسک نشت.
- `services/cascade_engine.py`: `GeneticOptimizer` + فاز `grid_search` (`PARAM_GRID`) + `genetic_generations=12`.
- **شمارش آزمایش (trial counting):** در `sweeper.py` و `cascade_engine` هیچ شمارندهٔ `n_trials` که به گزارش اعتبار برسد ندیدم.
- **DSR/PBO:** توابع وجود دارند — `backtesting/metrics/deflated_sharpe.py::deflated_sharpe_ratio` و `services/backtest_framework.py::StatisticalValidator.deflated_sharpe/reality_check` — اما grep هیچ **مصرف‌کننده‌ای** در سرویس‌های بک‌تست/گزارش نیافت ⇒ [خوانده‌شده] پیاده‌شده ولی استفاده‌نشده.
- **hold-out نهایی:** در `walk_forward_validator.py` ندیدم؛ `is_reliable = avg_test_accuracy > 0.55 and overfitting < 0.15`.
- **purge/embargo:** فقط `CPCV` در `services/backtest_framework.py` (`embargo_pct: float = 0.01`، `embargo_len = max(1, int(n_total * self.embargo_pct))`). `WalkForwardEngine.split` **هیچ embargo/purge ندارد**. هیچ‌کدام نسبت به افق برچسب کالیبره نشده‌اند (embargo صرفاً ۱٪ طول سری است).

**راه‌حل:** `GridSearchCV` با `TimeSeriesSplit`/CPCV purged، ثبت `n_trials`، و مصرف DSR در گزارش؛ آزمون: هر گزارش شامل `n_trials` و `deflated_sharpe` باشد.

---

## C8) رژیم، ensemble، calibrator، ۱۰ دروازه، بازآموزی خودکار

**وجود دارد؟ بله.** | شدت: متوسط/بالا [خوانده‌شده]

**۱۰ دروازه `services/signal_decision_engine.py`** (از docstring عین کد): 1 Data Quality, 2 Model, 3 Probability, 4 Regime, 5 Consensus, 6 Liquidity, 7 Risk/Reward, 8 Expectancy, 9 Portfolio, 10 Execution.

آستانه‌های گرید (عین کد، `:306-309`):
```
a_plus: min_probability 0.70, min_rr 2.0, min_expectancy 0.20, all_pass_required True
a:      min_probability 0.65, min_rr 1.5, min_expectancy 0.12, max_warnings 1
b:      min_probability 0.60, min_rr 1.0, min_expectancy 0.05, max_warnings 2
watchlist: min_probability 0.55, min_rr 0.0, min_expectancy 0.0
```
آستانهٔ پیش‌فرض احتمال: `base_threshold = 0.55` (`:365`)؛ حداقل انتظار خالص: `cfg.get("minimum_net_expectancy_r", 0.05)` (`:859`). سایر دروازه‌ها از `get_gate_config(gate, market)` خوانده می‌شوند (رژیم/نقدشوندگی/ریسک-بازده/پورتفوی/اجرا — `:268-300`).

**فیت روی چه داده‌ای؟** [حدس از نام برای بخش‌های فیت‌نشدنی]: رژیم/ensemble/calibrator در `services/` ماژول‌های جدا دارند (`services/ensemble_engine.py`, `services/calibration_loop.py`) که در این زمان اجرای کاملشان بررسی نشد؛ در کد این بخش شاهدی از فیت روی دادهٔ آینده **ندیدم** اما **تأیید نکردم**.

**ماشهٔ بازآموزی** (`services/auto_retrain_pipeline.py`): عین کد:
```python
ACCURACY_THRESHOLD = 0.55  # retrain if accuracy drops below 55%
SCHEDULE_DAYS = 7  # retrain at least every 7 days
MIN_SAMPLES_FOR_RETRAIN = 50
_min_accuracy_gain = 0.02
```
و کامنت: `Audit ML-004: a retrain only "sticks" if holdout accuracy improves on the current accuracy by this margin (guards against noise-promotion).` ⇒ **مدل جدید مستقیماً جایگزین نمی‌شود؛** باید ≥ ۰.۰۲ بهتر شود. [خوانده‌شده]

**راه‌حل:** مستندسازی دادهٔ فیت هر ماژول + آزمون منشأ سیگنال (بند B4).

---

## جمع‌بندی بخش C

| id | شرح | شدت | فایل:خط | اقدام |
|---|---|---|---|---|
| C-01 | `BacktestSimulator` روی close همان کندل پر می‌کند؛ `BacktestEngine` روی open روز بعد | بحرانی | `simulator.py`, `backtest_engine.py`, `ml_signal_strategy.py` | یکسان‌سازی قاعدهٔ اجرا |
| C-02 | `IRAN_LIMIT_HISTORY` زمان‌دار ولی **کد مرده** و مقدار ۲۰۲۴ = `0.03` (مثال) | بالا | `backtesting/data/price_limits.py` | فعال‌سازی + قاعدهٔ واقعی |
| C-03 | `rule_versioning` (tick/T+2/session) وجود دارد ولی به بک‌تست وصل نیست | متوسط | `backtesting/market/rule_versioning.py` | اتصال |
| C-04 | بک‌تست قیمت **خام** می‌خواند؛ `vw_daily_history_adjusted` بی‌استفاده | بالا | `services/backtest_service.py::_load_historical_data` | سوئیچ به adjusted |
| C-05 | رویداد فقط `capital_increase`؛ `dps` همه صفر؛ `corporate_actions` صفر ردیف | بالا | جدول‌های DB | افزودن سود نقدی |
| C-06 | برچسب ML با close روز `t` ولی اجرا با open `t+1` | بالا | `ml/datasets/labeling.py` | برچسب قابل‌اجرای بعدی |
| C-07 | `GridSearchCV(cv=5)` روی سری زمانی؛ بدون purge/embargo؛ DSR استفاده‌نشده | بالا | `ml/models/sweeper.py`, `backtest_framework.py` | TimeSeriesSplit/CPCV + DSR |
| C-08 | survivorship: نماد حذف‌شده در تاریخچه نیست (`2407 == 2407`) | بالا | DB | snapshot تاریخ‌دار universe |
| C-09 | ۲ باگ HIDDEN_ERRORS رفع شده (float_turnover_pct, net_inst_ratio) | اطلاعاتی | `services/feature_engine.py` | — |
| C-10 | بازآموزی کورکورانه جایگزین نمی‌کند (`_min_accuracy_gain=0.02`) | مثبت | `services/auto_retrain_pipeline.py` | — |

---

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

---

# بخش E — تست‌ها

> مبنا: لاگ ممیزی قبلی `audit_out/_logs/pytest_full.log` (۳۳٬۸۲۶ خط) و `audit_out/_logs/summary.txt` (اجرای `pytest tests/ -rA`، نتیجهٔ `175 failed, 5876 passed, 7 skipped, 1 error`) + بازاجرای زنده در `2026-10-10`.
> وضعیت محیط بازاجرا: PostgreSQL `localhost:5432/my_first_db` **در دسترس**؛ Redis پورت `6379` **در دسترس** (`redis port open`).

---

## E1) تقسیم ۱۷۵ شکست به سه گروه

خلاصهٔ شمارش از `summary.txt`:
```
87 tests/comprehensive/test_all.py
21 tests/test_backtest_api_integration.py
11 tests/unit/test_rate_limit_middleware.py
 7 tests/unit/services/test_news_read_canary.py
 6 tests/unit/services/test_signal_decision_engine.py
 6 tests/test_phase_engine.py
 6 tests/e2e/test_backtest_api.py
 ...
```

| فایل | تعداد | گروه | دلیل (عین خطای واقعی) |
|---|---|---|---|
| `tests/test_backtest_api_integration.py` | ۲۱ | **محیطی (auth/rate-limit)** | `AssertionError: Expected 200, got 401: {"error":"Authentication required for this endpoint","code":"AUTH_REQUIRED"}` و `assert 429 == 200` |
| `tests/e2e/test_backtest_api.py` | ۶ | **محیطی (auth)** | `AssertionError: Expected 200 or 422, got 401` / `assert 401 == 200` |
| `tests/unit/services/test_signal_decision_engine.py` | ۶ | **منطقی/تست‌کهنه** | `AssertionError: assert <GateVerdict.PASS> == <GateVerdict.BLOCK>` با `reason='رژیم RANGE — شرایط مناسب'`؛ `assert 'RANGE' == 'CRISIS'` |
| `tests/test_forecast_engine_integration.py` | ۲ | **محیطی (auth)** | `assert 401 == 200` |
| `tests/unit/services/test_backtest_service_v2.py` | ۱ | **منطقی (رفتار کد)** | `assert not result.success` ولی سرویس `status='completed'` برمی‌گرداند ⇒ «موفقیتِ خاموش روی دادهٔ خالی» |
| `tests/unit/services/test_adjusted_price_reader.py` | ۱ | **داده/محیط (پیش‌فرض تست)** | `assert 621818 == 0` (تست انتظار جدول فاکتور خالی دارد، ولی `daily_adjust_factors` ۶۲۱٬۸۱۸ ردیف دارد) |
| `tests/integration/test_ml_training_flow.py` | ۱ | **محیطی/داده** | `Result(error='No trained model available for test_model...')` |
| `tests/test_phase_engine.py` | ۶ | **تست‌کهنه** | `AttributeError: 'ScoringEngine' object has no attribute '_smooth_phase'` و `_phase_history` |
| `tests/comprehensive/test_all.py` | ۸۷ | **محیطی (DB/Auth/داده)** | [حدس از نام/الگو] تست‌های end-to-end HTTP نیازمند داده و auth زنده |

**الگوی کلی خطاها (خلاصهٔ ممیزی قبلی):** ۸۱ `assert N == N`، ۵۰ `Response [429]`، ۳۰ `KeyError: 'data'`، ۱۹ `Response [401]`.
⇒ اکثریت غالب **محیطی** (auth/rate-limit/داده) است، نه باگ منطق.

### E2) ده نمونهٔ `assert N == N`
خروجی واقعی (از `pytest_full.log`، خطوط `E assert`):
```
E       assert 6 == 2
E       assert 6 == 10
E       assert 385 == 30
E       assert 19 == 30
E       assert 129 == 10
E       assert 1 == 2
E       assert 1 == 0
E       assert 0 == 1
E           assert 25 == 30
E                   assert 621818 == 0
```
(شمارش کل `assert N == N` در لاگ = **۹۴**؛ اکثریت قاطع `429 == 200` و `401 == 200` هستند.)

---

## E3) بازاجرای زنده (Postgres + Redis در دسترس)

دستور و نتیجهٔ واقعی:

```
python -m pytest tests/unit/services/test_signal_decision_engine.py tests/test_phase_engine.py \
  tests/unit/services/test_backtest_service_v2.py tests/unit/services/test_adjusted_price_reader.py -q
# → 7 failed, 135 passed, 1 skipped  (12.68s)
```
```
python -m pytest tests/test_backtest_api_integration.py tests/e2e/test_backtest_api.py -q
# → 27 failed, 4 passed  (21.43s)
```

**تفاوت با لاگ قبلی:**

| فایل | لاگ قبلی (2026-10-09) | بازاجرا (2026-10-10) | تغییر |
|---|---|---|---|
| `test_signal_decision_engine` | ۶ failed | **۰ failed (پاس شدند)** | ✅ بهتر |
| `test_backtest_service_v2` | ۱ failed | **۰ failed (پاس شد)** | ✅ بهتر |
| `test_phase_engine` | ۶ failed | **۶ failed** | بدون تغییر |
| `test_adjusted_price_reader` | ۱ failed | **۱ failed** | بدون تغییر |
| `test_backtest_api_integration` + `e2e/test_backtest_api` | ۲۷ (۲۱+۶) | **۲۷ failed, 4 passed** | بدون تغییر (بلاکر auth) |

⇒ شکست‌های `signal_decision_engine` و `backtest_service_v2` **ناپایدار/محیطی** بوده‌اند (با همین محیط پاس شدند)، ولی شکست‌های backtest API با وجود Postgres و Redis **باقی است** چون ریشه‌اش **احراز هویت (401)** است، نه دسترسی DB.

---

## E4) تست‌های موجود/غایب برای اعتبارسنجی

| آزمون | در `tests/` هست؟ | مسیر یا «ندارد» |
|---|---|---|
| تصادفی ≈ صفر | **ندارد** (هیچ تستی net-random≈0 را نمی‌سنجد) | `ندارد` (harnes ممیزی در `audit_out/_tmp/partB_run.py`) |
| آینده‌بین رد شود | **جزئی** | `tests/unit/backtesting/test_audit_fixes_regression.py::TestLookAheadBias` — فقط «پر شدن روی open بار بعد» را چک می‌کند؛ منشأ سیگنال را رد نمی‌کند |
| label shuffle | **ندارد** | `ندارد` (grep خالی) |
| canary فیچر | **ندارد** (فقط خبری) | `tests/unit/services/test_news_read_canary.py` (canary خبر، نه فیچر) |
| بقای دفتر | **ندارد** (نزدیک‌ترین‌ها عمومی‌اند) | `ندارد` |
| تطبیق دو مسیر (parity) | **دارد** | `tests/unit/backtesting/test_cost_parity.py`، `tests/unit/backtesting/test_iran_costs.py`، `tests/unit/backtesting/test_engine_runner.py` |

**تست‌های پیشنهادی (نام + شرح یک‌خطی):**
1. `test_random_strategy_net_negative` — استراتژی تصادفی هم‌نوسان با هزینهٔ SSOT باید خالص منفی بدهد.
2. `test_foresight_rejected_by_engine` — سیگنالِ ساخته‌شده از `close[t+1]` باید در همهٔ موتورها به‌عنوان نشت رد شود.
3. `test_label_shuffle_kills_ic` — پس از shuffle برچسب، IC باید ≈۰ شود.
4. `test_feature_canary_tomorrow_return` — افزودن فیچر «بازده فردا» باید در خط لوله شناسایی شود.
5. `test_universe_includes_delisted` — universe بک‌تست باید نماد حذف‌شده داشته باشد.
6. `test_two_engine_cost_parity` — یک سیگنال روی Simulator/Vectorized/SignalBacktestEngine باید هزینهٔ یکسان بدهد.
7. `test_order_book_survival` — دفتر سفارش پس از رویدادهای شرکتی بازسازی شود.

---

## جمع‌بندی بخش E

| id | شرح | شدت | فایل | اقدام |
|---|---|---|---|---|
| E-01 | اکثریت شکست‌ها محیطی (401/429) نه باگ؛ بلاکر auth باقی است | متوسط | `apps/api` | fixture auth در تست‌ها |
| E-02 | `test_phase_engine` ۶ شکست واقعی (AttributeError روی `ScoringEngine._smooth_phase`) | بالا | `tests/test_phase_engine.py` | هم‌راستا کردن تست/کد |
| E-03 | `test_adjusted_price_reader` به‌خاطر داده (factor table پرشده) fail | پایین | `tests/unit/services/test_adjusted_price_reader.py:388` | ساخت fixture خالی |
| E-04 | `backtest_service_v2::test_no_data` رفتار «موفقیت خاموش روی دادهٔ خالی» را نشان می‌دهد (اکنون پاس می‌شود ⇒ تست ناپایدار) | متوسط | `services/backtest_service.py` | صریحاً fail روی دادهٔ خالی |
| E-05 | غیبت تست‌های اعتبارسنجی کلیدی (random≈0، label shuffle، canary فیچر، بقای دفتر) | بالا | `tests/` | افزودن ۷ تست پیشنهادی |

---

# بخش F — ML

> [خوانده‌شده+اجراشده] برای بازرسی آرتیفکت‌ها و آزمایش‌ها؛ [خوانده‌شده] برای کد.

---

## F1) مدل‌های ذخیره‌شده در `models/` و `ArtifactManager`

**وجود دارند.** روی دیسک `ml_artifacts/` شامل **۳۵۹ پوشه** مدل است:
```
212 xgboost | 20 lightgbm | 20 catboost | 18 random_forest | 18 huber_regressor
18 hist_gradient_boosting | 18 extra_trees | 18 bayesian_ridge | 17 stacking_ensemble
```
و جدول `ml_models` هم **۳۵۹ ردیف** دارد، همه با `created_at = 2026-08-02 08:53:54` (یک اجرای انبوه). برای خودرو، پنج خانواده مدل موجود است (`bayesian_ridge_خودرو`, `catboost_خودرو`, `extra_trees_خودرو`, `hist_gradient_boosting_خودرو`, `huber_regressor_خودرو`, و `xgboost_خودرو`).

هر پوشه نسخه‌هایی مثل `v1-a4f806b2/` دارد با `metadata.json` (۳٬۲۳۶ بایت) + `model_pipeline.pkl` (۲۰٬۴۲۷ بایت) و `latest_path.txt`.

**metadata مدل `xgboost_خودرو` (عین JSON):**
```json
"experiment_name": "xgboost-خودرو-20260718",
"created_at": "2026-07-18T22:18:20", "train_samples": 344,
"start_date": "2026-01-20", "end_date": "2026-07-19",
"metrics": {"mean_r2": -0.544574, "mean_directional_accuracy": 0.183032, "mean_mape": 125.589945},
"feature_names": [... 32 features: price + technical ...],
"feature_groups": ["price", "technical"]
```
⇒ خودِ متریک گزارش‌شدهٔ مدل: **دقت جهت ۱۸.۳٪ و R² منفی (−۰.۵۴)**؛ یعنی حتی مدل‌های ذخیره‌شده از شانس جهت‌دهی ضعیف‌ترند.

**علت صفر بودن مسیر `ml_signal` (ریشهٔ C1) [خوانده‌شده+اجراشده]:**
```
ArtifactManager().load_model('xgboost_خودرو')
→ FileNotFoundError [WinError 3] The system cannot find the path specified:
  'C:\\Users\\Iran\\Desktop\\temce\\data\\models\\xgboost_خودرو'
```
`ArtifactManager` ریشهٔ `settings.ml_model_dir` = `cwd/data/models` را می‌خواند، ولی آرتیفکت‌ها در `ml_artifacts/` هستند. لذا `services/backtest_service.py::_inject_ml_predictions`:
```python
model_id = strategy_params.get("model_id", f"xgboost_{symbol}")
...
model_obj, _ = artifact_mgr.load_model(model_id)   # ← FileNotFoundError
...
model = model_registry.create("xgboost")           # ← "Unknown model: xgboost"
```
⇒ مدل پیدا نمی‌شود ⇒ `b["predicted_change_pct"] = 0.0` ⇒ **صفر معامله**. (مدل وجود دارد؛ لودر مسیر اشتباه را می‌گردد.)

(توجه: `models/` پوشهٔ **مدل‌های ORM دیتابیس** است — `models/backtest.py`, `models/codal.py` … — نه آرتیفکت ML. آرتیفکت‌های ML در `ml_artifacts/` هستند.)

**تاریخچهٔ git:** ۴۷۶ کامیت؛ grep روی پیام‌ها چند کامیت مرتبط با ML نشان داد (مثلاً corporate-actions، options backtest). گردآوری «هرگز مدل آموزش داده نشده» رد می‌شود: مدل‌ها در `2026-08-02` ساخته شده‌اند.

---

## F2) مسیر آموزش و آزمایش کوچک [برچسب: آزمایشی، مدل پروژه نیست]

مسیر آموزش: `ml/training/trainer.py` + `services/training_service.py` + `services/ml_signal_connector.py` (که پس از آموزش، `WalkForwardValidator` را اجرا می‌کند). خروجی: پوشهٔ نسخه‌دار در `ml_artifacts/` + ردیف `ml_models`.

**آزمایش کوچک (خودم):** `audit_out/_tmp/partF_run.py` — ۵ نماد، ۲۰۲۴، ۵ فیچر ساده (ret_1, ret_5, ma5_ratio, vol_5, rsi_14)، برچسب = `close[t+5]/close[t]-1`، تقسیم زمانی ۷۰/۳۰، مدل `Ridge(alpha=1)`.

| سنجه | مقدار |
|---|---|
| ردیف‌ها / تست | ۱٬۰۶۸ / ۳۲۱ |
| **Pooled Spearman IC** | **۰.۱۱۸** |
| **RankIC مقطعی روزانه: میانگین** | **۰.۳۰۵** |
| RankIC انحراف معیار | ۰.۴۴۹ (بسیار پرنوسان) |
| **ICIR** | **۰.۶۷۹** (۶۴ روز) |
| IC تصادفی مورد انتظار | ۰.۰ |
| buy&hold ۵ نماد (میانگین) | +۱۳.۸۱٪ |

**خوانش صادقانه:** IC مقطعی روزانه (~۰.۳) با انحراف ۰.۴۵ و فقط ۶۴ روز، **خطای معیار بزرگ** دارد ⇒ قابل‌اتکا نیست. نرخ P/L استراتژی در این هارنس مطمئن محاسبه نشد (۰.۰ خروجی داد) و آن را گزارش نمی‌کنم. **این مدل پروژه نیست** — فقط نشان می‌دهد خط لولهٔ فیچر/برچسب ساده در این بازه، لبهٔ روشنی نمی‌سازد.

مقایسهٔ مفید: خودِ `xgboost_خودرو` پروژه دقت جهت `0.183` گزارش می‌کند (کمتر از شانس).

---

## F3) label shuffle (۳۰ بار) و canary

`audit_out/_tmp/partF3_run.py`، خروجی `audit_out/_tmp/partF3.json`:

| آزمون | نتیجه |
|---|---|
| label shuffle (۳۰ بار، IC) | **میانگین −۰.۰۰۹۷، انحراف ۰.۰۴۸** ⇒ **≈۰ ✅** |
| canary: افزودن «بازده فردا» به‌عنوان فیچر | **IC = ۰.۹۹۹** ⇒ خط لوله نشت را **نگرفت** ❌ |
| `pipeline_caught_canary` | **false** |

⇒ مدل با برچسب تصادفی فرو می‌ریزد (خوب)، اما **هیچ دروازهٔ نشت‌یابی** در خط لوله وجود ندارد و یک فیچر آینده‌بین را بی‌صدا می‌پذیرد (بد).

---

## جمع‌بندی بخش F

| id | شرح | شدت | فایل:خط | اقدام |
|---|---|---|---|---|
| F-01 | ۳۵۹ مدل وجود دارد ولی `ArtifactManager` ریشه را `data/models` می‌گیرد و آرتیفکت‌ها در `ml_artifacts/` ⇒ لودر شکست می‌خورد و ML صفر می‌شود | **بحرانی** | `ml/artifacts.py` + `services/backtest_service.py::_inject_ml_predictions` | یکسان‌سازی مسیر |
| F-02 | مدل‌های موجود دقت جهت ۱۸.۳٪ و R² منفی دارند | بالا | `ml_artifacts/xgboost_خودرو/*/metadata.json` | آموزش مجدد/ارزیابی |
| F-03 | آزمایش Ridge: pooled IC ۰.۱۱۸؛ RankIC روزانه ۰.۳۰۵±۰.۴۴۹ (ICIR ۰.۶۸، ۶۴ روز) | متوسط | `audit_out/_tmp/partF.json` | لبهٔ نامطمئن |
| F-04 | canary (فیچر آینده) بی‌صدا پذیرفته می‌شود (IC ۰.۹۹۹) | بالا | `ml/datasets`, `services/feature_engine.py` | گارد نشت |
| F-05 | label shuffle → IC ≈۰ (خوب) | مثبت | `audit_out/_tmp/partF3.json` | — |

---

# بخش G — داده

> [خوانده‌شده+اجراشده] با SELECT فقط (`audit_out/_tmp/partG_db.py` → `audit_out/_tmp/partG.json`). DB زنده: `localhost:5432/my_first_db`.

---

## G1) فهرست جدول‌های داده بک‌تست/ML (از DB واقعی، نه حدس)

| جدول | وجود دارد؟ | ستون‌های کلیدی | knowledge_time؟ | گذشته بازنویسی می‌شود؟ | تعداد ردیف / بازه |
|---|---|---|---|---|---|
| قیمت روزانه `brsapi_historical_daily` | ✅ | `symbol, date(Jalali varchar), time, trade_count, trade_volume, trade_value, price_min/max/yesterday/first/last/close, gregorian_date, shamsi_date, created_at, updated_at` | ❌ (فقط `created_at`/`updated_at`) | ✅ (updated_at دارد ⇒ upsert بازنویسی می‌کند) | **۵٬۵۵۴٬۶۲۵** |
| حقیقی/حقوقی `brsapi_historical_real_legal` | ✅ | `symbol, date, buy/sell_real/legal_count/volume/value, gregorian_date, shamsi_date, created_at, updated_at` | ❌ | ✅ | **۴٬۸۹۷٬۶۵۹** |
| صف/عمق (order book) | ⚠️ فقط `orderbook_snapshots` (hypertable) | — | ❌ | — | نمونه‌برداری نشد |
| وضعیت نماد | ✅ `brsapi_symbol_details` | — | ❌ | — | **۱۳٬۹۳۳** |
| رویدادهای شرکتی `corporate_action_events` | ✅ | `symbol_id, ex_date, action_type, ratio, dps, source, codal_ref, notes, created_at` | ❌ (`created_at` فقط) | — | **۵۸۶** (فقط `capital_increase`، همه `dps=0`) |
| `corporate_actions` | ✅ ولی **۰ ردیف** | `symbol, action_type, ex_date, record_date, params, applied, source, raw_text` | ❌ | — | **۰** |
| NAV `brsapi_nav_records` | ✅ | — | ❌ | — | **۳٬۵۸۸** |
| ارز `brsapi_currency_history` | ❌ (خطا: `ProgrammingError`) | — | — | — | ستون/جدول متفاوت است |
| سکه `brsapi_gold_coin_history` | ✅ | — | ❌ | — | **۴۴٬۹۶۵** |
| کدال `brsapi_codal_announcements` | ✅ | — | ❌ | — | **۷۸٬۷۸۹** |
| ضریب تعدیل `daily_adjust_factors` | ✅ | `symbol_id, trade_date, adj_factor, computed_at` | ❌ | — | **۶۲۱٬۸۱۸** (بازه `2001-03-25`..`2026-10-04`) |
| اسنپ‌شات آپشن `brsapi_option_snapshots` | ❌ (خطا: `DBAPIError`) | — | — | — | — |

نمونهٔ ردیف واقعی (بدون داده شخصی):
```
brsapi_historical_daily: {symbol:'بزاگرس3', date:'1405-07-15', time:'12:50:39', trade_volume:'15588', price_min:'7790.0', ...}
brsapi_historical_real_legal: {symbol:'آ س پ', date:'1402-11-17', buy_real_count:'1067', buy_legal_count:'6', sell_real_count:'746', ...}
corporate_action_events: {ex_date:'2026-08-15', action_type:'capital_increase', ratio:'0.249395', dps:'0.00',
   notes:'CODAL آگهی ثبت افزایش سرمایه(اصلاحیه) | TSETMC re-based prev close 10320→8260 (f=0.800388, ratio=0.249395)'}
daily_adjust_factors: {symbol_id:'7234567890123459', trade_date:'2026-10-04', adj_factor:'1.0000000000', computed_at:'2026-10-07 11:07:18'}
```

### 🔴 یافتهٔ بحرانی داده: معنای `gregorian_date`
برای خودرو: `date` (که بک‌تست روی آن فیلتر می‌کند) از `1380-01-05` تا `1405-06-22` (تاریخ معاملاتی جلالی) است، ولی `gregorian_date` **`2026-07-16`..`2026-09-14`** و `shamsi_date` ثابت `1405-04-27`/`1405-…` است. عین خروجی:
```
('1402-10-11', 2026-07-18, '1405-04-27', 2744.0)
('1402-10-12', 2026-07-18, '1405-04-27', 2732.0)
('1402-10-13', 2026-07-18, '1405-04-27', 2755.0)
('1402-10-16', 2026-07-18, '1405-04-27', 2851.0)
```
⇒ چند تاریخ معاملاتی جلالی **یک `gregorian_date` مشترک** دارند ⇒ `gregorian_date`/`shamsi_date` **تاریخ sync/ingest است، نه تاریخ معامله**. کل جدول `gregorian_date` بازهٔ `2026-07-15..2026-10-08` دارد (پنجرهٔ سینک).

**اثر:** `services/signal_backtest_engine.py::_fetch_future_prices` صریحاً روی `gregorian_date` فیلتر می‌کند (با این توضیح که «تاریخ واقعی است») — ولی این ستون «زمان سینک» است ⇒ پنجرهٔ «قیمت‌های آینده» بر اساس ترتیب ingest انتخاب می‌شود، نه ترتیب معاملاتی. `AdvResolver` هم همین ستون را با `CURRENT_DATE - 30 days` فیلتر می‌کند.

---

## G2) TimescaleDB: bitemporal یا نسخه‌بندی؟

- Hypertableها عبارت‌اند از: `candlesticks_deprecated, commodity_prices, daily_history_deprecated, daily_real_legal, etf_nav, gold_currency_prices, intraday_trades_deprecated, market_ticks, orderbook_snapshots, shareholders, symbol_snapshots_deprecated`.
- **`brsapi_historical_daily` (جدول اصلی بک‌تست) hypertable نیست.**
- ستون‌های شبه‌knowledge_time فقط در ۹ جدول غیرقیمتی وجود دارد: `fact_financials.valid_from/valid_to`، `fund_insurance_policies.valid_from/valid_to`، `news_*.published_at` — **روی هیچ جدول قیمتی/حقیقی-حقوقی نیست.**
- `brsapi_historical_daily` هم `created_at` و هم `updated_at` دارد ⇒ **upsert گذشته را بازنویسی می‌کند** (بدون نسخه‌بندی).

⇒ **bitemporal نیست.** بازآزمایی دقیق گذشته ممکن نیست (knowledge_time ذخیره نمی‌شود).

---

## G3) نمونهٔ واقعی جدول‌های اصلی
در `audit_out/_tmp/partG.json` → `samples` (۵ ردیف برای هرکدام از `brsapi_historical_daily`, `brsapi_historical_real_legal`, `daily_adjust_factors`, `corporate_action_events`). هیچ داده شخصی/اعتبارنامه‌ای در این جدول‌ها نیست.

---

## G4) چرا ADV برای خودرو resolve نمی‌شود (fallback 1,000,000)؟

**منبع `AdvResolver`:** `backtesting/engine/adv.py` → `SELECT AVG(trade_volume) FROM brsapi_historical_daily WHERE symbol=:sym ... AND gregorian_date >= CURRENT_DATE - INTERVAL '30 days'`.

دلیل fallback در اجرای مستقیم ممیزی:
1. مسیر `BacktestSimulator` **sync** است و نمی‌تواند await کند؛ فقط `self.adv_resolver.peek()` (کش) را می‌خواند. در اجرای مستقیم، `Broker` اصلاً `adv_resolver` ندارد ⇒ `_resolve_daily_volume` مقدار `None` می‌دهد ⇒ fallback `average_daily_volume=1_000_000` (عین سطر `broker.py`: `No ADV resolved for '%s' — using fallback %d`).
2. `adv_resolver.resolve` اگر فراخوانی شود، مقدار واقعی می‌دهد — ولی **مقدارش مشکوک است:**
```
resolve خودرو -> 8423355627     # ~8.4 میلیارد سهم در روز
resolve فولاد -> 3969817853
resolve آ س پ ->  2755101
```
`8.4e9` برای خودرو غیرواقعی است (احتمالاً به‌خاطر ردیف‌های تکراری/سینک‌های متنوع و اینکه پنجره روی `gregorian_date`=زمان سینک است).

⇒ **ناهم‌خوانی شدید هزینه:** در مسیر sync با fallback `1e6`، لغزش به سقف ۱۵۰bps می‌خورد؛ اگر ADV واقعی (`~8.4e9`) تزریق شود، لغزش ≈۰ می‌شود. یعنی هزینهٔ بک‌تست به این وابسته است که آیا resolver pre-warm شده یا نه — تفاوت چند هزاربرابری.

---

## جمع‌بندی بخش G

| id | شرح | شدت | فایل:خط | اقدام |
|---|---|---|---|---|
| G-01 | `gregorian_date`/`shamsi_date` = زمان سینک، نه تاریخ معامله؛ چند تاریخ معاملاتی یک gregorian مشترک دارند | **بحرانی** | جدول `brsapi_historical_daily` | افزودن `trade_date` واقعی |
| G-02 | `_fetch_future_prices` روی `gregorian_date` فیلتر می‌کند (ستون اشتباه) | بحرانی | `services/signal_backtest_engine.py` | فیلتر روی تاریخ معاملاتی |
| G-03 | `brsapi_historical_daily` hypertable نیست و bitemporal/نسخه‌بندی ندارد؛ upsert بازنویسی می‌کند | بالا | DB | افزودن knowledge_time |
| G-04 | ADV sync fallback ۱٬۰۰۰٬۰۰۰ در برابر مقدار resolve‌شدهٔ ~۸.۴e9 ⇒ تفاوت هزینهٔ چند هزاربرابری | بالا | `backtesting/engine/adv.py` + `broker.py` | pre-warm + محاسبهٔ درست ADV |
| G-05 | رویداد شرکتی فقط `capital_increase` و همه `dps=0`؛ `corporate_actions` صفر ردیف | بالا | DB | افزودن سود نقدی |
| G-06 | `brsapi_currency_history` و `brsapi_option_snapshots` با کوئری عمومی خطا دادند (نام ستون متفاوت) | پایین | DB | بازبینی اسکیما |

---

# بخش H — امنیت و حقوقی داده

> فقط مسیر و نوع گزارش می‌شود؛ هیچ مقدار رمزی در خروجی نوشته نشده (مقدارها `***`). [خوانده‌شده+اجراشده] برای اسکن فایل/گیت.

## H1) کلید/رمز/توکن

| محل | نوع یافته | مسیر | وضعیت |
|---|---|---|---|
| `.env` | ۶ کلید حساس **حاضر** (نام‌ها): `SECRET_KEY`, `ENCRYPTION_KEY`, `DB_PASSWORD`, `BRSAPI_API_KEY`, `SMTP_PASSWORD`, `SENTRY_DSN` (مقادیر `***`) | `.env` | در گیت **tracked نیست** (در `.gitignore` خطوط ۱۹-۲۳) |
| `.env.bak.1790980646` | نسخهٔ پشتیبان env (احتمالاً همان کلیدها) | `.env.bak.1790980646` | tracked نیست |
| `.env.production` | env تولیدی | `.env.production` | tracked نیست |
| `crawler_state.json` | **بدون رمز** — فقط شمارنده (`current_day`, `requests_today`, `hits_today`) | `crawler_state.json` | **tracked است** (بی‌خطر) |
| `docker-compose.yml` | هیچ کلید ثابت inline دیده نشد (احتمالاً `env_file`) | `docker-compose.yml` | — |
| کد پایتون (services/core/brsapi/ml/scripts) | هیچ کلید ثابت (grep الگوی `sk-…`/`api_key="…"` بدون نتیجه) | — | ✅ |
| `openrouter/deepseek/deepseek-chat` | **فایل ۰ بایتی** (خالی)؛ کلید ثابت ندارد | `openrouter/deepseek/deepseek-chat` | ✅ |
| زیرساخت امنیت | workflow اسکن رمز + مستندات چرخش | `.github/workflows/secrets-scan.yml`, `docs/secrets-management.md`, `docs/SECRETS_ROTATION_2026-09-16.md`, `core/security/secrets.py`, `integrations/secrets.py` | ✅ موجود |
| تاریخچهٔ گیت | اسکن کاملِ همهٔ کامیت‌ها **انجام نشد** (خارج از بودجه) | — | **بررسی‌نشده** |

**نتیجهٔ H3:** پوشهٔ `openrouter/deepseek` **وجود دارد** ولی `deepseek-chat` یک فایل **۰ بایتی** است؛ **کلید ثابتی ندیدم**.

## H2) منبع داده‌های اسکرپ‌شده و شرایط استفاده

| منبع | مسیر مستند/کد | شرایط استفاده |
|---|---|---|
| BrsApi (سهام/طلا/ارز/کریپتو/IME/کدال) | `docs/brsapi-data-sources.md`، `brsapi/` | **نامشخص** (سند فقط اندپوینت‌ها را فهرست می‌کند) |
| TGJU (اسکرپ) | `docs/CODEBASE_DISCOVERY_OPTIONS_2026-09-16.md` + `src/gold_desk/secondary_source.py` | **نامشخص** |
| Nobitex / TSE / Codal | اسناد `docs/` | **نامشخص** |

هیچ سند «Terms of Service / مجوز بازتوزیع / سیاست robots.txt» برای منابع اسکرپ‌شده پیدا نکردم ⇒ **نامشخص**.

## جمع‌بندی H

| id | شرح | شدت | اقدام |
|---|---|---|---|
| H-01 | `.env` و بکاپ‌ها در گیت نیستند (خوب)؛ اما ۶ کلید حساس روی دیسک هستند | متوسط | اطمینان از عدم اشتراک‌گذاری |
| H-02 | هیچ کلید ثابتی در کد/`openrouter`/`docker-compose` پیدا نشد | — | — |
| H-03 | شرایط استفادهٔ منابع اسکرپ‌شده (BrsApi/TGJU) مستند نشده | متوسط | افزودن سند ToS |
| H-04 | اسکن تاریخچهٔ گیت انجام نشد | اطلاعاتی | اجرای `gitleaks`/workflow موجود |

---

# بخش I — ساختار مخزن

> برچسب استفاده: [خوانده‌شده] اگر import/فراخوانی دیده شد؛ [حدس از نام] اگر نیافتم.

## I1) پوشه‌ها/فایل‌های هم‌پوشان یا موقت

| مورد | وظیفه (یک جمله) | استفاده می‌شود؟ | جایگزینِ کدام |
|---|---|---|---|
| `api/` | لایهٔ روتر/وب‌سوکت (`routers/`, `ws_manager.py`, `job_state.py`) | [حدس از نام] بله — `apps/api` روترها را از اینجا می‌گیرد | موازی با `apps/api/endpoints/` |
| `apps/` | اپلیکیشن‌های اجرایی (`api`, `admin`, `cli`, `gateway`, workers…) | بله (کانون FastAPI) | — |
| `brsapi/BrsApi_Forecasting/` | ظاهراً کلونِ کتابخانهٔ forecasting | **خالی** (هیچ فایلی نداشت) | `BrsApi_Forecasting/` ریشه |
| `BrsApi_Forecasting/` (ریشه) | اپ/کتابخانهٔ مستقل forecasting (`api`, `core`, `contracts`, `main.py`) | [حدس از نام] جدا از پلتفرم اصلی | — |
| `reports/`، `new_reports/`، `symbol_reports/`، `new_symbol_reports/` | چهار پوشهٔ خروجی گزارش | [حدس از نام] نسل‌های مختلف خروجی | هم‌پوشان — باید یکی بماند |
| `src/` | پکیج جایگزین (`domain`, `features`, `forecast_engine`, `forecasting`, `gold_desk`, `indicators`, `entities.py`) | [حدس از نام] بخشی (gold_desk) مستقل | موازی با ریشهٔ `domain/`, `services/` |
| `fix_critical_errors.py` | اسکریپت یک‌بارهٔ اصلاح خطاهای بحرانی | [حدس از نام] نه (اسکریپت اجرایی، import نشده) | کارِ انجام‌شده؛ قابل حذف |
| `fix_test_syntax.py` | اسکریپت یک‌بارهٔ اصلاح سینتکس تست‌ها | [حدس از نام] نه | قابل حذف |
| `gen_all.py` | **۱۵ بایت** (تقریباً خالی) | نه | قابل حذف |
| `mkpages.py` | **۳۰۰ بایت** تولید صفحات | [حدس از نام] نه | قابل حذف/ادغام |
| `funds-all-code.txt` | دامپ کد صندوق‌ها | [حدس از نام] نه (فایل متنی) | قابل حذف |
| `src/core/domain` | — **در `ls src/core` هیچ فایلی نیافتم ⇒ این مسیر ممکن است وجود نداشته باشد** | — | — |

> توجه: به‌دلیل timeout شدن `grep -r` روی کل مخزن، ستون «استفاده می‌شود؟» برای چند مورد با برچسب [حدس از نام] مانده و **تأیید قطعی import انجام نشد**.

## I2) ۱۵ PR و ۱ issue باز

**دسترسی بررسی نشد.** وجود ابزار `gh`/توکن و PRهای باز در این اجرا تأیید نشد؛ `git log` ۴۷۶ کامیت داشت ولی PR باز را نشان نمی‌دهد. ⇒ این بند **اجرا نشد** (دلیل: نبود ابزار/احراز هویت GH در محیط).

## جمع‌بندی I

| id | شرح | شدت | اقدام |
|---|---|---|---|
| I-01 | چهار پوشهٔ گزارش (`reports`/`new_reports`/`symbol_reports`/`new_symbol_reports`) هم‌پوشان | پایین | یکی‌سازی |
| I-02 | اسکریپت‌های یک‌بارهٔ ریشه (`fix_*.py`, `gen_all.py` ۱۵ بایت, `mkpages.py`) | پایین | حذف |
| I-03 | `brsapi/BrsApi_Forecasting` خالی در برابر `BrsApi_Forecasting/` ریشه | پایین | حذف پوشهٔ خالی |
| I-04 | دو لایهٔ API (`api/routers` و `apps/api/endpoints`) | متوسط | مشخص‌کردن نقش‌ها |
| I-05 | ۱۵ PR/۱ issue باز بررسی نشد (بدون دسترسی GH) | اطلاعاتی | اجرا با `gh` |

---

# بخش J — جمع‌بندی

## J1) جدول یکپارچهٔ یافته‌های جدید
کاملِ یافته‌ها در `audit_out/findings_new.csv` (ستون‌ها: `id,severity,area,file,line,description,confidence,suggested_action`) — **۴۹ یافته**: ۱۰ بحرانی، ۱۹ بالا، ۷ متوسط، ۶ پایین، ۷ اطلاعاتی. خلاصهٔ بحرانی‌ها:

| id | شرح | شدت | فایل:خط | اطمینان |
|---|---|---|---|---|
| A-03 | فروش از cash سایز می‌گیرد؛ پوزیشن هرگز بسته نمی‌شود | بحرانی | `ml_signal_strategy.py` | خوانده‌شده+اجراشده |
| A-04 | MDD = MDD خود قیمت (۳۸.۷۳) و به استراتژی حساس نیست | بحرانی | `drawdown_metrics.py` | خوانده‌شده+اجراشده |
| A-06 | سه موتور با یک ورودی، نتیجهٔ متناقض (+۲۸٪ در برابر −۲۱٪) | بحرانی | `backtest_framework.py` | خوانده‌شده+اجراشده |
| B-01 | baseline تصادفی در واقع buy&hold است | بحرانی | `sizing.py` | خوانده‌شده+اجراشده |
| B-04 | آینده‌بین در Vectorized پذیرفته می‌شود | بحرانی | `backtest_framework.py` | خوانده‌شده+اجراشده |
| C-01 | Simulator روی close همان کندل پر می‌کند | بحرانی | `simulator.py` | خوانده‌شده |
| D-03 | دروازهٔ ۹ Fail-OPEN است (ادعای Fail-closed رد می‌شود) | بحرانی | `quant_signal_orchestrator.py:1253` | خوانده‌شده |
| F-01 | مسیر آرتیفکت اشتباه ⇒ سیگنال ML صفر می‌شود | بحرانی | `ml/artifacts.py` | خوانده‌شده+اجراشده |
| G-01 | `gregorian_date` تاریخ سینک است نه تاریخ معامله | بحرانی | `brsapi_historical_daily` | خوانده‌شده+اجراشده |
| G-02 | `_fetch_future_prices` روی ستون اشتباه فیلتر می‌کند | بحرانی | `signal_backtest_engine.py` | خوانده‌شده+اجراشده |

## J2) اصلاحات لازم (به‌ترتیب اولویت)

اول اعتبار اندازه‌گیری، بعد داده، بعد ML:

| اولویت | فایل | تغییر پیشنهادی | آزمونی که باید پاس شود |
|---|---|---|---|
| ۱ | `ml_signal_strategy.py` (شاخهٔ sell) | فروش از پوزیشن باز سایز بگیرد (`self.ctx.position(instrument_id)`)، نه از `cash` | پوزیشن پس از سیگنال فروش = ۰ |
| ۲ | `backtesting/metrics/drawdown_metrics.py` | گزارش MDD نسبی به buy-and-hold | MDD دو استراتژی متفاوت، متفاوت شود |
| ۳ | `services/backtest_framework.py` | افزودن پارامتر هزینه + گارد منشأ سیگنال (ترانکیت) | تست پیشنهادی `audit_out/_proposed_tests/` پاس شود |
| ۴ | `services/signal_backtest_engine.py` | استفاده از `domain/trading/iran_costs.py` و `profit_factor` هم‌راستا | `signal_backtest_engine_ratio == 1.0`؛ `json.dumps` بدون `inf` |
| ۵ | `backtesting/engine/broker.py` + `adv.py` | pre-warm ADV و رفع معنای پنجرهٔ ADV | لغزش خرید اول ≠ سقف ۱.۵% |
| ۶ | `ml/artifacts.py` | ریشهٔ آرتیفکت = `ml_artifacts/` | `load_model('xgboost_خودرو')` موفق شود |
| ۷ | `brsapi_historical_daily` + `signal_backtest_engine.py` | افزودن `trade_date` واقعی و فیلتر روی آن | `_fetch_future_prices` ترتیب معاملاتی درست بدهد |
| ۸ | `services/quant_signal_orchestrator.py:1253` | Fail-closed واقعی در دروازهٔ ۹ | در نبود validator، سیگنال release نشود |
| ۹ | `ml/datasets/labeling.py` | برچسب روی قیمت قابل‌اجرای `t+1` | بازده برچسب با معاملهٔ مرجع هم‌خوان |
| ۱۰ | `services/feature_engine.py` | گارد نشت/فیچر آینده‌بین | canary شناسایی شود |
| ۱۱ | `ml/models/sweeper.py` | `TimeSeriesSplit`/CPCV + DSR | هر گزارش `n_trials` و `deflated_sharpe` داشته باشد |
| ۱۲ | universe بک‌تست | snapshot تاریخ‌دار شامل نماد حذف‌شده | `last_90d < all_time` |
| ۱۳ | `tests/test_phase_engine.py` | هم‌راستا با `ScoringEngine` فعلی | ۶ تست پاس |
| ۱۴ | `tests/` (fixtures) | احراز هویت برای API | ۲۷ تست backtest API پاس |
| ۱۵ | `tests/` | ۷ تست پیشنهادی (بند E4) | افزوده و سبز |

## J3) حکم نهایی

**حکم: غیرقابل‌اتکا** (بدون تغییر نسبت به `RELIABILITY_REPORT.md`، این بار با شواهد جدیدِ بخش‌های A–G).

سه دلیل:
۱. **اعتبارِ اندازه‌گیری از بین رفته است:** هزینهٔ بک‌تست به ADV fallback وابسته و ~ثابت است (۲۱.۰۸–۲۱.۲۱M)، MDD برابر MDD خود قیمت است (۳۸.۷۳)، استراتژی عملاً buy&hold است (باگ سایزِ فروش)، و سه موتور با یک ورودی نتایج متناقض می‌دهند (A-03/A-04/A-06/B-01).
۲. **مسیر ML خالی است:** مسیر آرتیفکت اشتباه است ⇒ سیگنال صفر ⇒ صفر معامله؛ و مدل‌های موجود دقت جهت ۱۸.۳٪ دارند (F-01/F-02). «baseline تصادفی» هم در واقع buy&hold است (B-01).
۳. **یکپارچگی داده و کنترل‌ها معیوب است:** `gregorian_date` تاریخ سینک است نه معامله (G-01/G-02)، رویداد سود نقدی ثبت نشده (C-05)، survivorship (C-08)، و دروازهٔ ۹ Fail-open (D-03).

## J4) «انجام نشد»

| بند | دلیل |
|---|---|
| C6: شمارش صریح فهرست نمادهای حذف‌شده | فقط شمارش تجمیعی انجام شد (`2407 == 2407`)؛ فهرست اسمی استخراج نشد |
| C5: نرمال‌سازی مقطعی/winsorize و knowledge_time بنیادی/کدال/NAV | در بودجهٔ زمانی کد کامل بررسی نشد |
| C8: رفتار کامل رژیم/ensemble/calibrator (فیت روی چه داده‌ای) | فقط دروازه‌ها/آستانه‌ها و ماشهٔ بازآموزی بررسی شد |
| E: بازاجرای کل `tests/` (۱۷۵ شکست) | فقط زیرمجموعهٔ کیفی بازاجرا شد؛ کل suite (۱ ساعت) اجرا نشد |
| F1: تاریخچهٔ کامل git برای آموزش | فقط grep پیام کامیت‌ها؛ تاریخچهٔ کامل اسکن نشد |
| H1: اسکن تاریخی گیت برای رمز | اجرا نشد |
| I2: ۱۵ PR / ۱ issue باز | نبود دسترسی `gh`/احراز هویت |
| A5: اجرای واقعی `SignalBacktestEngine` با هزینهٔ SSOT | بدون قلاب تزریق هزینه امکان‌پذیر نبود؛ فقط نسبت نرخ محاسبه شد |
| G3: نمونه برای همهٔ جدول‌ها | فقط ۴ جدول اصلی نمونه‌برداری شد |

## J5) خلاصهٔ ده‌خطی
۱. بخش A بازتولید کامل شد: هزینه‌ها (کمیسیون+تسویه+مالیات) در واقع اعمال می‌شوند، ولی اندازه‌گیری خراب است.
۲. فروش در `MlSignalStrategy` از cash سایز می‌گیرد ⇒ پوزیشن هیچ‌وقت بسته نمی‌شود ⇒ fillها به ۱ سهم می‌رسند.
۳. به همین دلیل MDD هر آزمایش (۳۸.۷۳) دقیقاً MDD خود قیمت است؛ استراتژی = buy&hold.
۴. هزینهٔ کل به تعداد fill وابسته نیست چون ارزش اسمی ~ثابت (~۱.۱۷B) و ۶۴٪ آن یک خرید اول است.
۵. سه موتور با یک سیگنال، نتایج متناقض می‌دهند؛ Vectorized هیچ قلاب هزینه یا گارد نشت ندارد.
۶. baseline تصادفی پروژه در واقع buy&hold است؛ تصادفیِ درست با هزینه در ۱۰۰۰/۱۰۰۰ اجرا منفی است.
۷. مسیر ML صفر است، چون لودر آرتیفکت مسیر `data/models` را می‌گردد و آرتیفکت‌ها در `ml_artifacts/` هستند.
۸. `gregorian_date` تاریخ سینک است نه معامله؛ `_fetch_future_prices` روی آن فیلتر می‌کند.
۹. دروازهٔ ۹ Fail-open است، survivorship هست، سود نقدی ثبت نشده، و DSR/PBO به پایپ‌لاین وصل نیست.
۱۰. حکم: **غیرقابل‌اتکا** تا زمانی که اصلاحات ۱–۵ جدول J2 انجام و بازسنجی شود.

---

---

# پیوست الف — جدول کامل یافته‌ها

منبع: `audit_out/findings_new.csv` — ستون‌ها: `id,severity,area,file,line,description,confidence,suggested_action` — **۴۹ یافته** (۱۰ بحرانی، ۱۹ بالا، ۷ متوسط، ۶ پایین، ۷ اطلاعاتی).

## یافته‌های بحرانی (۱۰)

| id | دامنه | فایل | خط | شرح | اطمینان | اقدام پیشنهادی |
|---|---|---|---|---|---|---|
| A-03 | backtest | `backtesting/strategies/ml_based/ml_signal_strategy.py` | 100 | sell branch sizes qty from cash not position; position never fully closed -> 1-share decay | read+executed | size sells from open position |
| A-04 | backtest | `backtesting/metrics/drawdown_metrics.py` | - | MDD 38.73 equals raw buy-and-hold price MDD; insensitive to strategy | read+executed | report MDD relative to buy-and-hold |
| A-06 | backtest | `services/backtest_framework.py` | 49 | three engines not comparable: Vectorized has no cost hook; Simulator +28.25% vs Vectorized -20.94% | read+executed | inject cost model into all engines |
| B-01 | backtest | `services/backtest_service.py` | - | random baseline in Simulator is really buy&hold (none of 200 seeds negative) | read+executed | fix sizing then re-baseline |
| B-04 | backtest | `services/backtest_framework.py` | - | foresight measurable in Vectorized (+264%..+772%) but invisible in Simulator | read+executed | add signal-origin guard |
| C-01 | backtest | `backtesting/engine/simulator.py` | 104 | Simulator fills at decision bar close; BacktestEngine fills next bar open - inconsistent | read | unify execution rule |
| D-03 | orchestration | `services/quant_signal_orchestrator.py` | 1253 | Gate 9 is fail-OPEN (portfolio_approved=True) contradicting fail-closed claim | read | true fail-closed |
| F-01 | ml | `services/backtest_service.py` | _inject_ml_predictions | ArtifactManager root=data/models but artifacts in ml_artifacts -> load fails -> ML signal zeroed | read+executed | fix artifact path |
| G-01 | data | `brsapi_historical_daily` | - | gregorian_date/shamsi_date are sync dates not trade dates; multiple trade dates share one gregorian_date | read+executed | add real trade_date |
| G-02 | data | `services/signal_backtest_engine.py` | _fetch_future_prices | future prices filtered on gregorian_date (wrong column, it is sync date) | read+executed | filter on trade date |

## یافته‌های بالا (۱۹)

| id | دامنه | فایل | خط | شرح | اطمینان | اقدام پیشنهادی |
|---|---|---|---|---|---|---|
| A-02 | backtest | `backtesting/engine/broker.py` | - | _compute_slippage caps at 150bps; first buy ~913M triggers full 1.5% slippage from ADV fallback | read+executed | resolve real ADV |
| A-05 | backtest | `backtesting/engine/broker.py` | - | total cost ~constant 21.08-21.21M because gross notional ~1.17B constant; 64% from first fill | read+executed | normalise cost by notional |
| A-07 | backtest | `services/signal_backtest_engine.py` | 124 | DEFAULT_TRANSACTION_COSTS stock=0.003 flat vs SSOT round-trip 0.0147 (4.9x low) | read+executed | use domain/trading/iran_costs.py |
| B-05 | backtest | `services/backtest_framework.py` | run | VectorizedBacktest has no signal-origin/truncation guard; proposed test fails | read+executed | add truncation guard |
| B-06 | backtest | `backtesting/engine/broker.py` | - | _compute_slippage cap eats foresight profits on 86 flips | read+executed | real ADV |
| C-02 | backtest | `backtesting/data/price_limits.py` | 21 | IRAN_LIMIT_HISTORY time-aware but dead code; 2024 rule set to 0.03 as example | read | wire tag_bars and fix rule |
| C-04 | data | `services/backtest_service.py` | _load_historical_data | backtest reads RAW price_close; vw_daily_history_adjusted unused | read+executed | switch to adjusted reader |
| C-05 | data | `database` | - | corporate_action_events only capital_increase, all dps=0; corporate_actions empty | read+executed | add dividend events |
| C-06 | ml | `ml/datasets/labeling.py` | 8 | label uses close[t] while execution uses open[t+1]; locked/suspended days not handled | read | use executable next price |
| C-07 | ml | `ml/models/sweeper.py` | - | GridSearchCV cv=5 on time series (no purge/embargo); DSR defined but unused | read | TimeSeriesSplit/CPCV + DSR |
| C-08 | data | `database` | - | survivorship: distinct_symbols_last_90d == all_time (2407); no delisted symbols | read+executed | dated universe snapshot |
| D-04 | backtest | `services/signal_backtest_engine.py` | - | profit_factor returns inf while AnalyticsEngine floors at 1.0 - inconsistent | read | unify |
| E-02 | tests | `tests/test_phase_engine.py` | 108 | 6 failures: AttributeError ScoringEngine._smooth_phase/_phase_history (stale tests) | read+executed | reconcile test/code |
| E-05 | tests | `tests/` | - | missing validity tests (random approx 0, label shuffle, feature canary, book survival) | read | add proposed tests |
| F-02 | ml | `ml_artifacts/xgboost_khodro` | - | stored xgboost model reports directional accuracy 0.183, R2 -0.545 | read+executed | retrain/evaluate |
| F-04 | ml | `services/feature_engine.py` | - | canary future-return feature accepted silently (IC 0.999) | read+executed | leak guard |
| G-03 | data | `brsapi_historical_daily` | - | main table is not a hypertable; no knowledge_time/versioning; upsert overwrites | read+executed | add knowledge_time |
| G-04 | backtest | `backtesting/engine/adv.py` | - | ADV sync fallback 1,000,000 vs resolved ~8.4e9 for khodro (thousands-x cost swing) | read+executed | pre-warm and fix ADV |
| G-05 | data | `database` | - | corporate_action_events only capital_increase and all dps=0; corporate_actions has 0 rows | read+executed | add dividend events |

## یافته‌های متوسط (۷)

| id | دامنه | فایل | خط | شرح | اطمینان | اقدام پیشنهادی |
|---|---|---|---|---|---|---|
| C-03 | backtest | `backtesting/market/rule_versioning.py` | - | versioned rules (tick/T+2/session) exist but not wired to backtest | read | connect to pipeline |
| D-02 | docs | `docs/quant-signal-goal-assessment.md` | 117 | goal-doc numbers stale (36.73%->38.43%; -4.03%->-3.73%) | read+executed | re-measure |
| E-01 | tests | `tests/test_backtest_api_integration.py` | - | 27 API backtest tests fail on 401 auth despite DB+Redis available | read+executed | auth fixture |
| E-04 | backtest | `services/backtest_service.py` | - | run_backtest returns success on empty data (test flaky) | read+executed | fail explicitly on no data |
| F-03 | ml | `audit_out/_tmp/partF.json` | - | exploratory Ridge: pooled IC 0.118; daily RankIC 0.305+-0.449 (ICIR 0.68) | read+executed | weak edge |
| H-01 | security | `.env` | - | 6 sensitive keys on disk; .env gitignored/untracked (no value printed) | read | .env hygiene |
| H-03 | security | `docs/brsapi-data-sources.md` | - | scraped data ToS undocumented (BrsApi/TGJU) | read | add ToS doc |

## یافته‌های پایین (۶)

| id | دامنه | فایل | خط | شرح | اطمینان | اقدام پیشنهادی |
|---|---|---|---|---|---|---|
| D-01 | docs | `README.md` | 24 | module counts inconsistent (backtesting 275 claimed vs 298 py files; services 103 vs 162) | read | update counts |
| E-03 | tests | `tests/unit/services/test_adjusted_price_reader.py` | 388 | fail: expects empty factor table but daily_adjust_factors has 621818 rows | read+executed | empty fixture |
| I-01 | structure | `reports/` | - | four overlapping report dirs (reports/new_reports/symbol_reports/new_symbol_reports) | read | consolidate |
| I-02 | structure | `gen_all.py` | - | one-off root scripts; gen_all.py is 15 bytes; mkpages.py 300 bytes | read | remove |
| I-03 | structure | `brsapi/BrsApi_Forecasting` | - | empty dir vs root BrsApi_Forecasting app | read | remove empty dir |
| G-06 | data | `database` | - | brsapi_currency_history and brsapi_option_snapshots error on generic column queries (different schema) | read+executed | review schema |

## یافته‌های اطلاعاتی (۷)

| id | دامنه | فایل | خط | شرح | اطمینان | اقدام پیشنهادی |
|---|---|---|---|---|---|---|
| A-01 | backtest | `backtesting/engine/broker.py` | - | sell tax 0.5% and clearing 0.085% ARE applied via cost_model; previous claim of commission-only is wrong | read+executed | correct prior audit note |
| B-02 | backtest | `audit_out/_tmp/partB.json` | - | clean harness random long/flat negative in 1000/1000 runs with SSOT costs | read+executed | mandatory reporting |
| B-03 | backtest | `audit_out/_tmp/partB.json` | - | detrended series net ~-59% (cost drag) | read+executed | document detrended-cost drag as expected, not alpha |
| C-09 | ml | `services/feature_engine.py` | 367 | float_turnover_pct and net_inst_ratio bugs from HIDDEN_ERRORS_REPORT are fixed | read | keep regression test for both features |
| C-10 | ml | `services/auto_retrain_pipeline.py` | 71 | retrain only sticks if holdout accuracy improves by 0.02 (not blind replace) | read | retain 0.02 improvement gate; add metric to report |
| F-05 | ml | `audit_out/_tmp/partF3.json` | - | label shuffle drives IC to ~0 (good) | read+executed | retain as sanity check in model promotion |
| H-02 | security | `openrouter/deepseek/deepseek-chat` | - | 0-byte file, no hardcoded key; no secrets in code/docker-compose | read+executed | exclude empty artifact from packaging |

---

# پیوست ب — شواهد خام و بازتولید

| مسیر | توضیح |
|---|---|
| `audit_out/part_A.md … part_J.md` | ۱۰ بخش ممیزی (منبع همین فایل) |
| `audit_out/findings_new.csv` | جدول ۴۹ یافته (۸ ستون) |
| `audit_out/progress.md` | وضعیت هر بخش + بندهای انجام‌نشده |
| `audit_out/equity_A.csv … equity_D.csv` | منحنی سرمایهٔ چهار اجرای بازتولیدشده (۲۴۰ سطر هرکدام) |
| `audit_out/fills_B.csv` | ریز پرکردن سفارش‌ها در آزمون B (۹۴ سطر) |
| `audit_out/_logs/pytest_full.log` | خروجی خام pytest (شکست‌ها با متن خطا) |
| `audit_out/_logs/partB.log` | خروجی خام آزمون‌های B |
| `audit_out/_logs/validity_harness.out` | خروجی هارنس اعتبارسنجی |
| `audit_out/_tmp/*.py / *.json` | اسکریپت‌ها و JSONهای خام (partA..partG، step1..step2) |
| `audit_out/_proposed_tests/test_vectorized_signal_origin.py` | تست پیشنهادی گارد منشأ سیگنال |
| `audit_out/MISSING_ITEMS_REPORT.md` | ادغام بخش‌های A..J |
| `audit_out/RELIABILITY_REPORT.md` | حکم پیشین (قبل از این ممیزی) |
