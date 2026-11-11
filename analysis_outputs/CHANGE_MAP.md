# Change Map

## Allowed Change Zones

- multi_market/market_adapter.py
- calibration/liquidity_depth_model.py
- costs/transaction_cost_model.py
- data/live_data_adapter.py
- execution/latency_model.py
- execution/order_models.py
- microstructure/cancel_model.py
- microstructure/impact_model.py
- portfolio/constraints.py
- risk/constraints.py
- risk/take_profit.py
- analytics/significance_tests.py

## Protected Eval Zones

- tests
- analytics/significance_tests.py
- alpha/fast_evaluator.py
- alpha/stress_testing.py
- calibration/validation.py
- engine/backtest_engine.py

## Data Interface Zones

- data/__init__.py
- data/data_source_registry.py
- data/data_versioning.py
- data/live_data_adapter.py
- data/memory_manager.py
- data/price_adjuster.py
- data/price_limits.py
- data/structural_break_detector.py

## Single-Variable High-Risk Zones

- tests
- analytics/significance_tests.py
- alpha/fast_evaluator.py
- alpha/stress_testing.py
- calibration/validation.py
- engine/backtest_engine.py
