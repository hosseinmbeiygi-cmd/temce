from __future__ import annotations

import pytest


def test_sma_calculation():
    from pipelines.indicators import IndicatorPipeline

    pipeline = IndicatorPipeline()
    prices = [100, 102, 104, 103, 101, 105, 107, 106, 108, 110]
    sma = pipeline.sma(prices, period=5)
    assert len(sma) == len(prices)
    assert sma[-1] == pytest.approx(107.2, rel=0.1)


def test_ema_calculation():
    from pipelines.indicators import IndicatorPipeline

    pipeline = IndicatorPipeline()
    prices = [100, 102, 104, 103, 101, 105, 107, 106, 108, 110]
    ema = pipeline.ema(prices, period=5)
    assert len(ema) == len(prices)


def test_rsi_calculation():
    from pipelines.indicators import IndicatorPipeline

    pipeline = IndicatorPipeline()
    prices = [100, 102, 104, 103, 101, 105, 107, 106, 108, 110, 112, 109, 107, 111, 115]
    rsi = pipeline.rsi(prices, period=5)
    assert len(rsi) == len(prices)
    assert 0 <= rsi[-1] <= 100


def test_macd_calculation():
    from pipelines.indicators import IndicatorPipeline

    pipeline = IndicatorPipeline()
    prices = [100 + i * 2 for i in range(50)]
    macd_line, signal, histogram = pipeline.macd(prices)
    assert len(macd_line) == len(prices)
    assert len(signal) == len(prices)
    assert len(histogram) == len(prices)


def test_bollinger_bands():
    from pipelines.indicators import IndicatorPipeline

    pipeline = IndicatorPipeline()
    prices = [100, 102, 104, 103, 101, 105, 107, 106, 108, 110]
    upper, middle, lower = pipeline.bollinger_bands(prices, period=5, num_std=2)
    assert len(upper) == len(prices)
    assert all(upper[i] >= middle[i] >= lower[i] for i in range(len(prices)) if upper[i] is not None)

