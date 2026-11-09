"""WS1: BrsApi resilience — circuit breaker, bounded backoff, formal pipeline.

RED (before fixes):
  1. sync_all() has no per-operation timeout → a hanging fetch blocks all ops forever
  2. circuit breaker recovery_timeout=30s hardcoded → too short for production
  3. retry delay has no jitter → concurrent retries stampede the provider together

GREEN (after fixes):
  1. sync_all() wraps each op with asyncio.wait_for(SYNC_OP_TIMEOUT_SECONDS)
  2. recovery_timeout comes from brsapi_settings.circuit_recovery_timeout (≥120s)
  3. retry delay includes ±jitter so successive calls don't pile up
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _mock_session():
    return AsyncMock()


async def _hang(*a, **kw):
    """An async function that hangs forever — simulates a stalled provider."""
    await asyncio.sleep(9999)


def _make_all_hanging_service() -> "BrsApiSyncService":
    """Return a BrsApiSyncService where every sync_xxx method hangs forever."""
    from brsapi.services.sync_service import BrsApiSyncService, SyncReport

    service = BrsApiSyncService()

    # Patch each individual method called by sync_all()
    for method_name in (
        "sync_all_symbols", "sync_index", "sync_options",
        "sync_ime_futures", "sync_ime_options", "sync_ime_certificates",
        "sync_ime_funds", "sync_commodities", "sync_crypto", "sync_gold_currency",
    ):
        setattr(service, method_name, _hang)

    return service


# ─── 1. Per-operation timeout in sync_all() ──────────────────────────────────

@pytest.mark.asyncio
async def test_sync_all_does_not_hang_when_provider_is_down():
    """sync_all() must complete within SYNC_OP_TIMEOUT_SECONDS even when
    every sync operation hangs.

    RED: sync_all() has no asyncio.wait_for() guard per operation — a single
         hanging sync stalls all subsequent ones indefinitely.
    GREEN: each op is wrapped in asyncio.wait_for(timeout=SYNC_OP_TIMEOUT_SECONDS)
           and a TimeoutError produces a SyncReport(outcome='timeout').
    """
    service = _make_all_hanging_service()

    # Patch both timeouts and the post-sync Redis call so the test finishes quickly.
    with patch("brsapi.services.sync_service.SYNC_OP_TIMEOUT_SECONDS", 0.05), \
         patch("brsapi.services.sync_service.SYNC_ALL_INTER_OP_DELAY_SECONDS", 0.0), \
         patch("core.agg_invalidation.publish_agg_token", AsyncMock()):
        reports = await asyncio.wait_for(
            service.sync_all(_mock_session()),
            timeout=5.0,  # 11 ops × 0.05s = 0.55s max; well within 5s
        )

    assert reports, "sync_all() must return a non-empty report list even when all ops time out"

    timeout_reports = [r for r in reports if r.outcome == "timeout"]
    assert timeout_reports, (
        "Expected at least one SyncReport with outcome='timeout' when provider hangs, "
        f"but got outcomes: {[r.outcome for r in reports]}. "
        "sync_all() must wrap each op with asyncio.wait_for(SYNC_OP_TIMEOUT_SECONDS)."
    )


@pytest.mark.asyncio
async def test_sync_all_continues_after_timeout():
    """When the first op times out, sync_all() must continue with remaining ops.

    Confirms the timeout is per-operation, not a global abort of sync_all().
    """
    from brsapi.services.sync_service import BrsApiSyncService, SyncReport

    service = BrsApiSyncService()
    call_count = {"n": 0}

    async def _first_hangs_rest_fast(*a, **kw):
        call_count["n"] += 1
        if call_count["n"] == 1:
            await asyncio.sleep(9999)  # only the first op hangs
        return SyncReport(endpoint="mock", success=True, outcome="ok")

    service.sync_all_symbols = _first_hangs_rest_fast
    service.sync_index = _first_hangs_rest_fast
    service.sync_options = _first_hangs_rest_fast
    service.sync_ime_futures = _first_hangs_rest_fast
    service.sync_ime_options = _first_hangs_rest_fast
    service.sync_ime_certificates = _first_hangs_rest_fast
    service.sync_ime_funds = _first_hangs_rest_fast
    service.sync_commodities = _first_hangs_rest_fast
    service.sync_crypto = _first_hangs_rest_fast
    service.sync_gold_currency = _first_hangs_rest_fast

    with patch("brsapi.services.sync_service.SYNC_OP_TIMEOUT_SECONDS", 0.05), \
         patch("brsapi.services.sync_service.SYNC_ALL_INTER_OP_DELAY_SECONDS", 0.0), \
         patch("core.agg_invalidation.publish_agg_token", AsyncMock()):
        reports = await asyncio.wait_for(
            service.sync_all(_mock_session()),
            timeout=5.0,
        )

    assert len(reports) > 1, (
        f"Expected multiple reports (first timeout + remaining successes), got {len(reports)}. "
        "A per-operation timeout must NOT abort the whole sync_all() run."
    )
    # First op times out
    assert reports[0].outcome == "timeout", (
        f"Expected first report outcome='timeout' but got {reports[0].outcome!r}."
    )


# ─── 2. Circuit breaker recovery timeout ─────────────────────────────────────

def test_circuit_breaker_recovery_timeout_comes_from_config():
    """_circuit_breaker() must use brsapi_settings.circuit_recovery_timeout.

    RED: recovery_timeout=30.0 is hardcoded.
    GREEN: it reads brsapi_settings.circuit_recovery_timeout (default ≥120s).
    """
    import brsapi.client as client_mod

    # Patch settings to use a custom recovery timeout
    with patch.object(client_mod.brsapi_settings, "circuit_recovery_timeout", 150.0):
        client = client_mod.BrsApiClient()
        cb = client._circuit_breaker("/Tsetmc/AllSymbols.php")

    assert cb.recovery_timeout == 150.0, (
        f"Expected circuit breaker recovery_timeout=150.0 from config, "
        f"got {cb.recovery_timeout}. "
        "_circuit_breaker() must use brsapi_settings.circuit_recovery_timeout, "
        "not the hardcoded 30.0."
    )


def test_circuit_breaker_default_recovery_timeout_is_at_least_120s():
    """The DEFAULT circuit_recovery_timeout must be ≥120s for production safety.

    RED: default is 30s.
    GREEN: default is ≥120s (we set it to 120.0).
    """
    from brsapi.config import BrsApiSettings

    # Create a default settings instance (no env overrides)
    settings = BrsApiSettings(
        api_key="test-key",
        base_url="http://localhost",
    )

    assert hasattr(settings, "circuit_recovery_timeout"), (
        "BrsApiSettings must have a circuit_recovery_timeout field. "
        "Add: circuit_recovery_timeout: float = Field(default=120.0, ge=10.0)"
    )
    assert settings.circuit_recovery_timeout >= 120.0, (
        f"Default circuit_recovery_timeout={settings.circuit_recovery_timeout} "
        "is too short for a production API. Must be ≥120s so a flapping provider "
        "does not get hammered every 30s."
    )


# ─── 3. Retry backoff jitter ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retry_delays_have_jitter():
    """The retry backoff delay must include jitter so concurrent retries spread out.

    RED: delay = min(base^n, max) with no jitter — all retries fire at the same
         instant when multiple requests are in-flight.
    GREEN: delay includes a random factor (±jitter) so successive attempts vary.
    """
    import httpx
    import brsapi.client as client_mod

    recorded_sleeps: list[float] = []

    async def _capture_sleep(secs: float) -> None:
        recorded_sleeps.append(secs)

    # Mock a 502 response so the retry path triggers.
    # Empty headers → _parse_retry_after() falls back to its default of "5"
    # (a 5s base delay), so jitter has a non-zero value to vary.
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 502
    mock_resp.headers = {}  # no Retry-After → default 5s used in _parse_retry_after
    mock_resp.content = b'{"error": "bad gateway"}'
    mock_resp.text = "bad gateway"

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=mock_resp)

    # Build two clients with the SAME backoff params
    max_retries = 3
    client_a = client_mod.BrsApiClient()
    client_a._client = mock_http
    client_a._max_retries = max_retries
    client_a._backoff_base = 2.0
    client_a._backoff_max = 60.0

    client_b = client_mod.BrsApiClient()
    client_b._client = mock_http
    client_b._max_retries = max_retries
    client_b._backoff_base = 2.0
    client_b._backoff_max = 60.0

    with patch.object(client_mod.brsapi_settings, "enabled", True):
        with patch.object(client_mod.brsapi_settings, "fail_fast_on_daily_exhausted", False):
            with patch("brsapi.client.asyncio.sleep", side_effect=_capture_sleep):
                from brsapi.config import BrsApiEndpoints

                ep = BrsApiEndpoints.ALL_SYMBOLS
                await client_a._do_fetch(
                    f"http://localhost{ep.path}", {"key": "k"}, "tsetmc", ep
                )
                run_a_sleeps = list(recorded_sleeps)
                recorded_sleeps.clear()

                await client_b._do_fetch(
                    f"http://localhost{ep.path}", {"key": "k"}, "tsetmc", ep
                )
                run_b_sleeps = list(recorded_sleeps)

    if not run_a_sleeps or not run_b_sleeps:
        pytest.skip("No retries triggered — cannot verify jitter")

    # Jitter means the same backoff formula produces different delays on each call.
    # Without jitter they are always EXACTLY equal (deterministic formula).
    all_equal = all(
        abs(a - b) < 1e-9
        for a, b in zip(run_a_sleeps, run_b_sleeps)
    )
    assert not all_equal, (
        f"Retry delays are identical between two calls (run_a={run_a_sleeps}, "
        f"run_b={run_b_sleeps}). Without jitter, concurrent retries all fire at "
        "the same instant (thundering herd). "
        "Add random.uniform() jitter to the backoff delay in _do_fetch()."
    )
