"""Normalize raw BRSAPI option snapshots into the canonical schema (OF6).

The raw ingestion pipeline writes to ``brsapi_option_snapshots`` (1 row per
contract per fetch cycle).  Three normalized tables were defined in
``models/option.py`` but had no writer; this job is that writer.

  option_contracts  — one row per unique contract (symbol); upserted on
                      each run so that field changes (name, sector) are picked up.
  option_snapshots  — one row per (contract_id, date); uses today's UTC date
                      and the latest fetched_at row for that symbol.

The job is idempotent: ``ON CONFLICT DO UPDATE`` for both tables.
Run daily after the BrsApi option sync (scheduler order: BrsApiOptionJob →
OptionsNormalizeJob).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import text

from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = logging.getLogger(__name__)


class OptionsNormalizeJob(BaseJob):
    """Sync brsapi_option_snapshots → option_contracts + option_snapshots."""

    async def execute(self, context: JobContext) -> JobResult:
        from jobs.definitions.gold_macro_jobs import _with_session

        async def run(session) -> JobResult:
            return await _normalize(session)

        return await _with_session(self._name, run)


async def _normalize(session) -> JobResult:
    today = datetime.now(timezone.utc).date().isoformat()

    # ── 1. Upsert option_contracts ────────────────────────────────────────────
    # Latest snapshot per symbol gives the most up-to-date contract metadata.
    upsert_contracts = text("""
        INSERT INTO option_contracts (
            symbol, underlying_symbol, option_type, strike_price,
            expiry_date, isin, contract_size, market,
            is_active, currency, style, settlement_mode, asset_class,
            created_at, updated_at
        )
        SELECT DISTINCT ON (symbol)
            symbol,
            COALESCE(underlying_symbol, ''),
            COALESCE(option_type, 'call'),
            COALESCE(strike_price, 0.0),
            CASE
                WHEN date_end IS NOT NULL AND date_end ~ '^\\d{4}-\\d{2}-\\d{2}$'
                THEN date_end::date
                ELSE CURRENT_DATE + COALESCE(days_remaining, 30)
            END,
            isin,
            COALESCE(contract_size, 1000),
            'tse',
            TRUE,
            'IRR',
            'european',
            'cash',
            'equity',
            NOW(),
            NOW()
        FROM brsapi_option_snapshots
        WHERE symbol IS NOT NULL
        ORDER BY symbol, fetched_at DESC NULLS LAST
        ON CONFLICT (symbol) DO UPDATE
            SET underlying_symbol  = EXCLUDED.underlying_symbol,
                option_type        = EXCLUDED.option_type,
                strike_price       = EXCLUDED.strike_price,
                expiry_date        = EXCLUDED.expiry_date,
                isin               = EXCLUDED.isin,
                contract_size      = EXCLUDED.contract_size,
                is_active          = TRUE,
                updated_at         = NOW()
    """)
    r_contracts = await session.execute(upsert_contracts)
    n_contracts = r_contracts.rowcount

    # ── 2. Upsert today's option_snapshots ───────────────────────────────────
    # Join the latest brsapi row per symbol with the just-upserted contracts.
    upsert_snapshots = text("""
        INSERT INTO option_snapshots (
            contract_id, date,
            open_price, high_price, low_price, close_price, last_price,
            volume, open_interest, bid_price, ask_price, implied_volatility,
            created_at, updated_at
        )
        SELECT
            oc.id,
            :today::date,
            COALESCE(snap.price_first, 0),
            COALESCE(snap.price_max, 0),
            COALESCE(snap.price_min, 0),
            COALESCE(snap.price_close, snap.price_last, 0),
            COALESCE(snap.price_last, 0),
            COALESCE(snap.trade_volume, 0),
            COALESCE(snap.open_interest, 0),
            snap.bid_price_1,
            snap.ask_price_1,
            NULL,
            NOW(),
            NOW()
        FROM (
            SELECT DISTINCT ON (symbol)
                symbol, price_first, price_max, price_min,
                price_close, price_last, trade_volume, open_interest,
                bid_price_1, ask_price_1
            FROM brsapi_option_snapshots
            WHERE symbol IS NOT NULL
            ORDER BY symbol, fetched_at DESC NULLS LAST
        ) snap
        JOIN option_contracts oc ON oc.symbol = snap.symbol
        ON CONFLICT (contract_id, date) DO UPDATE
            SET open_price       = EXCLUDED.open_price,
                high_price       = EXCLUDED.high_price,
                low_price        = EXCLUDED.low_price,
                close_price      = EXCLUDED.close_price,
                last_price       = EXCLUDED.last_price,
                volume           = EXCLUDED.volume,
                open_interest    = EXCLUDED.open_interest,
                bid_price        = EXCLUDED.bid_price,
                ask_price        = EXCLUDED.ask_price,
                updated_at       = NOW()
    """)
    r_snapshots = await session.execute(upsert_snapshots, {"today": today})
    n_snapshots = r_snapshots.rowcount

    await session.commit()

    # ── 3. OF4 quality check: flag options trading below intrinsic value ──────
    # Intrinsic: call = max(0, underlying - strike), put = max(0, strike - underlying).
    # We approximate underlying price from the most recent brsapi_symbol_snapshots
    # close for the underlying_symbol.  Rows without a matching underlying are skipped.
    below_intrinsic_query = text("""
        SELECT COUNT(*) AS n
        FROM option_snapshots os
        JOIN option_contracts oc ON oc.id = os.contract_id
        JOIN (
            SELECT DISTINCT ON (symbol)
                symbol, price_close
            FROM brsapi_symbol_snapshots
            WHERE price_close > 0
            ORDER BY symbol, time DESC NULLS LAST
        ) ul ON ul.symbol = oc.underlying_symbol
        WHERE os.date = :today::date
          AND os.last_price > 0
          AND (
              (oc.option_type = 'call' AND os.last_price < GREATEST(0, ul.price_close - oc.strike_price))
           OR (oc.option_type = 'put'  AND os.last_price < GREATEST(0, oc.strike_price - ul.price_close))
          )
    """)
    row = (await session.execute(below_intrinsic_query, {"today": today})).scalar_one_or_none()
    n_below = row or 0
    if n_below > 0:
        await session.execute(text("""
            INSERT INTO market_data_quality_events
                (source, instrument, severity, reason, details)
            VALUES ('OptionsNormalizeJob', 'option_snapshots', 'warning',
                    'below_intrinsic_value', :det::jsonb)
        """), {"det": f'{{"date":"{today}","count":{n_below}}}'})
        await session.commit()
        logger.warning("OptionsNormalizeJob: %d snapshots below intrinsic value on %s (OF4)", n_below, today)

    logger.info(
        "OptionsNormalizeJob: contracts=%d snapshots=%d below_intrinsic=%d date=%s",
        n_contracts, n_snapshots, n_below, today,
    )
    return JobResult.success_result(
        job_name="OptionsNormalizeJob",
        data={"contracts_upserted": n_contracts, "snapshots_upserted": n_snapshots, "below_intrinsic": n_below},
    )


__all__ = ["OptionsNormalizeJob"]
