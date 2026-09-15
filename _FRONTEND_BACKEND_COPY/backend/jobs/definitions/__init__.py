from jobs.definitions.alert_jobs import EvaluateAlertsJob
from jobs.definitions.analytics_jobs import AnalyticsComputationJob, IndicatorCalculationJob
from jobs.definitions.backtest_jobs import BacktestExecutionJob, BacktestOptimizationJob
from jobs.definitions.brsapi_jobs import (
    BrsApiAllSymbolsJob,
    BrsApiCodalJob,
    BrsApiCommoditiesJob,
    BrsApiCryptoJob,
    BrsApiImeCertificatesJob,
    BrsApiImeFundsJob,
    BrsApiImeFuturesJob,
    BrsApiImeOptionsJob,
    BrsApiImePhysicalJob,
    BrsApiIndexFaraboursJob,
    BrsApiIndexJob,
    BrsApiIndexSelectedJob,
    BrsApiOptionsJob,
)
from jobs.definitions.brsapi_ready_check_job import BrsApiReadyCheckJob
from jobs.definitions.codal_jobs import CodalAttachmentDownloadJob, CodalIngestionJob, CodalSyncJob
from jobs.definitions.feature_store_jobs import FeatureStoreBuildJob, ScreenerDailyScoresJob
from jobs.definitions.fund_jobs import FundsSyncJob
from jobs.definitions.housekeeping_jobs import (
    CacheWarmupJob,
    DataRetentionJob,
    HealthCheckJob,
    RefreshMaterializedViewsJob,
)
from jobs.definitions.macro_jobs import GoldPriceJob, MacroDataJob, MetalsPriceJob
from jobs.definitions.market_data_jobs import HistoricalDataJob, QuoteIngestionJob, RealtimeQuoteJob
from jobs.definitions.ml_jobs import BatchInferenceJob, ModelEvaluationJob, ModelTrainingJob
from jobs.definitions.news_jobs import NewsIngestionJob, NewsSentimentJob
from jobs.definitions.paper_trading_job import PaperTradingJob
from jobs.definitions.recommendation_jobs import RecommendationEvaluationJob, RecommendationGenerationJob
from jobs.definitions.reference_jobs import AliasResolutionJob, InstrumentSyncJob
from jobs.definitions.screener_jobs import Screener110RunCycleJob
from jobs.definitions.signal_jobs import SignalEvaluationJob, SignalGenerationJob
from jobs.definitions.sync_jobs import (
    SyncCodalJob,
    SyncInstrumentsJob,
    SyncNavAllJob,
    SyncQuotesJob,
    SyncSnapshotsToQuotesJob,
)
from services.history_backfill_service import BackfillHistoricalDataJob

__all__ = [
    "BackfillHistoricalDataJob",
    "BrsApiAllSymbolsJob",
    "BrsApiReadyCheckJob",
    "BrsApiCodalJob",
    "BrsApiCommoditiesJob",
    "BrsApiCryptoJob",
    "BrsApiImeCertificatesJob",
    "BrsApiImeFundsJob",
    "BrsApiImeFuturesJob",
    "BrsApiImeOptionsJob",
    "BrsApiImePhysicalJob",
    "BrsApiIndexFaraboursJob",
    "BrsApiIndexJob",
    "BrsApiIndexSelectedJob",
    "BrsApiOptionsJob",
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
    "Screener110RunCycleJob",
    "SignalGenerationJob",
    "SignalEvaluationJob",
    "SyncCodalJob",
    "SyncInstrumentsJob",
    "SyncNavAllJob",
    "SyncQuotesJob",
    "SyncSnapshotsToQuotesJob",
    "RecommendationGenerationJob",
    "RecommendationEvaluationJob",
    "AnalyticsComputationJob",
    "IndicatorCalculationJob",
    "EvaluateAlertsJob",
    "ModelTrainingJob",
    "BatchInferenceJob",
    "ModelEvaluationJob",
    "BacktestExecutionJob",
    "BacktestOptimizationJob",
    "CodalAttachmentDownloadJob",
    "PaperTradingJob",
    "FundsSyncJob",
    "FeatureStoreBuildJob",
    "ScreenerDailyScoresJob",
    "DataRetentionJob",
    "CacheWarmupJob",
    "HealthCheckJob",
    "RefreshMaterializedViewsJob",
]
