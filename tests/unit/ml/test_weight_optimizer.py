"""Unit tests for ml/train_weight_optimizer.WeightOptimizer."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from ml.train_weight_optimizer import (
    REGIMES,
    WeightOptimizer,
    assign_regime,
    normalize_weights,
)

# ── Pure helpers ────────────────────────────────────────────────────────


class TestAssignRegime:
    def test_classifies_bull_bear_neutral(self) -> None:
        idx = pd.date_range("2025-01-01", periods=5)
        rets = pd.Series([0.05, -0.05, 0.0, 0.03, -0.03], index=idx)
        labels = assign_regime(rets)
        assert list(labels.values) == ["bull", "bear", "neutral", "bull", "bear"]

    def test_thresholds_are_configurable(self) -> None:
        rets = pd.Series([0.01, -0.01])
        labels = assign_regime(rets, up_threshold=0.005, down_threshold=-0.005)
        assert list(labels.values) == ["bull", "bear"]


class TestNormalizeWeights:
    def test_sums_to_one_in_absolute_value(self) -> None:
        coefs = pd.Series({"a": 2.0, "b": -1.0, "c": 1.0})
        w = normalize_weights(coefs)
        assert abs(sum(abs(v) for v in w.values()) - 1.0) < 1e-9
        assert w["a"] > 0 and w["b"] < 0 and w["c"] > 0

    def test_zero_coefs_returns_zeros(self) -> None:
        coefs = pd.Series({"a": 0.0, "b": 0.0})
        w = normalize_weights(coefs)
        assert all(v == 0.0 for v in w.values())

    def test_single_feature(self) -> None:
        w = normalize_weights(pd.Series({"only": 3.0}))
        assert w == {"only": 1.0}


# ── WeightOptimizer ─────────────────────────────────────────────────────


class TestWeightOptimizer:
    def _make_optimizer(self) -> WeightOptimizer:
        return WeightOptimizer(horizon=2, min_samples=2, alpha=0.5)

    def _sample_scores(self) -> pd.DataFrame:
        """Scores with 2 numeric features + a text field (queue_status) that
        must be filtered out before fitting (regression: raw_scores JSONB
        embeds Persian categorical fields like 'رد_نمره' that broke Ridge)."""
        rows = []
        for sym, mom, val in [("A", 1.0, 2.0), ("B", 0.5, 1.0), ("C", 2.0, 3.0)]:
            for d in ("2025-01-01", "2025-01-02"):
                rows.append({
                    "trade_date": pd.Timestamp(d), "symbol": sym,
                    "feat_mom": mom + (0.5 if d == "2025-01-02" else 0.0),
                    "feat_val": val + (0.5 if d == "2025-01-02" else 0.0),
                    "queue_status": "BUY_QUEUE",
                })
        return pd.DataFrame(rows)

    def _sample_index(self) -> pd.DataFrame:
        """Index data in the same shape production ``_load_index`` returns:
        date as the (deduped) DatetimeIndex with an ``index_value`` column.

        Four values so the 2-day momentum is positive for both score dates
        (2025-01-01 and 2025-01-02), i.e. every merged row lands in 'bull'.
        """
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-12-29", "2024-12-30", "2025-01-01", "2025-01-02"]),
                "index_value": [90.0, 100.0, 110.0, 121.0],
            }
        )
        df = df.drop_duplicates(subset=["date"]).sort_values("date").set_index("date")
        return df[~df.index.duplicated(keep="last")]

    def _sample_returns(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"symbol": "A", "date": pd.Timestamp("2025-01-01"), "fwd_return": 0.05},
                {"symbol": "A", "date": pd.Timestamp("2025-01-02"), "fwd_return": 0.06},
                {"symbol": "B", "date": pd.Timestamp("2025-01-01"), "fwd_return": 0.02},
                {"symbol": "B", "date": pd.Timestamp("2025-01-02"), "fwd_return": 0.03},
                {"symbol": "C", "date": pd.Timestamp("2025-01-01"), "fwd_return": 0.09},
                {"symbol": "C", "date": pd.Timestamp("2025-01-02"), "fwd_return": 0.10},
            ]
        )

    async def test_train_writes_regime_json_files(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        opt = self._make_optimizer()

        async def load_scores() -> pd.DataFrame:
            return self._sample_scores()

        async def load_index() -> pd.DataFrame:
            return self._sample_index()

        async def load_returns(start=None, end=None) -> pd.DataFrame:
            return self._sample_returns()

        monkeypatch.setattr(opt, "_load_scores", load_scores)
        monkeypatch.setattr(opt, "_load_index", load_index)
        monkeypatch.setattr(opt, "_load_forward_returns", load_returns)

        summary = await opt.train(output_dir=tmp_path)

        assert summary["status"] == "ok"
        assert summary["horizon"] == 2

        files = list(tmp_path.glob("weights_*.json"))
        assert len(files) >= 1
        for regime in REGIMES:
            if regime in summary["regimes"] and summary["regimes"][regime]["status"] == "ok":
                payload = json.loads((tmp_path / f"weights_{regime}.json").read_text(encoding="utf-8"))
                assert payload["regime"] == regime
                assert "weights" in payload
                total = sum(abs(v) for v in payload["weights"].values())
                assert abs(total - 1.0) < 1e-6
                # weights keys must be feature columns
                assert set(payload["weights"].keys()) <= {"feat_mom", "feat_val"}
                # regression: text/categorical columns must be excluded
                assert "queue_status" not in payload["weights"]
                # F6: the payload must expose OOS validation fields.
                assert "r2_is_mean" in payload
                assert "r2_oos_mean" in payload
                assert "wf_n_windows" in payload
                assert "provisional" in payload
                # Tiny sample (6 rows) cannot be walk-forward validated → the
                # weights must be flagged provisional, never silently "valid".
                assert payload["provisional"] is True
                assert payload["r2_oos_mean"] is None

    async def test_train_reports_validation_in_summary(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        opt = self._make_optimizer()

        async def load_scores() -> pd.DataFrame:
            return self._sample_scores()

        async def load_index() -> pd.DataFrame:
            return self._sample_index()

        async def load_returns(start=None, end=None) -> pd.DataFrame:
            return self._sample_returns()

        monkeypatch.setattr(opt, "_load_scores", load_scores)
        monkeypatch.setattr(opt, "_load_index", load_index)
        monkeypatch.setattr(opt, "_load_forward_returns", load_returns)

        summary = await opt.train(output_dir=tmp_path)

        assert summary["validation"] == "purged_walk_forward"
        bull = summary["regimes"].get("bull", {})
        assert bull.get("status") == "ok"
        assert "r2_oos_mean" in bull
        assert "wf_n_windows" in bull
        assert "provisional" in bull

    async def test_train_no_walk_forward_marks_provisional(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """``wf_windows=0`` disables validation — weights must be flagged
        provisional so consumers know they are in-sample only."""
        opt = WeightOptimizer(horizon=2, min_samples=2, alpha=0.5, wf_windows=0)

        async def load_scores() -> pd.DataFrame:
            return self._sample_scores()

        async def load_index() -> pd.DataFrame:
            return self._sample_index()

        async def load_returns(start=None, end=None) -> pd.DataFrame:
            return self._sample_returns()

        monkeypatch.setattr(opt, "_load_scores", load_scores)
        monkeypatch.setattr(opt, "_load_index", load_index)
        monkeypatch.setattr(opt, "_load_forward_returns", load_returns)

        summary = await opt.train(output_dir=tmp_path)
        assert summary["validation"] == "in_sample_provisional"

        payload = json.loads((tmp_path / "weights_bull.json").read_text(encoding="utf-8"))
        assert payload["provisional"] is True
        assert payload["validation_reason"] == "validation_disabled"
        assert payload["r2_oos_mean"] is None
        # In-sample R² is still the fallback number, clearly flagged provisional.
        assert isinstance(payload["r2"], float)

    async def test_train_skips_regime_below_min_samples(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        # Only bull rows present (all index momentum positive) — bear/neutral skipped.
        opt = WeightOptimizer(horizon=2, min_samples=2, alpha=0.5)

        async def load_scores() -> pd.DataFrame:
            return self._sample_scores()

        async def load_index() -> pd.DataFrame:
            return self._sample_index()

        async def load_returns(start=None, end=None) -> pd.DataFrame:
            return self._sample_returns()

        monkeypatch.setattr(opt, "_load_scores", load_scores)
        monkeypatch.setattr(opt, "_load_index", load_index)
        monkeypatch.setattr(opt, "_load_forward_returns", load_returns)

        summary = await opt.train(output_dir=tmp_path)

        bull = summary["regimes"].get("bull", {})
        assert bull.get("status") == "ok"
        for regime in ("bear", "neutral"):
            assert summary["regimes"][regime]["status"] == "skipped"

    async def test_train_returns_error_without_scores(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        opt = self._make_optimizer()

        async def load_scores() -> pd.DataFrame:
            return pd.DataFrame()

        async def load_index() -> pd.DataFrame:
            return self._sample_index()

        async def load_returns() -> pd.DataFrame:
            return self._sample_returns()

        monkeypatch.setattr(opt, "_load_scores", load_scores)
        monkeypatch.setattr(opt, "_load_index", load_index)
        monkeypatch.setattr(opt, "_load_forward_returns", load_returns)

        summary = await opt.train(output_dir=tmp_path)
        assert summary["status"] == "error"
        assert summary["reason"] == "no_scores"
