import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ingestion.market_data import AssetClass, MarketTick, QualityFlag
from ingestion.parser.market_data import CanonicalMarketDataParser
from ingestion.validation import MarketDataValidator


def tick(price: str = "100") -> MarketTick:
    return MarketTick(
        source="nobitex_usdt",
        instrument="USDTIRT",
        asset_class=AssetClass.CRYPTO,
        observed_at=datetime.now(UTC),
        price=price,
    )


def test_validator_flags_large_jump() -> None:
    report = MarketDataValidator().validate(
        [tick("130")],
        last_prices={("nobitex_usdt", "USDTIRT"): Decimal("100")},
    )
    assert report.suspicious == 1
    assert report.accepted[0].quality is QualityFlag.SUSPICIOUS


def test_validator_flags_stale_tick() -> None:
    old = tick()
    old = old.model_copy(update={"observed_at": datetime.now(UTC) - timedelta(hours=1)})
    report = MarketDataValidator().validate([old])
    assert report.accepted[0].quality is QualityFlag.STALE


def test_parser_emits_market_tick() -> None:
    parser = CanonicalMarketDataParser()
    events = asyncio.run(
        parser.parse(b'{"source":"wallex_usdt","records":[{"instrument":"USDTIRT","price":"600000"}]}')
    )
    assert events[0].event_type == "market_tick"
    assert events[0].data["instrument_id"] == "USDTIRT"
