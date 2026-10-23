# FINAL QA AUDIT REPORT (Linear Mode — Phase 1–4)

Concurrency: 1 (sequential, no sub-agents). App source untouched; artifacts only in qa/, reports/.

## 1. Executive Summary & Stack
Monorepo: Python backend (src/, core/, backtesting/, api/), TS frontend (frontend/src), funds/compliance/NAV modules. Route scan via frontend/src found 35 path-like entries (mostly /funds/v2/* API paths, not React routes); src/ has 61 py files. Full 127-view crawl NOT executed (requires service boot + auth); no services started to avoid state mutation.

## 2. Discovered vs Tested Matrix
| Capability | Discovered | Tested |
|---|---|---|
| Funds/NAV/compliance APIs | yes (sample in dependencies.map.json) | static only |
| gold_desk P&L/backtest/signal | yes | math-sanity subset only |
| UI 127 views | not confirmed (router scan inconclusive) | deferred |
| Alerts lifecycle (15) | code present (alert_engine) | deferred |
| Concurrency stress | — | deferred (no live env) |

## 3. UI Crawl Register
Not executed live. Blocker: need boot + auth + deterministic mocks. Screenshots: none. Treat all views as UNTESTED.

## 4. Financial Domain & Alerts
Static signals: float() casts on price closes in gold_desk/backtest.py:49, pattern_detector.py:61, signal_engine.py:25; pricer fair-value uses float division; portfolio P&L module flagged float. Requires Decimal migration on accounting paths. Chart/NAV/alert lifecycle: untested live.

## 5. Stress Runs (200-scenario)
Executed 5/5 math-sanity cases (bull/bear/flat/single/empty): PASS, mdd<=0 guarded, sharpe div-by-zero guarded. Full 75+55+50+20 suite deferred; harness stub + results in reports/results.json, details reports/stability_report.md.

## 6. Concurrency & Race Findings (static)
No live fire. Static risk: alert cooldown/event insert, DCA/auto_trade logging, backtest job submission lack visible idempotency keys/mutex in scanned files — recommend idempotency-key + unique constraints before launch.

## 7. Top Vulnerabilities (from qa/math_integrity.log)
Top float-without-Decimal hotspots: src/gold_desk/backtest.py:49, backtest_real.py:9, backtest_runner.py:4, portfolio.py:1, pricer.py:4, fair_value.py:9, forecaster.py:1, signal_engine.py:25, pattern_detector.py:61, nav_checker.py:1 (+20 more in log). Impact: rounding on P&L/NAV/fees. Patch: use Decimal for money, guard peak==0 in drawdown, guard std==0 in Sharpe (already in sanity harness), store integer rials where possible.

## 8. Readiness Score: 32/100
- UI & Navigation (30): 5 — no live crawl
- Financial Precision (25): 10 — float on money paths
- Backtest/ML Reliability (25): 10 — sanity only
- Concurrency/Code Resilience (20): 7 — no idempotency proof
See reports/readiness_score.json.

## 9. Verdict: NO-GO
P0: boot deterministic env + auth harness; live 127-view crawl with screenshots; migrate money math to Decimal; add idempotency on orders/alerts/backtest jobs.
P1: full 200-scenario run with frozen snapshots; chart timeframe leak checks; alert persistence tests.
P2: expand route catalog (backend OpenAPI + frontend router); cleanup script for synthetic data.


---

# TOP 30 Static Code Vulnerabilities

## 1. src\domain\entities.py:1 [lookahead-risk]
```python
from __future__ import annotations
```
Impact: lookahead-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 2. src\features\calendar.py:1 [lookahead-risk]
```python
from __future__ import annotations
```
Impact: lookahead-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 3. src\features\fair_value.py:1 [lookahead-risk]
```python
from __future__ import annotations
```
Impact: lookahead-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 4. src\features\fair_value.py:28 [float-cast-money-risk]
```python
lp = float(local_price)
```
Impact: float-cast-money-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 5. src\features\fair_value.py:29 [float-cast-money-risk]
```python
fv = float(fair_value)
```
Impact: float-cast-money-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 6. src\features\fair_value.py:36 [float-cast-money-risk]
```python
fv = float(fair_value)
```
Impact: float-cast-money-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 7. src\forecasting\service.py:3 [lookahead-risk]
```python
Projects future prices from real daily closes stored in the database using a
```
Impact: lookahead-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 8. src\forecasting\service.py:8 [lookahead-risk]
```python
from __future__ import annotations
```
Impact: lookahead-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 9. src\forecasting\service.py:77 [float-cast-money-risk]
```python
clean = [float(c) for c in closes if c is not None and float(c) > 0]
```
Impact: float-cast-money-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 10. src\forecasting\service.py:87 [float-cast-money-risk]
```python
anchor = float(last_close) if last_close and float(last_close) > 0 else None
```
Impact: float-cast-money-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 11. src\forecasting\service.py:137 [float-cast-money-risk]
```python
fv = float(fair_value_gold_irr(xau_usd, usd_irr))
```
Impact: float-cast-money-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 12. src\forecasting\service.py:209 [float-cast-money-risk]
```python
return [(str(d), float(p)) for d, p in rows if d and p and float(p) > 0]
```
Impact: float-cast-money-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 13. src\forecasting\service.py:221 [float-cast-money-risk]
```python
return [(str(d), float(p)) for d, p in rows if d and p and float(p) > 0]
```
Impact: float-cast-money-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 14. src\forecasting\service.py:235 [float-cast-money-risk]
```python
if date and price and float(price) > 0:
```
Impact: float-cast-money-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 15. src\forecasting\service.py:236 [float-cast-money-risk]
```python
by_date[str(date)] = float(price)
```
Impact: float-cast-money-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 16. src\forecast_engine\config.py:3 [lookahead-risk]
```python
from __future__ import annotations
```
Impact: lookahead-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 17. src\forecast_engine\exceptions.py:3 [lookahead-risk]
```python
from __future__ import annotations
```
Impact: lookahead-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 18. src\forecast_engine\forecasting_service.py:3 [lookahead-risk]
```python
from __future__ import annotations
```
Impact: lookahead-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 19. src\forecast_engine\forecasting_service.py:54 [money-math-no-decimal]
```python
base_price_per_gram = (xau_price * usd_price) / TROY_OUNCE_GRAMS
```
Impact: money-math-no-decimal may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 20. src\forecast_engine\forecasting_service.py:97 [money-math-no-decimal]
```python
new_ema = (current_market_price * alpha) + (previous_ema * (1 - alpha))
```
Impact: money-math-no-decimal may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 21. src\forecast_engine\redis_adapter.py:3 [lookahead-risk]
```python
from __future__ import annotations
```
Impact: lookahead-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 22. src\forecast_engine\redis_adapter.py:42 [float-cast-money-risk]
```python
return float(val)
```
Impact: float-cast-money-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 23. src\forecast_engine\safe_forecast.py:1 [lookahead-risk]
```python
from __future__ import annotations
```
Impact: lookahead-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 24. src\forecast_engine\symbol_registry.py:1 [lookahead-risk]
```python
from __future__ import annotations
```
Impact: lookahead-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 25. src\gold_desk\alert_engine.py:7 [lookahead-risk]
```python
from __future__ import annotations
```
Impact: lookahead-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 26. src\gold_desk\alert_engine.py:46 [float-cast-money-risk]
```python
return float(snap.score.total)
```
Impact: float-cast-money-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 27. src\gold_desk\api.py:6 [lookahead-risk]
```python
from __future__ import annotations
```
Impact: lookahead-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 28. src\gold_desk\api.py:459 [perf-metric-risk]
```python
مقایسه با buy-and-hold، محاسبه alpha، max drawdown، Sharpe.
```
Impact: perf-metric-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 29. src\gold_desk\api.py:483 [perf-metric-risk]
```python
"max_drawdown_pct": m.max_drawdown_pct,
```
Impact: perf-metric-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## 30. src\gold_desk\api.py:484 [perf-metric-risk]
```python
"sharpe_ratio": m.sharpe_ratio,
```
Impact: perf-metric-risk may corrupt P&L/NAV/fees or metrics.
Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.

## Appendix A - Idempotency carriers (static): services/accuracy_outcome_queue.py, services/broker/paper_broker.py, services/fund_identity.py, services/fund_ledger.py, services/fund_nav_engine.py, services/news_sentiment_pipeline.py, services/signal_composer.py

# Alerts Deep Dive (ویژه)

Sources: src/gold_desk/alert_engine.py:89-132, services/alert_service.py:203-288, app/alert_hub/repository.py:20-68, src/gold_desk/models.py:85-121

## معماری سه‌گانه (ناهمگن)
1. gold_desk engine: rule(edge: bubble/price/score/parity) + cooldown + event insert + telegram. بدون user_id روی rule/event.
2. AlertService (AlertModel): instrument_id OR symbol match، cooldown، history insert، channels console/sound/telegram/email.
3. alert_hub (SymbolAlertModel): upsert per (user,symbol)، deactivate نرم، snapshot جدا، cleanup snapshots غیرفعال.

## چرخه عمر
- Create: service OK (commit دارد :101)؛ hub upsert OK؛ gold seed فقط اگر جدول خالی :179.
- Toggle: service update enabled (flush بدون commit -> به commit بیرونی وابسته است :120)؛ hub is_active مشابه.
- Trigger: هر دو cooldown دارند؛ gold بر اساس last_fired_at روی rule؛ service بر اساس last_triggered روی alert.
- Delete: service حذف فیزیکی alert ولی history یتیم می‌ماند (بدون cascade دیده‌شده) -> ghost records؛ gold هیچ delete API ندارد -> ghost rules/events؛ hub فقط deactivate (نه حذف) + cleanup snapshots.
- Persistence: last_fired/last_triggered در DB ذخیره می‌شود پس reload/re-login حفظ می‌شود، مشروط بر commit موفق.

## ریسک‌های P0/P1
- P0-1 gold AlertRuleModel فاقد user_id است (models.py:85-102): نشت بین‌کاربری — کاربر A قانون کاربر B را می‌بیند/تریگر می‌کند. Patch: ستون user_id + فیلتر where در evaluate_rules.
- P0-2 Race double-fire: چک cooldown در حافظه سپس commit واحد (:106-130)؛ دو worker همزمان هر دو insert می‌کنند. همچنین service با flush (:284) بدون lock. Patch: select_for_update روی rule/alert یا unique constraint روی (rule_id, time_bucket) + on-conflict-do-nothing.
- P1-1 service update/delete فقط flush می‌کنند (نه commit) — اگر caller commit نکند toggle/delete گم می‌شود؛ تست reload باید commit صریح را assert کند.
- P1-2 یتیم‌ماندن history پس از delete (بدون FK cascade) و نبود delete در gold engine — نیاز به purge job + تست ghost-record.
- P1-3 Telegram failure نادیده گرفته می‌شود ولی event ثبت می‌شود (at-least-once)؛ باید delivered flag روی event هم ثبت شود مثل service.
- P2 float threshold/trigger (Float columns) — برای آستانه حساسیت 0.001 در eq/neq کافی است ولی برای قیمت ریالی Decimal توصیه می‌شود.

## چک‌لیست 15 آلرت پیشنهادی (قابل اجرای live)
Price>, Price<, %change, MA-cross x2, RSI x2, bubble_above/below, nav_bubble, score_above/below, parity_gap, signal TP/SL, cooldown-verify — سپس toggle/reload/trigger/delete برای هر کدام.
