from __future__ import annotations


class ForecastingError(Exception):
    pass


class StaleDataError(ForecastingError):
    pass


class OutlierDataError(ForecastingError):
    pass


class NoDataError(ForecastingError):
    pass


class UnknownSymbolError(ForecastingError):
    pass


class FairValueNotApplicableError(ForecastingError):
    pass
