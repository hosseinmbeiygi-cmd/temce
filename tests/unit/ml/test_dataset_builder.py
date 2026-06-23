from __future__ import annotations


def test_dataset_builder_creates_features():
    from ml.dataset_builder import DatasetBuilder

    builder = DatasetBuilder()
    features = builder.build_feature_list(["close", "volume", "rsi"])
    assert len(features) == 3
    assert "close" in features


def test_dataset_builder_train_test_split():
    from ml.dataset_builder import DatasetBuilder

    builder = DatasetBuilder()
    data = list(range(100))
    train, test = builder.train_test_split(data, test_size=0.2)
    assert len(train) == 80
    assert len(test) == 20


def test_dataset_builder_normalize():
    from ml.dataset_builder import DatasetBuilder

    builder = DatasetBuilder()
    data = [10.0, 20.0, 30.0, 40.0, 50.0]
    normalized = builder.normalize(data)
    assert abs(sum(normalized)) < 0.01


def test_dataset_builder_create_sequences():
    from ml.dataset_builder import DatasetBuilder

    builder = DatasetBuilder()
    data = list(range(20))
    X, y = builder.create_sequences(data, sequence_length=5)
    assert len(X) == 15
    assert len(y) == 15


def test_dataset_builder_validate():
    from ml.dataset_builder import DatasetBuilder

    builder = DatasetBuilder()
    valid = builder.validate({"close": [1, 2, 3], "volume": [4, 5, 6]})
    assert valid is True
    invalid = builder.validate({"close": [1, 2, 3], "volume": [4, 5]})
    assert invalid is False

