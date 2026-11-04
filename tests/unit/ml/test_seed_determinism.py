"""Task 5: bit-by-bit determinism — same seed => identical tuning result."""
import numpy as np


def _data():
    rng = np.random.RandomState(0)
    X = rng.normal(size=(120, 4))
    y = (X[:, 0] + rng.normal(size=120) * 0.2 > 0).astype(int)
    return X, y


def test_tuning_deterministic_bit_by_bit():
    from sklearn.linear_model import LogisticRegression

    from ml.training.hyperparameter_tuning import HyperparameterTuner

    X, y = _data()
    space = {"C": [0.1, 1.0, 10.0]}
    r1 = HyperparameterTuner(n_trials=6, n_folds=3, horizon=1, seed=42).optimize(
        LogisticRegression, space, X, y
    )
    r2 = HyperparameterTuner(n_trials=6, n_folds=3, horizon=1, seed=42).optimize(
        LogisticRegression, space, X, y
    )
    assert r1 == r2, (r1, r2)


def test_seed_wired_into_entrypoints():
    import inspect

    from backtesting import runner as rmod
    from jobs import backtest_run as jb
    from jobs import model_training as jm
    from ml.training import hyperparameter_tuning as ht
    from ml.training import trainer as tr

    assert "set_global_seed" in inspect.getsource(tr.Trainer.train)
    assert "set_global_seed" in inspect.getsource(ht.HyperparameterTuner.optimize)
    assert "set_global_seed" in inspect.getsource(jb.BacktestRunJob.execute)
    assert "set_global_seed" in inspect.getsource(jm.ModelTrainingJob.execute)
    assert "set_global_seed" in inspect.getsource(rmod.BacktestRunner.run)
