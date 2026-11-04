"""Structural readiness for sukuk, FX futures and agricultural commodities."""

from __future__ import annotations

from datetime import datetime

from backtesting.multi_market import MarketAdapterFactory
from backtesting.multi_market import MarketType as AdapterMarketType
from core.constants import AssetClass, MarketType
from core.enums.instruments import CommodityKind, DerivativeUnderlying
from core.markets import (
    MARKET_REGISTRY,
    IntegrationStatus,
    get_market_definition,
    markets_requiring_integration,
)
from domain.instruments.instrument import Instrument
from providers.reference.instrument_master.market_classifier import MarketClassifier


def test_registry_covers_every_market_type() -> None:
    assert set(MARKET_REGISTRY) == set(MarketType)


def test_sukuk_is_modelled_but_not_fed() -> None:
    sukuk = get_market_definition(MarketType.SUKUK)
    assert sukuk.asset_class is AssetClass.SUKUK
    assert sukuk.integration_status is IntegrationStatus.PLANNED
    assert sukuk.data_sources == ()


def test_fx_futures_carry_a_currency_underlying() -> None:
    fx = get_market_definition(MarketType.FX)
    assert fx.underlying is DerivativeUnderlying.CURRENCY
    assert fx.integration_status is IntegrationStatus.PLACEHOLDER


def test_commodity_registry_covers_agriculture() -> None:
    commodity = get_market_definition(MarketType.COMMODITY)
    assert CommodityKind.AGRICULTURAL in commodity.commodity_kinds
    assert set(commodity.commodity_kinds) == set(CommodityKind)


def test_unfed_markets_are_reported() -> None:
    markets = {definition.market_type for definition in markets_requiring_integration()}
    assert {MarketType.SUKUK, MarketType.FX, MarketType.COMMODITY} <= markets


def test_every_adapter_market_type_has_a_working_adapter() -> None:
    for market_type in AdapterMarketType:
        adapter = MarketAdapterFactory.create(market_type)
        event = adapter.normalize_trade({"symbol": "X", "price": 10.0})
        assert event.market_type is market_type
        assert adapter.normalize_quote({}).event_type == "QUOTE"
        assert isinstance(adapter.normalize_execution_rules(), dict)


def test_classifier_recognises_new_markets() -> None:
    classifier = MarketClassifier()
    assert classifier.classify_market({"market": "بورس کالا"}) is MarketType.COMMODITY
    assert classifier.classify_market({"market": "بورس ارز"}) is MarketType.FX
    assert classifier.classify_market({"name": "صکوک اجاره"}) is MarketType.SUKUK
    assert classifier.classify_market({"name": "گندم"}) is MarketType.COMMODITY


def test_classifier_defaults_stay_unchanged() -> None:
    classifier = MarketClassifier()
    assert classifier.classify_market({"market": "بورس", "symbol": "فولاد"}) is MarketType.BOURS
    assert classifier.classify_market({"symbol": "ETF"}) is MarketType.ETF
    assert classifier.classify_market({"symbol": "AAPL"}) is MarketType.BOURS


def test_instrument_accepts_contract_terms() -> None:
    instrument = Instrument(
        id="inst-1",
        symbol="SUKUK1",
        maturity_date=datetime(2027, 1, 1),
        coupon_rate=0.2,
        underlying_symbol="USD_IRR",
        contract_size=1000,
    )
    assert instrument.maturity_date == datetime(2027, 1, 1)
    assert instrument.coupon_rate == 0.2
    assert instrument.underlying_symbol == "USD_IRR"
    assert instrument.contract_size == 1000
    assert Instrument(id="inst-2", symbol="EQ").coupon_rate is None
