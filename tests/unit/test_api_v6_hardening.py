"""Unit tests for Slice A (v6 hardening):
- error_handlers: trace_id in dev, hidden in prod, X-Trace-Id header always set
- RequestContextMiddleware: X-Trace-Id header echoed, fresh uuid4 when absent
- pagination: page_size > MAX_PAGE_SIZE rejected, default OK
- get_service: factory returns a service instance with session wired
- check_router_auth: passes against current router.py
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.error_handlers import _trace_id, error_payload
from apps.api.middleware import RequestContextMiddleware
from apps.api.pagination import MAX_PAGE_SIZE, PaginatedResult, PaginationParams, paginate

# ── error_handlers ────────────────────────────────────────────────────────


def test_trace_id_uses_state_when_present():
    request = SimpleNamespace(state=SimpleNamespace(trace_id="abc123"))
    assert _trace_id(request) == "abc123"


def test_trace_id_mints_when_missing():
    request = SimpleNamespace(state=SimpleNamespace())
    tid = _trace_id(request)
    assert len(tid) == 32  # uuid4 hex


def test_error_payload_dev_includes_trace_id():
    request = SimpleNamespace(state=SimpleNamespace(trace_id="dev-trace"))
    with patch("apps.api.error_handlers._is_dev", return_value=True):
        body = error_payload(message="x", code="X", request=request)
    assert body["success"] is False
    assert body["error"] == "x"
    assert body["code"] == "X"
    assert body["trace_id"] == "dev-trace"


def test_error_payload_prod_omits_trace_id():
    request = SimpleNamespace(state=SimpleNamespace(trace_id="dev-trace"))
    with patch("apps.api.error_handlers._is_dev", return_value=False):
        body = error_payload(message="x", code="X", request=request)
    assert "trace_id" not in body
    assert body == {"success": False, "error": "x", "code": "X"}


# ── RequestContextMiddleware ──────────────────────────────────────────────


def _build_app_with_middleware() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/echo")
    async def echo(request: Request) -> dict:
        return {"trace_id": getattr(request.state, "trace_id", None)}

    return app


def test_request_context_middleware_mints_trace_id():
    client = TestClient(_build_app_with_middleware())
    r = client.get("/echo")
    assert r.status_code == 200
    body = r.json()
    assert uuid.UUID(body["trace_id"], version=4).hex == body["trace_id"]
    assert r.headers["X-Trace-Id"] == body["trace_id"]


def test_request_context_middleware_propagates_inbound_trace_id():
    client = TestClient(_build_app_with_middleware())
    inbound = "deadbeef" * 4
    r = client.get("/echo", headers={"X-Trace-Id": inbound})
    assert r.json()["trace_id"] == inbound
    assert r.headers["X-Trace-Id"] == inbound


# ── pagination ────────────────────────────────────────────────────────────


def test_pagination_defaults_ok():
    p = PaginationParams()
    assert p.page == 1
    assert p.page_size == 50
    assert p.skip == 0
    assert p.limit == 50


def test_pagination_rejects_zero_page():
    with pytest.raises(ValidationError):
        PaginationParams(page=0)


def test_pagination_rejects_over_limit():
    with pytest.raises(ValidationError):
        PaginationParams(page_size=MAX_PAGE_SIZE + 1)


def test_pagination_accepts_max_limit():
    p = PaginationParams(page_size=MAX_PAGE_SIZE)
    assert p.page_size == MAX_PAGE_SIZE


def test_paginated_result_total_pages():
    r = PaginatedResult(items=[], total=0, page=1, page_size=10)
    assert r.total_pages == 1
    assert r.has_next is False
    assert r.has_prev is False


def test_paginate_helper():
    p = PaginationParams(page=2, page_size=3)
    res = paginate([1, 2, 3], total=10, params=p)
    assert res.page == 2
    assert res.page_size == 3
    assert res.total_pages == 4
    assert res.has_next is True
    assert res.has_prev is True


# ── get_service factory (smoke) ──────────────────────────────────────────


def test_get_service_validates_format():
    from apps.api.dependencies import get_service

    with pytest.raises(ValueError):
        get_service("not_a_module_path")  # type: ignore[arg-type]


def test_get_service_resolves_class():
    """get_service returns a Depends-compatible callable; calling it with a
    fake session yields an instance of the requested class."""
    from apps.api.dependencies import get_service

    factory = get_service("apps.api.pagination:PaginationParams")
    # Inject a dummy session to satisfy the Depends signature; we only need to
    # confirm the import path resolves and the instance is constructed.
    instance = factory(session=object())  # type: ignore[arg-type]
    assert isinstance(instance, PaginationParams)
    # Defaults were applied since we passed no other args.
    assert instance.page == 1


# ── check_router_auth script (smoke) ─────────────────────────────────────


def test_router_audit_script_runs_clean():
    """If this fails, somebody added an include_router without dependencies=."""
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parent.parent.parent / "scripts" / "check_router_auth.py"
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert result.returncode == 0, f"audit failed:\n{result.stdout}\n{result.stderr}"
