"""Train per-regime Ridge weight optimizers for the dynamic 110-column method.

Reads the daily score snapshot (``screener_daily_scores.raw_scores``) together
with realised forward returns computed from ``brsapi_historical_daily`` and a
market-regime label per trading day derived from ``brsapi_index_values``.
For each regime (bull / bear / neutral) a Ridge regression is fitted with the
110+ score columns as features and the N-day forward return as target.  The
resulting coefficients are normalised (sum of absolute values = 1) and saved
as ``weights_bull.json`` / ``weights_bear.json`` / ``weights_neutral.json``.

These files are consumed by ``services/dynamic_weighting.py`` to blend the
static CANSLIM weights with regime-specific learned weights.

Bootstrap note: early snapshots may be computed with ``build_screener_scores.py
--date <past_day>`` using the *current* feature store (mild look-ahead), so the
first weights are provisional until genuine as-of snapshots accumulate.

Run::

    python ml/train_weight_optimizer.py                     # all available data
    python ml/train_weight_optimizer.py --horizon 10        # 10-day forward return
    python ml/train_weight_optimizer.py --min-samples 50    # min rows per regime
    python ml/train_weight_optimizer.py --output-dir ml_artifacts/weights
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.linear_model import Ridge

from core.database import get_session
from core.logging import get_logger

logger = get_logger(__name__)

REGIMES = ("bull", "bear", "neutral")
DEFAULT_INDEX_NAME = "شاخص کل"
WEIGHTS_PREFIX = "weights_"
WEIGHTS_SUFFIX = ".json"


# ── Regime helpers ──────────────────────────────────────────────────────


def assign_regime(index_returns: pd.Series, up_threshold: float = 0.02, down_threshold: float = -0.02) -> pd.Series:
    """Map a series of N-day index returns to regime labels.

    Returns a pd.Series with the same index: 'bull', 'bear' or 'neutral'.
    """
    labels = pd.Series("neutral", index=index_returns.index, dtype=object)
    labels[index_returns > up_threshold] = "bull"
    labels[index_returns < down_threshold] = "bear"
    return labels


def normalize_weights(coefs: pd.Series) -> dict[str, float]:
    """Normalise a coefficient Series so sum of absolute values == 1.

    Preserves the sign of each coefficient so the dynamic weighting layer can
    tell positive (rewarded) from negative (penalised) features.
    """
    total = coefs.abs().sum()
    if total <= 0 or pd.isna(total):
        return {k: 0.0 for k in coefs.index}
    return {k: float(v / total) for k, v in coefs.items()}


# ── WeightOptimizer ─────────────────────────────────────────────────────


class WeightOptimizer:
    """Fit per-regime Ridge weight vectors from the daily score snapshot."""

    def __init__(
        self,
        horizon: int = 10,
        min_samples: int = 30,
        alpha: float = 1.0,
        up_threshold: float = 0.02,
        down_threshold: float = -0.02,
        index_name: str = DEFAULT_INDEX_NAME,
    ) -> None:
        self.horizon = horizon
        self.min_samples = min_samples
        self.alpha = alpha
        self.up_threshold = up_threshold
        self.down_threshold = down_threshold
        self.index_name = index_name

    # ── Data loading (each returns a DataFrame) ──────────────────────────

    async def _load_scores(self) -> pd.DataFrame:
        """Load (trade_date, symbol, raw_scores JSONB) from screener_daily_scores."""
        async for session in get_session():
            from sqlalchemy import text

            rows = (
                await session.execute(
                    text(
                        "SELECT trade_date, symbol, raw_scores "
                        "FROM screener_daily_scores "
                        "WHERE raw_scores IS NOT NULL "
                        "ORDER BY trade_date"
                    )
                )
            ).fetchall()
            break

        records = []
        for r in rows:
            raw = r.raw_scores
            if not raw or not isinstance(raw, dict):
                continue
            rec = {"trade_date": r.trade_date, "symbol": r.symbol}
            rec.update(raw)
            records.append(rec)

        df = pd.DataFrame(records)
        if not df.empty and "trade_date" in df:
            df["trade_date"] = pd.to_datetime(df["trade_date"])
        return df

    async def _load_index(self) -> pd.DataFrame:
        """Load daily index values for the main TSE index."""
        async for session in get_session():
            from sqlalchemy import text

            rows = (
                await session.execute(
                    text(
                        "SELECT gregorian_date, index_value "
                        "FROM brsapi_index_values "
                        "WHERE gregorian_date IS NOT NULL AND index_value > 0 "
                        "AND name = :index_name "
                        "ORDER BY gregorian_date"
                    ),
                    {"index_name": self.index_name},
                )
            ).fetchall()
            break

        df = pd.DataFrame([{"date": r.gregorian_date, "index_value": r.index_value} for r in rows])
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.drop_duplicates(subset=["date"]).sort_values("date").set_index("date")
            df = df[~df.index.duplicated(keep="last")]
        return df

    async def _load_last_price_date(self) -> pd.Timestamp | None:
        """Return the latest ``gregorian_date`` present in price history.

        Used to cap the forward-return window so we never ask for a price
        beyond what actually exists, while still being generous enough for the
        sparse Tehran trading calendar.
        """
        async for session in get_session():
            from sqlalchemy import text

            val = (
                await session.execute(
                    text("SELECT max(gregorian_date) FROM brsapi_historical_daily "
                         "WHERE gregorian_date IS NOT NULL")
                )
            ).scalar()
            break
        return pd.Timestamp(val) if val is not None else None

    async def _load_forward_returns(
        self, start: pd.Timestamp | None = None, end: pd.Timestamp | None = None
    ) -> pd.DataFrame:
        """Compute horizon-day forward return per (symbol, gregorian_date).

        return[t] = close[t+horizon] / close[t] - 1, computed per symbol from
        ``brsapi_historical_daily``.  ``start``/``end`` bound the rows read
        from the (potentially ~9.4M-row) table so we only pull the window the
        score snapshot actually covers.
        """
        async for session in get_session():
            from sqlalchemy import text

            where = "gregorian_date IS NOT NULL AND price_close > 0"
            params: dict[str, Any] = {}
            if start is not None:
                where += " AND gregorian_date >= :start"
                params["start"] = start.date()
            if end is not None:
                where += " AND gregorian_date <= :end"
                params["end"] = end.date()

            rows = (
                await session.execute(
                    text(
                        "SELECT symbol, gregorian_date, price_close "
                        "FROM brsapi_historical_daily "
                        f"WHERE {where} "
                        "ORDER BY symbol, gregorian_date"
                    ),
                    params,
                )
            ).fetchall()
            break

        df = pd.DataFrame(
            [{"symbol": r.symbol, "date": r.gregorian_date, "close": r.price_close} for r in rows]
        )
        if df.empty:
            return df
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values(["symbol", "date"])

        def _fwd(g: pd.DataFrame) -> pd.Series:
            close = g["close"]
            fwd = close.shift(-self.horizon) / close - 1.0
            return fwd

        df["fwd_return"] = df.groupby("symbol", group_keys=False).apply(_fwd)
        out = df.dropna(subset=["fwd_return"])[["symbol", "date", "fwd_return"]]
        return out

    # ── Training ─────────────────────────────────────────────────────────

    async def train(self, output_dir: str | Path | None = None) -> dict[str, Any]:
        """Fit per-regime Ridge models and persist the weights JSON files.

        Returns a summary dict with per-regime metrics.
        """
        scores = await self._load_scores()
        index_df = await self._load_index()

        if scores.empty:
            logger.error("No screener_daily_scores rows — run scripts/build_screener_scores.py first")
            return {"status": "error", "reason": "no_scores"}
        if index_df.empty:
            logger.error("No brsapi_index_values rows available for regime labelling")
            return {"status": "error", "reason": "no_index"}

        # Bound the history read to the score window. The ``end`` bound must be
        # GENEROUS: the Tehran calendar is sparse (weekends + public holidays),
        # so the forward price ``horizon`` trading days ahead can fall far
        # beyond ``score_end + horizon*2`` calendar days. Use the actual latest
        # price date when it is earlier than the generous cap (avoids reading a
        # future window that has no data anyway).
        score_start = scores["trade_date"].min()
        score_end = scores["trade_date"].max()
        end_bound = score_end + pd.Timedelta(days=max(self.horizon * 7, 30))
        last_price_date = await self._load_last_price_date()
        if last_price_date is not None:
            end_bound = min(end_bound, last_price_date)
        returns = await self._load_forward_returns(
            start=score_start,
            end=end_bound,
        )
        if returns.empty:
            logger.error("No brsapi_historical_daily rows for forward returns")
            return {"status": "error", "reason": "no_returns"}

        # Regime per trading day from the index's N-day momentum.
        index_ret = index_df["index_value"].pct_change(self.horizon)
        regime_map = assign_regime(index_ret, self.up_threshold, self.down_threshold)

        merged = scores.merge(
            returns, left_on=["trade_date", "symbol"], right_on=["date", "symbol"], how="inner"
        )
        regime_raw = merged["trade_date"].map(regime_map)
        unmapped_frac = float(regime_raw.isna().mean())
        merged["regime"] = regime_raw.fillna("neutral")
        if unmapped_frac > 0.05:
            logger.warning(
                "%.1f%% of merged rows have no index regime (sparse index "
                "history) — they are labelled 'neutral'",
                unmapped_frac * 100,
            )

        feature_cols = [c for c in merged.columns if c not in {
            "trade_date", "symbol", "date", "fwd_return", "regime", "raw_scores",
        }]
        # The 110-column model embeds categorical / text fields (e.g.
        # 'رد_نمره', 'queue_status') that Ridge cannot consume — keep only
        # numeric columns as features.
        feature_cols = [
            c for c in feature_cols if pd.api.types.is_numeric_dtype(merged[c])
        ]
        logger.info("Using %d numeric score features across %d rows", len(feature_cols), len(merged))

        out_dir = Path(output_dir) if output_dir else Path("ml_artifacts") / "weights"
        out_dir.mkdir(parents=True, exist_ok=True)

        summary: dict[str, Any] = {
            "horizon": self.horizon,
            "alpha": self.alpha,
            "trained_at": datetime.now(UTC).isoformat(),
            "rows": len(merged),
            "n_features": len(feature_cols),
            "regimes": {},
            "files": {},
        }

        for regime in REGIMES:
            sub = merged[merged["regime"] == regime]
            if len(sub) < self.min_samples:
                logger.warning("Regime '%s': only %d rows (< %d) — skipped", regime, len(sub), self.min_samples)
                summary["regimes"][regime] = {"status": "skipped", "rows": int(len(sub))}
                continue

            X = sub[feature_cols].fillna(0.0).astype(float)
            y = sub["fwd_return"].astype(float)

            model = Ridge(alpha=self.alpha)
            model.fit(X, y)

            coefs = pd.Series(model.coef_, index=feature_cols)
            weights = normalize_weights(coefs)

            file_name = f"{WEIGHTS_PREFIX}{regime}{WEIGHTS_SUFFIX}"
            file_path = out_dir / file_name
            payload = {
                "regime": regime,
                "horizon": self.horizon,
                "alpha": self.alpha,
                "rows": int(len(sub)),
                "intercept": float(model.intercept_),
                "r2": float(model.score(X, y)),
                "n_features": len(feature_cols),
                "trained_at": datetime.now(UTC).isoformat(),
                "weights": weights,
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            logger.info("Saved %s (%d rows, R2=%.3f)", file_path, len(sub), payload["r2"])

            summary["regimes"][regime] = {
                "status": "ok",
                "rows": int(len(sub)),
                "r2": payload["r2"],
                "top_features": dict(
                    sorted(weights.items(), key=lambda kv: -abs(kv[1]))[:10]
                ),
            }
            summary["files"][regime] = str(file_path)

        fitted = [r for r in summary["regimes"].values() if r.get("status") == "ok"]
        if not fitted:
            summary["status"] = "insufficient_data"
            logger.warning("No regime had >= %d rows — no weights written", self.min_samples)
        else:
            summary["status"] = "ok"
        return summary

    # ── CLI ──────────────────────────────────────────────────────────────

    @classmethod
    async def from_args(cls, argv: list[str] | None = None) -> None:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--horizon", type=int, default=10, help="forward return horizon (days)")
        parser.add_argument("--min-samples", type=int, default=30, help="min rows per regime to fit")
        parser.add_argument("--alpha", type=float, default=1.0, help="Ridge regularisation alpha")
        parser.add_argument("--up-threshold", type=float, default=0.02, help="index return % for bull regime")
        parser.add_argument("--down-threshold", type=float, default=-0.02, help="index return % for bear regime")
        parser.add_argument("--output-dir", type=str, default=None, help="output directory for weights JSON")
        args = parser.parse_args(argv)

        opt = cls(
            horizon=args.horizon,
            min_samples=args.min_samples,
            alpha=args.alpha,
            up_threshold=args.up_threshold,
            down_threshold=args.down_threshold,
        )
        summary = await opt.train(output_dir=args.output_dir)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if summary.get("status") != "ok":
            raise SystemExit(1)


async def _main() -> None:
    try:
        await WeightOptimizer.from_args()
    finally:
        from core.database import close_database

        await close_database()


if __name__ == "__main__":
    asyncio.run(_main())
