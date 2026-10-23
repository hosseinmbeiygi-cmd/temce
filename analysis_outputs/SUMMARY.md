# Project Analysis Summary

- Target repo: `C:\Users\Iran\Desktop\temce\backtesting`
- README present: `True`
- Task family: `time-series-backtest-ml`
- Top-level items: ARCHITECTURE.md, README.md, __init__.py, __pycache__, abm, alpha, analytics, api, calibration, capital, commission.py, composer, constants.py, contracts.py, corporate_actions.py, costs, costs.py, data, data_quality, engine
- Train entry candidates: portfolio/constraints.py, risk/constraints.py, risk/take_profit.py
- Inference entry candidates: none
- Evaluation entry candidates: analytics/significance_tests.py, alpha/fast_evaluator.py, alpha/stress_testing.py, calibration/validation.py, engine/backtest_engine.py
- Task-relevant files: analytics/significance_tests.py, calibration/regime_transition.py, engine/market_state.py, engine/unified_timeline.py, execution/market_impact.py

## Conservative Suggestions

- Read the main model or backbone file before changing configs.
- Verify the train entrypoint and config loading path before inserting new modules.
- Treat suspicious patterns as heuristics until confirmed by command-level evidence.
- Freeze one evaluation contract before comparing any candidate result against SOTA.

## Additional Documents

- `RESEARCH_MAP.md`
- `CHANGE_MAP.md`
- `EVAL_CONTRACT.md`
