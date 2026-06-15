from __future__ import annotations


def test_feature_flag_default():
    from core.feature_flags import FeatureFlag

    ff = FeatureFlag()
    assert ff.is_enabled("non_existent") is False


def test_feature_flag_enable():
    from core.feature_flags import FeatureFlag

    ff = FeatureFlag()
    ff.enable("test_feature")
    assert ff.is_enabled("test_feature") is True


def test_feature_flag_disable():
    from core.feature_flags import FeatureFlag

    ff = FeatureFlag()
    ff.enable("test_feature")
    ff.disable("test_feature")
    assert ff.is_enabled("test_feature") is False


def test_feature_flag_context_manager():
    from core.feature_flags import FeatureFlag

    ff = FeatureFlag()
    with ff.override("test_feature", True):
        assert ff.is_enabled("test_feature") is True
    assert ff.is_enabled("test_feature") is False


def test_feature_flag_list():
    from core.feature_flags import FeatureFlag

    ff = FeatureFlag()
    ff.enable("feature_a")
    ff.enable("feature_b")
    flags = ff.list_flags()
    assert "feature_a" in flags
    assert "feature_b" in flags
