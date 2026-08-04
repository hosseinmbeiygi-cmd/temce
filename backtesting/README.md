# 🧪 backtesting/ — موتور بک‌تست چندبازاری ایران

> **آخرین به‌روزرسانی:** ۲۰۲۶-۰۸-۰۱ — فاز ۹

موتور بک‌تست حرفه‌ای برای بازار سرمایه ایران با پشتیبانی از ۸ بازار مختلف.
معماری event-driven با قابلیت شبیه‌سازی سطح ۳ دفتر سفارشات، impact market و latency.

---

## 🏗️ معماری

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

### دو موتور اصلی

| موتور | فایل | توضیح |
|-------|------|-------|
| **BacktestEngine** | `engine/backtest_engine.py` | موتور ساده — bar-by-bar با clock، cash manager، position manager |
| **SimulationEngine** | `engine/simulation_engine.py` | موتور پیشرفته — event-driven با Level-3 order book، market impact، latency |

---

## 📁 ساختار — ۴۳ زیرپوشه

### 🎯 هسته (Core Engine)
| پوشه | توضیح |
|------|-------|
| `engine/` | هسته شبیه‌سازی — event loop، clock، data lake، market state، portfolio accounting |
| `market/` | موتور بازار — market engine، rule engine (قوانین هر بازار) |
| `execution/` | شبیه‌ساز اجرا — fill simulator، market impact، latency model، Level-3 order book |
| `orders/` | مدیریت سفارشات — order manager، order types |

### 📊 مدیریت ریسک و سرمایه
| پوشه/فایل | توضیح |
|-----------|-------|
| `risk/` | **PortfolioRiskEngine** (VaR, CVaR, Stress VaR, Tail Risk, Factor Exposure) + **PreTradeRiskEngine** (kill switch, drawdown, sector limits, daily loss) |
| `risk/stop_loss.py` | Stop Loss درصدی، مطلق، trailing |
| `risk/take_profit.py` | Take Profit درصدی و مطلق |
| `risk/position_sizing.py` | اندازه‌گیری پوزیشن با فرمول Kelly + volatility-adjusted |
| `risk/portfolio_risk.py` | ریسک پرتفوی — ۹ معیار مختلف |
| `capital/` | مدیریت سرمایه |
| `portfolio/` | PortfolioManager — NAV، cash، positions |

### 📈 استراتژی‌ها
| پوشه | توضیح |
|------|-------|
| `strategies/` | BaseStrategy + پیاده‌سازی‌های آماده (moving average cross و غیره) |
| `meta_strategy/` | استراتژی‌های متا |
| `signals/` | مدل‌های سیگنال — Signal dataclass، SignalModel abstract |

### 📉 متریک‌ها و آنالیز
| پوشه/فایل | توضیح |
|-----------|-------|
| `metrics/` | PerformanceMetrics، RiskMetrics، TradeMetrics، DrawdownMetrics |
| `metrics/risk_free_rate.py` | نرخ بدون ریسک بازار ایران (۱۵٪-۳۰٪) + داده‌های تاریخی ۱۳۹۵-۱۴۰۴ |
| `analytics/` | AnalyticsEngine |
| `reporting/` | گزارش‌گیری — Excel، PDF |
| `visualization/` | نمودارها |

### 🔬 پیشرفته
| پوشه | توضیح |
|------|-------|
| `microstructure/` | ریزساختار بازار |
| `calibration/` | کالیبراسیون پارامترها |
| `optimization/` | بهینه‌سازی — grid search، walk-forward |
| `experiment/` | مدیریت آزمایش‌ها |
| `research/` | ابزارهای تحقیقاتی |
| `hybrid/` | مدل‌های ترکیبی |
| `abm/` | Agent-Based Modeling |
| `scenarios/` | سناریوهای stress test |
| `data_quality/` | اعتبارسنجی داده |
| `multi_market/` | بک‌تست چندبازاری |
| `regime/` | تشخیص رژیم بازار |
| `relations/` | روابط بین نمادها |
| `features/` | feature engineering |
| `models/` | مدل‌های آماری |
| `platform/` | platform-specific |
| `universe/` | انتخاب universe |
| `utils/` | ابزارهای کمکی |
| `observability/` | مانیتورینگ |
| `costs/` | مدیریت هزینه‌ها |
| `api/` | API endpoints |
| `composer/` | ترکیب استراتژی‌ها |
| `corporate_actions.py` | اعمال رویدادهای شرکتی |
| `slippage.py` | ۳ مدل slippage — Fixed, Volume-Based, Volatility-Adjusted |

---

## 🐛 باگ‌های رفع‌شده (۱۰ مورد از ۲۰ مورد شناسایی‌شده)

این باگ‌ها در نسخه‌های قبلی شناسایی و رفع شده‌اند.
۱۰ باگ دیگر (عمدتاً low-priority) در backlog باقی مانده‌اند:

| # | باگ | فایل | توضیح |
|---|-----|------|-------|
| ۱ | Stop Loss درصدی | `risk/stop_loss.py:94` | چک نادرست در برابر entry price → رفع با `_entry_prices` dict |
| ۲ | Take Profit درصدی | `risk/take_profit.py:42` | مشابه Stop Loss → رفع با `_entry_prices` dict |
| ۵ | Volatility صفر | `risk/position_sizing.py:19` | تقسیم بر صفر → fallback به max position |
| ۶ | Kelly فرمول | `risk/position_sizing.py:24` | فرمول استاندارد Kelly برای payoff کسری |
| ۷ | محاسبه PnL | `metrics/trade_metrics.py:19` | جفت‌سازی خرید/فروش به ازای هر نماد |
| ۹ | Calmar Ratio | `metrics/risk_metrics.py:23` | max_drawdown از قبل درصد بود — واحد ناسازگار |
| ۱۰ | Omega Ratio | `metrics/risk_metrics.py:37` | تقسیم بر صفر — clamp به ۹۹۹۹ |
| ۱۱ | بازده مثبت | `metrics/risk_metrics.py:43` | Sortino با همه بازده مثبت → fallback |
| ۱۵ | فروش بدون موقعیت | `strategies/rule_based/moving_average_cross.py:45` | فروش وقتی long نیست |
| ۲۰ | انحراف معیار نمونه | `metrics/risk_metrics.py:16,56` | `ddof=1` برای سری بازده مالی |

---

## 📊 نرخ بدون ریسک — بازار ایران

| حالت | نرخ سالانه | توضیح |
|------|-----------|-------|
| `conservative` | ۱۵٪ | حداقل نرخ سپرده |
| `moderate` | ۲۵٪ | متوسط اوراق خزانه |
| `aggressive` | ۳۰٪ | نرخ سپرده بلندمدت |
| `inflation_hedged` | ۲۰٪ | بازده واقعی بالای تورم |

داده‌های تاریخی سالانه برای ۱۳۹۵ تا ۱۴۰۴ در `metrics/risk_free_rate.py` موجود است.

---

## 🧪 تست‌ها

- **۱۷۲ تست پاس** ✅ — پوشش کامل slippage، commission، execution، position sizing، metrics، rebalancing، stress testing، auction engine
- **ruff پاک** ✅ — کل ۴۳ زیرپوشه بدون خطا
- **همه importها سالم** ✅

---

## 📋 بازارهای پشتیبانی‌شده

| بازار | پوشش | ملاحظات |
|-------|------|---------|
| بورس تهران (TSE) | ۹۵٪ | ±۵٪ دامنه نوسان، volume-based |
| فرابورس (IFB) | ۹۰٪ | ±۵٪ دامنه، liquidity adjustment |
| بازار پایه | ۸۵٪ | دامنه ۱-۳٪، auction periodic |
| مشتقه | ۷۵٪ | margin، daily settlement |
| کالا (IME) | ۷۰٪ | auction، contract spec |
| انرژی | ۶۵٪ | block trades، delivery rules |
| ETF | ۹۰٪ | NAV reference |
| اوراق | ۸۰٪ | accrued interest، yield |

---

## 🚀 اجرای سریع

```python
from backtesting.engine.backtest_engine import BacktestEngine
from backtesting.risk.position_sizing import PositionSizing
from backtesting.risk.stop_loss import StopLoss
from backtesting.risk.take_profit import TakeProfit
from backtesting.metrics.risk_free_rate import get_risk_free_rate

engine = BacktestEngine(initial_capital=1_000_000_000)
sizing = PositionSizing(risk_per_trade_pct=1.0, max_position_pct=10.0)
stop = StopLoss(pct=2.0, trailing=True)
profit = TakeProfit(pct=5.0)
rf = get_risk_free_rate("moderate")  # 25%

result = await engine.run(strategy, market_data)
metrics = RiskMetrics.compute(result, risk_free_rate=rf)
```
