"""Assistant 4 — market data adapters (source layer).

Exports
-------
MarketRecord, Quality, BaseAdapter
"""

from .base import DEFAULT_TTL_SECONDS, IR_TZ, BaseAdapter, MarketRecord, Quality
from .brsapi_adapter import BrsApiAdapter, brsapi_normalize
from .derivative_adapter import DerivativeAdapter, derivative_normalize
from .freshness_adapter import FreshnessAdapter, freshness_mark
from .news_adapter import FIXED_LABELS, NewsAdapter, news_normalize
from .silver_adapter import SilverAdapter, silver_normalize

__all__ = [
    "DEFAULT_TTL_SECONDS",
    "IR_TZ",
    "MarketRecord",
    "Quality",
    "BaseAdapter",
    "BrsApiAdapter",
    "brsapi_normalize",
    "DerivativeAdapter",
    "derivative_normalize",
    "FreshnessAdapter",
    "freshness_mark",
    "NewsAdapter",
    "news_normalize",
    "FIXED_LABELS",
    "SilverAdapter",
    "silver_normalize",
]
