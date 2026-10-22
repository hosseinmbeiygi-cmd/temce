"""STEP 5-FIX-2: per-contract IV history table and the daily snapshot.

Covers:
  - ``ImeOptionsChainProvider.load_iv_history`` reads ``gold_option_iv_history``
  - ``snapshot_option_iv`` stores (symbol, expiry, strike, iv, forward, as_of)
    and is idempotent per (symbol, as_of, strike)
  - ``derivatives.options.iv_history_min_days`` (N from config) is passed into
    the chain report and missing histories report ``unavailable`` honestly
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from models.gold_options import GoldOptionIvHistoryModel
from services.gold.black76_engine import black76_price
from services.gold.options_chain_service import (
    ImeOptionsChainProvider,
    snapshot_option_iv,
)

# The chain endpoint defaults to risk_free_rate=0.0 and the snapshot stores
# IVs computed the same way, so the fixture must price at r=0.0 as well.
R = 0.0


@pytest.fixture()
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(GoldOptionIvHistoryModel.__table__.create)
    async with AsyncSession(engine, expire_on_commit=False) as async_session:
        yield async_session
    await engine.dispose()


async def _count_rows(session) -> int:
    result = await session.execute(
        select(func.count()).select_from(GoldOptionIvHistoryModel)
    )
    return int(result.scalar_one())


def _iv_contract(
    key: str,
    strike: float = 100.0,
    option_type: str = "call",
    iv: float = 0.25,
    days: int = 30,
    expiry: str = "2027-01-15",
) -> dict:
    price = black76_price(100.0, strike, days / 365.0, R, iv, option_type)
    assert price > 0  # sanity: fixture must be a real option price
    return {
        "contract_key": key,
        "symbol": key,
        "strike": strike,
        "option_type": option_type,
        "market_price": price,
        "days_to_expiry": days,
        "expiry": expiry,
        "volume": 10,
        "open_interest": 10,
    }


class FakeChainProvider(ImeOptionsChainProvider):
    """ImeOptionsChainProvider with the DB replaced by fixed fixtures."""

    def __init__(self, contracts, *, forward: float | None = 100.0):
        super().__init__(session=None)
        self._contracts = contracts
        self._forward = forward

    async def load_contracts(self, *, commodity=None, limit=500):
        return [dict(contract) for contract in self._contracts]

    async def load_forward_price(self, *, commodity, expiry):
        return self._forward

    async def load_iv_history(self, contract_key, *, limit=60):
        return []

    async def load_previous_open_interest(self, contract_key):
        return None


class TestLoadIvHistory:
    async def test_returns_stored_series_newest_first(self, session):
        rows = [
            GoldOptionIvHistoryModel(
                symbol="IME-100-C",
                expiry="2027-01-15",
                strike=100.0,
                iv=0.21,
                forward=100.0,
                as_of=date(2026, 10, 20),
            ),
            GoldOptionIvHistoryModel(
                symbol="IME-100-C",
                expiry="2027-01-15",
                strike=100.0,
                iv=0.23,
                forward=100.0,
                as_of=date(2026, 10, 22),
            ),
            GoldOptionIvHistoryModel(
                symbol="IME-100-C",
                expiry="2027-01-15",
                strike=100.0,
                iv=0.22,
                forward=100.0,
                as_of=date(2026, 10, 21),
            ),
            GoldOptionIvHistoryModel(
                symbol="IME-OTHER",
                expiry="2027-01-15",
                strike=100.0,
                iv=0.99,
                forward=100.0,
                as_of=date(2026, 10, 22),
            ),
        ]
        session.add_all(rows)
        await session.commit()

        provider = ImeOptionsChainProvider(session)
        history = await provider.load_iv_history("IME-100-C", limit=10)

        assert history == pytest.approx([0.23, 0.22, 0.21])

    async def test_respects_limit_and_unknown_contract(self, session):
        provider = ImeOptionsChainProvider(session)
        assert await provider.load_iv_history("NOPE", limit=5) == []

        session.add_all(
            [
                GoldOptionIvHistoryModel(
                    symbol="IME-100-C",
                    expiry="2027-01-15",
                    strike=100.0,
                    iv=iv,
                    forward=100.0,
                    as_of=date(2026, 10, day),
                )
                for day, iv in ((10, 0.21), (11, 0.22), (12, 0.23))
            ]
        )
        await session.commit()

        history = await provider.load_iv_history("IME-100-C", limit=2)
        assert history == pytest.approx([0.23, 0.22])


class TestSnapshotOptionIv:
    async def test_stores_contract_rows_and_is_idempotent_per_day(self, session):
        provider = FakeChainProvider(
            [
                _iv_contract("IME-100-C", strike=100.0, option_type="call", iv=0.25),
                _iv_contract("IME-105-C", strike=105.0, option_type="call", iv=0.27),
            ]
        )
        as_of = date(2026, 10, 22)

        first = await snapshot_option_iv(session, as_of=as_of, provider=provider)
        assert first["stored"] == 2
        assert first["inserted"] == 2
        assert await _count_rows(session) == 2

        second = await snapshot_option_iv(session, as_of=as_of, provider=provider)
        assert second["inserted"] == 0
        assert second["updated"] + second["skipped"] == 2
        assert second["stored"] == 2
        # idempotent per (symbol, as_of, strike): still exactly two rows
        assert await _count_rows(session) == 2

        row = (
            await session.execute(
                select(GoldOptionIvHistoryModel).where(
                    GoldOptionIvHistoryModel.symbol == "IME-100-C"
                )
            )
        ).scalar_one()
        assert row.symbol == "IME-100-C"
        assert row.expiry == "2027-01-15"
        assert row.strike == pytest.approx(100.0)
        assert row.iv == pytest.approx(0.25, rel=1e-6)
        assert row.forward == pytest.approx(100.0)
        assert row.as_of == as_of

    async def test_new_day_appends_new_observations(self, session):
        provider = FakeChainProvider([_iv_contract("IME-100-C")])

        await snapshot_option_iv(
            session, as_of=date(2026, 10, 21), provider=provider
        )
        await snapshot_option_iv(
            session, as_of=date(2026, 10, 22), provider=provider
        )

        assert await _count_rows(session) == 2

    async def test_contracts_without_iv_are_counted_not_faked(self, session):
        provider = FakeChainProvider([_iv_contract("IME-100-C")], forward=None)

        result = await snapshot_option_iv(
            session, as_of=date(2026, 10, 22), provider=provider
        )

        assert result["stored"] == 0
        assert result["missing_iv"] == 1
        assert await _count_rows(session) == 0


class TestMinDaysConfigWiring:
    def test_config_supplies_iv_history_min_days(self):
        from core.config.ime_engine import load_ime_config

        cfg = load_ime_config()
        min_days = cfg["derivatives"]["options"]["iv_history_min_days"]
        assert isinstance(min_days, int)
        assert min_days >= 1

    def test_yaml_file_overrides_min_days(self, tmp_path):
        from core.config.ime_engine import load_ime_config

        yaml_path = tmp_path / "ime.yaml"
        yaml_path.write_text(
            "derivatives:\n  options:\n    iv_history_min_days: 14\n",
            encoding="utf-8",
        )
        cfg = load_ime_config(yaml_path)
        assert cfg["derivatives"]["options"]["iv_history_min_days"] == 14

    async def test_report_passes_configured_min_days(self, monkeypatch):
        import services.gold.options_chain_service as service_module

        # the service must read config through the real YAML loader
        assert service_module._ime_config().get("derivatives") is not None

        captured: dict = {}

        async def fake_build(provider, **kwargs):
            captured.update(kwargs)
            return {"available": True, "contracts": []}

        monkeypatch.setattr(
            service_module, "build_options_chain_report", fake_build
        )
        monkeypatch.setattr(
            service_module,
            "_ime_config",
            lambda: {"derivatives": {"options": {"iv_history_min_days": 30}}},
        )

        report = await service_module.get_options_chain_report(
            MagicMock(), commodity="GOLD"
        )

        assert captured["min_history_days"] == 30
        assert captured["iv_history_limit"] >= 30
        assert report["iv_history_source"] == "unavailable"
        assert "gold_option_iv_history" in report["iv_history_reason"]
