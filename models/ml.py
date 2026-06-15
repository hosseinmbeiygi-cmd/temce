from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


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
    model_id: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    stage: Mapped[str | None] = mapped_column(String(20), server_default="development")
    metrics: Mapped[str | None] = mapped_column(Text)
    parameters: Mapped[str | None] = mapped_column(Text)
    artifact_path: Mapped[str | None] = mapped_column(Text)
    dataset_snapshot: Mapped[str | None] = mapped_column(String(100))
    training_run_id: Mapped[str | None] = mapped_column(String(50))


class MlTrainingRunModel(TimestampMixin, Base):
    __tablename__ = "ml_training_runs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    experiment_name: Mapped[str | None] = mapped_column(String(200))
    run_name: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str | None] = mapped_column(String(20), server_default="pending")
    model_type: Mapped[str | None] = mapped_column(String(50))
    config: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[str | None] = mapped_column(Text)
    best_params: Mapped[str | None] = mapped_column(Text)
    progress_pct: Mapped[float | None] = mapped_column(Float, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)
