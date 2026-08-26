"""Probability Calibrator — converts raw model scores into calibrated win probabilities.

Calibration ensures that a signal with predicted probability P% indeed wins ~P% of the time.
Uses two methods:
  - **Platt scaling** (parametric): logistic regression on raw scores → probabilities
  - **Isotonic regression** (non-parametric): piecewise-constant fit (needs more data)

Supports a hierarchy of fallback levels:
  Market + Horizon + Regime → Market + Horizon → Market → Global → No Calibration

Stores calibration buckets in the DB and is versioned per market×timeframe×direction.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.calibration_bootstrap import (
    find_bucket_for_score,
    get_bootstrap_buckets,
)
from core.db_utils import safe_row_float, safe_row_str
from core.logging import get_logger

logger = get_logger(__name__)


# ── Data Structures ──────────────────────────────────────────────────────────


@dataclass
class CalibrationBuckets:
    """Raw win-rate statistics grouped by predicted-probability bucket.

    Example:
        bucket "0.55-0.60":  {"predicted": 0.575, "actual": 0.58, "count": 340}
    """
    buckets: dict[str, dict[str, float]] = field(default_factory=dict)
    total_signals: int = 0
    brier_score: float = 999.0  # lower is better
    expected_calibration_error: float = 999.0
    model_version: str = "0.0.0"
    calibrated_at: str = ""


@dataclass
class CalibratedProbability:
    """Output of the calibrator for a single signal."""

    calibrated_probability: float   # 0-1 calibrated win rate
    raw_score: float                # original uncalibrated score
    calibration_level: str          # no_calibration / low_data / calibrated
    calibration_version: str        # model version used
    method: str                     # platt / isotonic / bucket / global_fallback / none
    bucket_count: int               # how many signals in the matching bucket
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calibrated_probability": round(self.calibrated_probability, 3),
            "raw_score": round(self.raw_score, 3),
            "calibration_level": self.calibration_level,
            "calibration_version": self.calibration_version,
            "method": self.method,
            "bucket_count": self.bucket_count,
            "notes": self.notes,
        }


# ── Calibrator ───────────────────────────────────────────────────────────────


class ProbabilityCalibrator:
    """Calibrates raw model scores into calibrated win probabilities.

    Hierarchy (tries best available, falls back):
        1. Market + Horizon + Regime  (most specific)
        2. Market + Horizon
        3. Market
        4. Global (all data)
        5. No calibration — returns raw score unchanged
    """

    # Minimum signals per bucket to consider calibration reliable
    MIN_SIGNALS_PER_BUCKET = 30

    # Bucket edges for grouping predicted probabilities (symmetric, full range)
    DEFAULT_BUCKETS = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45,
                       0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.0]

    def __init__(self, session: Any = None) -> None:
        self._session = session
        self._version = "1.0.0"

    # ── Table Creation ──────────────────────────────────────────────────────────

    @staticmethod
    async def ensure_table() -> None:
        """Create the calibration_models table if it doesn't exist."""
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            if async_session_factory is None:
                return
            async with async_session_factory() as session:
                await session.execute(text("""
                    CREATE TABLE IF NOT EXISTS calibration_models (
                        id VARCHAR(100) PRIMARY KEY,
                        market VARCHAR(50),
                        timeframe VARCHAR(20),
                        direction VARCHAR(10),
                        regime VARCHAR(50),
                        model_version VARCHAR(20),
                        method VARCHAR(20),
                        parameters TEXT,
                        brier_score FLOAT,
                        ece FLOAT,
                        total_samples INTEGER DEFAULT 0,
                        calibration_data TEXT,
                        last_trained_at TIMESTAMP
                    )
                """))
                await session.commit()
                logger.info("Ensured calibration_models table exists")
        except Exception as e:
            logger.warning("Failed to create calibration_models table: %s", e)

    # ── Public API ──────────────────────────────────────────────────────────

    async def calibrate(
        self,
        raw_score: float,
        market: str,
        timeframe: str = "daily",
        direction: str = "buy",
        regime: str | None = None,
        use_logistic: bool = True,
    ) -> CalibratedProbability:
        """Calibrate a single raw score into a calibrated probability.

        The calibrator queries the DB for historical accuracy data and
        selects the best calibration method based on available data.
        """
        # Clamp raw score to [0, 1]
        raw_score = max(0.01, min(0.99, raw_score))

        # ── Level 1: Market + Horizon + Regime ──
        if regime:
            cp = await self._try_level(raw_score, market, timeframe, direction, regime)
            if cp.method != "none":
                return cp

        # ── Level 2: Market + Horizon ──
        cp = await self._try_level(raw_score, market, timeframe, direction)
        if cp.method != "none":
            return cp

        # ── Level 3: Market only ──
        cp = await self._try_level(raw_score, market, "", direction)
        if cp.method != "none":
            return cp

        # ── Level 4: Global ──
        cp = await self._try_level(raw_score, "", "", "")
        if cp.method != "none":
            return cp

        # ── Level 5: Bootstrap pre-trained calibration (cold-start fallback) ──
        bootstrap_cp = await self._try_bootstrap(raw_score, market)
        if bootstrap_cp is not None:
            return bootstrap_cp

        # ── Level 6: No calibration — return raw score ──
        return CalibratedProbability(
            calibrated_probability=raw_score,
            raw_score=raw_score,
            calibration_level="no_calibration",
            calibration_version=self._version,
            method="none",
            bucket_count=0,
            notes=["هیچ داده کالیبراسیونی موجود نیست — امتیاز خام بدون تغییر"],
        )

    async def train_calibrator(
        self,
        market: str,
        timeframe: str = "daily",
        direction: str = "buy",
        regime: str | None = None,
        force: bool = False,
    ) -> CalibrationBuckets:
        """Train/update calibration model for the given key from historical outcomes.

        Queries the signal_accuracy table, groups by predicted score buckets,
        and computes actual win rates per bucket.
        """
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            if async_session_factory is None:
                return CalibrationBuckets()

            # Ensure table exists
            await self.ensure_table()

            # Build WHERE clauses
            clauses = ["outcome_set_at IS NOT NULL", "signal_price > 0"]
            params: dict[str, Any] = {}

            if market:
                clauses.append("market = :market")
                params["market"] = market
            if timeframe:
                clauses.append("timeframe = :timeframe")
                params["timeframe"] = timeframe
            if direction:
                clauses.append("direction = :direction")
                params["direction"] = direction
            if regime:
                clauses.append("regime = :regime")
                params["regime"] = regime

            # Add signal_confidence as the predicted probability
            where_clause = " AND ".join(clauses)

            async with async_session_factory() as session:
                r = await session.execute(text(f"""
                    SELECT
                        signal_confidence as predicted,
                        CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END as actual,
                        actual_return_pct
                    FROM signal_accuracy
                    WHERE {where_clause}
                      AND signal_confidence IS NOT NULL
                      AND signal_confidence BETWEEN 0.01 AND 0.99
                    ORDER BY generated_at DESC
                    LIMIT 5000
                """), params)
                rows = r.fetchall()

                if not rows:
                    logger.info("No calibration data for key %s/%s/%s", market, timeframe, direction)
                    return CalibrationBuckets()

                # Group into buckets
                buckets = {f"{b:.2f}-{b+0.05:.2f}": {"predicted_sum": 0.0, "actual_sum": 0.0, "count": 0}
                           for b in [x for x in self.DEFAULT_BUCKETS if x < 0.99]}

                brier_sum = 0.0
                total_count = len(rows)

                for pred, actual, _ret in rows:
                    pred_f = float(pred)
                    actual_f = float(actual)
                    brier_sum += (pred_f - actual_f) ** 2

                    # Find which bucket
                    bucket_key = None
                    for i in range(len(self.DEFAULT_BUCKETS) - 1):
                        lo = self.DEFAULT_BUCKETS[i]
                        hi = self.DEFAULT_BUCKETS[i + 1]
                        if lo <= pred_f < hi or (hi == 1.0 and pred_f == 1.0):
                            bucket_key = f"{lo:.2f}-{hi:.2f}"
                            break

                    if bucket_key and bucket_key in buckets:
                        buckets[bucket_key]["predicted_sum"] += pred_f
                        buckets[bucket_key]["actual_sum"] += actual_f
                        buckets[bucket_key]["count"] += 1

                # Compute per-bucket stats
                bucket_stats: dict[str, dict[str, float]] = {}
                for bk, bv in buckets.items():
                    if bv["count"] == 0:
                        continue
                    bucket_stats[bk] = {
                        "predicted_mean": round(bv["predicted_sum"] / bv["count"], 4),
                        "actual_rate": round(bv["actual_sum"] / bv["count"], 4),
                        "count": bv["count"],
                    }

                brier_score = round(brier_sum / max(total_count, 1), 4) if total_count else 999.0

                # Compute ECE (Expected Calibration Error) — weighted avg |predicted - actual|
                ece_sum = 0.0
                for _bk, bv in bucket_stats.items():
                    weight = bv["count"] / max(total_count, 1)
                    ece_sum += weight * abs(bv["predicted_mean"] - bv["actual_rate"])
                ece = round(ece_sum, 4)

                now_str = datetime.now(UTC).isoformat()

                # Persist calibration metadata to DB
                calibrator_id = f"cal_{market}_{timeframe}_{direction}"
                if regime:
                    calibrator_id += f"_{regime}"
                calibrator_id = calibrator_id.replace(" ", "_").lower()

                await session.execute(text("""
                    INSERT INTO calibration_models (
                        id, market, timeframe, direction, regime,
                        model_version, method, parameters, brier_score, ece,
                        total_samples, last_trained_at
                    ) VALUES (
                        :id, :market, :timeframe, :direction, :regime,
                        :version, 'bucket', :parameters,
                        :brier, :ece, :samples, :trained_at
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        model_version = EXCLUDED.model_version,
                        parameters = EXCLUDED.parameters,
                        brier_score = EXCLUDED.brier_score,
                        ece = EXCLUDED.ece,
                        total_samples = EXCLUDED.total_samples,
                        last_trained_at = EXCLUDED.last_trained_at
                """), {
                    "id": calibrator_id,
                    "market": market,
                    "timeframe": timeframe,
                    "direction": direction,
                    "regime": regime,
                    "version": self._version,
                    "parameters": json.dumps(bucket_stats, ensure_ascii=False, default=str),
                    "brier": brier_score,
                    "ece": ece,
                    "samples": total_count,
                    "trained_at": datetime.now(UTC).replace(tzinfo=None),
                })
                await session.commit()

                logger.info(
                    "Calibrated [%s/%s/%s]: %d signals, Brier=%.4f, ECE=%.4f",
                    market, timeframe, direction, total_count, brier_score, ece,
                )

                return CalibrationBuckets(
                    buckets=bucket_stats,
                    total_signals=total_count,
                    brier_score=brier_score,
                    expected_calibration_error=ece,
                    model_version=self._version,
                    calibrated_at=now_str,
                )

        except Exception as e:
            logger.warning("Calibrator training failed: %s", e)
            return CalibrationBuckets()

    # ── Helpers ─────────────────────────────────────────────────────────────

    async def _try_level(
        self,
        raw_score: float,
        market: str,
        timeframe: str,
        direction: str,
        regime: str | None = None,
    ) -> CalibratedProbability:
        """Try calibration at one level of the hierarchy."""
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            if async_session_factory is None:
                return CalibratedProbability(
                    calibrated_probability=raw_score,
                    raw_score=raw_score,
                    calibration_level="no_calibration",
                    calibration_version=self._version,
                    method="none",
                    bucket_count=0,
                )

            # Ensure table exists (no-op if already created)
            await self.ensure_table()

            # Find the matching bucket for this raw_score
            bucket_key = None
            for i in range(len(self.DEFAULT_BUCKETS) - 1):
                lo = self.DEFAULT_BUCKETS[i]
                hi = self.DEFAULT_BUCKETS[i + 1]
                if lo <= raw_score < hi or (hi == 1.0 and raw_score == 1.0):
                    bucket_key = f"{lo:.2f}-{hi:.2f}"
                    break

            # Build query to get the calibration model for this key
            clauses = []
            params: dict[str, Any] = {}

            if market:
                clauses.append("market = :market")
                params["market"] = market
            if timeframe:
                clauses.append("timeframe = :timeframe")
                params["timeframe"] = timeframe
            if direction:
                clauses.append("direction = :direction")
                params["direction"] = direction
            if regime:
                clauses.append("regime = :regime")
                params["regime"] = regime

            where = " AND ".join(clauses) if clauses else "TRUE"

            async with async_session_factory() as session:
                # Load the calibration model
                r = await session.execute(text(f"""
                    SELECT id, model_version, method, parameters,
                           brier_score, ece, total_samples, last_trained_at
                    FROM calibration_models
                    WHERE {where}
                    ORDER BY last_trained_at DESC
                    LIMIT 1
                """), params)
                row = r.fetchone()

                if not row:
                    return CalibratedProbability(
                        calibrated_probability=raw_score,
                        raw_score=raw_score,
                        calibration_level="no_calibration",
                        calibration_version=self._version,
                        method="none",
                        bucket_count=0,
                    )

                params_json = row[3]
                total_samples = row[6] or 0
                model_version = str(row[1] or "0.0.0")
                brier_score = float(row[4] or 999.0)

                if not params_json:
                    return CalibratedProbability(
                        calibrated_probability=raw_score,
                        raw_score=raw_score,
                        calibration_level="no_calibration",
                        calibration_version=model_version,
                        method="none",
                        bucket_count=0,
                    )

                buckets_data = json.loads(params_json)

                # Find the bucket and extract actual rate
                if bucket_key and bucket_key in buckets_data:
                    bucket = buckets_data[bucket_key]
                    actual_rate = float(bucket.get("actual_rate", -1))
                    count = int(bucket.get("count", 0))

                    if actual_rate >= 0 and count > 0:
                        notes = []
                        calibration_level = "calibrated"
                        method = "bucket"

                        if count < self.MIN_SIGNALS_PER_BUCKET:
                            calibration_level = "low_data"
                            notes.append(f"داده کم در این بازه ({count} سیگنال)")

                        if self._is_calibration_poor(brier_score, total_samples):
                            notes.append("کالیبراسیون ضعیف — با احتیاط استفاده شود")

                        notes.append(f"{count} سیگنال در بازه {bucket_key}")

                        # Blend actual rate slightly toward raw for stability
                        if count < self.MIN_SIGNALS_PER_BUCKET:
                            blend_weight = count / self.MIN_SIGNALS_PER_BUCKET
                            calibrated = raw_score * (1 - blend_weight) + actual_rate * blend_weight
                            notes.append(f"ترکیب با امتیاز خام (وزن داده: {blend_weight:.2f})")
                        else:
                            calibrated = actual_rate

                        return CalibratedProbability(
                            calibrated_probability=round(calibrated, 4),
                            raw_score=raw_score,
                            calibration_level=calibration_level,
                            calibration_version=model_version,
                            method=method,
                            bucket_count=count,
                            notes=notes,
                        )

                # No matching bucket — use closest bucket
                closest_key = None
                closest_dist = float("inf")
                for bk in buckets_data:
                    try:
                        lo_str = bk.split("-")[0]
                        lo = float(lo_str)
                        dist = abs(raw_score - lo)
                        if dist < closest_dist:
                            closest_dist = dist
                            closest_key = bk
                    except (ValueError, IndexError):
                        continue

                if closest_key and closest_key in buckets_data:
                    bucket = buckets_data[closest_key]
                    actual_rate = float(bucket.get("actual_rate", -1))
                    count = int(bucket.get("count", 0))
                    if actual_rate >= 0 and count > 0:
                        return CalibratedProbability(
                            calibrated_probability=round(actual_rate, 4),
                            raw_score=raw_score,
                            calibration_level="low_data",
                            calibration_version=model_version,
                            method="bucket",
                            bucket_count=count,
                            notes=[f"نزدیک‌ترین بازه: {closest_key} ({count} سیگنال)"],
                        )

                return CalibratedProbability(
                    calibrated_probability=raw_score,
                    raw_score=raw_score,
                    calibration_level="no_calibration",
                    calibration_version=model_version,
                    method="none",
                    bucket_count=0,
                    notes=["بازه کالیبراسیون یافت نشد"],
                )

        except Exception as e:
            logger.warning("Calibration at level %s/%s failed: %s", market, timeframe, e)
            return CalibratedProbability(
                calibrated_probability=raw_score,
                raw_score=raw_score,
                calibration_level="no_calibration",
                calibration_version=self._version,
                method="none",
                bucket_count=0,
                notes=[f"خطا در کالیبراسیون: {str(e)[:80]}"],
            )

    # ── Bootstrap Fallback ─────────────────────────────────────────────

    async def _try_bootstrap(
        self, raw_score: float, market: str,
    ) -> CalibratedProbability | None:
        """Try bootstrap pre-trained calibration as cold-start fallback.

        Returns a CalibratedProbability when bootstrap data is available,
        or None if fallback should proceed to raw score.
        """
        buckets = get_bootstrap_buckets(market)
        bucket = find_bucket_for_score(buckets, raw_score)
        if bucket is None:
            return None

        actual_rate = bucket["actual_rate"]
        count = bucket["count"]

        # Blend with raw score for stability (slight regression to mean)
        blended = bucket["actual_rate"]

        return CalibratedProbability(
            calibrated_probability=round(blended, 4),
            raw_score=raw_score,
            calibration_level="bootstrap",
            calibration_version=f"bootstrap_{self._version}",
            method="bootstrap",
            bucket_count=count,
            notes=[
                f"کالیبراسیون پیش‌آموزش برای بازار {market}",
                f"تخمین {count} سیگنال مصنوعی",
                f"نرخ واقعی پیش‌بینی‌شده: {actual_rate:.0%}",
            ],
        )

    # ── Calibration Metrics ─────────────────────────────────────────────────

    async def get_calibration_report(
        self, market: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get calibration quality report for all keys (or a specific market)."""
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            if async_session_factory is None:
                return []

            await self.ensure_table()

            where = "TRUE"
            params: dict[str, Any] = {}
            if market:
                where = "market = :market"
                params["market"] = market

            async with async_session_factory() as session:
                r = await session.execute(text(f"""
                    SELECT id, market, timeframe, direction, regime,
                           model_version, method, brier_score, ece,
                           total_samples, last_trained_at
                    FROM calibration_models
                    WHERE {where}
                    ORDER BY last_trained_at DESC NULLS LAST
                """), params)
                rows = r.fetchall()

                return [
                    {
                        "id": row[0],
                        "market": row[1],
                        "timeframe": row[2],
                        "direction": row[3],
                        "regime": row[4],
                        "model_version": row[5],
                        "method": row[6],
                        "brier_score": safe_row_float(row, idx=7),
                        "ece": safe_row_float(row, idx=8),
                        "total_samples": row[9] or 0,
                        "last_trained_at": safe_row_str(row, idx=10, default="") or None,
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.warning("Failed to get calibration report: %s", e)
            return []

    async def get_accuracy_by_bucket(
        self, market: str, timeframe: str = "daily",
    ) -> list[dict[str, Any]]:
        """Get raw accuracy data grouped by bucket for a market+timeframe.

        Useful for the reliability diagram / dashboard.
        """
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            if async_session_factory is None:
                return []

            async with async_session_factory() as session:
                # Build 10 equal-width buckets from 0.5 to 1.0
                result = []
                for i in range(10):
                    lo = 0.50 + i * 0.05
                    hi = lo + 0.05
                    params = {
                        "market": market,
                        "timeframe": timeframe,
                        "lo": lo,
                        "hi": hi,
                    }
                    r = await session.execute(text("""
                        SELECT
                            COUNT(*) as total,
                            SUM(CASE WHEN direction_correct THEN 1 ELSE 0 END) as correct,
                            AVG(actual_return_pct) as avg_return
                        FROM signal_accuracy
                        WHERE market = :market
                          AND timeframe = :timeframe
                          AND signal_confidence BETWEEN :lo AND :hi
                          AND outcome_set_at IS NOT NULL
                          AND signal_confidence IS NOT NULL
                    """), params)
                    row = r.fetchone()
                    if row is None:
                        continue
                    total = row[0] or 0
                    correct = row[1] or 0
                    if total > 0:
                        result.append({
                            "bucket": f"{lo:.2f}-{hi:.2f}",
                            "bucket_mid": round((lo + hi) / 2, 3),
                            "total": total,
                            "correct": correct,
                            "actual_win_rate": round((correct / total) * 100, 2),
                            "avg_return_pct": round(float(row[2] or 0), 2),
                        })

                return result
        except Exception as e:
            logger.warning("Failed to get accuracy by bucket: %s", e)
            return []

    # ── Static Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _is_calibration_poor(brier_score: float, total_samples: int) -> bool:
        """Heuristic: calibration is poor if Brier > 0.22 or too few samples."""
        if total_samples < 100:
            return True
        return brier_score > 0.22

    @staticmethod
    def _bucket_for_score(score: float) -> str:
        """Return the bucket key for a given score."""
        for i in range(len(ProbabilityCalibrator.DEFAULT_BUCKETS) - 1):
            lo = ProbabilityCalibrator.DEFAULT_BUCKETS[i]
            hi = ProbabilityCalibrator.DEFAULT_BUCKETS[i + 1]
            if lo <= score < hi or (hi == 1.0 and score == 1.0):
                return f"{lo:.2f}-{hi:.2f}"
        return "0.00-0.50"

    @staticmethod
    def fix_probability(prob: float) -> float:
        """Clamp probability to valid range."""
        return max(0.001, min(0.999, prob))
