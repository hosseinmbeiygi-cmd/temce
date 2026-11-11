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
