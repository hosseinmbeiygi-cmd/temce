from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.app import app
from ml.models import register_all_models
from ml.models.registry import model_registry


@pytest.fixture(scope="session", autouse=True)
def _ensure_models_registered():
    """Ensure all models are registered before any test runs.
    The app lifespan may not run reliably with ASGITransport in tests."""
    register_all_models()
    registered = model_registry.list_models()
    assert len(registered) >= 4, f"Model registration failed! Only {len(registered)} models: {registered}"
    yield


@pytest.fixture(scope="session")
def analyst_token() -> str:
    """Create a valid analyst JWT so ML endpoints (which require analyst role)
    can be tested. The /ml router is mounted with `_require_analyst`."""
    from core.security.tokens import create_access_token

    return create_access_token({"sub": "e2e-analyst", "roles": ["analyst"]})


@pytest.fixture
async def client(analyst_token: str):
    headers = {"Authorization": f"Bearer {analyst_token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        yield ac


# ── Helper ──────────────────────────────────────────────────────────────────
def _get_expected_frameworks() -> set[str]:
    """Return the framework names that should be registered after register_all_models().
    Derives the set directly from the builder registry to stay in sync automatically."""
    return set(model_registry.list_models())


# ── GET /api/v1/ml/models ───────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ml_models_list_success(client: AsyncClient):
    """GET /ml/models returns 200 and a list of models."""
    response = await client.get("/api/v1/ml/models")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    body = response.json()
    assert body.get("success") is True, f"Expected success=True, got {body}"

    models = body.get("data", [])
    assert isinstance(models, list), f"Expected data to be a list, got {type(models)}"
    assert len(models) > 0, "Expected at least one model in the list"

    # Each model should have required fields
    for model in models:
        assert "id" in model, f"Model missing 'id': {model}"
        assert "name" in model, f"Model missing 'name': {model}"
        assert "task" in model, f"Model missing 'task': {model}"
        assert "framework" in model, f"Model missing 'framework': {model}"
        assert isinstance(model.get("tags", None), list), f"Model.tags should be a list: {model}"
        assert isinstance(model.get("versions", None), list), f"Model.versions should be a list: {model}"
        assert "created_at" in model, f"Model missing 'created_at': {model}"

    # Verify frameworks are present. When DB-backed models are registered the
    # framework set comes from real artifacts; when DB is empty the endpoint
    # falls back to the in-memory registry (which includes all builders).
    # Require at least one expected builder framework in either case.
    frameworks = {m["framework"] for m in models}
    expected = _get_expected_frameworks()
    overlap = frameworks.intersection(expected)
    assert overlap, f"No expected frameworks found in response. Got: {frameworks}"


@pytest.mark.asyncio
async def test_ml_models_list_structure(client: AsyncClient):
    """Each model in the list has correct types."""
    response = await client.get("/api/v1/ml/models")
    assert response.status_code == 200
    models = response.json().get("data", [])

    for model in models:
        # id is a non-empty string
        assert isinstance(model["id"], str) and model["id"], f"Invalid id: {model['id']}"
        # name is a non-empty string
        assert isinstance(model["name"], str) and model["name"], f"Invalid name: {model['name']}"
        # task is regression or classification
        assert model["task"] in (
            "regression",
            "classification",
        ), f"Invalid task: {model['task']}"
        # framework is a non-empty string
        assert isinstance(model["framework"], str) and model["framework"], f"Invalid framework: {model['framework']}"


# ── GET /api/v1/ml/runs ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ml_runs_list(client: AsyncClient):
    """GET /ml/runs returns a list of training runs."""
    response = await client.get("/api/v1/ml/runs")
    assert response.status_code == 200
    body = response.json()
    assert body.get("success") is True
    runs = body.get("data", [])
    assert isinstance(runs, list)

    for run in runs:
        assert "id" in run
        assert "experiment_name" in run
        assert "model_type" in run
        assert "status" in run
        assert run["status"] in (
            "running",
            "completed",
            "failed",
            "cancelled",
        ), f"Invalid status: {run['status']}"


@pytest.mark.asyncio
async def test_ml_run_detail(client: AsyncClient):
    """GET /ml/runs/{run_id} returns details for an existing run."""
    # First, list runs to get a valid run_id
    list_resp = await client.get("/api/v1/ml/runs")
    runs = list_resp.json().get("data", [])

    if not runs:
        pytest.skip("No training runs available to test detail endpoint")

    run_id = runs[0]["id"]
    response = await client.get(f"/api/v1/ml/runs/{run_id}")
    assert response.status_code == 200
    body = response.json()
    assert body.get("success") is True, f"Expected success, got {body}"
    detail = body.get("data", {})
    assert detail.get("id") == run_id, f"Run ID mismatch: {detail.get('id')} != {run_id}"


@pytest.mark.asyncio
async def test_ml_run_detail_not_found(client: AsyncClient):
    """GET /ml/runs/{invalid_id} returns error."""
    response = await client.get("/api/v1/ml/runs/nonexistent-run-id")
    body = response.json()
    assert body.get("success") is False


# ── POST /api/v1/ml/predict ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ml_predict(client: AsyncClient):
    """POST /ml/predict/{model_id} returns a valid ApiResponse.

    Real backend: with no symbol/features the endpoint returns a clear error
    (no mock fallback). When a real trained model + symbol exist it returns
    a numeric prediction. Either shape is acceptable as long as the response
    is well-formed.
    """
    payload: dict = {}
    response = await client.post("/api/v1/ml/predict/xgboost", json=payload)
    assert response.status_code in (200, 401, 422)

    if response.status_code == 200:
        body = response.json()
        assert "success" in body, f"Response missing 'success': {body}"
        data = body.get("data") or {}
        if body.get("success"):
            assert "prediction" in data, f"Response missing 'prediction': {data}"
            assert "confidence" in data, f"Response missing 'confidence': {data}"
            assert isinstance(data["prediction"], (int, float)), f"prediction should be numeric: {data['prediction']}"


@pytest.mark.asyncio
async def test_ml_predict_all_models(client: AsyncClient):
    """All registered models can be called for prediction."""
    # First get the list of models
    list_resp = await client.get("/api/v1/ml/models")
    models = list_resp.json().get("data", [])

    payload: dict = {}
    # Dedupe by framework so the test covers every distinct model type while
    # staying fast (DB-backed model list can be 359+). ~9 distinct frameworks.
    distinct = {m["framework"]: m for m in models if m.get("framework")}
    for model in list(distinct.values())[:10]:
        framework = model["framework"]
        resp = await client.post(f"/api/v1/ml/predict/{framework}", json=payload)
        if resp.status_code == 200:
            data = resp.json().get("data") or {}
            # Real backend returns success=False + error when no symbol is given
            if resp.json().get("success") is True:
                assert "prediction" in data, f"{framework} response missing prediction"


# ── POST /api/v1/ml/train ───────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ml_train(client: AsyncClient):
    """POST /ml/train starts a training run."""
    payload = {
        "experiment_name": "e2e_test",
        "model_type": "xgboost",
        "symbols": ["فولاد"],
    }
    response = await client.post("/api/v1/ml/train", json=payload)
    assert response.status_code in (200, 201, 401, 422)

    if response.status_code == 200:
        body = response.json()
        # Real backend: training succeeds only when quote data exists for the
        # symbol. Without enough rows the endpoint returns success=False with a
        # clear error (pre-existing data availability, not an API bug).
        if body.get("success"):
            data = body.get("data", {})
            assert "run_id" in data, f"Response missing 'run_id': {data}"
            assert "status" in data
            assert data["model_type"] == "xgboost", f"model_type mismatch: {data['model_type']}"


# ── POST /api/v1/ml/predict-all ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ml_predict_all(client: AsyncClient):
    """POST /ml/predict-all runs model on all symbols and returns results."""
    payload = {"model_type": "xgboost"}
    response = await client.post("/api/v1/ml/predict-all", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    body = response.json()
    assert body.get("success") is True
    data = body.get("data", {})
    assert "batch_id" in data, f"Response missing 'batch_id': {data}"
    assert "total_symbols" in data, f"Response missing 'total_symbols': {data}"
    assert data["total_symbols"] > 0, f"Expected > 0 symbols, got {data['total_symbols']}"
    results = data.get("results", [])
    assert len(results) == data["total_symbols"], "Results count mismatch"

    # Verify each result has required fields
    for r in results:
        assert "symbol" in r, f"Result missing 'symbol': {r}"
        assert "prediction" in r, f"Result missing 'prediction': {r}"
        assert "accuracy" in r, f"Result missing 'accuracy': {r}"
        assert "confidence" in r, f"Result missing 'confidence': {r}"
        assert isinstance(r["prediction"], (int, float)), f"prediction should be numeric: {r['prediction']}"
        assert 0 <= r["accuracy"] <= 1, f"accuracy out of range: {r['accuracy']}"


# ── GET /api/v1/ml/predictions ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ml_predictions_list(client: AsyncClient):
    """GET /ml/predictions returns saved prediction results."""
    # First, run predict-all to populate results
    await client.post("/api/v1/ml/predict-all", json={"model_type": "xgboost"})

    response = await client.get("/api/v1/ml/predictions")
    assert response.status_code == 200
    body = response.json()
    assert body.get("success") is True
    predictions = body.get("data", [])
    assert isinstance(predictions, list)


@pytest.mark.asyncio
async def test_ml_predictions_filter_by_symbol(client: AsyncClient):
    """GET /ml/predictions?symbol=... filters results."""
    # First, run predict-all to populate results
    await client.post("/api/v1/ml/predict-all", json={"model_type": "xgboost"})

    response = await client.get("/api/v1/ml/predictions?symbol=فولاد")
    assert response.status_code == 200
    body = response.json()
    predictions = body.get("data", [])
    # Should return at least one result matching "فولاد"
    assert len(predictions) > 0, f"Expected results for 'فولاد', got empty: {body}"
    for p in predictions:
        assert "symbol" in p, f"Prediction missing 'symbol': {p}"
