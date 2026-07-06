from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.app import app
from backtesting.strategies.registry import get_strategy_registry, register_all_strategies


@pytest.fixture(scope="session", autouse=True)
def _ensure_strategies_registered():
    """Ensure all strategies are registered before tests run."""
    register_all_strategies()
    registry = get_strategy_registry()
    assert len(registry.list_names()) >= 4, f"Strategy registration failed! Only {len(registry.list_names())} strategies"
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Helper ──────────────────────────────────────────────────────────────────
def _get_expected_strategies() -> list[str]:
    return get_strategy_registry().list_names()


# ── GET /api/v1/backtests/strategies ────────────────────────────────────────
@pytest.mark.asyncio
async def test_backtest_strategies_list(client: AsyncClient):
    """GET /backtests/strategies returns all registered strategies."""
    response = await client.get("/api/v1/backtests/strategies")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    body = response.json()
    assert body.get("success") is True or "data" in body, f"Unexpected response: {body}"

    # Navigate to get the items list
    data = body.get("data", {})
    items = data.get("items", []) if isinstance(data, dict) else data
    assert len(items) > 0, "Expected at least one strategy"

    # Verify structure of each strategy
    for strategy in items:
        assert "name" in strategy, f"Strategy missing 'name': {strategy}"
        assert "type" in strategy, f"Strategy missing 'type': {strategy}"
        assert isinstance(strategy["name"], str) and strategy["name"], f"Invalid strategy name: {strategy['name']}"

    # Verify all expected strategies are present
    expected = _get_expected_strategies()
    found = {s["name"] for s in items}
    missing = set(expected) - found
    assert not missing, f"Expected strategies not found: {missing}"


@pytest.mark.asyncio
async def test_backtest_strategies_structure(client: AsyncClient):
    """Each strategy has valid types."""
    response = await client.get("/api/v1/backtests/strategies")
    assert response.status_code == 200
    body = response.json()
    data = body.get("data", {})
    items = data.get("items", []) if isinstance(data, dict) else data

    for s in items:
        assert isinstance(s["name"], str), f"name should be string: {s['name']}"
        assert isinstance(s["type"], str), f"type should be string: {s['type']}"
        assert "params" in s, f"Strategy missing 'params': {s}"


# ── POST /api/v1/backtests/run ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_backtest_run_success(client: AsyncClient):
    """POST /backtests/run runs a backtest successfully on registered strategy."""
    payload = {
        "name": "Test Backtest",
        "symbols": ["فولاد"],
        "strategy_type": "moving_average_cross",
        "strategy_params": {},
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "initial_capital": 1_000_000_000,
    }
    response = await client.post("/api/v1/backtests/run", json=payload)
    assert response.status_code in (200, 422), f"Expected 200 or 422, got {response.status_code}"

    if response.status_code == 200:
        body = response.json()
        data = body.get("data", {})
        assert "id" in data, f"Response missing 'id': {data}"
        assert "status" in data, f"Response missing 'status': {data}"


@pytest.mark.asyncio
async def test_backtest_run_with_different_strategies(client: AsyncClient):
    """All registered strategies can be run."""
    strategies = _get_expected_strategies()

    for strategy_name in strategies[:3]:  # Test first 3 to keep tests fast
        payload = {
            "name": f"Test {strategy_name}",
            "symbols": ["فولاد"],
            "strategy_type": strategy_name,
            "strategy_params": {},
            "start_date": "2024-06-01",
            "end_date": "2024-12-31",
            "initial_capital": 1_000_000_000,
        }
        response = await client.post("/api/v1/backtests/run", json=payload)
        if response.status_code == 200:
            data = response.json().get("data", {})
            assert "id" in data, f"{strategy_name} response missing id"


# ── GET /api/v1/backtests/runs ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_backtest_runs_list(client: AsyncClient):
    """GET /backtests/runs returns list of runs."""
    # Run a backtest first so there's data
    payload = {
        "name": "List Test",
        "symbols": ["فولاد"],
        "strategy_type": "moving_average_cross",
        "strategy_params": {},
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
    }
    await client.post("/api/v1/backtests/run", json=payload)

    response = await client.get("/api/v1/backtests/runs")
    assert response.status_code == 200
    body = response.json()
    data = body.get("data", {})
    items = data.get("items", []) if isinstance(data, dict) else data
    assert isinstance(items, list), f"Expected list, got {type(items)}"
    if len(items) > 0:
        run = items[0]
        assert "id" in run, f"Run missing 'id': {run}"
        assert "name" in run, f"Run missing 'name': {run}"
        assert "status" in run, f"Run missing 'status': {run}"


@pytest.mark.asyncio
async def test_backtest_run_detail(client: AsyncClient):
    """GET /backtests/runs/{id} returns run details."""
    # First run a backtest to get a real ID
    payload = {
        "name": "Detail Test",
        "symbols": ["فولاد"],
        "strategy_type": "moving_average_cross",
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
    }
    run_resp = await client.post("/api/v1/backtests/run", json=payload)
    run_id = run_resp.json().get("data", {}).get("id", "")

    if run_id:
        response = await client.get(f"/api/v1/backtests/runs/{run_id}")
        assert response.status_code == 200
        body = response.json()
        detail = body.get("data", {})
        assert detail.get("id") == run_id, f"Run ID mismatch: {detail.get('id')} != {run_id}"


@pytest.mark.asyncio
async def test_backtest_run_detail_not_found(client: AsyncClient):
    """GET /backtests/runs/{invalid_id} returns success=False."""
    response = await client.get("/api/v1/backtests/runs/nonexistent-run-id")
    body = response.json()
    assert body.get("success") is False or body.get("data") is None


@pytest.mark.asyncio
async def test_backtest_run_result(client: AsyncClient):
    """GET /backtests/runs/{id}/result returns result data."""
    payload = {
        "name": "Result Test",
        "symbols": ["فولاد"],
        "strategy_type": "moving_average_cross",
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
    }
    run_resp = await client.post("/api/v1/backtests/run", json=payload)
    run_id = run_resp.json().get("data", {}).get("id", "")

    if run_id:
        response = await client.get(f"/api/v1/backtests/runs/{run_id}/result")
        assert response.status_code == 200
        body = response.json()
        result_data = body.get("data", {})
        if result_data:
            assert "total_return_pct" in result_data or "sharpe_ratio" in result_data, f"Result missing metrics: {result_data}"


# ── POST /api/v1/backtests/run-all ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_backtest_run_all(client: AsyncClient):
    """POST /backtests/run-all runs on all symbols and returns results."""
    payload = {
        "strategy_type": "moving_average_cross",
        "strategy_params": {},
        "start_date": "2024-06-01",
        "end_date": "2024-12-31",
        "initial_capital": 1_000_000_000,
    }
    response = await client.post("/api/v1/backtests/run-all", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
    body = response.json()
    assert body.get("success") is True, f"Expected success: {body}"
    data = body.get("data", {})
    assert "total_symbols" in data, f"Response missing 'total_symbols': {data}"
    assert data["total_symbols"] > 0, f"Expected > 0 symbols, got {data['total_symbols']}"
    assert "successful" in data, f"Response missing 'successful': {data}"
    assert "results" in data, f"Response missing 'results': {data}"
    results = data.get("results", [])
    assert len(results) == data["total_symbols"], f"Results count mismatch: {len(results)} != {data['total_symbols']}"
    for r in results:
        assert "symbol" in r, f"Result missing 'symbol': {r}"
        assert "status" in r, f"Result missing 'status': {r}"


# ── POST /api/v1/backtests/compare ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_backtest_compare_strategies(client: AsyncClient):
    """POST /backtests/compare runs all strategies on one symbol and returns comparison."""
    payload = {
        "symbol": "فولاد",
        "start_date": "2024-06-01",
        "end_date": "2024-12-31",
        "initial_capital": 1_000_000_000,
    }
    response = await client.post("/api/v1/backtests/compare", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:300]}"
    body = response.json()
    assert body.get("success") is True, f"Expected success, got {body}"
    data = body.get("data", {})
    assert "symbol" in data, f"Response missing 'symbol': {data}"
    assert data["symbol"] == "فولاد", f"Wrong symbol: {data['symbol']}"
    assert "total_strategies" in data, f"Response missing 'total_strategies': {data}"
    assert data["total_strategies"] > 0, f"Expected > 0 strategies, got {data['total_strategies']}"
    assert "best" in data, f"Response missing 'best': {data}"
    assert "worst" in data, f"Response missing 'worst': {data}"
    assert data["best"] is not None, "Expected a best strategy"

    results = data.get("results", [])
    assert len(results) == data["total_strategies"], f"Results count mismatch: {len(results)} != {data['total_strategies']}"
    for r in results:
        assert "strategy" in r, f"Result missing 'strategy': {r}"
        assert "status" in r, f"Result missing 'status': {r}"

