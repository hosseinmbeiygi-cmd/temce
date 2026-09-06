"""Rate collectors. Fixture (default) or live Tgju/Nobitex via CURRENCY_USE_LIVE."""

from __future__ import annotations

from apps.currency_service.domain.entities import RateSnapshot
from apps.currency_service.infra.fixtures import load_fixture_snapshot


class FixtureCollector:
    """Returns a fresh ``RateSnapshot`` per call.

    No network. No DB. Stateless — pure in-memory mock.
    """

    async def fetch(self) -> RateSnapshot:
        return load_fixture_snapshot()


def get_collector():
    """FixtureCollector unless CURRENCY_USE_LIVE=true → LiveCollector."""
    from apps.currency_service.config import settings

    if settings.use_live:
        from apps.currency_service.infra.collectors import LiveCollector

        return LiveCollector()
    return FixtureCollector()
