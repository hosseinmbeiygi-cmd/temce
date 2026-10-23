# Project Analysis Summary

- Target repo: `C:\Users\Iran\Desktop\temce\ml`
- README present: `True`
- Task family: `time-series-backtest-ml`
- Top-level items: README.md, __init__.py, __pycache__, artifacts.py, constants.py, contracts.py, dataset_builder.py, datasets, evaluation, exceptions.py, experiments.py, feature_store.py, features, global_registry.py, inference, metrics.py, model_loader.py, model_registry.py, models, policies.py
- Train entry candidates: train_weight_optimizer.py, training/__init__.py, training/callbacks.py, training/cv_trainer.py, training/dataloader.py
- Inference entry candidates: inference/__init__.py, inference/batch_predictor.py, inference/cache.py, inference/drift_detector.py, inference/label_encoder.py
- Evaluation entry candidates: datasets/validation.py, evaluation/__init__.py, evaluation/benchmark.py, evaluation/classification_report.py, evaluation/comparison.py
- Task-relevant files: experiments.py, features/candlestick_features.py, features/fundamental_features.py, evaluation/metrics.py, evaluation/regression_metrics.py

## Conservative Suggestions

- Read the main model or backbone file before changing configs.
- Verify the train entrypoint and config loading path before inserting new modules.
- Treat suspicious patterns as heuristics until confirmed by command-level evidence.
- Freeze one evaluation contract before comparing any candidate result against SOTA.

## Additional Documents

- `RESEARCH_MAP.md`
- `CHANGE_MAP.md`
- `EVAL_CONTRACT.md`
