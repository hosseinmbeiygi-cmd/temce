"""Tests for Decision Engine auto-seed logic (_auto_seed) with SQLite.

Verifies that:
  1. An empty DB gets seeded with architecture data
  2. Calling _auto_seed again is idempotent (no duplicate records)
  3. The seeded data is valid (version, layers, features, services)
  4. Graceful handling when JSON files are missing

Uses an in-memory SQLite database with JSONB→JSON compilation override,
so the tests run without any external PostgreSQL dependency.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import JSON, delete, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from models.decision_engine import DecisionArchitecture

# ── JSONB → SQLite compilation override ─────────────────────────
# DecisionArchitecture.model uses JSONB (postgres-specific).
# The @compiles decorator tells SQLAlchemy to emit "JSON" (SQLite-compatible)
# when it encounters a JSONB column on a SQLite backend.


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_: Any, compiler: Any, **kw: Any) -> str:
    """Override JSONB → JSON for SQLite so DecisionArchitecture model works."""
    return compiler.visit_JSON(JSON(), **kw)


# ── Sample architecture data (mocked replacement for JSON files) ─

SAMPLE_SYSTEM: dict[str, Any] = {
    "name": "سامانه تصمیم‌یار بورس تهران",
    "version": "Enterprise-Final-1.0",
    "type": "Multi-Layer Decision Support System",
    "principles": ["Scalability", "Explainability"],
    "objectives": ["غربالگری کل بازار", "تحلیل چندمرحله‌ای"],
}

SAMPLE_LAYERS: list[dict[str, Any]] = [
    {"order": i, "name": name, "title_fa": f"لایه {i}",
     "responsibilities": [f"مسئولیت {name}"]}
    for i, name in enumerate([
        "Ingestion", "StandardizationAndQuality", "Storage",
        "FeatureEngineering", "BaseScoring", "CandidateQueue",
        "MicrotradeAnalysis", "RiskEngine", "DecisionEngine",
        "ExplainabilityAndReporting", "AuditBacktestReplay",
        "OperationsGovernance",
    ], 1)
]

SAMPLE_FEATURES: dict[str, Any] = {
    "meta": {"total_features": 110, "blocks": 8, "version": "Enterprise-Final-1.0"},
    "blocks": [{"code": "A", "title": "کیفیت داده", "count": 10}],
    "features": [{
        "id": i, "code": f"feat_{i:03d}",
        "title": f"Feature {i}", "block": chr(64 + (i % 8 or 8)),
    } for i in range(1, 111)],
}

SAMPLE_SERVICES: dict[str, Any] = {
    "meta": {"total_services": 22, "version": "Enterprise-Final-1.0"},
    "services": [{"name": f"service-{i:02d}", "type": t}
                 for i, t in enumerate([
                     "collector", "collector", "collector", "collector", "collector",
                     "processor", "processor", "processor", "processor", "processor",
                     "processor", "processor", "processor", "processor", "processor",
                     "processor", "management", "management", "management",
                     "management", "management", "management",
                 ], 1)],
}

SAMPLE_DATABASE: dict[str, Any] = {
    "meta": {"table_groups": 5, "version": "Enterprise-Final-1.0"},
    "tables": [
        {"group": "reference", "tables": ["ref_symbols", "ref_industries"]},
        {"group": "raw", "tables": ["raw_quotes", "raw_candles"]},
        {"group": "quality", "tables": ["dq_validation_results"]},
        {"group": "feature", "tables": ["feat_symbol_snapshot"]},
        {"group": "score", "tables": ["score_base_results"]},
    ],
}

SAMPLE_API: dict[str, Any] = {
    "meta": {"internal": 16, "external": 16, "version": "Enterprise-Final-1.0"},
    "internal": ["POST /internal/ingestion/quotes/run", "POST /internal/scoring/base"],
    "external": ["GET /api/v1/symbols", "GET /api/v1/market/buy-candidates"],
}


# ── Mock helpers ─────────────────────────────────────────────────


def _bare_arch() -> dict[str, Any]:
    """Return a bare architecture dict (no features/services/database/api merged)."""
    return {
        "system": dict(SAMPLE_SYSTEM),
        "layers": [dict(layer) for layer in SAMPLE_LAYERS],
    }


def _make_side_effect(arch: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a side-effect dict mapping filename → mock data.

    Args:
        arch: The architecture dict to return for "architecture.json".
              Defaults to a bare architecture (no pre-merged sections).
    """
    if arch is None:
        arch = _bare_arch()
    return {
        "architecture.json": arch,
        "features.json": SAMPLE_FEATURES,
        "services.json": SAMPLE_SERVICES,
        "database.json": SAMPLE_DATABASE,
        "api.json": SAMPLE_API,
    }


# ── SQLite fixtures ──────────────────────────────────────────────


@pytest_asyncio.fixture(scope="module")
async def sqlite_engine():
    """Create an in-memory SQLite engine and all Decision Engine tables.

    The JSONB→JSON compilation override is active globally (module-level),
    so DecisionArchitecture's JSONB column works on SQLite.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
    )

    # Import models and create all tables
    import models.decision_engine  # noqa: F401 — register model
    from models.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def sqlite_session(sqlite_engine):
    """Provide a clean SQLite session for each test, rolled back after."""

    factory = async_sessionmaker(
        sqlite_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with factory() as session:
        yield session
        await session.rollback()
        await session.close()


# ── Test isolation ──────────────────────────────────────────────


@pytest_asyncio.fixture(autouse=True)
async def clean_arch_table(sqlite_session: AsyncSession) -> None:
    """Clean the decision_architectures table before each test.

    Required because _auto_seed commits its own transaction, so the
    sqlite_session fixture's rollback cannot undo seeded data.
    Without this, tests would have false positives due to stale data.
    """
    await sqlite_session.execute(delete(DecisionArchitecture))
    await sqlite_session.commit()


# ── Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_seeds_empty_db(sqlite_session: AsyncSession) -> None:
    """An empty database should be seeded with architecture data."""
    from apps.api.endpoints.decision_engine import _auto_seed

    side_effect_map = _make_side_effect()

    def _side_effect(fname: str) -> dict | None:
        return side_effect_map.get(fname)

    with patch("apps.api.endpoints.decision_engine._load_json") as mock_load:
        mock_load.side_effect = _side_effect
        await _auto_seed(sqlite_session)

    # Assert — a record was created
    result = await sqlite_session.execute(select(DecisionArchitecture).limit(1))
    row = result.scalar_one_or_none()
    assert row is not None, "Expected a seeded architecture record"

    # ── Metadata ──
    assert row.version == "Enterprise-Final-1.0"
    assert row.is_active is True, "Seeded record should be active"
    assert row.title == "سامانه تصمیم‌یار بورس تهران"

    # ── Top-level architecture keys ──
    data = row.data
    assert isinstance(data, dict)
    assert data["system"]["name"] == "سامانه تصمیم‌یار بورس تهران"
    assert data["system"]["version"] == "Enterprise-Final-1.0"

    # ── 12-layer architecture ──
    layers = data.get("layers", [])
    assert len(layers) == 12, f"Expected 12 layers, got {len(layers)}"
    layer_names = {layer.get("name") for layer in layers}
    for expected in [
        "Ingestion", "StandardizationAndQuality", "Storage",
        "FeatureEngineering", "BaseScoring", "CandidateQueue",
        "MicrotradeAnalysis", "RiskEngine", "DecisionEngine",
        "ExplainabilityAndReporting", "AuditBacktestReplay",
        "OperationsGovernance",
    ]:
        assert expected in layer_names, f"Missing layer: {expected}"

    # ── Features (merged from features.json) ──
    features = data.get("features", {})
    assert features["meta"]["total_features"] == 110
    assert len(features["features"]) == 110

    # ── Services (merged from services.json) ──
    services = data.get("services", {})
    assert services["meta"]["total_services"] == 22
    assert len(services["services"]) == 22

    # ── Database (merged from database.json) ──
    database = data.get("database", {})
    assert len(database["tables"]) == 5

    # ── API (merged from api.json) ──
    api_data = data.get("api", {})
    assert len(api_data["internal"]) == 2
    assert len(api_data["external"]) == 2


@pytest.mark.asyncio
async def test_is_idempotent(sqlite_session: AsyncSession) -> None:
    """Calling _auto_seed twice must not create duplicate records."""
    from apps.api.endpoints.decision_engine import _auto_seed

    side_effect_map = _make_side_effect()

    def _side_effect(fname: str) -> dict | None:
        return side_effect_map.get(fname)

    with patch("apps.api.endpoints.decision_engine._load_json") as mock_load:
        mock_load.side_effect = _side_effect
        await _auto_seed(sqlite_session)  # First call — seed
        await _auto_seed(sqlite_session)  # Second call — should be no-op

    result = await sqlite_session.execute(select(DecisionArchitecture))
    rows = result.scalars().all()
    assert len(rows) == 1, (
        f"Expected exactly 1 record after calling _auto_seed twice, got {len(rows)}"
    )


@pytest.mark.asyncio
async def test_skips_when_json_missing(sqlite_session: AsyncSession) -> None:
    """If architecture.json is missing, _auto_seed should silently skip."""
    from apps.api.endpoints.decision_engine import _auto_seed

    with patch("apps.api.endpoints.decision_engine._load_json") as mock_load:
        mock_load.return_value = None  # Simulate missing JSON file

        await _auto_seed(sqlite_session)

    # Verify nothing was written
    result = await sqlite_session.execute(select(DecisionArchitecture))
    rows = result.scalars().all()
    assert len(rows) == 0, "Should not seed when JSON is missing"


@pytest.mark.asyncio
async def test_merges_five_json_files(sqlite_session: AsyncSession) -> None:
    """Verify _auto_seed loads & merges all 5 JSON files into one record."""
    from apps.api.endpoints.decision_engine import _auto_seed

    side_effect_map = _make_side_effect()
    call_count: dict[str, int] = {}

    def _side_effect(fname: str) -> dict | None:
        call_count[fname] = call_count.get(fname, 0) + 1
        return side_effect_map.get(fname)

    with patch("apps.api.endpoints.decision_engine._load_json") as mock_load:
        mock_load.side_effect = _side_effect
        await _auto_seed(sqlite_session)

    # Verify all 5 files were loaded
    assert call_count.get("architecture.json") == 1
    assert call_count.get("features.json") == 1
    assert call_count.get("services.json") == 1
    assert call_count.get("database.json") == 1
    assert call_count.get("api.json") == 1

    # Verify the merged record has all sections
    result = await sqlite_session.execute(select(DecisionArchitecture).limit(1))
    row = result.scalar_one_or_none()
    assert row is not None
    data = row.data

    assert "features" in data
    assert "services" in data
    assert "database" in data
    assert "api" in data
    assert data["features"]["meta"]["total_features"] == 110
    assert data["services"]["meta"]["total_services"] == 22
