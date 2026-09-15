from models.alert import AlertHistoryModel, AlertModel
from models.approval_gateway import ProposalAuditModel, ProposalModel
from models.audit_log import AuditLogModel
from models.backtest import BacktestRunModel, BacktestTradeModel
from models.base import Base
from models.codal import CodalReportModel
from models.compare import CompareResultModel

# Currency service (apps/currency_service) — manual positions tracker.
from models.currency import CurrencyManualPositionModel
from models.fund import FundModel
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
from models.provider_health import ProviderHealthHistoryModel, ProviderHealthModel
from models.quote import QuoteModel
from models.recommendation import RecommendationModel
from models.reference_db import ContractModel, MarketSnapshotModel
from models.screener import ScreenerProfile, ScreenerSignal, ScreenerSnapshot
from models.signal import SignalModel
from models.trade import TradeModel
from models.user import UserModel
