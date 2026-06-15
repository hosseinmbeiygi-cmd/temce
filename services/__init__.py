from services.analytics_service import AnalyticsService
from services.codal_service import CodalService
from services.market_service import MarketService
from services.news_service import NewsService
from services.quote_service import QuoteService
from services.recommendation_service import RecommendationService
from services.signal_service import SignalService
from services.symbol_service import SymbolService


def get_backtest_service():
    from services.backtest_service import BacktestService

    return BacktestService


def get_training_service():
    from services.training_service import TrainingService

    return TrainingService


def get_inference_service():
    from services.inference_service import InferenceService

    return InferenceService


__all__ = [
    "SymbolService",
    "QuoteService",
    "MarketService",
    "AnalyticsService",
    "SignalService",
    "RecommendationService",
    "CodalService",
    "NewsService",
]
