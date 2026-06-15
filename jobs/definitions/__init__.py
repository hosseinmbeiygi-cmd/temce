from jobs.definitions.analytics_jobs import AnalyticsComputationJob, IndicatorCalculationJob
from jobs.definitions.backtest_jobs import BacktestExecutionJob, BacktestOptimizationJob
from jobs.definitions.codal_jobs import CodalIngestionJob, CodalSyncJob
from jobs.definitions.housekeeping_jobs import CacheWarmupJob, DataRetentionJob, HealthCheckJob
from jobs.definitions.macro_jobs import GoldPriceJob, MacroDataJob, MetalsPriceJob
from jobs.definitions.market_data_jobs import HistoricalDataJob, QuoteIngestionJob, RealtimeQuoteJob
from jobs.definitions.ml_jobs import BatchInferenceJob, ModelEvaluationJob, ModelTrainingJob
from jobs.definitions.news_jobs import NewsIngestionJob, NewsSentimentJob
from jobs.definitions.recommendation_jobs import RecommendationEvaluationJob, RecommendationGenerationJob
from jobs.definitions.reference_jobs import AliasResolutionJob, InstrumentSyncJob
from jobs.definitions.signal_jobs import SignalEvaluationJob, SignalGenerationJob

__all__ = [
    "QuoteIngestionJob",
    "HistoricalDataJob",
    "RealtimeQuoteJob",
    "CodalIngestionJob",
    "CodalSyncJob",
    "NewsIngestionJob",
    "NewsSentimentJob",
    "MacroDataJob",
    "GoldPriceJob",
    "MetalsPriceJob",
    "InstrumentSyncJob",
    "AliasResolutionJob",
    "SignalGenerationJob",
    "SignalEvaluationJob",
    "RecommendationGenerationJob",
    "RecommendationEvaluationJob",
    "AnalyticsComputationJob",
    "IndicatorCalculationJob",
    "ModelTrainingJob",
    "BatchInferenceJob",
    "ModelEvaluationJob",
    "BacktestExecutionJob",
    "BacktestOptimizationJob",
    "DataRetentionJob",
    "CacheWarmupJob",
    "HealthCheckJob",
]
