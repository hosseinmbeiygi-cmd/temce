"""Per-market isotonic calibration for signal confidence scores.

Why a separate module and not extending ``ProbabilityCalibrator``?
The existing calibrator is bucket-based, persists to ``calibration_models``
table, and is wired into the live request path. The isotonic layer is:

  - **regenerable from scratch** (no online updates, no drift detection)
  - **slower per call** (must build the whole fit per market on each
    refresh, but called on a schedule not per request)
  - **fitted to a wider window** (default 6 months, vs the bucket
    calibrator's 5000 most-recent rows)

Use this module for the **retraining step** in the calibration
pipeline; use the bucket calibrator for the **online apply** step.
The two coexist: the isotonic model is the source of truth for the
next refresh, the bucket model is the source of truth for the next
request.

Model choice: isotonic regression
  - Non-parametric, monotonic
  - Works with as few as 30 samples (we require 100 min)
  - sklearn ships it; no extra dependency
  - Outperforms Platt when the calibration curve is non-linear
    (which our reliability diagram shows: deciles 3-5 at conf=0.32
    span 0-37% accuracy — linear scaling cannot fix this)

Platt scaling (one-parameter sigmoid) is the alternative; it is more
robust with very small samples but cannot model the kink in the
middle of our curve. The module is structured so a Platt variant can
be added later.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class CalibrationPoint:
    """One (predicted, actual) pair from ``signal_accuracy``."""

    predicted: float
    actual: float  # 0.0 or 1.0


@dataclass(frozen=True)
class IsotonicModel:
    """A trained isotonic model plus enough metadata to apply it.

    ``buckets`` is the discrete, fitted mapping: for any raw predicted
    confidence, you binary-search the upper bound of the bucket and
    return the mapped actual. This avoids the sklearn object for
    serialization; the model lives in Postgres as a JSON column.
    """

    market: str
    timeframe: str
    direction: str
    n_samples: int
    brier_score: float
    ece: float
    trained_at: datetime
    buckets: list[tuple[float, float]] = field(default_factory=list)
    # Each tuple is (threshold, calibrated_probability). Apply by
    # binary search on `threshold` and return the calibrated value.

    def apply(self, raw: float) -> float:
        """Map a raw confidence through the calibration curve.

        Returns the original value clamped to [0.01, 0.99] when no
        bucket covers it (cold-start fallback for unmodelled markets).
        """
        if not self.buckets:
            return max(0.01, min(0.99, raw))
        # Buckets are stored sorted by threshold ascending. Find the
        # first threshold >= raw, return its calibrated value.
        for thr, cal in self.buckets:
            if raw <= thr:
                return cal
        # raw exceeds all thresholds → return the last bucket's value.
        return self.buckets[-1][1]

    def to_dict(self) -> dict:
        return {
            "market": self.market,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "n_samples": self.n_samples,
            "brier_score": self.brier_score,
            "ece": self.ece,
            "trained_at": self.trained_at.isoformat(),
            "buckets": [[t, c] for t, c in self.buckets],
        }

    @classmethod
    def from_dict(cls, payload: dict) -> IsotonicModel:
        return cls(
            market=payload["market"],
            timeframe=payload["timeframe"],
            direction=payload["direction"],
            n_samples=int(payload["n_samples"]),
            brier_score=float(payload["brier_score"]),
            ece=float(payload["ece"]),
            trained_at=datetime.fromisoformat(payload["trained_at"]),
            buckets=[(float(t), float(c)) for t, c in payload["buckets"]],
        )


def _train_isotonic(points: list[CalibrationPoint]) -> tuple[list[tuple[float, float]], float, float]:
    """Fit sklearn.isotonic and return (buckets, brier, ece).

    Returns an empty bucket list when there are too few samples; the
    caller should treat that as "no model trained" and fall back to
    the raw confidence.
    """
    if len(points) < 30:
        return [], 999.0, 999.0

    try:
        from sklearn.isotonic import IsotonicRegression

        preds = [p.predicted for p in points]
        actuals = [p.actual for p in points]

        ir = IsotonicRegression(out_of_bounds="clip", y_min=0.001, y_max=0.999)
        ir.fit(preds, actuals)

        # Build a compact bucket table by sampling thresholds.
        # We store 21 points (every 0.05) which is enough for
        # ~0.1% accuracy in the applied mapping.
        thresholds = [round(0.05 * i, 2) for i in range(1, 20)]
        buckets = [(t, float(ir.predict([t])[0])) for t in thresholds]

        # Brier: mean squared error of the *fitted* predictions vs actuals.
        fitted = ir.predict(preds)
        brier = sum((f - a) ** 2 for f, a in zip(fitted, actuals, strict=True)) / len(points)

        # ECE: bucket predictions into 10 deciles of predicted, compare
        # mean(predicted) vs mean(actual) per bucket.
        ece = 0.0
        for i in range(10):
            lo, hi = i * 0.1, (i + 1) * 0.1
            bucket_idx = [j for j, p in enumerate(preds) if lo <= p < hi or (i == 9 and p == 1.0)]
            if not bucket_idx:
                continue
            mean_pred = sum(preds[j] for j in bucket_idx) / len(bucket_idx)
            mean_actual = sum(actuals[j] for j in bucket_idx) / len(bucket_idx)
            ece += (len(bucket_idx) / len(points)) * abs(mean_pred - mean_actual)
        return buckets, round(brier, 4), round(ece, 4)
    except Exception as exc:
        logger.warning("isotonic fit failed: %s", exc)
        return [], 999.0, 999.0


async def _load_market_points(
    engine: AsyncEngine,
    *,
    market: str,
    timeframe: str,
    direction: str,
    window_days: int,
) -> list[CalibrationPoint]:
    """Pull (signal_confidence, direction_correct) pairs for one market."""
    cutoff = (datetime.now(UTC) - timedelta(days=window_days)).replace(tzinfo=None)
    q = text(
        """
        SELECT signal_confidence::float, direction_correct::int
        FROM signal_accuracy
        WHERE market = :market
          AND timeframe = :timeframe
          AND direction = :direction
          AND direction_correct IS NOT NULL
          AND signal_confidence IS NOT NULL
          AND signal_confidence BETWEEN 0.01 AND 0.99
          AND outcome_set_at IS NOT NULL
          AND outcome_set_at >= :cutoff
        ORDER BY outcome_set_at DESC
        LIMIT 5000
        """
    )
    async with engine.connect() as c:
        rows = (
            await c.execute(
                q,
                {
                    "market": market,
                    "timeframe": timeframe,
                    "direction": direction,
                    "cutoff": cutoff,
                },
            )
        ).fetchall()
    return [CalibrationPoint(predicted=float(p), actual=float(a)) for p, a in rows]


async def train_market(
    engine: AsyncEngine,
    *,
    market: str,
    timeframe: str = "daily",
    direction: str = "buy",
    window_days: int | None = None,
    min_samples: int = 100,
) -> IsotonicModel | None:
    """Train an isotonic model for one market and return it.

    Returns None when there are fewer than ``min_samples`` settled outcomes
    in the window — i.e. the market is too quiet to fit reliably.
    """
    window = window_days or int(os.environ.get("ISOTONIC_WINDOW_DAYS", "180"))
    points = await _load_market_points(
        engine,
        market=market,
        timeframe=timeframe,
        direction=direction,
        window_days=window,
    )
    if len(points) < min_samples:
        logger.info("skipping market=%s: only %d samples (need %d)", market, len(points), min_samples)
        return None

    buckets, brier, ece = _train_isotonic(points)
    if not buckets:
        return None
    return IsotonicModel(
        market=market,
        timeframe=timeframe,
        direction=direction,
        n_samples=len(points),
        brier_score=brier,
        ece=ece,
        trained_at=datetime.now(UTC),
        buckets=buckets,
    )


# ── Persistence ───────────────────────────────────────────────────

CALIBRATION_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS isotonic_calibration (
    id VARCHAR(150) PRIMARY KEY,
    market VARCHAR(50) NOT NULL,
    timeframe VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    n_samples INTEGER NOT NULL,
    brier_score FLOAT NOT NULL,
    ece FLOAT NOT NULL,
    buckets TEXT NOT NULL,
    trained_at TIMESTAMP NOT NULL
)
"""


def _model_id(market: str, timeframe: str, direction: str) -> str:
    return f"isotonic_{market}_{timeframe}_{direction}".replace(" ", "_").lower()


async def ensure_table(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(CALIBRATION_TABLE_DDL))


async def save_model(engine: AsyncEngine, model: IsotonicModel) -> None:
    await ensure_table(engine)
    q = text(
        """
        INSERT INTO isotonic_calibration (
            id, market, timeframe, direction, n_samples, brier_score, ece, buckets, trained_at
        ) VALUES (
            :id, :market, :timeframe, :direction, :n_samples, :brier, :ece, :buckets, :trained_at
        )
        ON CONFLICT (id) DO UPDATE SET
            n_samples = EXCLUDED.n_samples,
            brier_score = EXCLUDED.brier_score,
            ece = EXCLUDED.ece,
            buckets = EXCLUDED.buckets,
            trained_at = EXCLUDED.trained_at
        """
    )
    payload = model.to_dict()
    async with engine.begin() as conn:
        await conn.execute(
            q,
            {
                "id": _model_id(model.market, model.timeframe, model.direction),
                "market": model.market,
                "timeframe": model.timeframe,
                "direction": model.direction,
                "n_samples": model.n_samples,
                "brier": model.brier_score,
                "ece": model.ece,
                "buckets": json.dumps(payload["buckets"]),
                "trained_at": model.trained_at.replace(tzinfo=None),
            },
        )


async def load_model(
    engine: AsyncEngine,
    *,
    market: str,
    timeframe: str,
    direction: str,
) -> IsotonicModel | None:
    q = text("SELECT n_samples, brier_score, ece, buckets, trained_at FROM isotonic_calibration WHERE id = :id")
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                q,
                {
                    "id": _model_id(market, timeframe, direction),
                },
            )
        ).first()
    if not row:
        return None
    payload = {
        "market": market,
        "timeframe": timeframe,
        "direction": direction,
        "n_samples": int(row[0]),
        "brier_score": float(row[1]),
        "ece": float(row[2]),
        "trained_at": (row[4] if isinstance(row[4], datetime) else datetime.fromisoformat(str(row[4]))).isoformat(),
        "buckets": json.loads(row[3]),
    }
    return IsotonicModel.from_dict(payload)


# ── Bulk training ──────────────────────────────────────────────────


SUPPORTED_MARKETS = ("stock", "gold", "currency", "crypto", "commodity", "ime")


async def train_all_markets(
    engine: AsyncEngine,
    *,
    window_days: int | None = None,
) -> dict[str, IsotonicModel | None]:
    """Train one model per (market, "buy") and return the results.

    Returns a dict keyed by market. ``None`` means the market was
    skipped (insufficient samples or fit failure).
    """
    results: dict[str, IsotonicModel | None] = {}
    for market in SUPPORTED_MARKETS:
        try:
            model = await train_market(engine, market=market, window_days=window_days)
            if model is not None:
                await save_model(engine, model)
            results[market] = model
        except Exception as exc:
            logger.warning("train failed for market=%s: %s", market, exc)
            results[market] = None
    return results


async def train_all_default() -> dict[str, IsotonicModel | None]:
    """Convenience: build the engine from ``DATABASE_URL`` and train all markets."""
    db = os.environ.get("DATABASE_URL")
    if not db:
        raise RuntimeError("DATABASE_URL not set")
    engine = create_async_engine(db)
    try:
        return await train_all_markets(engine)
    finally:
        await engine.dispose()
