"""Unit tests for the BrsApi key-readiness probe.

Covers:
- ``BrsApiClient.probe_ready()`` — HTTP 200 => ready, HTTP 302 => not ready,
  and that it works even while ``BRSAPI_ENABLED=false`` (the whole point of
  the probe is to run in DB-only mode).
- ``brsapi.readiness.check_and_notify()`` — state persistence and the
  not-ready -> ready transition firing the notification exactly once.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import brsapi.client as client_mod
from brsapi.client import BrsApiClient
from brsapi.rate_limiter import RateLimiter

# ── Helpers ───────────────────────────────────────────────────────────


class _FakeResp:
    def __init__(self, status_code: int, content: bytes = b"{}"):
        self.status_code = status_code
        self.content = content
        self.text = "fake"
        self.headers = {}


def _make_client(rate_limiter: RateLimiter | None = None) -> BrsApiClient:
    # Always pass an explicit limiter: a client built without one would use the
    # production persistent budget-governor singleton and could read/write a
    # real 302 block/state file during tests.
    limiter = rate_limiter or RateLimiter()
    client = BrsApiClient(api_key="test", base_url="http://test.local",
                          rate_limiter=limiter)
    client._client = AsyncMock()
    return client


# ── probe_ready() ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_probe_ready_200_means_ready() -> None:
    client = _make_client()
    client._client.get = AsyncMock(return_value=_FakeResp(200, b'{"ok": true}'))
    probe = await client.probe_ready()
    assert probe["ready"] is True
    assert probe["status_code"] == 200
    assert client._client.get.await_count == 1


@pytest.mark.asyncio
async def test_probe_ready_302_means_not_ready() -> None:
    """The anti-abuse 302 (heavy-file redirect) must map to ready=False."""
    client = _make_client()
    resp = _FakeResp(302)
    resp.headers = {"Location": "https://cdn.example/Windows.part1.rar"}
    client._client.get = AsyncMock(return_value=resp)
    probe = await client.probe_ready()
    assert probe["ready"] is False
    assert probe["status_code"] == 302
    assert "302" in probe["detail"]
    assert client._client.get.await_count == 1  # never follows the redirect


@pytest.mark.asyncio
async def test_probe_ready_unexpected_status_is_not_ready() -> None:
    client = _make_client()
    client._client.get = AsyncMock(return_value=_FakeResp(500))
    probe = await client.probe_ready()
    assert probe["ready"] is False
    assert probe["status_code"] == 500


@pytest.mark.asyncio
async def test_probe_ready_request_error_is_not_ready() -> None:
    import httpx

    client = _make_client()
    client._client.get = AsyncMock(side_effect=httpx.ConnectError("boom"))
    probe = await client.probe_ready()
    assert probe["ready"] is False
    assert probe["status_code"] == 0


@pytest.mark.asyncio
async def test_probe_ready_bypasses_kill_switch() -> None:
    """The probe must still make its request while BRSAPI_ENABLED=false —
    that is exactly when it is needed most."""
    client = _make_client()
    client._client.get = AsyncMock(return_value=_FakeResp(200, b"{}"))
    with patch.object(client_mod.brsapi_settings, "enabled", False):
        probe = await client.probe_ready()
    assert probe["ready"] is True
    assert client._client.get.await_count == 1


@pytest.mark.asyncio
async def test_probe_ready_fail_fast_on_exhausted_budget() -> None:
    """Even the probe must not sleep when the daily budget is exhausted."""
    limiter = RateLimiter(daily_limit=1, five_min_limit=500)
    await limiter.acquire("tsetmc")
    client = _make_client(rate_limiter=limiter)
    probe = await client.probe_ready()
    assert probe["ready"] is False
    assert "rate-limited" in probe["detail"]
    client._client.get.assert_not_awaited()


# ── check_and_notify() ────────────────────────────────────────────────


async def _run_check(state_file: Path, probe_result: dict) -> dict:
    with patch("brsapi.readiness.probe_key", new=AsyncMock(return_value=probe_result)):
        from brsapi.readiness import check_and_notify

        return await check_and_notify(state_file=state_file)


@pytest.mark.asyncio
async def test_transition_not_ready_to_ready_fires_notification(tmp_path: Path) -> None:
    state_file = tmp_path / "readiness_state.json"
    state_file.write_text('{"ready": false}', encoding="utf-8")

    with patch("brsapi.readiness._notify_ready", new=AsyncMock()) as mock_notify:
        summary = await _run_check(state_file, {"ready": True, "status_code": 200, "detail": "OK"})

    assert summary["ready"] is True
    assert summary["transitioned"] is True
    assert summary["notified"] is True
    mock_notify.assert_awaited_once()

    # State persisted as ready
    saved = state_file.read_text(encoding="utf-8")
    assert '"ready": true' in saved


@pytest.mark.asyncio
async def test_no_notification_when_still_not_ready(tmp_path: Path) -> None:
    state_file = tmp_path / "readiness_state.json"
    state_file.write_text('{"ready": false}', encoding="utf-8")

    with patch("brsapi.readiness._notify_ready", new=AsyncMock()) as mock_notify:
        summary = await _run_check(
            state_file, {"ready": False, "status_code": 302, "detail": "still redirecting"}
        )

    assert summary["ready"] is False
    assert summary["transitioned"] is False
    assert summary["notified"] is False
    mock_notify.assert_not_awaited()
    assert '"ready": false' in state_file.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_no_notification_when_already_ready(tmp_path: Path) -> None:
    """No spam: if the last probe already saw ready, a new ready probe must
    not notify again."""
    state_file = tmp_path / "readiness_state.json"
    state_file.write_text('{"ready": true}', encoding="utf-8")

    with patch("brsapi.readiness._notify_ready", new=AsyncMock()) as mock_notify:
        summary = await _run_check(state_file, {"ready": True, "status_code": 200, "detail": "OK"})

    assert summary["ready"] is True
    assert summary["transitioned"] is False
    assert summary["notified"] is False
    mock_notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_ready_to_not_ready_regression(tmp_path: Path) -> None:
    """If the key goes back to blocked, the next reset must notify again."""
    state_file = tmp_path / "readiness_state.json"
    state_file.write_text('{"ready": true}', encoding="utf-8")

    with patch("brsapi.readiness._notify_ready", new=AsyncMock()):
        await _run_check(state_file, {"ready": False, "status_code": 302, "detail": "blocked again"})

    assert '"ready": false' in state_file.read_text(encoding="utf-8")

    with patch("brsapi.readiness._notify_ready", new=AsyncMock()) as mock_notify:
        summary = await _run_check(state_file, {"ready": True, "status_code": 200, "detail": "OK"})

    assert summary["transitioned"] is True
    assert summary["notified"] is True
    mock_notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_first_run_bootstraps_silently(tmp_path: Path) -> None:
    """First ever run (no state file): the probe must record state but NOT
    notify — an already-healthy key must not fire a spurious 'key is READY
    again' message on a fresh deploy."""
    state_file = tmp_path / "does_not_exist.json"

    with patch("brsapi.readiness._notify_ready", new=AsyncMock()) as mock_notify:
        summary = await _run_check(state_file, {"ready": True, "status_code": 200, "detail": "OK"})

    assert summary["transitioned"] is False
    assert summary["notified"] is False
    mock_notify.assert_not_awaited()
    assert state_file.exists()
    assert '"ready": true' in state_file.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_second_run_after_silent_bootstrap_is_quiet(tmp_path: Path) -> None:
    """After a silent bootstrap with ready=True, a subsequent ready probe must
    stay quiet (no spam)."""
    state_file = tmp_path / "does_not_exist.json"

    with patch("brsapi.readiness._notify_ready", new=AsyncMock()):
        await _run_check(state_file, {"ready": True, "status_code": 200, "detail": "OK"})

    with patch("brsapi.readiness._notify_ready", new=AsyncMock()) as mock_notify:
        summary = await _run_check(state_file, {"ready": True, "status_code": 200, "detail": "OK"})

    assert summary["transitioned"] is False
    assert summary["notified"] is False
    mock_notify.assert_not_awaited()
