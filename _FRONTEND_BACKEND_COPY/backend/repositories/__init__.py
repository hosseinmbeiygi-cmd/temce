"""Repository layer — data access for domain entities.

Each repository follows the same dual-backend pattern:

- **InMemory** (no ``session``) — for dev, tests and the demo server.
- **PostgreSQL** (``AsyncSession``) — production, via ``DbRepository``.

Imports are **lazy** (PEP 562 ``__getattr__``): ``import repositories``
costs almost nothing and ``from repositories import InstrumentRepository``
loads only that one module — consistent with the project's sub-second
import-time goal (see ``apps/api/router.py``).
"""

from __future__ import annotations

# Maps public name → module that defines it.
_LAZY_IMPORTS: dict[str, str] = {
    "BaseRepository": "repositories.base_repository",
    "InMemoryRepository": "repositories.base_repository",
    "InstrumentRepository": "repositories.instrument_repository",
    "QuoteRepository": "repositories.quote_repository",
    "SignalRepository": "repositories.signal_repository",
    "IndicatorRepository": "repositories.indicator_repository",
    "RecommendationRepository": "repositories.recommendation_repository",
    "CodalRepository": "repositories.codal_repository",
    "NewsRepository": "repositories.news_repository",
    "UserRepository": "repositories.user_repository",
    "User": "repositories.user_repository",
    "AlertRepository": "repositories.alert_repository",
    "AlertHistory": "repositories.alert_repository",
    "BacktestRepository": "repositories.backtest_repository",
    "TradeRepository": "repositories.trade_repository",
    "Trade": "repositories.trade_repository",
    "MacroRepository": "repositories.macro_repository",
    "MarketRepository": "repositories.market_repository",
    "Market": "repositories.market_repository",
    "MlRepository": "repositories.ml_repository",
    "MlModel": "repositories.ml_repository",
    "OrderBookRepository": "repositories.orderbook_repository",
    "FundRepository": "repositories.fund_repository",
    "PortfolioRepository": "repositories.portfolio_repository",
    "PredictionRepository": "repositories.prediction_repository",
}

__all__ = list(_LAZY_IMPORTS)


def __getattr__(name: str):
    module_name = _LAZY_IMPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(module_name)
    attr = getattr(module, name)
    # Cache the resolved attribute on this module for fast repeat access.
    globals()[name] = attr
    return attr
