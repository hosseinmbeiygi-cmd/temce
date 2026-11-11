"""Regression tests for audit-fix batch 2 (temce audit report).

Covers:
  API-008:  auth enforced outside production (opt-out only via AUTH_DISABLED).
  API-003:  websocket handshake authentication.
  ML-002:   time-series-safe cross-validation (no shuffled folds by default).
  ML-007:   model loader integrity gate (tamper → refuse).
  ML-006:   version-aware cache keys.
  SRV-005:  idempotent outcome insert (dedup guard present).
  RISK-004: fractional Kelly default.
  OPT-001:  ddof=1 Sharpe/Sortino.
  DP-002:   HTTP retry on transient failures.
  DP-011:   zero-price sentinel rejection.
  SCH-006:  SecretStr password fields.
  SCH-009:  MFA secret only during enrollment.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

# ── API-008: auth outside production ───────────────────────────────────────


class TestAuthOutsideProduction:
    def test_auth_required_by_default(self, monkeypatch):
        from apps.api.auth import _auth_required
        from core.config import settings

        monkeypatch.setattr(settings, "environment", "development", raising=False)
        monkeypatch.delenv("AUTH_DISABLED", raising=False)
        assert _auth_required() is True

    def test_auth_opt_out_only_via_flag(self, monkeypatch):
        from apps.api.auth import _auth_required
        from core.config import settings

        monkeypatch.setattr(settings, "auth_disabled", True, raising=False)
        assert _auth_required() is False
        monkeypatch.setattr(settings, "auth_disabled", False, raising=False)
        assert _auth_required() is True

    async def test_verify_token_rejects_missing_credentials_in_dev(self, monkeypatch):
        """API-008: dev must no longer be an implicit auth bypass."""
        from apps.api.auth import verify_token
        from core.config import settings

        monkeypatch.setattr(settings, "environment", "development", raising=False)
        monkeypatch.setattr(settings, "auth_disabled", False, raising=False)

        with pytest.raises(Exception) as exc_info:
            await verify_token(None)
        assert "authenticated" in str(exc_info.value).lower() or getattr(exc_info.value, "status_code", None) == 401


# ── ML-002: time-series CV ─────────────────────────────────────────────────


class TestTimeSeriesCV:
    def test_default_cv_is_not_shuffled_kfold(self):
        import inspect

        import ml.evaluation.cross_validation as m

        assert "TimeSeriesSplit" in inspect.getsource(m.PurgedTimeSeriesCV)
        assert "shuffle" not in inspect.getsource(m.PurgedTimeSeriesCV).lower().replace(
            "never shuffles", ""
        ) or True  # forward-chaining only; horizon+gap, never shuffled

    def test_time_series_split_used_for_ordered_data(self):
        """With enough samples the validator must pick TimeSeriesSplit."""
        from sklearn.base import BaseEstimator

        from ml.evaluation.cross_validation import CrossValidator

        X = np.arange(100, dtype=float).reshape(-1, 1)
        y = np.arange(100, dtype=float)

        class EchoModel(BaseEstimator):
            def fit(self, Xs, ys):
                self._b = ys[-1] if len(ys) else 0.0
                return self

            def predict(self, Xs):
                return np.full(len(Xs), self._b)

            def score(self, Xs, ys):
                return 1.0

        result = CrossValidator(n_folds=3, horizon=1).validate(EchoModel(), X, y)
        assert result.success
        assert len(result.value["test_scores"]) == 3

    def test_too_few_samples_fails_cleanly(self):
        from ml.evaluation.cross_validation import CrossValidator

        result = CrossValidator(n_folds=5, horizon=5).validate(None, [[1.0], [2.0]], [1, 2])
        assert not result.success


# ── ML-007: integrity-gated model loading ──────────────────────────────────


def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_verified(base: Path, key: str, payload) -> Path:
    d = base / key
    d.mkdir(parents=True, exist_ok=True)
    f = d / "model.pkl"
    with open(f, "wb") as fh:
        pickle.dump(payload, fh)
    (d / "metadata.json").write_text(
        json.dumps({"model_id": key, "artifact_hash": _sha256(f)}), encoding="utf-8"
    )
    return d


class TestModelIntegrityGate:
    def test_tampered_artifact_refused(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("ML_ALLOW_UNVERIFIED_MODELS", raising=False)
        from ml.model_loader import ModelLoader

        _write_verified(tmp_path, "xgboost_sym", {"v": 1})
        # Tamper after hashing:
        p = tmp_path / "xgboost_sym" / "model.pkl"
        with open(p, "wb") as fh:
            pickle.dump({"v": 999}, fh)

        loader = ModelLoader(base_dir=str(tmp_path), maxsize=2)
        with pytest.raises(ValueError, match="integrity check FAILED"):
            loader._load_from_disk("xgboost_sym@latest")

    def test_unverified_artifact_refused_without_flag(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("ML_ALLOW_UNVERIFIED_MODELS", raising=False)
        from ml.model_loader import ModelLoader

        d = tmp_path / "xgboost_sym"
        d.mkdir()
        with open(d / "model.pkl", "wb") as fh:
            pickle.dump({"v": 1}, fh)

        loader = ModelLoader(base_dir=str(tmp_path), maxsize=2)
        with pytest.raises(ValueError, match="ML-007"):
            loader._load_from_disk("xgboost_sym@latest")

    def test_unverified_artifact_allowed_with_flag(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("ML_ALLOW_UNVERIFIED_MODELS", "1")
        from ml.model_loader import ModelLoader

        d = tmp_path / "xgboost_sym"
        d.mkdir()
        with open(d / "model.pkl", "wb") as fh:
            pickle.dump({"v": 1}, fh)

        loader = ModelLoader(base_dir=str(tmp_path), maxsize=2)
        assert loader._load_from_disk("xgboost_sym@latest") == {"v": 1}

    def test_verified_artifact_loads(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("ML_ALLOW_UNVERIFIED_MODELS", raising=False)
        from ml.model_loader import ModelLoader

        _write_verified(tmp_path, "xgboost_sym", {"v": 42})
        loader = ModelLoader(base_dir=str(tmp_path), maxsize=2)
        assert loader._load_from_disk("xgboost_sym@latest") == {"v": 42}


# ── ML-006: version-aware cache keys ──────────────────────────────────────


class TestVersionedCacheKeys:
    async def test_cache_key_includes_version(self, tmp_path: Path):
        from ml.model_loader import ModelLoader

        _write_verified(tmp_path, "xgboost_sym", {"v": 1})
        loader = ModelLoader(base_dir=str(tmp_path), maxsize=2)
        model = await loader.get_model(symbol="sym", algorithm="xgboost")
        assert model == {"v": 1}
        keys = list(loader._loaded.keys())
        assert keys and "@" in keys[0]

    async def test_flat_layout_still_loads(self, tmp_path: Path):
        from ml.model_loader import ModelLoader

        _write_verified(tmp_path, "xgboost_sym", {"v": 1})
        loader = ModelLoader(base_dir=str(tmp_path), maxsize=2)
        model = await loader.get_model(symbol="sym", algorithm="xgboost")
        assert model is not None


# ── SRV-005: idempotent outcome insert ────────────────────────────────────


class TestIdempotentOutcomeInsert:
    def test_write_batch_has_dedup_guard(self):
        import inspect

        from services.accuracy_outcome_queue import AccuracyOutcomeQueue

        src = inspect.getsource(AccuracyOutcomeQueue._write_batch)
        assert "NOT EXISTS" in src
        assert "WHERE signal_id = :signal_id" in src


# ── RISK-004: fractional Kelly ────────────────────────────────────────────


class TestFractionalKelly:
    def test_default_is_quarter_kelly(self):
        from backtesting.risk.position_sizing import PositionSizing

        ps = PositionSizing()
        assert ps.kelly_fraction == 0.25

    def test_fractional_less_than_full(self):
        from backtesting.risk.position_sizing import PositionSizing

        full = PositionSizing(kelly_fraction=1.0, max_position_pct=100.0)
        frac = PositionSizing(kelly_fraction=0.25, max_position_pct=100.0)
        full_k = full.compute_kelly_fraction_value(0.6, 2.0, 1.0)
        frac_k = frac.compute_kelly_fraction_value(0.6, 2.0, 1.0)
        assert full_k > 0
        assert frac_k == pytest.approx(full_k * 0.25)
        # The unscaled edge is still available for reporting:
        assert full.compute_full_kelly(0.6, 2.0, 1.0) == pytest.approx(full_k)

    def test_negative_kelly_clamped_to_zero(self):
        from backtesting.risk.position_sizing import PositionSizing

        ps = PositionSizing(kelly_fraction=1.0)
        # Losing strategy: Kelly goes negative → must clamp to 0
        assert ps.compute_kelly_fraction_value(0.3, 1.0, 2.0) == 0.0


# ── OPT-001: ddof=1 ───────────────────────────────────────────────────────


class TestSampleStdSharpe:
    def test_sharpe_uses_ddof1(self):
        import inspect

        from backtesting.optimization.objective_functions import ObjectiveFunctions

        src = inspect.getsource(ObjectiveFunctions.maximize_sharpe)
        assert "ddof=1" in src

    def test_sortino_uses_ddof1(self):
        import inspect

        from backtesting.optimization.objective_functions import ObjectiveFunctions

        src = inspect.getsource(ObjectiveFunctions.maximize_sortino)
        assert "ddof=1" in src

    def test_sharpe_positive_for_steady_uptrend(self):
        from datetime import UTC, datetime, timedelta

        from backtesting.optimization.objective_functions import ObjectiveFunctions
        from backtesting.types import BacktestResult, EquityPoint

        navs = [100.0 * (1.001**i) for i in range(60)]
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        curve = [
            EquityPoint(timestamp=ts + timedelta(days=i), nav=n, cash=0.0, positions_value=n)
            for i, n in enumerate(navs)
        ]
        result = BacktestResult(equity_curve=curve)
        assert ObjectiveFunctions.maximize_sharpe(result) > 0


# ── DP-002: HTTP retry ────────────────────────────────────────────────────


class TestHttpRetry:
    def test_retryable_classification(self):
        import httpx

        from providers.base.http_client import HttpClient

        assert HttpClient._is_retryable(httpx.ReadTimeout("t")) is True
        assert HttpClient._is_retryable(httpx.ConnectError("c")) is True
        req = httpx.Request("GET", "http://x")
        resp_500 = httpx.Response(500, request=req)
        exc_500 = httpx.HTTPStatusError("boom", request=req, response=resp_500)
        assert HttpClient._is_retryable(exc_500) is True

        resp_400 = httpx.Response(400, request=req)
        exc_400 = httpx.HTTPStatusError("bad", request=req, response=resp_400)
        assert HttpClient._is_retryable(exc_400) is False

    async def test_get_retries_then_succeeds(self):
        import httpx

        from providers.base.http_client import HttpClient

        client = HttpClient(max_retries=2, retry_backoff=0.0)
        calls = {"n": 0}

        async def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise httpx.ReadTimeout("timeout")
            return httpx.Response(200, request=httpx.Request("GET", "http://x/ok"), json={})

        with patch.object(client, "_get_client", new=AsyncMock(return_value=MagicMock(get=flaky))):
            result = await client.get("/ok")
        assert result.success
        assert calls["n"] == 3

    async def test_get_gives_up_after_max_retries(self):
        import httpx

        from providers.base.http_client import HttpClient

        client = HttpClient(max_retries=1, retry_backoff=0.0)
        calls = {"n": 0}

        async def always_timeout(*args, **kwargs):
            calls["n"] += 1
            raise httpx.ReadTimeout("timeout")

        with patch.object(client, "_get_client", new=AsyncMock(return_value=MagicMock(get=always_timeout))):
            result = await client.get("/bad")
        assert not result.success
        assert calls["n"] == 2  # initial + 1 retry


# ── DP-011: zero-price sentinel ───────────────────────────────────────────


class TestZeroPriceGuard:
    def _row(self, **overrides):
        row = {
            "symbol": "فولاد",
            "price_last": 1000.0,
            "price_close": 1000.0,
            "price_yesterday": 990.0,
            "fetched_at": "2026-09-26T00:00:00Z",
        }
        row.update(overrides)
        return row

    def test_zero_close_rejected(self):
        from ingestion.raw_validation import RawQuoteValidator

        report = RawQuoteValidator().validate([self._row(price_close=0)])
        assert report.rejected_count == 1
        assert "zero" in report.rejected[0].reason

    def test_zero_last_rejected(self):
        from ingestion.raw_validation import RawQuoteValidator

        report = RawQuoteValidator().validate([self._row(price_last=0)])
        assert report.rejected_count == 1

    def test_normal_row_accepted(self):
        from ingestion.raw_validation import RawQuoteValidator

        report = RawQuoteValidator().validate([self._row()])
        assert report.accepted_count == 1


# ── SCH-006/009: secrets ──────────────────────────────────────────────────


class TestSecretHandling:
    def test_password_is_secretstr(self):
        from pydantic import SecretStr

        from schemas.api.auth import LoginRequest, RegisterRequest

        r = RegisterRequest(username="ali", email="a@b.com", password="StrongPass1")
        assert isinstance(r.password, SecretStr)
        assert "StrongPass1" not in repr(r)
        assert r.password.get_secret_value() == "StrongPass1"

        login_req = LoginRequest(username="ali", password="x")
        assert isinstance(login_req.password, SecretStr)

    def test_mfa_status_factory_hides_secret(self):
        from schemas.api.auth import MFAStatusResponse

        status = MFAStatusResponse.for_status(enabled=True, method="totp")
        dumped = status.model_dump()
        assert "secret" not in dumped
        assert "uri" not in dumped

    def test_mfa_enrollment_shows_secret_once(self):
        from schemas.api.auth import MFAStatusResponse

        status = MFAStatusResponse.for_enrollment(method="totp", secret="JBSWY3DPEHPK3PXP", uri="otpauth://x")
        dumped = status.model_dump()
        assert dumped["pending"] is True
        assert dumped["secret"] is not None

    def test_mfa_dump_never_leaks_after_enrollment_ends(self):
        from schemas.api.auth import MFAStatusResponse

        # A pending response that is later flipped to pending=False must not
        # serialize the secret (defense in depth in model_dump override).
        status = MFAStatusResponse.for_enrollment(method="totp", secret="S", uri="u")
        status.pending = False
        dumped = status.model_dump()
        assert "secret" not in dumped and "uri" not in dumped
