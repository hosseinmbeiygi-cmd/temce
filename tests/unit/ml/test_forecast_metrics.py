from __future__ import annotations

import pytest


def test_mean_squared_error():
    from ml.metrics import ForecastMetrics

    metrics = ForecastMetrics()
    actual = [100, 200, 300, 400, 500]
    predicted = [110, 190, 310, 390, 510]
    mse = metrics.mse(actual, predicted)
    expected = sum((a - p) ** 2 for a, p in zip(actual, predicted, strict=False)) / len(actual)
    assert mse == pytest.approx(expected, rel=0.01)


def test_root_mean_squared_error():
    from ml.metrics import ForecastMetrics

    metrics = ForecastMetrics()
    actual = [100, 200, 300]
    predicted = [110, 190, 310]
    rmse = metrics.rmse(actual, predicted)
    assert rmse >= 0


def test_mean_absolute_error():
    from ml.metrics import ForecastMetrics

    metrics = ForecastMetrics()
    actual = [100, 200, 300]
    predicted = [110, 190, 310]
    mae = metrics.mae(actual, predicted)
    expected = sum(abs(a - p) for a, p in zip(actual, predicted, strict=False)) / len(actual)
    assert mae == pytest.approx(expected, rel=0.01)


def test_r2_score():
    from ml.metrics import ForecastMetrics

    metrics = ForecastMetrics()
    actual = [100, 200, 300, 400, 500]
    predicted = [110, 190, 310, 390, 510]
    r2 = metrics.r2(actual, predicted)
    assert r2 > 0


def test_direction_accuracy():
    from ml.metrics import ForecastMetrics

    metrics = ForecastMetrics()
    actual = [100, 200, 150, 300, 250]
    predicted = [110, 190, 160, 290, 260]
    acc = metrics.direction_accuracy(actual, predicted)
    assert 0 <= acc <= 100
