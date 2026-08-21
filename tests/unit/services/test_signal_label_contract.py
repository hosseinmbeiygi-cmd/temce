"""Tests for the explicit label contract in ``prepare_training_data`` (audit F8).

Guards against the previous silent-misalignment risk: a caller-supplied
``returns`` array could be shifted by one step and the model would train on
leaky/misaligned labels without any error. The new contract derives labels
internally from ``closes`` (asserting each feature was built from a prefix of
that array) and only keeps a length-validated legacy ``targets`` path.
"""

from __future__ import annotations

import pytest

from ml.types import FeatureMatrix, TargetVector
from services.signal_feature_pipeline import MarketFeatures, SignalFeaturePipeline


def _make_features(closes: list[float], start_count: int = 2) -> list[MarketFeatures]:
    """Build features from prefixes of `closes`, matching the production path.

    Feature with closes_count=c is built from closes[:c], so its last_price is
    closes[c - 1] and its own last bar is index c - 1.
    """
    feats: list[MarketFeatures] = []
    for c in range(start_count, len(closes)):
        feats.append(
            MarketFeatures(
                symbol="TEST",
                market="stock",
                timestamp="",
                vector=[float(c)],
                feature_names=["bar_index"],
                metadata={"last_price": closes[c - 1], "closes_count": c},
            )
        )
    return feats


class TestClosesMode:
    def test_derives_next_bar_labels_from_closes(self) -> None:
        # closes: 100 101 102 100 105 104 106
        # features: c=2 (last 101), c=3 (last 102), c=4 (last 100), c=5 (last 105), c=6 (last 104)
        closes = [100.0, 101.0, 102.0, 100.0, 105.0, 104.0, 106.0]
        feats = _make_features(closes, start_count=2)

        fm, tv = SignalFeaturePipeline.prepare_training_data(
            feats, closes=closes, sequence_length=2
        )

        assert tv.data is not None
        y = list(tv.data)
        # Row i=2: last feature c=3 -> closes[3]/closes[2]-1 = 100/102-1 < 0 -> 0
        # Row i=3: last feature c=4 -> closes[4]/closes[3]-1 = 105/100-1 > 0 -> 1
        # Row i=4: last feature c=5 -> closes[5]/closes[4]-1 = 104/105-1 < 0 -> 0
        assert y == [0.0, 1.0, 0.0]
        assert fm.data is not None
        assert len(fm.data) == 3

    def test_no_lookahead_last_feature_bar_is_excluded_from_label(self) -> None:
        closes = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
        feats = _make_features(closes, start_count=2)

        fm, tv = SignalFeaturePipeline.prepare_training_data(
            feats, closes=closes, sequence_length=2
        )

        # Row i=2: X = features 0,1 (last_price 10,11); label uses closes[3]=13,
        #          closes[2]=12 — both after the last X bar (11). No look-ahead.
        assert tv.data is not None
        # Row i=4 uses closes[5]/closes[4] = 15/14 > 0 -> 1
        assert list(tv.data)[-1] == 1.0

    def test_shifted_closes_array_is_rejected(self) -> None:
        closes = [100.0, 101.0, 102.0, 100.0, 105.0]
        feats = _make_features(closes, start_count=2)
        # A foreign/shifted closes array whose closes[c-1] != metadata.last_price
        foreign = [0.0, 0.0, 0.0, 0.0, 0.0]

        with pytest.raises(ValueError, match="misaligned with `closes`"):
            SignalFeaturePipeline.prepare_training_data(
                feats, closes=foreign, sequence_length=2
            )

    def test_feature_without_closes_count_metadata_is_rejected(self) -> None:
        feats = [
            MarketFeatures(symbol="T", market="stock", vector=[1.0], feature_names=["x"], metadata={})
            for _ in range(5)
        ]
        with pytest.raises(ValueError, match="closes_count"):
            SignalFeaturePipeline.prepare_training_data(
                feats, closes=[1.0] * 5, sequence_length=2
            )

    def test_label_requires_a_future_bar(self) -> None:
        # The last feature used for a label has closes_count == len(closes),
        # so there is no future bar to compute y_{t+1} from.
        closes = [1.0, 2.0, 3.0, 4.0]
        feats = [
            MarketFeatures(
                symbol="T", market="stock", vector=[1.0], feature_names=["x"],
                metadata={"last_price": 2.0, "closes_count": 2},
            ),
            MarketFeatures(
                symbol="T", market="stock", vector=[1.0], feature_names=["x"],
                metadata={"last_price": 4.0, "closes_count": 4},
            ),
            MarketFeatures(
                symbol="T", market="stock", vector=[1.0], feature_names=["x"],
                metadata={"last_price": 4.0, "closes_count": 4},
            ),
        ]
        with pytest.raises(ValueError, match="no future bar"):
            SignalFeaturePipeline.prepare_training_data(
                feats, closes=closes, sequence_length=1
            )


class TestArgumentValidation:
    def test_requires_exactly_one_label_source(self) -> None:
        closes = [1.0, 2.0, 3.0, 4.0]
        feats = _make_features(closes, start_count=2)

        with pytest.raises(ValueError, match="exactly one"):
            SignalFeaturePipeline.prepare_training_data(
                feats, closes=closes, targets=[0.1, 0.1], sequence_length=2
            )
        with pytest.raises(ValueError, match="exactly one"):
            SignalFeaturePipeline.prepare_training_data(
                feats, sequence_length=2
            )

    def test_sequence_length_must_be_positive(self) -> None:
        closes = [1.0, 2.0, 3.0, 4.0]
        feats = _make_features(closes, start_count=2)
        with pytest.raises(ValueError, match=">= 1"):
            SignalFeaturePipeline.prepare_training_data(feats, closes=closes, sequence_length=0)

    def test_too_few_features_for_sequence_length(self) -> None:
        closes = [1.0, 2.0, 3.0]
        feats = _make_features(closes, start_count=2)
        with pytest.raises(ValueError, match="Not enough features"):
            SignalFeaturePipeline.prepare_training_data(feats, closes=closes, sequence_length=5)


class TestLegacyTargetsPath:
    def test_targets_used_verbatim(self) -> None:
        feats = _make_features([1.0, 2.0, 3.0, 4.0, 5.0], start_count=2)
        # 3 features (c=2,3,4), 3 targets; seq_len=2 -> 1 row using targets[2]
        fm, tv = SignalFeaturePipeline.prepare_training_data(
            feats, targets=[-0.1, -0.2, 0.3], sequence_length=2
        )
        assert tv.data is not None
        assert list(tv.data) == [1.0]  # targets[2] = 0.3 > 0

    def test_targets_length_mismatch_is_rejected(self) -> None:
        feats = _make_features([1.0, 2.0, 3.0, 4.0, 5.0], start_count=2)
        with pytest.raises(ValueError, match="misaligned"):
            SignalFeaturePipeline.prepare_training_data(
                feats, targets=[0.1], sequence_length=2
            )


class TestWalkForwardIntegration:
    async def test_validate_model_uses_closes_for_labels(self, monkeypatch) -> None:
        """validate_model passes closes through; labels come from closes, not targets."""
        import pandas as pd

        from services.walk_forward_validator import WalkForwardValidator

        captured: dict = {}

        def fake_prepare(feature_sequence, closes=None, targets=None, sequence_length=20):
            captured["closes"] = closes
            captured["targets"] = targets
            y = pd.Series([1.0, 0.0, 1.0, 0.0, 1.0], name="direction_up")
            fm = FeatureMatrix(
                data=pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0]}),
                feature_names=["a"],
            )
            tv = TargetVector(data=y, name="direction_up", task_type="classification")
            return fm, tv

        monkeypatch.setattr(
            SignalFeaturePipeline, "prepare_training_data", staticmethod(fake_prepare)
        )

        class FakeModel:
            is_fitted = True

            def fit(self, fm, tv):
                return self

            def predict(self, fm):
                from types import SimpleNamespace

                return SimpleNamespace(mean=0.6, predictions=[0.6])

        class FakeRegistry:
            def create(self, model_name, params=None):
                return FakeModel()

        monkeypatch.setattr("services.walk_forward_validator.model_registry", FakeRegistry())

        closes = [100.0 + i for i in range(120)]
        feats = _make_features(closes, start_count=2)  # 118 features >= 100

        validator = WalkForwardValidator()
        result = await validator.validate_model(
            market="stock",
            model_name="xgboost",
            feature_sequence=feats,
            closes=closes,
            num_windows=5,
        )

        assert result.success, result.error
        assert captured["closes"] is closes
        assert captured["targets"] is None
        assert result.value.num_windows >= 1

    async def test_validate_model_legacy_targets_still_works(self, monkeypatch) -> None:
        from services.walk_forward_validator import WalkForwardValidator

        captured: dict = {}

        def fake_prepare(feature_sequence, closes=None, targets=None, sequence_length=20):
            captured["closes"] = closes
            captured["targets"] = targets
            import pandas as pd

            y = pd.Series([1.0] * 5, name="direction_up")
            fm = FeatureMatrix(
                data=pd.DataFrame({"a": [1.0] * 5}),
                feature_names=["a"],
            )
            return fm, TargetVector(data=y, name="direction_up", task_type="classification")

        monkeypatch.setattr(
            SignalFeaturePipeline, "prepare_training_data", staticmethod(fake_prepare)
        )

        class FakeModel:
            is_fitted = True

            def fit(self, fm, tv):
                return self

            def predict(self, fm):
                from types import SimpleNamespace

                return SimpleNamespace(mean=0.6, predictions=[0.6])

        class FakeRegistry:
            def create(self, model_name, params=None):
                return FakeModel()

        monkeypatch.setattr("services.walk_forward_validator.model_registry", FakeRegistry())

        feats = _make_features([1.0 + i for i in range(120)], start_count=2)
        targets = [0.1] * len(feats)

        validator = WalkForwardValidator()
        result = await validator.validate_model(
            market="stock",
            model_name="xgboost",
            feature_sequence=feats,
            targets=targets,
            num_windows=5,
        )

        assert result.success, result.error
        assert captured["closes"] is None
        assert captured["targets"] is not None
