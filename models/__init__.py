from models.alert import AlertHistoryModel, AlertModel
from models.audit_log import AuditLogModel
from models.backtest import BacktestRunModel, BacktestTradeModel
from models.base import Base
from models.codal import CodalReportModel
from models.compare import CompareResultModel
from models.corporate_action import CorporateActionModel, DailyAdjustFactorModel

# Currency service (apps/currency_service) — manual positions tracker.
from models.currency import CurrencyManualPositionModel
from models.fund import FundModel
from models.fund_compliance import (
    FundAmlAlertModel,
    FundAmlStrReportModel,
    FundClassAllocationModel,
    FundComplaintModel,
    FundCsdiReconciliationBreakModel,
    FundCsdiStatementModel,
    FundLifecycleEventModel,
    FundNavThresholdCalibrationModel,
    FundProspectusVersionModel,
    FundRelatedPartyTransactionModel,
    FundShariaApprovalModel,
    FundUnitClassModel,
)
from models.fund_enterprise import (
    FundCapabilityModel,
    FundHoldingModel,
    FundIngestionQuarantineModel,
    FundMarketQuoteCacheModel,
    FundNavHistoryModel,
    FundPortfolioDiffModel,
    FundPortfolioReportModel,
    FundScoreHistoryModel,
)
from models.fund_governance import (
    FundDisciplinaryCaseModel,
    FundFofValuationModel,
    FundGovernanceCommitteeModel,
    FundInsurancePolicyModel,
    FundInternalAuditReportModel,
    FundRegulatorAccessLogModel,
    FundTaxCalculationModel,
)
from models.fund_ledger import (
    ChartOfAccountModel,
    FundNavOutboxModel,
    JournalEntryModel,
    JournalLineModel,
)
from models.fund_nav import (
    FundNavReconciliationBreakModel,
    FundNavReconciliationRunModel,
    FundNavReferenceReportModel,
    FundNavResultModel,
    FundNavRunModel,
    FundNavThresholdModel,
    FundPositionValuationModel,
    FundUnitMovementModel,
)
from models.gold_macro import (
    GoldCotPositionModel,
    GoldEconomicCalendarEventModel,
    GoldIranManualEventModel,
    GoldMacroIndicatorModel,
)
from models.gold_options import GoldOptionIvHistoryModel
from models.indicator import IndicatorModel
from models.instrument import InstrumentModel
from models.job_run import JobRunModel
from models.macro import MacroIndicatorModel
from models.market import MarketModel
from models.market_data import (
    CommodityCertificateModel,
    CommodityFundModel,
    CommodityFuturesModel,
    CommodityGlobalPriceModel,
    CommodityOptionModel,
    CommodityTradeModel,
    DailyHistoryModel,
    DailyRealLegalModel,
    EtfNavModel,
    GoldCurrencyPriceModel,
    IndexModel,
    IntradayTradeModel,
    ShareholderModel,
    StockOptionModel,
    SymbolModel,
)
from models.ml import MlModelModel, MlModelVersionModel, MlTrainingRunModel
from models.news import NewsArticleModel
from models.orderbook import OrderbookModel
from models.paper_trading import (
    PaperEquityModel,
    PaperSignalSnapshotModel,
    PaperTradeModel,
)
from models.portfolio import PortfolioModel, PortfolioPositionModel
from models.pre_buy import PreBuyReview, PreBuySheet
from models.provider_health import ProviderHealthHistoryModel, ProviderHealthModel
from models.quote import QuoteModel
from models.recommendation import RecommendationModel
from models.screener import ScreenerProfile, ScreenerSignal, ScreenerSnapshot
from models.signal import SignalModel
from models.stock_enterprise import (
    MarketMacroIndicatorModel,
    StockIndicatorsSnapshotModel,
    StockLiveTapeModel,
    StockMonthlySalesModel,
    StockNewsSentimentModel,
    StockOrderBookL2Model,
    StockQuantSignalModel,
)
from models.trade import TradeModel
from models.user import UserModel

# DB-03: modules below were absent from this file so their tables never reached
# Base.metadata — Alembic --autogenerate would have proposed dropping them.
from models.alert_hub import SymbolAlertModel, SymbolAssessmentSnapshotModel
from models.approval_gateway import ProposalModel, ProposalAuditModel
from models.codal_analysis import (
    AccountMapping,
    AnalysisReport,
    AuditTrail,
    DataLineage,
    DimAccount,
    DimCompany,
    DimDate,
    DimDocument,
    DimReportType,
    FactFinancials,
    FactGrowth,
    FactQualitySignals,
    FactRatios,
    FactTextAnalytics,
)
from models.codal_financial import CodalFinancialStatementModel
from models.decision_engine import DecisionArchitecture, DecisionResult
from models.generated_strategy import GeneratedStrategyModel, GenerationBatchModel
from models.gold import (
    GoldFuturesPositionModel,
    GoldKillSwitchEventModel,
    GoldPortfolioHoldingModel,
)
from models.gold_feed_health import GoldFeedHealthAttemptModel
from models.news_items import NewsItemModel, NewsTagModel
from models.option import (
    OpenInterestHistoryModel,
    OptionContractModel,
    OptionSnapshotModel,
    OptionTradeModel,
    VolatilitySurfaceModel,
    CorporateActionModel as OptionCorporateActionModel,
)
from models.queue_analysis import QueueAnalysisResult
from models.reference_db import ContractModel, MarketSnapshotModel
from models.saved_filter import SavedFilter
from models.signal_accuracy import SignalAccuracyModel
from models.symbol_relation import SymbolRelationModel
