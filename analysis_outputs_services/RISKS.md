# Suspicious Patterns

- adaptive_engine.py: verify optimizer parameter coverage if custom freezing is expected.
- cascade_engine.py: verify optimizer parameter coverage if custom freezing is expected.
- ensemble_optimizer.py: verify optimizer parameter coverage if custom freezing is expected.
- strategy_generator.py: verify optimizer parameter coverage if custom freezing is expected.
- quantitative/normalizer.py: repeated `sigmoid` usage detected; review for duplicated post-processing.
- quantitative/__init__.py: repeated `sigmoid` usage detected; review for duplicated post-processing.
- smart_money/__init__.py: repeated `sigmoid` usage detected; review for duplicated post-processing.
- Repository contains attention-like code but no obvious positional encoding signal was detected; review sequence-order handling.
