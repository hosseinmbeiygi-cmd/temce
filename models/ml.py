from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
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


class MlEngineeredFeatureModel(Base):
    """ORM model for ml_engineered_features (MLD-10).

    Previously defined only in migration 0035, leaving it outside
    Base.metadata. Adding the ORM model lets Alembic track schema changes
    and allows the ML pipeline to read rows via SQLAlchemy.
    """

    __tablename__ = "ml_engineered_features"

    # Primary key
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)

    # Price
    price_close: Mapped[float | None] = mapped_column(Float)
    price_open: Mapped[float | None] = mapped_column(Float)
    price_high: Mapped[float | None] = mapped_column(Float)
    price_low: Mapped[float | None] = mapped_column(Float)

    # Volume & value
    volume: Mapped[int | None] = mapped_column(BigInteger)
    trade_value: Mapped[float | None] = mapped_column(Float)
    trade_count: Mapped[int | None] = mapped_column(Integer)

    # Technical indicators
    rsi_14: Mapped[float | None] = mapped_column(Float)
    macd_histogram: Mapped[float | None] = mapped_column(Float)
    macd_signal: Mapped[float | None] = mapped_column(Float)
    bb_upper: Mapped[float | None] = mapped_column(Float)
    bb_lower: Mapped[float | None] = mapped_column(Float)
    bb_middle: Mapped[float | None] = mapped_column(Float)
    sma_5: Mapped[float | None] = mapped_column(Float)
    sma_10: Mapped[float | None] = mapped_column(Float)
    sma_20: Mapped[float | None] = mapped_column(Float)
    sma_50: Mapped[float | None] = mapped_column(Float)
    sma_200: Mapped[float | None] = mapped_column(Float)
    ema_5: Mapped[float | None] = mapped_column(Float)
    ema_10: Mapped[float | None] = mapped_column(Float)
    ema_20: Mapped[float | None] = mapped_column(Float)
    atr_14: Mapped[float | None] = mapped_column(Float)
    volume_zscore: Mapped[float | None] = mapped_column(Float)
    volume_ma_20_ratio: Mapped[float | None] = mapped_column(Float)

    # Real / legal flow
    real_buy_ratio: Mapped[float | None] = mapped_column(Float)
    legal_buy_ratio: Mapped[float | None] = mapped_column(Float)
    real_sell_ratio: Mapped[float | None] = mapped_column(Float)
    legal_sell_ratio: Mapped[float | None] = mapped_column(Float)
    net_legal_flow: Mapped[float | None] = mapped_column(Float)

    # Fundamental
    eps: Mapped[float | None] = mapped_column(Float)
    pe_ratio: Mapped[float | None] = mapped_column(Float)
    free_float_pct: Mapped[float | None] = mapped_column(Float)
    market_cap: Mapped[float | None] = mapped_column(Float)

    # Macro correlations
    gold_correlation_3d: Mapped[float | None] = mapped_column(Float)
    usd_correlation_3d: Mapped[float | None] = mapped_column(Float)
    index_correlation_3d: Mapped[float | None] = mapped_column(Float)

    # Queue features
    queue_status: Mapped[str | None] = mapped_column(String(16))
    queue_volume_ratio: Mapped[float | None] = mapped_column(Float)
    queue_days_streak: Mapped[int | None] = mapped_column(Integer)
    queue_type_change: Mapped[str | None] = mapped_column(String(20))
    distance_to_limit: Mapped[float | None] = mapped_column(Float)

    # Outcome labels (supervised ML targets)
    target_return_5d: Mapped[float | None] = mapped_column(Float)
    target_return_10d: Mapped[float | None] = mapped_column(Float)
    target_direction_5d: Mapped[int | None] = mapped_column(Integer, index=True)

    # Score summary
    score_total: Mapped[float | None] = mapped_column(Float)
    final_decision: Mapped[str | None] = mapped_column(String(16))

    # Full payload + metadata
    features_json: Mapped[dict | None] = mapped_column(JSONB)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa.text("NOW()"),
        nullable=False,
        index=True,
    )
