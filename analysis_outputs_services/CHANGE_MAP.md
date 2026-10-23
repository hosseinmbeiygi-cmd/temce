# Change Map

## Allowed Change Zones

- fund_api_adapter.py
- ime_signal_adapter.py
- backtest/cost_model.py
- smart_money/config_loader.py
- auto_retrain_pipeline.py
- global_training_service.py
- training_service.py
- chat/sentiment_analyzer.py
- codal_analysis/point_in_time.py
- fund_circuit_breaker.py
- fund_class_nav.py
- fund_compliance.py

## Protected Eval Zones

- tests
- options_backtest_service.py
- backtest/cost_model.py
- backtest_framework.py
- backtest_service.py
- codal_analysis/audit_control_testing.py

## Data Interface Zones

- data_layer.py
- data_mesh/__init__.py
- historical_data_service.py
- smart_money/config_loader.py
- smart_money/data_quality.py

## Single-Variable High-Risk Zones

- tests
- options_backtest_service.py
- backtest/cost_model.py
- backtest_framework.py
- backtest_service.py
- codal_analysis/audit_control_testing.py
- smart_money/config_loader.py
