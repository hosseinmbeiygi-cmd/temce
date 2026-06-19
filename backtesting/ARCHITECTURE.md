# معماری سیستم بک‌تست چندبازاری ایران

این سند چک‌لیست بازارها را به یک معماری عملی برای سیستم بک‌تست چندبازاری ایران تبدیل می‌کند. هدف این است که سیستم بتواند قوانین متفاوت هر بازار را بدون تغییر در هسته موتور اجرا کند.

## اصول معماری

- **Market‑aware**: هر بازار قوانین خودش را دارد
- **Rule‑versioned**: قوانین در زمان تغییر می‌کنند
- **Event‑driven**: بازار با رویداد جلو می‌رود

## معماری کلان سیستم Backtest

```
                Historical Data Lake
                        │
                        ▼
                Data Normalization
                        │
                        ▼
                  Event Builder
                        │
                        ▼
                Unified Event Timeline
                        │
                        ▼
                    Replay Engine
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
   Market Engine   Strategy Engine   Risk Engine
         │              │
         └──────► Execution Simulator ◄──────┐
                         │                    │
                   Market Rule Engine        │
                         │                    │
                      Fill Engine             │
                         │                    │
                     Portfolio Engine         │
                         │                    │
                     Analytics Engine         │
```

---

## 1. Data Layer

تمام داده‌های بازارها در یک Data Lake ذخیره می‌شوند.

### ساختار پیشنهادی

```
/data
   /tse
   /ifb
   /base_market
   /ime
   /energy
   /derivatives
   /bonds
```

### فرمت ذخیره

- Parquet
- Arrow

### داده‌ها

- trade
- quote
- orderbook snapshot
- auction
- status change
- corporate action

---

## 2. Event Builder

داده‌های هر بازار به event استاندارد تبدیل می‌شوند.

### ساختار event

```
event_id
timestamp
instrument_id
market_id
event_type
payload
```

### نمونه event

- TRADE
- QUOTE
- AUCTION
- SESSION_START
- SESSION_END
- STATUS_CHANGE
- CORPORATE_ACTION

---

## 3. Unified Event Timeline

تمام eventها در یک timeline قرار می‌گیرند.

### مرتب‌سازی

```
(timestamp, priority)
```

`priority` برای حل هم‌زمانی eventها استفاده می‌شود.

---

## 4. Replay Engine

هسته شبیه‌سازی.

### وظایف

- مدیریت clock
- dispatch eventها
- مدیریت چند نماد
- chunk loading از data lake

### توان هدف

- 100M event per run
- 1000+ instrument

---

## 5. Market Engine

این لایه state بازار را نگه می‌دارد.

### برای هر نماد

```
best_bid
best_ask
bid_volume
ask_volume
last_trade
queue_state
session_state
price_limit
```

Market Engine از Rule Engine استفاده می‌کند.

---

## 6. Market Rule Engine

مهم‌ترین بخش برای بازار ایران. هر بازار policy مخصوص دارد.

### ساختار

```
MarketRule
    session_rules
    price_limit_rules
    tick_size_rules
    auction_rules
    order_validation_rules
```

### Policy هر بازار

#### TSE Policy

```
price_limit = ±5%
session:
   preopen 08:45
   open 09:00
   close 12:30
volume_base = enabled
queue = enabled
```

#### IFB Policy

```
price_limit = ±5%
volume_base = enabled
liquidity_adjustment = high
```

#### Base Market Policy

```
price_limit:
   yellow 3%
   orange 2%
   red 1%

auction_mode = periodic
queue_model = weak_liquidity
```

#### ETF Policy

```
price_limit = ±5%
nav_reference = enabled
market_maker = optional
```

#### Bonds Policy

```
price_limit = small
yield_calculation = enabled
accrued_interest = enabled
```

#### Derivatives Policy

```
margin_required = true
daily_settlement = true
expiry = contract_specific
price_limit = contract_specific
```

#### IME Policy

```
session:
   preopen 11:45
   open 12:00
   close 18:00

auction = enabled
contract_spec = required
```

#### Energy Exchange Policy

```
auction_based
block_trades
delivery_rules
```

---

## 7. Execution Simulator

مدل اجرای سفارش.

### state سفارش

```
NEW
SUBMITTED
QUEUED
PARTIAL_FILL
FILLED
CANCELLED
REJECTED
```

### مدل اجرا

- market order
- limit order
- queue based execution
- impact model

---

## 8. Queue Simulation

برای بازار ایران حیاتی است.

### مدل صف

```
queue_position
cancel_rate
trade_rate
```

### احتمال fill

```
P(fill) = 1 - e^(-λV)
```

---

## 9. Corporate Action Engine

رویدادهای بنیادی را اعمال می‌کند.

```
dividend
capital increase
rights issue
split
merger
```

### اثرات

- adjust price
- adjust position

---

## 10. Portfolio Engine

### محاسبه

```
cash
positions
margin
exposure
pnl
fees
tax
```

### برای مشتقه

```
variation margin
daily settlement
```

---

## 11. Risk Engine

### قوانین ریسک

```
max_position
max_sector_exposure
max_drawdown
volatility_limit
```

می‌تواند اجرای سفارش را متوقف کند.

---

## 12. Analytics Engine

### محاسبه عملکرد

```
CAGR
Sharpe
Sortino
MaxDD
Turnover
WinRate
```

---

## 13. Experiment Engine

مدیریت تست‌ها.

### ذخیره

```
run_id
strategy
parameters
data_version
result
```

### برای

- grid search
- walk-forward
- monte carlo

---

## Deployment

```
Research Node
      │
      ▼
Job Scheduler
      │
 ┌────┴─────┐
 ▼          ▼
Worker 1   Worker 2
 ▼          ▼
Result Store
```

---

## ویژگی‌های مهم معماری

- **Multi‑market**
- **Rule‑based**
- **Event‑driven**
- **Deterministic**
- **Scalable**

### سطح پوشش برای بازار ایران

| بازار | پوشش |
|-------|------|
| سهام | 95% |
| فرابورس | 90% |
| بازار پایه | 85% |
| مشتقه | 75% |
| کالا | 70% |
| انرژی | 65% |
