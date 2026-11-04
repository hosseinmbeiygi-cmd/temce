# Change Map

## Allowed Change Zones

- inference/label_encoder.py
- model_loader.py
- model_registry.py
- models/__init__.py
- models/base.py
- models/checkpointer.py
- models/deep/__init__.py
- models/deep/attention.py
- train_weight_optimizer.py
- training/__init__.py
- training/callbacks.py
- training/cv_trainer.py

## Protected Eval Zones

- tests
- datasets/validation.py
- evaluation/__init__.py
- evaluation/benchmark.py
- evaluation/classification_report.py
- evaluation/comparison.py
- evaluation/metrics.py
- evaluation/regression_metrics.py

## Data Interface Zones

- dataset_builder.py
- datasets/__init__.py
- datasets/augmentation.py
- datasets/base.py
- datasets/builders.py
- datasets/cache.py
- datasets/labeling.py
- datasets/loaders.py

## Single-Variable High-Risk Zones

- tests
- datasets/validation.py
- evaluation/__init__.py
- evaluation/benchmark.py
- evaluation/classification_report.py
- evaluation/comparison.py
- evaluation/metrics.py
- evaluation/regression_metrics.py
- metrics.py
