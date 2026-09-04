"""Fixture-backed collector. Replace with httpx-based Tgju/Nobitex later."""

from __future__ import annotations

from apps.currency_service.domain.entities import RateSnapshot
from apps.currency_service.infra.fixtures import load_fixture_snapshot


class FixtureCollector:
    """Returns a fresh ``RateSnapshot`` per call.

    No network. No DB. Stateless — pure in-memory mock today.
    """

    async def fetch(self) -> RateSnapshot:
        return load_fixture_snapshot()
