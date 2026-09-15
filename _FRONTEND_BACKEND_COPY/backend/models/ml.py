from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class MlPredictionModel(TimestampMixin, Base):
    __tablename__ = "ml_predictions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    prediction: Mapped[float | None] = mapped_column(Float)
    accuracy: Mapped[float | None] = mapped_column(Float, server_default="0")
    confidence: Mapped[float | None] = mapped_column(Float, server_default="0")
    f1_score: Mapped[float | None] = mapped_column(Float, server_default="0")
    mse: Mapped[float | None] = mapped_column(Float, server_default="0")
    samples: Mapped[int | None] = mapped_column(Integer, server_default="0")
    duration_seconds: Mapped[float | None] = mapped_column(Float, server_default="0")
    predicted_change_pct: Mapped[float | None] = mapped_column(Float)
    last_price: Mapped[float | None] = mapped_column(Float)
    feature_importance: Mapped[str | None] = mapped_column(Text)
    model_loaded_from: Mapped[str | None] = mapped_column(String(30))
    prediction_failed: Mapped[bool | None] = mapped_column(Boolean, server_default=sa.text("false"))
    model_id: Mapped[str | None] = mapped_column(String(50), index=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=sa.func.now(), index=True)


class MlModelModel(TimestampMixin, Base):
    __tablename__ = "ml_models"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    task: Mapped[str | None] = mapped_column(String(50), server_default="classification")
    framework: Mapped[str | None] = mapped_column(String(50), server_default="sklearn")
    latest_version: Mapped[str | None] = mapped_column(String(20), server_default="1.0.0")
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class MlModelVersionModel(TimestampMixin, Base):
    __tablename__ = "ml_model_versions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    model_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    stage: Mapped[str | None] = mapped_column(String(20), server_default="development", index=True)
    metrics: Mapped[str | None] = mapped_column(Text)
    parameters: Mapped[str | None] = mapped_column(Text)
    artifact_path: Mapped[str | None] = mapped_column(Text)
    dataset_snapshot: Mapped[str | None] = mapped_column(String(100))
    training_run_id: Mapped[str | None] = mapped_column(String(50))


class MlTrainingRunModel(TimestampMixin, Base):
    __tablename__ = "ml_training_runs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    experiment_name: Mapped[str | None] = mapped_column(String(200), index=True)
    run_name: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str | None] = mapped_column(String(20), server_default="pending", index=True)
    model_type: Mapped[str | None] = mapped_column(String(50))
    config: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[str | None] = mapped_column(Text)
    best_params: Mapped[str | None] = mapped_column(Text)
    progress_pct: Mapped[float | None] = mapped_column(Float, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)
