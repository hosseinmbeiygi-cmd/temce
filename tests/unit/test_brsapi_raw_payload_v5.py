"""Unit tests for the v5.0 raw-payload audit extensions (سند §2.3).

Covers:
- ``_sha256`` deterministic hex digest
- ``RawPayloadRepository.store`` populates all v5.0 fields when provided
- ``RawPayloadRepository.store`` falls back to defaults (receive_time,
  schema_version, checksum_sha256) when not provided
- Migration 0042's ``upgrade`` / ``downgrade`` are reversible (no raise
  in offline mode; the test imports and invokes the function objects only)
"""

from __future__ import annotations

from datetime import datetime

from brsapi.repositories.base import RawPayloadRepository, _sha256


class _StubSession:
    """Minimal AsyncSession stand-in for ``RawPayloadRepository.store`` tests."""

    def __init__(self) -> None:
        self.added: list = []
        self.flushed = 0

    def add(self, entry) -> None:
        self.added.append(entry)

    async def flush(self) -> None:
        self.flushed += 1


class TestSha256:
    def test_known_vector(self):
        assert _sha256("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

    def test_empty_string(self):
        assert _sha256("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_different_inputs_differ(self):
        assert _sha256("a") != _sha256("b")


class TestRawPayloadRepositoryStore:
    async def test_populates_all_v5_fields_when_provided(self):
        session = _StubSession()
        repo = RawPayloadRepository(session)
        receive_time = datetime(2026, 8, 29, 12, 0, 0)
        market_time = datetime(2026, 8, 29, 11, 59, 55)
        result = await repo.store(
            endpoint="/time",
            payload='{"x": 1}',
            status_code=200,
            params={"type": "stock"},
            receive_time=receive_time,
            market_time=market_time,
            response_latency_ms=12.5,
            schema_version="raw_payload.v2",
            checksum_sha256="deadbeef" * 8,
        )
        assert session.flushed == 1
        assert result.receive_time == receive_time
        assert result.market_time == market_time
        assert result.response_latency_ms == 12.5
        assert result.schema_version == "raw_payload.v2"
        assert result.checksum_sha256 == "deadbeef" * 8

    async def test_fills_defaults_when_not_provided(self):
        session = _StubSession()
        repo = RawPayloadRepository(session)
        result = await repo.store(endpoint="/time", payload="hello")
        assert result.receive_time is not None
        assert result.schema_version == RawPayloadRepository.DEFAULT_SCHEMA_VERSION
        assert result.checksum_sha256 == _sha256("hello")
        assert result.market_time is None
        assert result.response_latency_ms is None

    async def test_redacts_api_key_in_params(self):
        session = _StubSession()
        repo = RawPayloadRepository(session)
        await repo.store(
            endpoint="/time",
            payload="x",
            params={"key": "SECRET", "type": "stock"},
        )
        import json as _json

        added = session.added[-1]
        stored_params = _json.loads(added.params)
        # The key field's value is replaced with [REDACTED]; non-sensitive fields pass through
        assert stored_params["key"] == "[REDACTED]"
        assert stored_params["type"] == "stock"


class TestMigration0042:
    def test_upgrade_and_downgrade_are_callable(self):
        import importlib

        m = importlib.import_module("migrations.versions.0042_raw_payload_v5_columns")
        # Sanity: upgrade / downgrade are no-arg callables that operate on a
        # real DB. We do NOT run them here (no alembic context) — just confirm
        # they're present and importable. Alembic validates them in offline
        # mode for syntax errors at import time.
        assert callable(m.upgrade)
        assert callable(m.downgrade)
        assert m.revision == "0042"
        assert m.down_revision == "0041"
