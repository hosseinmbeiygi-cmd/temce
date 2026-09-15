"""Regression tests for the screener audit fixes (2026-09).

Covers:
  1. ``get_session()`` is an async generator — FastAPI endpoint session
     management must go through the ``get_db_session`` dependency, and the
     screener110 job must fully consume the generator so its commit runs
     (early ``return`` inside ``async for`` silently rolls back the cycle).
  2. ``apps/api/endpoints/screener_v2.py`` must import ``safe_error_message``
     (it used to be trapped inside the module docstring → NameError in every
     error path).
  3. Production error responses must not leak ``str(exc)`` internals.
  4. ``sort_order`` is whitelisted at the API edge.
  5. Screener ``reason`` strings are valid Persian (no cp1252 mojibake).
  6. ``page`` without ``page_size`` still paginates (limit honored).
"""

from __future__ import annotations

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.endpoints import screener as screener_ep
from apps.api.endpoints import screener_v2 as screener_v2_ep
from services.screener_service import ScreenedSymbol, ScreenerPipeline, ScreenerService


# ── 1. Job commit regression ─────────────────────────────────────────────
class TestScreenerJobsCommitRegression:
    """``Screener110RunCycleJob`` must not return inside ``async for``."""

    def test_job_consumes_get_session_to_commit(self, tmp_path) -> None:
        from jobs.definitions.screener_jobs import Screener110RunCycleJob
        from jobs.job_context import JobContext

        commit_log: list[str] = []

        async def fake_get_session():
            session = AsyncMock(name="db-session")
            try:
                yield session
                commit_log.append("commit")  # ← skipped if caller returns early
            except Exception:
                commit_log.append("rollback")
                raise
            finally:
                commit_log.append("close")

        svc = MagicMock()
        svc.run_full_cycle = AsyncMock(return_value=[{"symbol": "TEST", "decision": "خرید", "final_score": 85.0, "current_price": 100}])
        svc_cls = MagicMock(return_value=svc)

        context = JobContext(job_id="test-1", job_name="screener110_run_cycle", params={})
        job = Screener110RunCycleJob(name="screener110_run_cycle")

        with (
            patch("core.database.get_session", fake_get_session),
            patch("services.screener110_service.Screener110Service", svc_cls),
        ):
            result = asyncio.run(job.execute(context))

        assert result.success is True
        assert commit_log == ["commit", "close"], (
            f"job abandoned the session generator before commit: {commit_log}"
        )

    def test_ml_signal_connector_session_pattern(self) -> None:
        """``get_accuracy_by_market`` must consume ``get_session()`` with async for."""
        import services.ml_signal_connector as msc

        src = inspect.getsource(msc)
        assert "async with get_session() as" not in src, (
            "async with on an async generator raises TypeError; use async for / aclosing"
        )


# ── 2. screener_v2 safe_error_message ───────────────────────────────────
class TestScreenerV2ErrorHelper:
    def test_helper_defined(self) -> None:
        assert callable(getattr(screener_v2_ep, "safe_error_message", None)), (
            "screener_v2 used safe_error_message without importing it (NameError in error paths)"
        )

    def test_helper_returns_default_in_production(self) -> None:
        with patch("core.config.settings.environment", "production"):
            msg = screener_v2_ep.safe_error_message(ValueError("select * from secret_table"), default_message="fallback")
        assert msg == "fallback"

    def test_helper_detail_in_development(self) -> None:
        with patch("core.config.settings.environment", "development"):
            msg = screener_v2_ep.safe_error_message(ValueError("boom"), default_message="fallback")
        assert msg == "boom"

    def test_endpoint_error_path_no_nameerror(self) -> None:
        """A failing V2 request must return ApiResponse, not NameError."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        app = FastAPI()
        app.include_router(screener_v2_ep.router, prefix="/screener-v2")

        async def _run() -> dict:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                with (
                    patch("core.config.settings.environment", "production"),
                    patch.object(screener_v2_ep, "_check_rate_limit", return_value=True),
                    patch.object(screener_v2_ep, "_cache_get", return_value=None),
                    patch.object(
                        screener_v2_ep,
                        "_fetch_v2_market_data",
                        side_effect=RuntimeError("secret-connection-string"),
                    ),
                ):
                    r = await client.get("/screener-v2")
            return r

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "secret-connection-string" not in str(body)  # production default


# ── 3. Session management in screener endpoints ──────────────────────────
class TestScreenerEndpointSessionManagement:
    def test_screener_endpoint_uses_depends(self) -> None:
        sig = inspect.signature(screener_ep.screener)
        assert "session" in sig.parameters, "screener endpoint must get its session via Depends"

    def test_no_async_with_on_get_session(self) -> None:
        import apps.api.endpoints.screener as m

        src = inspect.getsource(m)
        assert "async with get_session()" not in src

    def test_screener_filter_endpoint_uses_depends(self) -> None:
        sig = inspect.signature(screener_ep.screener_filter)
        assert "session" in sig.parameters


# ── 4. sort_order whitelist ──────────────────────────────────────────────
class TestSortOrderValidation:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("asc", "asc"), ("ASC", "asc"), ("desc", "desc"), ("", "desc"), ("bogus", "desc")],
    )
    def test_validate_sort_order(self, raw: str, expected: str) -> None:
        assert screener_ep._validate_sort_order(raw) == expected


# ── 6. screener110 limit validation (Medium patch) ───────────────────────
class TestScreener110LimitValidation:
    @staticmethod
    def _bounds(fn):
        import inspect

        default = inspect.signature(fn).parameters["limit"].default
        metadata = getattr(default, "metadata", None)
        assert metadata is not None, "limit must be a validated Query param"
        ge = le = None
        for m in metadata:
            if hasattr(m, "ge"):
                ge = m.ge
            if hasattr(m, "le"):
                le = m.le
        return ge, le

    def test_top_buys_limit_bounds(self) -> None:
        from apps.api.endpoints import screener110 as ep

        ge, le = self._bounds(ep.screener110_top_buys)
        assert (ge, le) == (1, 100)

    def test_market_report_limit_bounds(self) -> None:
        from apps.api.endpoints import screener110 as ep

        ge, le = self._bounds(ep.screener110_ai_market_report)
        assert (ge, le) == (1, 100)


# ── 7. dead code removal (Low patch) ─────────────────────────────────────
class TestSortValueNoDeadCode:
    def test_get_sort_value_returns_zero_for_unknown(self) -> None:
        from services.screener_service import ScreenedSymbol, _get_sort_value

        item = ScreenedSymbol(
            symbol="T", name="T", market="M", industry="I",
            last_price=1, change_pct=0, volume=0, value=0,
        )
        assert _get_sort_value(item, "nonexistent_field") == 0.0


# ── 5. Persian reason strings (mojibake regression) ──────────────────────
class TestReasonStringsPersian:
    def test_reasons_not_mojibake(self) -> None:
        pipeline = ScreenerPipeline()
        quote = {
            "symbol": "TEST",
            "price_close": 1000,
            "price_last": 1000,
            "price_change_pct": 1.0,
            "volume": 100000,
            "value": 1e8,
        }
        history = [
            {
                "symbol": "TEST",
                "date": f"2026-08-{d:02d}",
                "price_close": 1000,
                "price_open": 990,
                "price_high": 1010,
                "price_low": 980,
                "volume": 100000,
                "value": 1e8,
                "real_buy_value": 6e7,
                "real_sell_value": 2e7,
            }
            for d in range(1, 21)
        ]
        result = pipeline.run("TEST", "Test Co", "BOURS", "STEEL", quote, history)
        # either ASCII-free Persian text or empty — never cp1252 mojibake
        bad_markers = ("Ù†", "Ø¨", "ÛŒ", "â")
        assert not any(m in result.reason for m in bad_markers), result.reason


# ── 6. pagination edge: page without page_size ───────────────────────────
class TestScreenPaginationEdge:
    async def test_page_without_page_size_paginates(self) -> None:
        svc = ScreenerService(session=None)
        svc._prebuild = AsyncMock(return_value=({"price_close": 100, "price_change_pct": 0}, []))

        def _fake_run(symbol: str, **kwargs) -> ScreenedSymbol:
            # stable distinct scores so ordering is deterministic
            score = ord(symbol[-1]) / 1000.0
            return ScreenedSymbol(
                symbol=symbol,
                name=symbol,
                market="BOURS",
                industry="I",
                last_price=100.0,
                change_pct=0.0,
                volume=1,
                value=1.0,
                smc_score=score,
            )

        svc._pipeline.run = MagicMock(side_effect=_fake_run)

        instruments = [{"symbol": f"SYM{c}", "name": c, "market": "BOURS", "industry": "I"} for c in "ABCDE"]
        watch = [{"symbol": f"SYM{c}", "market": "BOURS"} for c in "ABCDE"]

        results, pag = await svc.screen(
            instruments=instruments,
            market_watch=watch,
            sort_by="smc_score",
            sort_order="desc",
            limit=2,
            page=2,
        )

        assert pag["total"] == 5
        assert len(results) == 2, f"limit ignored with bare page: {[r.symbol for r in results]}"
        assert [r.symbol for r in results] == ["SYMC", "SYMB"]


# ── 8. symbol path-param bounds (reflected-input hardening) ──────────────
class TestSymbolPathBounds:
    """``models/screener.py`` stores symbols as ``String(20)``; the endpoints
    echoed unbounded path input into error messages."""

    @staticmethod
    def _client(router, prefix: str):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from apps.api.dependencies import get_db_session

        app = FastAPI()
        app.include_router(router, prefix=prefix)

        async def _fake_db():
            yield AsyncMock(name="db-session")

        app.dependency_overrides[get_db_session] = _fake_db
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    def test_report_rejects_overlong_symbol(self) -> None:
        from apps.api.endpoints import screener110 as ep

        long_symbol = "X" * 400
        async def _run() -> int:
            async with self._client(ep.router, "/screener110") as client:
                r = await client.get(f"/screener110/report/{long_symbol}")
                return r.status_code

        assert asyncio.run(_run()) == 422

    def test_populate_rejects_overlong_symbol(self) -> None:
        from apps.api.endpoints import screener110 as ep

        async def _run() -> int:
            async with self._client(ep.router, "/screener110") as client:
                r = await client.post(f"/screener110/populate/{'X' * 400}")
                return r.status_code

        assert asyncio.run(_run()) == 422

    def test_accuracy_by_symbol_rejects_overlong(self) -> None:
        from apps.api.endpoints import signal_insights as ep

        async def _run() -> int:
            async with self._client(ep.router, "/signal-insights") as client:
                r = await client.get(f"/signal-insights/accuracy/symbol/{'X' * 400}")
                return r.status_code

        assert asyncio.run(_run()) == 422


# ── 9. indirect leaks via Result.error passthrough ───────────────────────
class TestSafeErrorDetail:
    def test_production_suppresses_result_error(self) -> None:
        from apps.api.error_handlers import safe_error_detail

        with patch("core.config.settings.environment", "production"):
            out = safe_error_detail(
                "connection to localhost:5432 refused", default_message="Backtest failed"
            )
        assert out == "Backtest failed"

    def test_development_keeps_detail(self) -> None:
        from apps.api.error_handlers import safe_error_detail

        with patch("core.config.settings.environment", "development"):
            assert safe_error_detail("boom", default_message="x") == "boom"

    def test_signal_insights_uses_safe_detail(self) -> None:
        import inspect

        from apps.api.endpoints import signal_insights as ep

        src = inspect.getsource(ep)
        assert "result.error or " not in src, "Result.error must not be echoed unfiltered"
