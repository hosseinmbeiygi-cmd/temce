# Project Analysis Summary

- Target repo: `C:\Users\Iran\Desktop\temce\services`
- README present: `True`
- Task family: `time-series-backtest-ml`
- Top-level items: README.md, __init__.py, __pycache__, accuracy_outcome_queue.py, adaptive_engine.py, adjusted_price_reader.py, alert_service.py, analytics_service.py, auto_retrain_pipeline.py, backtest, backtest_framework.py, backtest_service.py, block_trade_detector.py, broker, calibration_loop.py, cascade_engine.py, chat, codal_accounting_service.py, codal_analysis, codal_attachment_service.py
- Train entry candidates: auto_retrain_pipeline.py, global_training_service.py, training_service.py
- Inference entry candidates: gap_prediction.py, inference_service.py
- Evaluation entry candidates: options_backtest_service.py, backtest/cost_model.py, backtest_framework.py, backtest_service.py, codal_analysis/audit_control_testing.py
- Task-relevant files: chat/sentiment_analyzer.py, codal_analysis/point_in_time.py, fund_api_adapter.py, fund_circuit_breaker.py, fund_class_nav.py

## Conservative Suggestions

- Read the main model or backbone file before changing configs.
- Verify the train entrypoint and config loading path before inserting new modules.
- Treat suspicious patterns as heuristics until confirmed by command-level evidence.
- Freeze one evaluation contract before comparing any candidate result against SOTA.

## Additional Documents

- `RESEARCH_MAP.md`
- `CHANGE_MAP.md`
- `EVAL_CONTRACT.md`
