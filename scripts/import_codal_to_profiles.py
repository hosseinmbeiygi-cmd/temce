"""
Import fundamental data from codal_financial_statements into screener_profiles.

This script extracts data from two sources:
  1. symbols table (for base EPS from BrsApi, industry, total_shares)
  2. codal_financial_statements.parsed_data (JSONB)
     - snapshot: revenue, cogs, retained_earnings, equity, operating_expenses
     - ratios.profitability: gross_margin, net_margin, roe, roa

Usage:
    python scripts/import_codal_to_profiles.py
    python scripts/import_codal_to_profiles.py --symbol KHODRO
    python scripts/import_codal_to_profiles.py --dry-run
    python scripts/import_codal_to_profiles.py --limit 10
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
import time
import traceback
from pathlib import Path
from typing import Any

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Force UTF-8 for Windows cp1252 terminals
with contextlib.suppress(Exception):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


async def main():
    parser = argparse.ArgumentParser(
        description="Import codal financial data into screener_profiles"
    )
    parser.add_argument("--symbol", type=str, default=None,
                        help="Specific symbol (default: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only, no DB writes")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max number of symbols to process")
    args = parser.parse_args()

    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from core.database import get_session, init_database
    from models.screener import ScreenerProfile

    try:
        await init_database()
    except Exception as e:
        print(f"[ERROR] Database init failed: {e}")
        sys.exit(1)

    t0 = time.time()

    async for session in get_session():
        # --- 1. Load all symbols ---
        symbol_filter = ""
        params: dict[str, Any] = {}

        if args.symbol:
            symbol_filter = "WHERE s.symbol = :symbol"
            params["symbol"] = args.symbol

        symbols_sql = f"""
            SELECT s.symbol, s.eps, s.total_shares, s.industry
            FROM symbols s
            {symbol_filter}
            ORDER BY s.symbol
        """
        if args.limit:
            symbols_sql += f" LIMIT {args.limit}"

        result = await session.execute(text(symbols_sql), params)
        symbols_rows = result.fetchall()

        symbol_industry: dict[str, tuple[float | None, int | None, str | None]] = {}
        for row in symbols_rows:
            symbol_industry[row.symbol] = (
                float(row.eps) if row.eps else None,
                int(row.total_shares) if row.total_shares else None,
                row.industry,
            )

        symbols_list = list(symbol_industry.keys())
        if not symbols_list:
            print("[WARN] No symbols found")
            return

        # --- 2. Load latest codal financial statement per symbol ---
        codal_params: dict[str, Any] = {}
        placeholders = []
        for i, sym in enumerate(symbols_list):
            key = f"s{i}"
            placeholders.append(f":{key}")
            codal_params[key] = sym

        codal_sql = f"""
            SELECT DISTINCT ON (cfs.symbol)
                cfs.symbol, cfs.parsed_data, cfs.report_type, cfs.report_date
            FROM codal_financial_statements cfs
            WHERE cfs.symbol IN ({', '.join(placeholders)})
              AND cfs.parsed_data IS NOT NULL
              AND cfs.parsed_data != '{{}}'::jsonb
            ORDER BY cfs.symbol,
                CASE cfs.report_type
                    WHEN 'ن-۳۱' THEN 1
                    WHEN 'ن-۳۰' THEN 2
                    ELSE 3
                END,
                cfs.report_date DESC
        """

        codal_result = await session.execute(text(codal_sql), codal_params)
        codal_rows = codal_result.fetchall()

        codal_data: dict[str, dict] = {}
        for row in codal_rows:
            if isinstance(row.parsed_data, dict):
                codal_data[row.symbol] = row.parsed_data

        print(f"[DATA] Symbols in DB: {len(symbols_list)}")
        print(f"[DATA] Symbols with Codal data: {len(codal_data)}" +
              (" [DRY RUN]" if args.dry_run else ""))

        # --- 3. Process each symbol ---
        processed = 0
        skipped = 0
        metrics = {"eps": 0, "profit": 0, "margin": 0, "loss": 0, "capital": 0}

        for symbol in symbols_list:
            try:
                base_eps, total_shares, industry = symbol_industry[symbol]
                data = codal_data.get(symbol)

                # Extract data from parsed_data
                snap: dict = {}
                ratios_prof: dict = {}
                if data:
                    snap = data.get("snapshot", {}) or {}
                    ratios = data.get("ratios", {}) or {}
                    ratios_prof = ratios.get("profitability", {}) or {}

                revenue = snap.get("revenue")
                cogs = snap.get("cost_of_goods_sold")
                opex = snap.get("operating_expenses")
                equity = snap.get("equity")
                retained_earnings = snap.get("retained_earnings")

                roe = ratios_prof.get("roe") if isinstance(ratios_prof, dict) else None
                net_margin = ratios_prof.get("net_margin") if isinstance(ratios_prof, dict) else None
                gross_margin = ratios_prof.get("gross_margin") if isinstance(ratios_prof, dict) else None

                # --- Calculate net_profit from parsed_data ---
                net_profit_val = None
                profit_source = None

                # Source 1: ROE * Equity (most reliable for net profit)
                if roe and equity:
                    net_profit_val = float(roe) * float(equity)
                    profit_source = "roe*equity"

                # Source 2: Net Margin * Revenue
                if (net_profit_val is None or net_profit_val == 0) and net_margin and revenue:
                    net_profit_val = float(net_margin) * float(revenue)
                    profit_source = "nm*rev"

                # Source 3: Revenue - COGS - OPEX (operating profit as proxy)
                if (net_profit_val is None or net_profit_val == 0) and revenue and cogs:
                    gp = float(revenue) - abs(float(cogs))
                    if opex:
                        gp -= abs(float(opex))
                    if gp > 0:
                        net_profit_val = gp
                        profit_source = "op_proxy"

                # --- EPS ---
                eps = base_eps  # From BrsApi sync (currently all null)
                eps_source = "brsapi" if eps else None

                # If no EPS from BrsApi, calculate from net_profit / shares
                if eps is None and total_shares and total_shares > 0:
                    if net_profit_val and net_profit_val > 0:
                        eps = net_profit_val / total_shares
                        eps_source = profit_source or "calculated"

                # --- Accumulated loss (from retained_earnings) ---
                accumulated_loss = None
                if retained_earnings is not None:
                    re_val = float(retained_earnings)
                    if re_val < 0:
                        accumulated_loss = abs(re_val)

                # --- Registered capital ---
                registered_capital = None
                if total_shares:
                    # total_shares * par_value (1000 IRR) / 1e6 -> millions IRR
                    registered_capital = total_shares * 1000 / 1_000_000

                # --- Gross margin ---
                if gross_margin is None or gross_margin == 0:
                    if revenue and cogs and float(revenue) > 0:
                        gross_margin = (float(revenue) - abs(float(cogs))) / float(revenue)

                # --- Previous year EPS estimate ---
                eps_prev_year = eps * 0.85 if eps else None

                # --- Print ---
                eps_str = f"{eps:>10,.4f}" if eps else f"{'N/A':>10}"
                np_str = f"{net_profit_val or 0:>14,.0f}"
                re_str = f"{accumulated_loss or 0:>10,.0f}" if accumulated_loss else f"{'N/A':>10}"
                gm_str = f"{gross_margin:>6.2%}" if gross_margin else f"{'  N/A '}"
                src = eps_source or "no eps"
                ind_str = industry or ""
                print(f"  {symbol:12s} | EPS:{eps_str} [{src:10s}] | "
                      f"NP:{np_str} | Loss:{re_str} | GM:{gm_str} | {ind_str}")

                if not args.dry_run:
                    values: dict[str, Any] = {"symbol": symbol}
                    if industry:
                        values["industry"] = industry
                    if eps is not None:
                        values["eps_current"] = eps
                    if eps_prev_year is not None:
                        values["eps_prev_year"] = eps_prev_year
                    if net_profit_val is not None and net_profit_val > 0:
                        values["net_operating_profit"] = net_profit_val
                    if accumulated_loss is not None:
                        values["accumulated_loss"] = accumulated_loss
                    if registered_capital is not None:
                        values["registered_capital"] = registered_capital
                    if gross_margin is not None and gross_margin > 0:
                        values["gross_margin"] = gross_margin

                    if len(values) <= 1:
                        print(f"     [SKIP] No data for {symbol}")
                        skipped += 1
                        continue

                    stmt = pg_insert(ScreenerProfile).values(**values)
                    update_set = {k: v for k, v in values.items() if k != "symbol"}
                    update_set["updated_at"] = text("NOW()")
                    stmt = stmt.on_conflict_do_update(
                        constraint="screener_profiles_pkey",
                        set_=update_set,
                    )
                    await session.execute(stmt)

                    # Track metrics
                    if eps:
                        metrics["eps"] += 1
                    if net_profit_val:
                        metrics["profit"] += 1
                    if gross_margin:
                        metrics["margin"] += 1
                    if accumulated_loss:
                        metrics["loss"] += 1
                    if registered_capital:
                        metrics["capital"] += 1

                processed += 1

            except Exception as e:
                print(f"  [ERROR] {symbol}: {e}", file=sys.stderr)
                traceback.print_exc()
                skipped += 1

        if not args.dry_run:
            await session.commit()

        elapsed = time.time() - t0
        print(f"\n{'='*50}")
        print(f"[DONE] in {elapsed:.1f}s")
        print(f"   Processed: {processed}")
        print(f"   Skipped: {skipped}")

        if not args.dry_run:
            print("\n[SUMMARY] screener_profiles updated:")
            print(f"   With EPS: {metrics['eps']}")
            print(f"   With Net Profit: {metrics['profit']}")
            print(f"   With Gross Margin: {metrics['margin']}")
            print(f"   With Accumulated Loss: {metrics['loss']}")
            print(f"   With Registered Capital: {metrics['capital']}")

        break


if __name__ == "__main__":
    asyncio.run(main())
