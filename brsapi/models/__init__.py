"""
BrsApi SQLAlchemy ORM Models
=============================

All database models for the BrsApi integration layer.

New tables created by this module:

=============================== ===================================================
Table                           Purpose
=============================== ===================================================
``brsapi_symbol_snapshots``     Realtime snapshots of all TSETMC symbols
``brsapi_symbol_details``       Enriched symbol detail (Symbol.php endpoint)
``brsapi_index_values``         Index values (TSE, Farabours, selected)
``brsapi_nav_records``          NAV issue/redemption for ETF funds
``brsapi_option_snapshots``     Option contract snapshots (TSETMC)
``brsapi_intraday_trades``      Intraday trade ticks
``brsapi_historical_daily``     Daily historical price summaries
``brsapi_historical_real_legal`` Daily real/legal breakdowns
``brsapi_candlesticks``         OHLCV candlestick data
``brsapi_shareholder_records``  Shareholder composition snapshots
``brsapi_ime_futures``          IME futures contracts
``brsapi_ime_options``          IME option contracts
``brsapi_ime_certificates``     IME certificate/depository receipts
``brsapi_ime_funds``            IME commodity fund snapshots
``brsapi_ime_physical_trades``  IME physical trade records
``brsapi_commodity_prices``     Global commodity prices
``brsapi_crypto_prices``        Cryptocurrency prices
``brsapi_codal_announcements``  Codal announcements
``brsapi_raw_payloads``         Raw JSON audit trail
``brsapi_sync_log``             Sync operation tracking
=============================== ===================================================
"""

from brsapi.models.base import BrsApiBase, RawPayloadModel, SyncLogModel
from brsapi.models.codal import CodalAnnouncementModel
from brsapi.models.commodity import (
    CommodityPriceModel,
    Currency24hModel,
    CurrencyPriceModel,
    Gold24hModel,
    GoldCoinHistoryModel,
    GoldCoinPriceModel,
    GoldCurrencyProDailyHistoryModel,
    GoldCurrencyProHistory24hModel,
    GoldCurrencyProPriceModel,
)
from brsapi.models.crypto import CryptoPriceModel
from brsapi.models.ime import (
    ImeCertificateModel,
    ImeFundModel,
    ImeFutureModel,
    ImeOptionModel,
    ImePhysicalTradeModel,
)
from brsapi.models.tsetmc import (
    CandlestickModel,
    HistoricalDailyModel,
    HistoricalRealLegalModel,
    IndexValueModel,
    IntradayTradeModel,
    NavRecordModel,
    OptionSnapshotModel,
    ShareholderRecordModel,
    SymbolDetailModel,
    SymbolSnapshotModel,
)

__all__ = [
    "BrsApiBase",
    "RawPayloadModel",
    "SyncLogModel",
    # TSETMC
    "SymbolSnapshotModel",
    "SymbolDetailModel",
    "IndexValueModel",
    "NavRecordModel",
    "OptionSnapshotModel",
    "IntradayTradeModel",
    "HistoricalDailyModel",
    "HistoricalRealLegalModel",
    "CandlestickModel",
    "ShareholderRecordModel",
    # IME
    "ImeFutureModel",
    "ImeOptionModel",
    "ImeCertificateModel",
    "ImeFundModel",
    "ImePhysicalTradeModel",
    # Commodities / Crypto
    "CommodityPriceModel",
    "CryptoPriceModel",
    # Gold & Forex
    "GoldCoinPriceModel",
    "GoldCoinHistoryModel",
    "CurrencyPriceModel",
    "Currency24hModel",
    "Gold24hModel",
    # Gold & Currency Pro
    "GoldCurrencyProPriceModel",
    "GoldCurrencyProHistory24hModel",
    "GoldCurrencyProDailyHistoryModel",
    # Codal
    "CodalAnnouncementModel",
]
