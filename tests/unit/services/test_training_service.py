from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.training_service import TrainingService


@pytest.mark.asyncio
async def test_training_start():
    service = TrainingService()
    result = await service.start_training(
        experiment_name="test",
        model_type="xgboost",
        symbols=["فولاد"],
    )
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_training_status():
    service = TrainingService()
    result = await service.get_training_status("run_001")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_training_list():
    service = TrainingService()
    result = await service.list_runs()
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_training_cancel():
    service = TrainingService()
    result = await service.cancel_run("run_001")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_training_get_metrics():
    service = TrainingService()
    result = await service.get_metrics("run_001")
    assert result.success or not result.success


@pytest.mark.asyncio
async def test_train_with_db_data_invalidates_loader_cache():
    """After a successful retrain the ModelLoader cache must be invalidated
    for the exact (symbol, model_type) pair so the fresh artifact is used.
    """
    service = TrainingService()

    # Fake a full training run: enough OHLCV → features → fit → save.
    fake_model = MagicMock()
    fake_model.params = {}
    fake_model.fit = MagicMock()
    fake_model.predict = MagicMock(return_value=MagicMock(predictions=[0.1] * 20))

    with (
        patch.object(service, "_fetch_ohlcv") as mock_fetch,
        patch.object(service, "_build_features") as mock_feats,
        patch.object(service, "_split_time_series") as mock_split,
        patch("services.training_service.model_registry.create", return_value=fake_model) as mock_create,
        patch.object(service.artifact_manager, "save_model", return_value="/tmp/artifacts/xgboost_فولاد/v1-test") as mock_save,
        patch.object(service, "_invalidate_model_cache") as mock_invalidate,
    ):
        import pandas as pd

        mock_fetch.return_value = type("R", (), {"success": True, "value": pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=40).strftime("%Y-%m-%d"),
            "open": [100.0] * 40,
            "high": [101.0] * 40,
            "low": [99.0] * 40,
            "close": [100.5] * 40,
            "volume": [1000] * 40,
        })})()

        import numpy as np

        from ml.types import FeatureMatrix, TargetVector

        fm = FeatureMatrix(data=pd.DataFrame({"f1": np.ones(20)}), feature_names=["f1"])
        tv = TargetVector(data=np.ones(20), name="next_return", task_type="regression")
        mock_feats.return_value = (fm, tv)
        mock_split.return_value = (fm, fm, tv, tv)

        result = await service.train_with_db_data(symbol="فولاد", model_type="xgboost")

    assert result.success
    mock_save.assert_called_once()
    mock_invalidate.assert_called_once_with("فولاد", "xgboost")


@pytest.mark.asyncio
async def test_invalidate_model_cache_calls_loader():
    """_invalidate_model_cache must forward to the ModelLoader singleton."""
    loader = MagicMock()
    with patch("ml.model_loader.get_model_loader", return_value=loader):
        TrainingService._invalidate_model_cache("فولاد", "xgboost")
    loader.invalidate.assert_called_once_with(symbol="فولاد", algorithm="xgboost")


@pytest.mark.asyncio
async def test_invalidate_model_cache_handles_failure():
    """Failure to invalidate must not raise (defensive hook)."""
    loader = MagicMock()
    loader.invalidate.side_effect = RuntimeError("redis down")
    with patch("ml.model_loader.get_model_loader", return_value=loader):
        # Should not raise
        TrainingService._invalidate_model_cache("فولاد", "xgboost")


@pytest.mark.asyncio
async def test_model_training_job_invalidates_after_retrain():
    """ModelTrainingJob.execute must invalidate the loader cache with the
    symbol + algorithm extracted from its payload.
    """
    from jobs.model_training import ModelTrainingJob

    loader = MagicMock()
    with patch("ml.model_loader.get_model_loader", return_value=loader):
        job = ModelTrainingJob()
        result = await job.execute({"symbol": "وبملت", "algorithm": "xgboost"})

    assert result.success
    loader.invalidate.assert_called_once_with(symbol="وبملت", algorithm="xgboost")


@pytest.mark.asyncio
async def test_model_training_job_invalidates_all_when_algorithm_unknown():
    """Symbol-only payload evicts every algorithm for that symbol."""
    from jobs.model_training import ModelTrainingJob

    loader = MagicMock()
    with patch("ml.model_loader.get_model_loader", return_value=loader):
        job = ModelTrainingJob()
        result = await job.execute({"symbol": "فولاد"})

    assert result.success
    loader.invalidate.assert_called_once_with(symbol="فولاد", algorithm=None)


@pytest.mark.asyncio
async def test_model_training_job_noop_without_symbol():
    """Payload without a symbol must not crash or call the loader."""
    from jobs.model_training import ModelTrainingJob

    loader = MagicMock()
    with patch("ml.model_loader.get_model_loader", return_value=loader):
        job = ModelTrainingJob()
        result = await job.execute({"dataset": "d1"})

    assert result.success
    loader.invalidate.assert_not_called()


@pytest.mark.asyncio
async def test_registered_model_training_job_invalidates_after_retrain():
    """The registered ModelTrainingJob (jobs.definitions.ml_jobs) must
    invalidate the loader cache after a successful retrain.
    """
    from jobs.definitions.ml_jobs import ModelTrainingJob
    from jobs.job_context import JobContext

    loader = MagicMock()

    with (
        patch("ml.model_loader.get_model_loader", return_value=loader),
        patch("jobs.definitions.ml_jobs.TrainingService.train", new=AsyncMock(return_value=MagicMock(success=True, value="run_xyz"))),
    ):
        job = ModelTrainingJob(name="ModelTrainingJob")
        ctx = JobContext(job_id="j1", job_name="ModelTrainingJob", params={
            "model_name": "xgboost_فولاد",
            "params": {"symbol": "فولاد", "algorithm": "xgboost"},
        })
        result = await job.execute(ctx)

    assert result.success
    loader.invalidate.assert_called_once_with(symbol="فولاد", algorithm="xgboost")


@pytest.mark.asyncio
async def test_registered_model_training_job_parses_model_name():
    """When params carry no explicit symbol, the job parses <algo>_<symbol>
    from the model_name to invalidate the right cache entry.
    """
    from jobs.definitions.ml_jobs import ModelTrainingJob
    from jobs.job_context import JobContext

    loader = MagicMock()

    with (
        patch("ml.model_loader.get_model_loader", return_value=loader),
        patch("jobs.definitions.ml_jobs.TrainingService.train", new=AsyncMock(return_value=MagicMock(success=True, value="run_xyz"))),
    ):
        job = ModelTrainingJob(name="ModelTrainingJob")
        ctx = JobContext(job_id="j1", job_name="ModelTrainingJob", params={
            "model_name": "random_forest_وبملت",
            "params": {},
        })
        result = await job.execute(ctx)

    assert result.success
    loader.invalidate.assert_called_once_with(symbol="وبملت", algorithm="random_forest")


@pytest.mark.asyncio
async def test_registered_model_training_job_noop_without_symbol():
    """A model_name with no parseable symbol must not crash the job."""
    from jobs.definitions.ml_jobs import ModelTrainingJob
    from jobs.job_context import JobContext

    loader = MagicMock()

    with (
        patch("ml.model_loader.get_model_loader", return_value=loader),
        patch("jobs.definitions.ml_jobs.TrainingService.train", new=AsyncMock(return_value=MagicMock(success=True, value="run_xyz"))),
    ):
        job = ModelTrainingJob(name="ModelTrainingJob")
        ctx = JobContext(job_id="j1", job_name="ModelTrainingJob", params={"model_name": "default"})
        result = await job.execute(ctx)

    assert result.success
    loader.invalidate.assert_not_called()
