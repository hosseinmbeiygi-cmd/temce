<div dir="rtl">

# سیستم بک‌تست چندبازاری (Multi-Market Backtesting System)

**Iran Market Backtesting Engine** — موتور بک‌تست رویدادمحور با پشتیبانی از چند بازار، ریزساختار بازار، مدل‌سازی عامل‌محور (ABM)، و بهینه‌سازی پیشرفته استراتژی‌ها.

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-009688)](https://fastapi.tiangolo.com)
[![NumPy](https://img.shields.io/badge/NumPy-1.24%2B-orange)](https://numpy.org)

---

## فهرست مطالب

- [نمای کلی](#نمای-کلی)
- [معماری سیستم](#معماری-سیستم)
- [اجزای اصلی](#اجزای-اصلی)
- [موتور شبیه‌سازی (Simulator)](#موتور-شبیه‌سازی-simulator)
- [موتور بازپخش (Replay Engine)](#موتور-بازپخش-replay-engine)
- [خط زمانی یکپارچه (Unified Timeline)](#خط-زمانی-یکپارچه-unified-timeline)
- [موتور بازار (Market Engine)](#موتور-بازار-market-engine)
- [موتور قوانین بازار (Market Rule Engine)](#موتور-قوانین-بازار-market-rule-engine)
- [شبیه‌ساز اجرا (Execution Simulator)](#شبیه‌ساز-اجرا-execution-simulator)
- [مدل صف (Queue Model)](#مدل-صف-queue-model)
- [مدل ایمپکت قیمت (Impact Model)](#مدل-ایمپکت-قیمت-impact-model)
- [کالیبراسیون ریزساختار](#کالیبراسیون-ریزساختار)
- [موتور تحلیل (Analytics Engine)](#موتور-تحلیل-analytics-engine)
- [معیارهای ریسک (Risk Metrics)](#معیارهای-ریسک-risk-metrics)
- [Deflated Sharpe Ratio](#deflated-sharpe-ratio)
- [موتور آزمایش (Experiment Engine)](#موتور-آزمایش-experiment-engine)
- [مدل‌سازی عامل‌محور (ABM)](#مدل‌سازی-عامل‌محور-abm)
- [تولید Alpha](#تولید-alpha)
- [مدل هزینه معاملات](#مدل-هزینه-معاملات)
- [اندازه‌گیری پوزیشن (Position Sizing)](#اندازه‌گیری-پوزیشن-position-sizing)
- [اعتبارسنجی (Validation)](#اعتبارسنجی-validation)
- [ترکیب‌کننده استراتژی (Strategy Composer)](#ترکیب‌کننده-استراتژی-strategy-composer)
- [موتور بصری‌سازی (Visualization)](#موتور-بصری‌سازی-visualization)
- [API Endpoints](#api-endpoints)
- [نمونه استفاده](#نمونه-استفاده)
- [ساختار فایل‌ها](#ساختار-فایل‌ها)
- [قوانین بازار نسخه‌دار (Versioned Market Rules)](#قوانین-بازار-نسخه‌دار-versioned-market-rules)
- [رویدادهای شرکتی و قیمت تعدیل‌شده (Corporate Actions)](#رویدادهای-شرکتی-و-قیمت-تعدیل‌شده-corporate-actions)
- [دفتر کل پرتفوی (Portfolio Ledger)](#دفتر-کل-پرتفوی-portfolio-ledger)
- [مدیریت ریسک پیش‌از-معامله (Pre-Trade Risk)](#مدیریت-ریسک-پیش‌از-معامله-pre-trade-risk)
- [نرخ بدون ریسک پویا و تورم (Dynamic Risk-Free Rate)](#نرخ-بدون-ریسک-پویا-و-تورم-dynamic-risk-free-rate)
- [شناسایی رژیم بازار (Regime Detection)](#شناسایی-رژیم-بازار-regime-detection)
- [تکرارپذیری کامل (Reproducibility & Run Manifest)](#تکرارپذیری-کامل-reproducibility--run-manifest)
- [جلوگیری از Look-Ahead Bias](#جلوگیری-از-look-ahead-bias)
- [بهاپذیری نمادها (Survivorship Bias)](#بهاپذیری-نمادها-survivorship-bias)
- [اجرا موازی و بهینه‌سازی عملکرد](#اجرا-موازی-و-بهینه‌سازی-عملکرد)
- [اتریبیوشن و تحلیل مبنا (Attribution & Benchmark)](#اتریبیوشن-و-تحلیل-مبنا-attribution--benchmark)
- [نکات قابل بهبود](#نکات-قابل-بهبود)
- [نقشه راه ارتقا](#نقشه-راه-ارتقا)

---

## نمای کلی

سیستم بک‌تست یک موتور رویدادمحور است که برای شبیه‌سازی دقیق معاملات در بازارهای مختلف ایران طراحی شده است. این سیستم قادر است:

- **۱۰۰ میلیون رویداد** در هر اجرا پردازش کند
- **بیش از ۱۰۰۰ نماد** را هم‌زمان مدیریت کند
- **قوانین متفاوت هر بازار** را بدون تغییر در هسته موتور اجرا کند
- **ریزساختار بازار** (صف، ایمپکت، حراج، نقدینگی پنهان) را شبیه‌سازی کند
- **هزینه‌های واقعی معاملات** (کارمزد، اسپرد، ایمپکت، لغزش) را محاسبه کند
- **آزمایش‌های آماری** (Grid Search, Walk-Forward, Monte Carlo) اجرا کند

---

## معماری سیستم

```
┌─────────────────────────────────────────────────────────────────┐
│                    Backtesting System Architecture               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              Historical Data Lake                     │       │
│  │         (Parquet / Arrow / InMemory)                  │       │
│  └──────────────────────┬───────────────────────────────┘       │
│                          │                                       │
│  ┌──────────────────────▼───────────────────────────────┐       │
│  │              Data Normalization                       │       │
│  └──────────────────────┬───────────────────────────────┘       │
│                          │                                       │
│  ┌──────────────────────▼───────────────────────────────┐       │
│  │              Event Builder                            │       │
│  │         (Trade / Quote / Auction)                     │       │
│  └──────────────────────┬───────────────────────────────┘       │
│                          │                                       │
│  ┌──────────────────────▼───────────────────────────────┐       │
│  │         Unified Event Timeline                        │       │
│  │        (sorted by timestamp + priority)               │       │
│  └──────────────────────┬───────────────────────────────┘       │
│                          │                                       │
│  ┌──────────────────────▼───────────────────────────────┐       │
│  │              Replay Engine                            │       │
│  │  ┌────────────┬────────────┬────────────┐            │       │
│  │  │  Market    │ Strategy   │   Risk     │            │       │
│  │  │  Engine    │ Engine     │   Engine   │            │       │
│  │  ├────────────┼────────────┼────────────┤            │       │
│  │  │  Micro-    │ Execution  │ Corporate  │            │       │
│  │  │  structure │ Simulator  │ Actions    │            │       │
│  │  └─────┬──────┴─────┬──────┴─────┬──────┘            │       │
│  │        │            │            │                    │       │
│  │  ┌─────▼────────────▼────────────▼──────┐            │       │
│  │  │         Portfolio Engine             │            │       │
│  │  └──────────────────┬───────────────────┘            │       │
│  │                      │                               │       │
│  │  ┌──────────────────▼───────────────────┐            │       │
│  │  │         Analytics Engine             │            │       │
│  │  └──────────────────────────────────────┘            │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              Experiment Engine                        │       │
│  │    (Grid Search / Walk-Forward / Monte Carlo)         │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              ABM Simulation                           │       │
│  │    (Market Maker / Noise Trader / Trend Follower)     │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### اجزای اصلی

| لایه | فایل | وظیفه |
|------|------|--------|
| **Data Lake** | `backtesting/engine/data_layer.py` | ذخیره و بارگذاری داده‌های تاریخی |
| **Event Builder** | `backtesting/engine/event_builder.py` | تبدیل داده‌ها به رویدادهای استاندارد |
| **Unified Timeline** | `backtesting/engine/unified_timeline.py` | خط زمانی مرتب‌شده از تمام رویدادها |
| **Replay Engine** | `backtesting/engine/replay_engine.py` | هسته شبیه‌سازی — مدیریت clock و dispatch |
| **Market Engine** | `backtesting/market/market_engine.py` | نگهداری state بازار برای هر نماد |
| **Rule Engine** | `backtesting/market/rule_engine.py` | اعمال قوانین هر بازار |
| **Execution Simulator** | `backtesting/execution/` | شبیه‌سازی اجرای سفارش |
| **Microstructure** | `backtesting/microstructure/` | ریزساختار بازار |
| **Portfolio Engine** | `backtesting/engine/portfolio.py` | مدیریت دارایی، margin، PnL |
| **Risk Engine** | `backtesting/engine/risk.py` | کنترل ریسک |
| **Analytics Engine** | `backtesting/analytics/engine.py` | محاسبه معیارهای عملکرد |
| **Experiment Engine** | `backtesting/experiment/engine.py` | مدیریت آزمایش‌ها |
| **ABM** | `backtesting/abm/` | مدل‌سازی عامل‌محور |

---

## موتور شبیه‌سازی (Simulator)

**فایل:** `backtesting/engine/simulator.py`

موتور اصلی بک‌تست که استراتژی را روی داده‌های تاریخی اجرا می‌کند.

### ویژگی‌ها

- اجرای ناهمزمان (async) برای عملکرد بهتر
- پشتیبانی از لغو اجرا (cancel_event)
- محاسبه mark-to-market در هر بار
- محاسبه NAV، وجه نقد و ارزش پوزیشن‌ها

### نحوه عملکرد

```python
class BacktestSimulator:
    def __init__(self, broker=None, portfolio=None, commission_pct=None, slippage_bps=None):
        self.broker = broker or Broker(commission_pct=commission_pct, slippage_bps=slippage_bps)
        self.portfolio = portfolio or PortfolioManager()

    async def run(self, strategy, initial_capital=1_000_000_000, data=None, cancel_event=None):
        self.portfolio.reset(initial_capital)
        strategy.reset()

        equity_curve = []
        all_fills = []

        for bar in data:
            if cancel_event and cancel_event.is_set():
                break

            # دریافت سفارشات از استراتژی
            orders = strategy.on_bar(bar)

            # اجرای سفارشات
            for order in orders:
                fill = await self.broker.submit_order(order)
                if fill:
                    await self.portfolio.update_fill(fill)
                    all_fills.append(fill)

            # محاسبه mark-to-market
            await self.portfolio.mark_to_market({instrument_id: close_price})

            # ذخیره NAV
            equity_curve.append(EquityPoint(
                timestamp=bar.get("timestamp"),
                nav=self.portfolio.get_nav(),
                cash=self.portfolio.get_cash(),
                positions_value=self.portfolio.get_positions_value(),
            ))

        return BacktestResult(
            strategy_name=strategy.__class__.__name__,
            initial_capital=initial_capital,
            final_capital=self.portfolio.get_nav(),
            total_return=self.portfolio.get_nav() - initial_capital,
            total_return_pct=((self.portfolio.get_nav() / initial_capital) - 1) * 100,
            total_trades=len(all_fills),
            equity_curve=equity_curve,
            trades=all_fills,
        )
```

### نمونه استفاده

```python
from backtesting.engine.simulator import BacktestSimulator
from backtesting.strategies.base import BaseStrategy

class MyStrategy(BaseStrategy):
    def on_bar(self, bar: dict) -> list[OrderEvent]:
        if bar["close"] > bar["sma_20"]:
            return [OrderEvent(instrument_id="IRAN123", side="buy", quantity=1000)]
        return []

async def run():
    simulator = BacktestSimulator()
    result = await simulator.run(
        strategy=MyStrategy(),
        initial_capital=1_000_000_000,
        data=historical_bars,
    )
    print(f"Return: {result.total_return_pct:.2f}%")
```

---

## موتور بازپخش (Replay Engine)

**فایل:** `backtesting/engine/replay_engine.py`

موتور بازپخش رویدادمحور با پشتیبانی از ریزساختار.

### ویژگی‌ها

- مدیریت clock مجازی
- dispatch رویدادها به موتورهای مختلف
- chunk loading از data lake
- پشتیبانی از ۱۰۰ میلیون رویداد

---

## خط زمانی یکپارچه (Unified Timeline)

**فایل:** `backtesting/engine/unified_timeline.py`

### ویژگی‌ها

- **مرتب‌سازی بر اساس `(timestamp, priority)`** — حل هم‌زمانی رویدادها
- **فیلتر بر اساس نماد، بازار، نوع رویداد، بازه زمانی**
- **پشتیبانی از streaming** — پردازش دسته‌ای برای حافظه کم
- **آمار تجمیعی** — تعداد رویدادها، بازه زمانی، توزیع نمادها

### ساختار رویداد

```python
@dataclass
class MarketEvent:
    event_id: str
    timestamp: datetime
    instrument_id: str
    market_id: str
    event_type: str  # TRADE, QUOTE, AUCTION, SESSION_START, etc.
    payload: dict[str, Any]
    priority: int = 0
```

### نمونه استفاده

```python
from backtesting.engine.unified_timeline import UnifiedTimeline

timeline = UnifiedTimeline()
timeline.add_events(events)

# فیلتر بر اساس نماد
tse_events = timeline.filter_by_market("tse")

# فیلتر بر اساس بازه زمانی
q1_events = timeline.filter_by_time_range(start, end)

# دریافت آمار
stats = timeline.get_stats()
print(f"Total events: {stats.total_events}")
```

---

## موتور بازار (Market Engine)

state بازار را برای هر نماد نگهداری می‌کند:

```
best_bid          # بهترین قیمت خرید
best_ask          # بهترین قیمت فروش
bid_volume        # حجم صف خرید
ask_volume        # حجم صف فروش
last_trade        # آخرین معامله
queue_state       # وضعیت صف
session_state     # وضعیت سشن (پیش‌گشایش، عادی، پایانی)
price_limit       # دامنه نوسان
```

---

## موتور قوانین بازار (Market Rule Engine)

مهم‌ترین بخش برای بازار ایران. هر بازار policy مخصوص خود را دارد.

### ساختار

```
MarketRule
├── session_rules          # قوانین سشن معاملاتی
├── price_limit_rules      # قوانین دامنه نوسان
├── tick_size_rules        # قوانین اندازه تیک
├── auction_rules          # قوانین حراج
└── order_validation_rules # قوانین اعتبارسنجی سفارش
```

### قوانین هر بازار

| بازار | شناسه | دامنه نوسان | سشن | حراج | سفارش بازار |
|-------|-------|-------------|------|------|------------|
| **بورس تهران (TSE)** | `tse` | ±۵٪ | ۰۸:۴۵-۱۲:۳۰ | ✅ | ✅ |
| **فرابورس (IFB)** | `ifb` | ±۵٪ | ۰۸:۴۵-۱۲:۳۰ | ✅ | ✅ |
| **بازار پایه** | `base_market` | ۳-۱٪ پلکانی | ۰۸:۴۵-۱۲:۳۰ | دوره‌ای | ❌ |
| **ETF** | `etf` | ±۵٪ | ۰۸:۴۵-۱۲:۳۰ | ✅ | ✅ |
| **اوراق بدهی** | `bonds` | ±۱٪ | ۰۸:۴۵-۱۲:۳۰ | ❌ | ✅ |
| **مشتقه** | `derivatives` | متغیر | ۰۸:۴۵-۱۲:۳۰ | ❌ | ✅ |
| **بورس کالا (IME)** | `ime` | ±۵٪ | ۱۱:۴۵-۱۸:۰۰ | ✅ | ✅ |
| **بورس انرژی** | `energy` | ±۵٪ | ۱۱:۴۵-۱۸:۰۰ | دوره‌ای | ❌ |

---

## شبیه‌ساز اجرا (Execution Simulator)

### حالت‌های سفارش

```
NEW            # سفارش جدید
SUBMITTED      # ارسال شده
QUEUED         # در صف
PARTIAL_FILL   # پردازش جزئی
FILLED         # کامل اجرا شده
CANCELLED      # لغو شده
REJECTED       # رد شده
```

### مدل‌های اجرا

| مدل | توضیح |
|------|--------|
| **Market Order** | سفارش بازار — اجرای فوری |
| **Limit Order** | سفارش محدود — اجرا در قیمت مشخص |
| **Queue-based** | اجرای مبتنی بر صف — محاسبه احتمال fill |
| **Impact Model** | مدل ایمپکت قیمت — لغزش بر اساس حجم |

---

## مدل صف (Queue Model)

**فایل:** `backtesting/microstructure/queue_state.py`

برای بازار ایران حیاتی است — صف‌های خرید و فروش بخش مهمی از ریزساختار هستند.

### پارامترها

```
queue_position        # موقعیت در صف
cancel_rate           # نرخ کنسل
trade_rate            # نرخ معامله
queue_decay           # نرخ کاهش صف
```

### احتمال fill

```
P(fill) = 1 - e^(-λV)
```

که در آن:
- `λ` = نرخ معامله (`fill_prob_lambda`)
- `V` = حجم معامله

### نحوه عملکرد

```python
class QueueState:
    def add_order(self, order: SimulatedOrder) -> None:
        if order.side == "buy":
            order.queue_ahead = self.total_bid_volume
            self.bids.append(order)
            self.bid_queue_volume += order.remaining
        else:
            order.queue_ahead = self.total_ask_volume
            self.asks.append(order)
            self.ask_queue_volume += order.remaining

    def update_from_trade(self, trade_volume, trade_price, side) -> list[FillEvent]:
        fills = []
        target_orders = self.bids if side == "buy" else self.asks
        remaining_trade = trade_volume

        for order in target_orders:
            if order.queue_ahead <= 0 and order.remaining > 0:
                fill_qty = min(order.remaining, remaining_trade)
                fills.append(FillEvent(...))
                order.remaining -= fill_qty
                remaining_trade -= fill_qty

        return fills
```

---

## مدل ایمپکت قیمت (Impact Model)

**فایل:** `backtesting/microstructure/impact_model.py`

### قانون جذر (Square Root Law)

```
impact = η × (Q/ADV)^α
```

که در آن:
- `η` = ضریب ایمپکت (eta) — پیش‌فرض: 0.1
- `Q` = حجم سفارش
- `ADV` = میانگین حجم روزانه
- `α` = توان ایمپکت (alpha) — پیش‌فرض: 0.6

### نحوه استفاده

```python
from backtesting.microstructure.impact_model import ImpactModel

model = ImpactModel(eta=0.1, alpha=0.6)

# محاسبه ایمپکت
impact = model.calculate_impact(quantity=10000, adv=1000000, price=45000)
print(f"Impact: {impact:.4f}")  # → 0.0015

# دریافت قیمت اجرایی
exec_price = model.get_execution_price(
    quantity=10000, adv=1000000, price=45000, side="buy"
)
print(f"Execution price: {exec_price:.2f}")  # → 45067.50

# کالیبراسیون از داده واقعی
model.calibrate_from_data(trade_sizes, price_moves, adv)
```

---

## کالیبراسیون ریزساختار

**فایل:** `backtesting/microstructure/calibration.py`

### SymbolMicrostructureParams

پارامترهای کالیبره‌شده برای هر نماد:

| پارامتر | توضیح | مقدار پیش‌فرض |
|----------|--------|---------------|
| `trade_rate` | نرخ معامله (دقیقه) | 0.8 |
| `cancel_rate` | نرخ کنسل | 0.12 |
| `arrival_rate` | نرخ ورود سفارش | 0.5 |
| `impact_eta` | ضریب ایمپکت | 0.11 |
| `impact_alpha` | توان ایمپکت | 0.6 |
| `avg_queue` | میانگین اندازه صف | 1,200,000 |
| `avg_trade_size` | میانگین اندازه معامله | 10,000 |
| `adv` | میانگین حجم روزانه | 1,000,000 |
| `hidden_liquidity_mult` | ضریب نقدینگی پنهان | 1.3 |
| `fill_prob_lambda` | پارامتر احتمال fill | 0.0001 |
| `queue_lifetime_minutes` | عمر مفید صف | 0.0 |

### نحوه کالیبراسیون

```python
from backtesting.microstructure.calibration import MicrostructureCalibrator

calibrator = MicrostructureCalibrator()

# کالیبراسیون از رویدادها
params = calibrator.calibrate_from_events(
    symbol="فولاد",
    quotes=historical_quotes,
    trades=historical_trades,
)

print(f"Trade rate: {params.trade_rate:.2f}/min")
print(f"Impact η: {params.impact_eta:.4f}")
print(f"Impact α: {params.impact_alpha:.4f}")
print(f"Avg queue: {params.avg_queue:,}")

# کالیبراسیون ویژه بازار ایران
params = calibrator.calibrate_iran_market(
    symbol="فولاد",
    quotes=historical_quotes,
    trades=historical_trades,
)

# ذخیره پارامترها
calibrator.save_params([params], "calibration_params.json")

# بارگذاری پارامترها
loaded_params = calibrator.load_params("calibration_params.json")
```

---

## موتور تحلیل (Analytics Engine)

**فایل:** `backtesting/analytics/engine.py`

### AnalyticsResult

```python
@dataclass
class AnalyticsResult:
    cagr: float              # نرخ رشد مرکب سالانه
    sharpe_ratio: float      # نسبت شارپ
    sortino_ratio: float     # نسبت سورتینو
    max_drawdown: float      # حداکثر افت سرمایه
    max_drawdown_pct: float  # حداکثر افت سرمایه (درصد)
    turnover: float          # نرخ گردش معاملات
    win_rate: float          # نرخ برد
    total_return: float      # بازده کل
    total_return_pct: float  # بازده کل (درصد)
    volatility: float        # نوسان‌پذیری
    downside_volatility: float # نوسان‌پذیری نزولی
    calmar_ratio: float      # نسبت کالمار
    avg_win: float           # میانگین برد
    avg_loss: float          # میانگین باخت
    profit_factor: float     # فاکتور سود
    total_trades: int        # تعداد کل معاملات
    winning_trades: int      # معاملات سودده
    losing_trades: int       # معاملات زیان‌ده
```

### نحوه استفاده

```python
from backtesting.analytics.engine import AnalyticsEngine

analytics = AnalyticsEngine()
ar = analytics.compute(result, trading_days=252)

print(f"CAGR: {ar.cagr:.2f}%")
print(f"Sharpe: {ar.sharpe_ratio:.2f}")
print(f"Sortino: {ar.sortino_ratio:.2f}")
print(f"Max DD: {ar.max_drawdown_pct:.2f}%")
print(f"Win Rate: {ar.win_rate:.1f}%")
print(f"Profit Factor: {ar.profit_factor:.2f}")
```

---

## معیارهای ریسک (Risk Metrics)

**فایل:** `backtesting/metrics/risk_metrics.py`

### معیارهای موجود

| معیار | فرمول | توضیح |
|--------|--------|--------|
| **Volatility** | `σ × √252` | نوسان‌پذیری سالانه |
| **Sharpe Ratio** | `(R - Rf) / σ` | نسبت ریسک به بازده |
| **Sortino Ratio** | `R / σ_down` | نسبت سورتینو (فقط نوسان منفی) |
| **Calmar Ratio** | `CAGR / MaxDD` | نسبت کالمار |
| **VaR 95%** | `percentile(returns, 5)` | ارزش در معرض ریسک ۹۵٪ |
| **CVaR 95%** | `mean(returns <= VaR)` | ارزش شرطی در معرض ریسک |
| **Omega Ratio** | `Σ(gains) / Σ(losses)` | نسبت اومگا |
| **Tail Ratio** | `percentile(95) / percentile(5)` | نسبت دُم |
| **Skewness** | `E[(X-μ)³] / σ³` | چولگی |
| **Kurtosis** | `E[(X-μ)⁴] / σ⁴ - 3` | کشیدگی |
| **Pain Index** | `mean(drawdowns)` | شاخص درد |
| **Recovery Factor** | `Σ(returns) / MaxDD` | فاکتور بازیابی |

### نحوه استفاده

```python
from backtesting.metrics.risk_metrics import RiskMetrics

risk = RiskMetrics.compute(result, risk_free_rate=0.25)  # 25% نرخ بدون ریسک

print(f"Volatility: {risk['volatility']:.2f}%")
print(f"Sharpe: {risk['sharpe_ratio']:.2f}")
print(f"Sortino: {risk['sortino_ratio']:.2f}")
print(f"VaR 95%: {risk['var_95']:.4f}")
print(f"CVaR 95%: {risk['cvar_95']:.4f}")
print(f"Omega: {risk['omega_ratio']:.2f}")
```

---

## Deflated Sharpe Ratio

**فایل:** `backtesting/metrics/deflated_sharpe.py`

### چرا Deflated Sharpe مهم است؟

وقتی استراتژی‌های زیادی را آزمایش می‌کنید، برخی به‌صورت تصادفی سودآور به نظر می‌رسند. Deflated Sharpe Ratio این اثر را تصحیح می‌کند.

### فرمول

```
DSR = Φ((SR_observed - E[max_SR]) / SE(SR))
```

که در آن:
- `SR_observed` = شارپ مشاهده شده
- `E[max_SR]` = مورد انتظار بیشترین شارپ تحت فرض صفر
- `SE(SR)` = خطای استاندارد شارپ
- `Φ` = تابع توزیع نرمال استاندارد

### نمونه استفاده

```python
from backtesting.metrics.deflated_sharpe import deflated_sharpe_ratio

result = deflated_sharpe_ratio(
    sharpe_observed=1.5,      # شارپ مشاهده شده
    n_trials=100,             # تعداد استراتژی‌های آزمایش شده
    n_observations=1000,      # تعداد مشاهدات
    skewness=0.0,             # چولگی
    kurtosis=3.0,             # کشیدگی
)

print(f"DSR: {result['deflated_sharpe']:.4f}")
print(f"P-value: {result['p_value']:.6f}")
print(f"Significant 95%: {result['significant_95']}")
print(f"Significant 99%: {result['significant_99']}")
```

### اصلاح چندگانه آزمون

```python
from backtesting.metrics.deflated_sharpe import multiple_testing_correction

result = multiple_testing_correction(
    p_values=[0.01, 0.03, 0.04, 0.06, 0.08],
    method="fdr_bh",  # Bonferroni, Holm, FDR-BH
)

print(f"Adjusted p-values: {result['adjusted_p_values']}")
print(f"Significant 95%: {result['n_significant_95']}")
```

---

## موتور آزمایش (Experiment Engine)

**فایل:** `backtesting/experiment/engine.py`

### Grid Search

جستجوی ترکیبی پارامترها:

```python
from backtesting.experiment.engine import ExperimentEngine, GridSearch

exp_engine = ExperimentEngine()
grid = GridSearch(exp_engine)

runs = grid.generate(
    strategy_name="SmaCross",
    param_grid={
        "fast_period": [5, 10, 20],
        "slow_period": [50, 100, 200],
    },
)

# تعداد کل اجراها: 3 × 3 = 9
```

### Walk-Forward

آزمایش پنجره‌های متوالی برای جلوگیری از overfitting:

```python
from backtesting.experiment.engine import WalkForward

wf = WalkForward(exp_engine, n_windows=5, train_pct=0.7)

runs = wf.generate(
    strategy_name="MyStrategy",
    base_params={"lookback": 20},
)

# هر پنجره: 70% آموزش + 30% آزمایش
```

### Monte Carlo

شبیه‌سازی تصادفی پارامترها:

```python
from backtesting.experiment.engine import MonteCarlo

mc = MonteCarlo(exp_engine, n_simulations=1000)

runs = mc.generate(
    strategy_name="MyStrategy",
    param_distributions={
        "threshold": (0.001, 0.05),
        "lookback": (10, 100),
    },
    seed=42,
)
```

---

## مدل‌سازی عامل‌محور (ABM)

**فایل:** `backtesting/abm/`

شبیه‌سازی رفتار معامله‌گران مختلف در بازار.

### عامل‌ها

#### MarketMaker

بازارگردان با مدیریت موجودی:

```python
from backtesting.abm.agents import MarketMaker

mm = MarketMaker(
    agent_id="mm1",
    initial_capital=1_000_000_000,
    spread_pct=0.01,        # ۱٪ اسپرد
    order_size=1000,        # اندازه سفارش
    inventory_target=0,     # هدف موجودی
)
```

#### NoiseTrader

معامله‌گر تصادفی:

```python
from backtesting.abm.agents import NoiseTrader

nt = NoiseTrader(
    agent_id="nt1",
    initial_capital=1_000_000_000,
    min_size=100,
    max_size=2000,
    market_order_prob=0.3,  # ۳۰٪ احتمال سفارش بازار
)
```

#### TrendFollower

دنبال‌کننده روند:

```python
from backtesting.abm.agents import TrendFollower

tf = TrendFollower(
    agent_id="tf1",
    initial_capital=1_000_000_000,
    lookback=20,            # بازه بررسی روند
    order_size=1000,
    threshold_pct=0.005,    # ۰.۵٪ آستانه ورود
)
```

#### MeanReversionAgent

بازگشت به میانگین:

```python
from backtesting.abm.agents import MeanReversionAgent

mr = MeanReversionAgent(
    agent_id="mr1",
    initial_capital=1_000_000_000,
    lookback=50,
    order_size=1000,
    entry_z=1.0,            # آستانه Z-Score
)
```

### اجرای شبیه‌سازی

```python
from backtesting.abm.simulation import Simulation
from backtesting.abm.environment import MarketEnvironment

sim = Simulation(random_seed=42)
sim.add_agent(MarketMaker(agent_id="mm1"))
sim.add_agent(NoiseTrader(agent_id="nt1"))
sim.add_agents([
    TrendFollower(agent_id="tf1"),
    MeanReversionAgent(agent_id="mr1"),
])

result = sim.run(n_steps=10000)

print(f"Final price: {result.final_mid}")
print(f"Total trades: {result.total_trades}")
print(f"Agent PnLs: {result.agent_pnls}")
```

---

## تولید Alpha

**فایل:** `backtesting/alpha/alpha_generator.py`

### تولید Alpha از ویژگی‌های ریزساختار

```python
from backtesting.alpha.alpha_generator import AlphaGenerator

gen = AlphaGenerator(seed=42)

# Alpha بازگشت به میانگین
alpha_mr = gen.mean_reversion(price=45000, rolling_mean=44000)

# Alpha مومنتوم
alpha_mom = gen.momentum(price=45000, price_lag=43000)

# Alpha Z-Score
alpha_z = gen.zscore_alpha(feature_value=0.8, mean=0.5, std=0.1)

# تولید تمام templateها
alphas = gen.generate_all_templates(features)
print(alphas)
# {'alpha_mr': 0.0222, 'alpha_mom': 0.0465, 'alpha_imb': ..., ...}
```

---

## مدل هزینه معاملات

**فایل:** `backtesting/costs/transaction_cost_model.py`

### اجزای هزینه

| جزء | فرمول | توضیح |
|------|--------|--------|
| **Spread Cost** | `order_value × spread × 0.5` | هزینه اسپرد |
| **Temporary Impact** | `order_value × coeff × (participation)^0.6` | ایمپکت موقت |
| **Permanent Impact** | `order_value × coeff × (participation)^0.3` | ایمپکت دائمی |
| **Queue Loss** | `order_value × rate × queue_ratio` | هزینه عدم اجرا |
| **Adverse Selection** | `order_value × rate × (participation)^0.5` | انتخاب عکس |
| **Commission** | `order_value × commission_pct` | کارمزد |
| **Tax** | `order_value × tax_pct` | مالیات |

### نحوه استفاده

```python
from backtesting.costs.transaction_cost_model import TransactionCostModel

model = TransactionCostModel(
    spread_cost_pct=0.0005,      # ۵ bps اسپرد
    temp_impact_coeff=0.1,       # ضریب ایمپکت موقت
    perm_impact_coeff=0.02,      # ضریب ایمپکت دائمی
    commission_pct=0.0003,       # ۳ bps کارمزد
    tax_pct=0.0005,              # ۵ bps مالیات
)

breakdown = model.compute_cost(
    side="buy",
    quantity=10000,
    price=45000,
    adv=1_000_000,
)

print(f"Total cost: {breakdown.total_cost:.2f}")
print(f"Total cost (bps): {breakdown.total_cost_bps:.1f}")
```

---

## اندازه‌گیری پوزیشن (Position Sizing)

**فایل:** `backtesting/sizing.py`

### روش‌های موجود

| روش | فرمول | توضیح |
|------|--------|--------|
| **fixed** | `value / price` | اندازه ثابت |
| **percent** | `(capital × value%) / price` | درصدی از سرمایه |
| **kelly** | `kelly% × capital / price` | فرمول کلی |
| **risk_based** | `risk_amount / risk_per_share` | مبتنی بر ریسک |

### نحوه استفاده

```python
from backtesting.sizing import PositionSizer

sizer = PositionSizer(method="kelly", value=0.25)  # حداکثر 25% Kelly

shares = sizer.calculate(
    capital=1_000_000_000,
    price=45000,
    win_rate=0.6,
    avg_win=0.1,
    avg_loss=0.05,
)
print(f"Shares to buy: {shares:.0f}")
```

---

## اعتبارسنجی (Validation)

**فایل:** `backtesting/validation.py`

```python
from backtesting.validation import BacktestValidator

validator = BacktestValidator()

# اعتبارسنجی تنظیمات
errors = validator.validate_config({
    "strategy": "moving_average_cross",
    "start_date": "2023-01-01",
    "end_date": "2024-01-01",
})

# اعتبارسنجی نتایج
warnings = validator.validate_results(result)
```

---

## ترکیب‌کننده استراتژی (Strategy Composer)

**فایل:** `backtesting/composer/strategy_composer.py`

تولید خودکار ترکیب‌های مختلف استراتژی‌ها.

### StrategyBlueprint

```python
@dataclass
class StrategyBlueprint:
    entry_indicator: str          # اندیکاتور ورود
    entry_params: dict            # پارامترهای ورود
    entry_condition: str          # شرط ورود
    exit_indicator: str           # اندیکاتور خروج
    exit_params: dict             # پارامترهای خروج
    exit_condition: str           # شرط خروج
    filter1_indicator: str        # فیلتر ۱ (اختیاری)
    filter2_indicator: str        # فیلتر ۲ (اختیاری)
    stop_loss_pct: float          # حد ضرر
    take_profit_pct: float        # حد سود
    trailing_stop: bool           # حد ضرر شناور
    sizing_method: str            # روش اندازه‌گیری
    sizing_value: float           # مقدار اندازه‌گیری
```

### نحوه استفاده

```python
from backtesting.composer.strategy_composer import StrategyComposer

composer = StrategyComposer(include_filters=True)

# تولید تمام ترکیب‌ها
blueprints = composer.generate_all_combinations(max_combinations=5000)

# تولید batch
batch = composer.generate_batch(offset=0, batch_size=100)

# تخمین تعداد کل
total = composer.estimate_total_count()
print(f"Total combinations: {total:,}")
```

---

## موتور بصری‌سازی (Visualization)

**فایل:** `backtesting/visualization/engine.py`

### ChartData

```python
@dataclass
class ChartData:
    equity_curve: list[dict]           # منحنی سرمایه
    drawdown_curve: list[dict]         # منحنی افت سرمایه
    monthly_returns: list[dict]        # بازده ماهانه
    trade_pnl_distribution: list[dict] # توزیع سود/زیان
    underwater_plot: list[dict]        # نمودار زیرآبی
    rolling_sharpe: list[dict]         # شارپ م移动平均
    rolling_volatility: list[dict]     # نوسان م移动平均
    summary_metrics: dict              # خلاصه معیارها
```

### نحوه استفاده

```python
from backtesting.visualization.engine import VisualizationEngine

viz = VisualizationEngine()
chart = viz.prepare(result)

# ارسال به فرانت‌اند
equity_curve = chart.equity_curve
drawdown = chart.drawdown_curve
metrics = chart.summary_metrics
```

---

## API Endpoints

### ۱. اجرای بک‌تست (POST /api/v1/backtests/run)

```bash
curl -X POST "http://localhost:8000/api/v1/backtests/run" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Run",
    "symbols": ["فولاد"],
    "strategy_type": "moving_average_cross",
    "strategy_params": {"fast_period": 10, "slow_period": 50},
    "start_date": "2023-01-01",
    "end_date": "2024-01-01",
    "initial_capital": 1000000000
  }'
```

### ۲. مقایسه استراتژی‌ها (POST /api/v1/backtests/compare)

```bash
curl -X POST "http://localhost:8000/api/v1/backtests/compare" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "فولاد",
    "start_date": "2023-01-01",
    "end_date": "2024-01-01",
    "initial_capital": 1000000000
  }'
```

### ۳. Walk-Forward (POST /api/v1/backtests/walk-forward)

```bash
curl -X POST "http://localhost:8000/api/v1/backtests/walk-forward" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "فولاد",
    "strategy": "moving_average_cross",
    "start_date": "2021-01-01",
    "end_date": "2024-01-01",
    "windows": 5,
    "train_ratio": 0.7
  }'
```

### ۴. Monte Carlo (POST /api/v1/backtests/monte-carlo)

```bash
curl -X POST "http://localhost:8000/api/v1/backtests/monte-carlo" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "فولاد",
    "strategy": "moving_average_cross",
    "start_date": "2023-01-01",
    "end_date": "2024-01-01",
    "n_simulations": 1000
  }'
```

### ۵. بک‌تست پرتفوی (POST /api/v1/backtests/portfolio-run)

```bash
curl -X POST "http://localhost:8000/api/v1/backtests/portfolio-run" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["فولاد", "فملی", "شپنا"],
    "strategy_type": "moving_average_cross",
    "start_date": "2023-01-01",
    "end_date": "2024-01-01",
    "allocation_method": "equal",
    "rebalance_frequency_days": 30
  }'
```

### ۶. تولید خودکار استراتژی (POST /api/v1/backtests/generate)

```bash
curl -X POST "http://localhost:8000/api/v1/backtests/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "فولاد",
    "start_date": "2023-01-01",
    "end_date": "2024-01-01",
    "max_combinations": 5000,
    "use_genetic": true,
    "genetic_generations": 8
  }'
```

---

## نمونه استفاده

### بک‌تست ساده

```python
from backtesting.engine.simulator import BacktestSimulator
from backtesting.strategies.base import BaseStrategy

class SmaCross(BaseStrategy):
    def __init__(self, fast=10, slow=50):
        self.fast = fast
        self.slow = slow

    def on_bar(self, bar):
        sma_fast = bar.get("sma_fast", 0)
        sma_slow = bar.get("sma_slow", 0)

        if sma_fast > sma_slow:
            return [OrderEvent(side="buy", quantity=1000)]
        elif sma_fast < sma_slow:
            return [OrderEvent(side="sell", quantity=1000)]
        return []

async def main():
    simulator = BacktestSimulator(
        commission_pct=0.0003,
        slippage_bps=5,
    )

    result = await simulator.run(
        strategy=SmaCross(fast=10, slow=50),
        initial_capital=1_000_000_000,
        data=historical_data,
    )

    # تحلیل نتایج
    analytics = AnalyticsEngine()
    ar = analytics.compute(result)

    print(f"Total Return: {ar.total_return_pct:.2f}%")
    print(f"CAGR: {ar.cagr:.2f}%")
    print(f"Sharpe: {ar.sharpe_ratio:.2f}")
    print(f"Max DD: {ar.max_drawdown_pct:.2f}%")
    print(f"Win Rate: {ar.win_rate:.1f}%")
```

### بک‌تست چندنماده

```python
from backtesting.engine.portfolio_simulator import PortfolioBacktestSimulator
from backtesting.portfolio.allocator import Allocator

simulator = PortfolioBacktestSimulator(
    broker=Broker(commission_pct=0.0003),
    allocator=Allocator(method="equal"),
)

result = await simulator.run(
    strategy=SmaCross(),
    initial_capital=1_000_000_000,
    data_by_instrument={
        "فولاد": data_foolad,
        "فملی": data_fameli,
        "شپنا": data_shapna,
    },
)
```

### بک‌تست با ریزساختار

```python
from backtesting.microstructure.calibration import MicrostructureCalibrator

# کالیبراسیون
calibrator = MicrostructureCalibrator()
params = calibrator.calibrate_from_events(
    symbol="فولاد",
    quotes=quotes,
    trades=trades,
)

# استفاده از پارامترها در شبیه‌سازی
simulator = BacktestSimulator(
    broker=Broker(
        impact_model=ImpactModel(eta=params.impact_eta, alpha=params.impact_alpha),
    ),
)
```

---

## ساختار فایل‌ها

```
backtesting/
├── __init__.py                    # خروجی‌های ماژول
├── ARCHITECTURE.md                # معماری سیستم
│
├── engine/                        # موتور اصلی
│   ├── simulator.py               # شبیه‌ساز اصلی
│   ├── replay_engine.py           # موتور بازپخش
│   ├── unified_timeline.py        # خط زمانی یکپارچه
│   ├── event_builder.py           # سازنده رویداد
│   ├── portfolio.py               # مدیریت پرتفوی
│   ├── broker.py                  # کارگزار مجازی
│   ├── clock.py                   # ساعت مجازی
│   ├── risk.py                    # موتور ریسک
│   └── slippage.py                # مدل لغزش
│
├── market/                        # موتور بازار
│   ├── market_engine.py           # موتور بازار
│   └── rule_engine.py             # موتور قوانین
│
├── execution/                     # شبیه‌سازی اجرا
│   ├── fill_simulator.py          # شبیه‌ساز fill
│   ├── queue_simulation.py        # شبیه‌ساز صف
│   ├── order_models.py            # مدل‌های سفارش
│   ├── market_impact.py           # ایمپکت بازار
│   ├── latency_model.py           # مدل تأخیر
│   └── execution_policy.py        # سیاست اجرا
│
├── microstructure/                # ریزساختار بازار
│   ├── queue_state.py             # وضعیت صف
│   ├── impact_model.py            # مدل ایمپکت
│   ├── calibration.py             # کالیبراسیون
│   ├── auction_engine.py          # موتور حراج
│   ├── hidden_liquidity.py        # نقدینگی پنهان
│   ├── cancel_model.py            # مدل کنسل
│   └── order_arrival_model.py     # مدل ورود سفارش
│
├── analytics/                     # موتور تحلیل
│   └── engine.py                  # موتور تحلیل اصلی
│
├── metrics/                       # معیارها
│   ├── performance.py             # معیارهای عملکرد
│   ├── risk_metrics.py            # معیارهای ریسک
│   ├── deflated_sharpe.py         # Deflated Sharpe Ratio
│   ├── trade_metrics.py           # معیارهای معاملاتی
│   ├── drawdown_metrics.py        # معیارهای افت سرمایه
│   ├── turnover_metrics.py        # معیارهای گردش
│   ├── benchmark_metrics.py       # معیارهای مرجع
│   └── exposure_metrics.py        # معیارهای مواجهه
│
├── experiment/                    # موتور آزمایش
│   └── engine.py                  # Grid Search, Walk-Forward, Monte Carlo
│
├── abm/                           # مدل‌سازی عامل‌محور
│   ├── simulation.py              # شبیه‌سازی
│   ├── agents.py                  # عامل‌ها
│   ├── agent.py                   # کلاس پایه عامل
│   ├── environment.py             # محیط بازار
│   ├── order_book.py              # دفتر سفارشات
│   └── matching_engine.py         # موتور تطبیق
│
├── alpha/                         # تولید Alpha
│   ├── alpha_generator.py         # تولیدکننده Alpha
│   ├── alpha_pool.py              # استخر Alpha
│   ├── alpha_selection.py         # انتخاب Alpha
│   ├── alpha_portfolio.py         # پرتفوی Alpha
│   └── feature_library.py         # کتابخانه ویژگی‌ها
│
├── costs/                         # مدل هزینه
│   ├── transaction_cost_model.py  # مدل هزینه معاملات
│   └── execution_analytics.py     # تحلیل اجرایی
│
├── composer/                      # ترکیب‌کننده استراتژی
│   ├── strategy_composer.py       # ترکیب‌کننده
│   └── indicator_registry.py      # ثبت‌کننده اندیکاتورها
│
├── visualization/                 # بصری‌سازی
│   └── engine.py                  # موتور بصری‌سازی
│
├── calibration/                   # کالیبراسیون
│   ├── calibration.py             # کالیبراسیون ریزساختار
│   ├── parameter_store.py         # ذخیره پارامترها
│   └── nightly_calibration.py     # کالیبراسیون شبانه
│
├── capital/                       # مدیریت سرمایه
│   └── dynamic_allocator.py       # تخصیص پویا
│
├── data_quality/                  # کیفیت داده
│   └── tick_validator.py          # اعتبارسنجی تیک
│
├── events/                        # رویدادها
│   ├── calendar.py                # تقویم بازار
│   ├── corporate.py               # رویدادهای شرکتی
│   └── symbol_changes.py          # تغییرات نماد
│
├── hybrid/                        # هیبرید
│   ├── hybrid_simulator.py        # شبیه‌ساز هیبرید
│   └── agent_engine.py            # موتور عامل
│
├── sizing.py                      # اندازه‌گیری پوزیشن
├── validation.py                  # اعتبارسنجی
├── constants.py                   # ثابت‌ها
├── contracts.py                   # قراردادها
├── commission.py                  # کارمزد
└── costs.py                       # هزینه‌ها
```

---

## نکات قابل بهبود

| اولویت | مورد | وضعیت | فایل |
|--------|------|--------|------|
| ~~بحرانی~~ | یکسان‌سازی مسیر شبیه‌سازی | ✅ انجام شد | `engine/simulator.py` |
| ~~بحرانی~~ | Look-Ahead Bias | ✅ انجام شد | `strategies/incremental_indicators.py` |
| ~~بحرانی~~ | Corporate Actions | ✅ انجام شد | `events/corporate_actions.py` |
| ~~بحرانی~~ | قوانین بازار تاریخی | ✅ انجام شد | `market/rule_versioning.py` |
| ~~بحرانی~~ | اجرای Deterministic | ✅ انجام شد | `engine/simulator.py` |
| ~~بالا~~ | دفتر کل پرتفوی | ✅ انجام شد | `portfolio/ledger.py` |
| ~~بالا~~ | Survivorship Bias | ✅ انجام شد | `events/corporate_actions.py` |
| ~~بالا~~ | Pre-Trade Risk | ✅ انجام شد | `risk/pre_trade_risk.py` |
| ~~بالا~~ | Data Versioning | ✅ انجام شد | `data/data_versioning.py` |
| ~~متوسط~~ | نرخ بدون ریسک پویا | ✅ انجام شد | `metrics/dynamic_risk_free.py` |
| ~~متوست~~ | Attribution | ✅ انجام شد | `analytics/attribution.py` |
| ~~متوسط~~ | Capacity Analysis | ✅ انجام شد | `analytics/capacity_analyzer.py` |
| ~~متوسط~~ | Run Manifest | ✅ انجام شد | `engine/run_manifest.py` |
| ~~متوسط~~ | Purged Walk-Forward | ✅ انجام شد | `experiment/purged_walk_forward.py` |
| ~~متوسط~~ | Job Queue | ✅ انجام شد | `platform/job_queue.py` |
| ~~متوسط~~ | مدیریت خطا و لاگ‌گیری شبیه‌سازی | ✅ انجام شد | `observability/simulation_logger.py` |
| ~~متوسط~~ | حالت‌های حراج متنوع (بازار پایه، کالا، انرژی) | ✅ انجام شد | `microstructure/auction_engine.py` |
| ~~متوسط~~ | ادغام با منابع داده زنده (Live Data Adapter) | ✅ انجام شد | `data/live_data_adapter.py` |
| ~~متوسط~~ | محاسبه MTM با نرخ تسویه روزانه | ✅ انجام شد | `engine/portfolio.py` |
| ~~متوسط~~ | آزمون‌های استرس بر اساس سناریوهای تاریخی | ✅ انجام شد | `risk/stress_testing.py` |
| ~~متوسط~~ | مدیریت حافظه و پارتیشن‌بندی داده | ✅ انجام شد | `data/memory_manager.py` |
| ~~متوسط~~ | گزارش‌گیری خودکار Excel | ✅ انجام شد | `reporting/excel_report.py` |
| ~~متوسط~~ | مدیریت چندین ارز و نرخ ارز | ✅ انجام شد | `engine/forex_manager.py` |
| ~~متوسط~~ | سیاست‌های تنظیم مجدد پرتفوی (Rebalancing) | ✅ انجام شد | `portfolio/rebalancer.py` |
| ~~متوسط~~ | تحلیل حساسیت (Sensitivity Analysis) | ✅ انجام شد | `analytics/sensitivity_analysis.py` |
| در حال انتظار | تست‌های Golden Master | — | `tests/` |
| در حال انتظار | Regime Detection تکمیل | — | `regime/` |

---

## نقشه راه ارتقا

### فاز ۱: قابل اعتماد کردن هسته (اولویت بحرانی)

| مورد | توضیح | فایل |
|------|--------|------|
| **Deterministic Event Engine** | حذف async از حلقه اصلی، اضافه کردن `sequence_id` به رویدادها | `engine/replay_engine.py` |
| **Incremental Indicators** | محاسبه اندیکاتورها فقط از داده‌های گذشته | `strategies/indicators.py` |
| **Corporate Actions کامل** | تعدیل قیمت برای افزایش سرمایه، سود نقدی، تقسیم سهام | `events/corporate_actions.py` |
| **Versioned Market Rules** | قوانین تاریخی بازارها با `effective_date` | `market/rule_versioning.py` |
| **Portfolio Ledger** | حسابداری دوطرفه با T+2 و FIFO | `portfolio/ledger.py` |
| **Test Suite** | تست‌های Golden Master و Regression | `tests/` |

### فاز ۲: حرفه‌ای‌سازی تحلیل

| مورد | توضیح |
|------|--------|
| **Walk-Forward دقیق** | Purged Walk-Forward با Embargo برای جلوگیری از نشت اطلاعات |
| **Overfitting Controls** | Purged K-Fold CV, Combinatorial CV, reality check |
| **Attribution** | Brinson attribution, factor exposure, cost attribution |
| **Capacity Analysis** | حداکثر سرمایه قبل از کاهش Sharpe, days to liquidate |
| **Regime Analysis** | تفکیک عملکرد بر اساس رژیم بازار |
| **Transaction Cost Stress** | تست با هزینه‌های سنگین‌تر |

### فاز ۳: پلتفرم سازمانی

| مورد | توضیح |
|------|--------|
| **Job Queue** | اجرای پس‌زمینه با Celery/RQ |
| **Result Persistence** | ذخیره نتایج در PostgreSQL + Parquet |
| **Experiment Registry** | ثبت و مقایسه تاریخی اجراها |
| **Parallel Execution** | اجرای موازی با ProcessPoolExecutor |
| **Run Manifest خودکار** | ذخیره متادیتا در هر اجرا |
| **Performance Optimization** | Cython/Rust برای bottleneckها |

---

## ساختار فایل‌ها (به‌روزرسانی شده)

```
backtesting/
├── __init__.py
├── ARCHITECTURE.md
│
├── engine/                        # موتور اصلی
│   ├── simulator.py               # ★ شبیه‌ساز یکسان‌Deterministic (bar + event)
│   ├── replay_engine.py           # موتور بازپخش event-based
│   ├── unified_timeline.py        # خط زمانی یکپارچه
│   ├── event_builder.py           # سازنده رویداد
│   ├── portfolio.py               # مدیریت پرتفوی + MTM با نرخ تسویه
│   ├── broker.py                  # کارگزار مجازی
│   ├── clock.py                   # ساعت مجازی
│   ├── risk.py                    # موتور ریسک
│   ├── slippage.py                # مدل لغزش
│   ├── run_manifest.py            # ★ متادیتای تکرارپذیری
│   └── forex_manager.py           # ★ مدیریت چندین ارز و نرخ ارز
│
├── market/                        # موتور بازار
│   ├── market_engine.py           # موتور بازار
│   ├── rule_engine.py             # موتور قوانین
│   ├── policies.py                # سیاست‌های بازار
│   └── rule_versioning.py         # ★ قوانین نسخه‌دار تاریخی
│
├── execution/                     # شبیه‌سازی اجرا
│   ├── fill_simulator.py          # شبیه‌ساز fill
│   ├── queue_simulation.py        # شبیه‌ساز صف
│   ├── order_models.py            # مدل‌های سفارش
│   ├── market_impact.py           # ایمپکت بازار
│   ├── latency_model.py           # مدل تأخیر
│   └── execution_policy.py        # سیاست اجرا
│
├── microstructure/                # ریزساختار بازار
│   ├── queue_state.py             # وضعیت صف
│   ├── impact_model.py            # مدل ایمپکت
│   ├── calibration.py             # کالیبراسیون
│   ├── auction_engine.py          # موتور حراج
│   ├── hidden_liquidity.py        # نقدینگی پنهان
│   ├── cancel_model.py            # مدل کنسل
│   └── order_arrival_model.py     # مدل ورود سفارش
│
├── analytics/                     # موتور تحلیل
│   ├── engine.py                  # موتور تحلیل اصلی
│   ├── attribution.py             # ★ تحلیل اتریبیوشن
│   ├── capacity_analyzer.py       # ★ تحلیل ظرفیت
│   └── sensitivity_analysis.py    # ★ تحلیل حساسیت (Sensitivity Analysis)
│
├── metrics/                       # معیارها
│   ├── performance.py             # معیارهای عملکرد
│   ├── risk_metrics.py            # ★ معیارهای ریسک (با بازده واقعی)
│   ├── deflated_sharpe.py         # Deflated Sharpe Ratio
│   ├── dynamic_risk_free.py       # ★ نرخ بدون ریسک پویا و تورم
│   ├── trade_metrics.py           # معیارهای معاملاتی
│   ├── drawdown_metrics.py        # معیارهای افت سرمایه
│   ├── turnover_metrics.py        # معیارهای گردش
│   ├── benchmark_metrics.py       # معیارهای مرجع
│   └── exposure_metrics.py        # معیارهای مواجهه
│
├── experiment/                    # موتور آزمایش
│   ├── engine.py                  # Grid Search, Walk-Forward, Monte Carlo
│   └── purged_walk_forward.py     # ★ Purged Walk-Forward (بدون نشت اطلاعات)
│
├── platform/                      # ★ پلتفرم اجرایی
│   └── job_queue.py               # ★ صف کار پس‌زمینه
│
├── abm/                           # مدل‌سازی عامل‌محور
│   ├── simulation.py              # شبیه‌سازی
│   ├── agents.py                  # عامل‌ها (MarketMaker, NoiseTrader, etc.)
│   ├── agent.py                   # کلاس پایه عامل
│   ├── environment.py             # محیط بازار
│   └── order_book.py              # دفتر سفارشات
│
├── alpha/                         # تولید Alpha
│   ├── alpha_generator.py         # تولیدکننده Alpha
│   └── feature_library.py         # کتابخانه ویژگی‌ها
│
├── costs/                         # مدل هزینه
│   └── transaction_cost_model.py  # مدل هزینه معاملات
│
├── strategies/                    # ★ استراتژی‌ها
│   └── incremental_indicators.py  # ★ اندیکاتورهای Incremental (جلوگیری Look-Ahead)
│
├── portfolio/                     # ★ پرتفوی و حسابداری
│   ├── allocator.py               # تخصیص سرمایه
│   ├── rebalancer.py              # بازتعادیلی
│   ├── ledger.py                  # ★ دفتر کل دوطرفه (T+2, FIFO)
│   ├── risk_budgeting.py          # ★ بودجه ریسک
│   └── exposure_limits.py         # ★ محدودیت مواجهه
│
├── events/                        # رویدادها
│   ├── calendar.py                # تقویم بازار
│   ├── corporate.py               # رویدادهای شرکتی
│   ├── corporate_actions.py       # ★ تعدیل قیمت و Survivorship
│   └── symbol_changes.py          # تغییرات نماد
│
├── composer/                      # ترکیب‌کننده استراتژی
│   └── strategy_composer.py       # ترکیب‌کننده
│
├── visualization/                 # بصری‌سازی
│   └── engine.py                  # موتور بصری‌سازی
│
├── calibration/                   # کالیبراسیون
│   └── calibration.py             # کالیبراسیون ریزساختار
│
├── capital/                       # مدیریت سرمایه
│   └── dynamic_allocator.py       # تخصیص پویا
│
├── risk/                          # ★ مدیریت ریسک
│   ├── pre_trade_risk.py          # ★ ریسک پیش‌از-معامله
│   └── stress_testing.py          # ★ آزمون استرس (سناریوهای تاریخی + مونت‌کارلو)
│
├── data/                          # ★ مدیریت داده
│   ├── data_versioning.py         # ★ نسخه‌بندی داده‌ها
│   ├── tick_validator.py          # اعتبارسنجی تیک
│   ├── live_data_adapter.py       # ★ اتصال به داده‌های زنده (APIهای برخط)
│   └── memory_manager.py          # ★ مدیریت حافظه (Parquet/Arrow/پارتیشن‌بندی)
│
├── sizing.py                      # اندازه‌گیری پوزیشن
├── validation.py                  # اعتبارسنجی
├── constants.py                   # ثابت‌ها
└── commission.py                  # کارمزد
```

---

## نکات فنی

### عملکرد (Performance)

- **پردازش ناهمزمان (async)** — اجرای همزمان چند بک‌تست
- **Chunk Loading** — بارگذاری تدریجی داده‌ها از حافظه
- **کشینگ** — ذخیره نتایج محاسبات تکراری
- **NumPy** — محاسبات ریاضی بهینه

### دقت (Accuracy)

- **کالیبراسیون از داده واقعی** — پارامترهای واقعی بازار ایران
- **مدل صف** — شبیه‌سازی دقیق صف‌های خرید و فروش
- **هزینه‌های واقعی** — کارمزد، مالیات، اسپرد، ایمپکت
- **Deflated Sharpe** — تصحیح اثر آزمون‌های چندگانه
- **법인 Actions** — تعدیل قیمت برای افزایش سرمایه و سود نقدی
- **Versioned Rules** — قوانین تاریخی بازارها

### مقیاس‌پذیری (Scalability)

- **پشتیبانی از ۱۰۰۰+ نماد** — مدیریت همزمان چند نماد
- **پشتیبانی از ۱۰۰M رویداد** — خط زمانی یکپارچه
- **پردازش دسته‌ای** — streaming برای حافظه کم
- **اجرا موازی** — asyncio.Semaphore برای کنترل تعداد همزمان

---

## مجوز

این بخش جزئی از پروژه Iran Market Data & Analytics Platform است و تحت مجوز MIT منتشر شده است.

</div>
