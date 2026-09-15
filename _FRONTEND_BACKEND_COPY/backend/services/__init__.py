def get_analytics_service():
    from services.analytics_service import AnalyticsService

    return AnalyticsService


def get_codal_service():
    from services.codal_service import CodalService

    return CodalService


def get_market_service():
    from services.market_service import MarketService

    return MarketService


def get_news_service():
    from services.news_service import NewsService

    return NewsService


def get_quote_service():
    from services.quote_service import QuoteService

    return QuoteService


def get_recommendation_service():
    from services.recommendation_service import RecommendationService

    return RecommendationService


def get_signal_service():
    from services.signal_service import SignalService

    return SignalService


def get_symbol_service():
    from services.symbol_service import SymbolService

    return SymbolService


def get_backtest_service():
    from services.backtest_service import BacktestService

    return BacktestService


def get_training_service():
    from services.training_service import TrainingService

    return TrainingService


def get_inference_service():
    from services.inference_service import InferenceService

    return InferenceService


def get_report_service():
    from services.report_service import ReportService

    return ReportService


__all__ = [
    "get_analytics_service",
    "get_codal_service",
    "get_market_service",
    "get_news_service",
    "get_quote_service",
    "get_recommendation_service",
    "get_signal_service",
    "get_symbol_service",
    "get_backtest_service",
    "get_training_service",
    "get_inference_service",
    "get_report_service",
]
