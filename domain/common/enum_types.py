"""Domain enum aliases.

The single definition lives in :mod:`core.constants` so infrastructure code can
use these enums without importing the domain layer. This module preserves the
historical ``domain.common.enum_types`` import path.
"""

from __future__ import annotations

from core.constants import (
    AssetClass,
    DataSource,
    InstrumentStatus,
    JobStatus,
    MarketType,
    ModelStage,
    OrderSide,
    OrderType,
    ProviderHealth,
    RecommendationAction,
    SignalType,
    TimeFrame,
    TimeSeriesGranularity,
)

__all__ = [
    "AssetClass",
    "DataSource",
    "InstrumentStatus",
    "JobStatus",
    "MarketType",
    "ModelStage",
    "OrderSide",
    "OrderType",
    "ProviderHealth",
    "RecommendationAction",
    "SignalType",
    "TimeFrame",
    "TimeSeriesGranularity",
]
