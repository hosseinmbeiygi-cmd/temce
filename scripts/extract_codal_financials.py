"""
استخراج اطلاعات مالی از codal_financial_statements.parsed_data
و ذخیره در codal_audit_summary
"""
import json
import sys

sys.path.insert(0, ".")
import asyncio
import time


async def main():
    from core.database import init_database
    await init_database()
    from sqlalchemy import text

    from core.database import async_session_factory

    t0 = time.time()

    async with async_session_factory() as s:
        r = await s.execute(text("""
            SELECT id, symbol, title, parsed_data, report_type
            FROM codal_financial_statements
            WHERE parsed_data IS NOT NULL
        """))
        rows = r.fetchall()
        print(f"Total financial statements: {len(rows)}")

        updated = 0
        errors = 0

        for row in rows:
            fid, symbol, title, parsed_data, report_type = row
            try:
                # parsed_data is already a dict
                data = parsed_data if isinstance(parsed_data, dict) else json.loads(parsed_data)

                snap = data.get("snapshot", {})
                ratios = data.get("ratios", {})
                dupont = data.get("dupont", {})
                forensic = data.get("forensic", {})
                health = data.get("health_score", 0)
                # health_score might be a dict with overall_score
                if isinstance(health, dict):
                    health = health.get("overall_score", 0)
                earnings_q = data.get("earnings_quality", {})

                # Snapshot
                revenue = snap.get("revenue")
                equity = snap.get("equity")
                cogs = snap.get("cost_of_goods_sold")
                opex = snap.get("operating_expenses")
                snap.get("depreciation")
                snap.get("retained_earnings")

                # Computed
                (revenue - cogs) if revenue and cogs else None
                operating_profit = (revenue - cogs - opex) if revenue and cogs and opex else None

                # Ratios
                prof = ratios.get("profitability", {})
                liq = ratios.get("liquidity", {})
                lev = ratios.get("leverage", {})
                act = ratios.get("activity", {})

                roe = dupont.get("roe") or prof.get("roe")
                roa = prof.get("roa")
                gross_margin = prof.get("gross_margin")
                net_margin = prof.get("net_margin")
                prof.get("operating_margin")
                current_ratio = liq.get("current_ratio")
                liq.get("quick_ratio")
                debt_to_equity = lev.get("debt_to_equity")
                lev.get("debt_to_assets")
                asset_turnover = act.get("asset_turnover")
                dupont.get("equity_multiplier")

                # Growth
                horizontal = data.get("horizontal", {})
                revenue_growth = None
                profit_growth = None
                if isinstance(horizontal, dict):
                    for key in ["revenue", "درآمد فروش", "فروش"]:
                        if key in horizontal:
                            h = horizontal[key]
                            if isinstance(h, dict):
                                revenue_growth = h.get("growth") or h.get("change_pct") or h.get("تغییر")
                            break
                    for key in ["net_profit", "سود خالص", "سود پس از کسر مالیات"]:
                        if key in horizontal:
                            h = horizontal[key]
                            if isinstance(h, dict):
                                profit_growth = h.get("growth") or h.get("change_pct") or h.get("تغییر")
                            break

                # Forensic
                forensic_risk_val = forensic.get("overall_risk", 0) if isinstance(forensic, dict) else 0
                forensic_risk = str(forensic_risk_val)
                warnings = forensic.get("warnings", []) if isinstance(forensic, dict) else []
                "; ".join(warnings) if isinstance(warnings, list) else str(warnings)

                # Earnings quality
                eq_score = earnings_q.get("score") if isinstance(earnings_q, dict) else None

                # Update codal_audit_summary
                try:
                    await s.execute(text("""
                        UPDATE codal_audit_summary SET
                            revenue = :revenue,
                            net_profit = :operating_profit,
                            total_assets = NULL,
                            total_equity = :equity,
                            roe = :roe,
                            roa = :roa,
                            gross_margin = :gross_margin,
                            net_margin = :net_margin,
                            current_ratio = :current_ratio,
                            debt_to_equity = :debt_to_equity,
                            asset_turnover = :asset_turnover,
                            revenue_growth = :revenue_growth,
                            net_profit_growth = :profit_growth,
                            health_score = :health_score,
                            forensic_risk = :forensic_risk,
                            earnings_quality_score = :eq_score,
                            analysis_status = 'extracted'
                        WHERE symbol = :symbol
                    """), {
                        "symbol": symbol,
                        "revenue": revenue,
                        "operating_profit": operating_profit,
                        "equity": equity,
                        "roe": roe,
                        "roa": roa,
                        "gross_margin": gross_margin,
                        "net_margin": net_margin,
                        "current_ratio": current_ratio,
                        "debt_to_equity": debt_to_equity,
                        "asset_turnover": asset_turnover,
                        "revenue_growth": revenue_growth,
                        "profit_growth": profit_growth,
                        "health_score": health if health else None,
                        "forensic_risk": forensic_risk,
                        "eq_score": eq_score,
                    })
                    updated += 1
                except Exception as e:
                    errors += 1
                    print(f"  Update error {symbol}: {e}")

            except Exception:
                errors += 1

        await s.commit()

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Updated: {updated}")
    print(f"  Errors: {errors}")

    # Show results
    async with async_session_factory() as s:
        r = await s.execute(text("""
            SELECT symbol, revenue, roe, roa, gross_margin, net_margin,
                   current_ratio, debt_to_equity, health_score, analysis_status
            FROM codal_audit_summary
            WHERE analysis_status = 'extracted'
            ORDER BY revenue DESC NULLS LAST
            LIMIT 10
        """))
        print("\n=== Top 10 by revenue ===")
        for row in r.fetchall():
            print(f"  {row[0]}: rev={row[1]:,.0f} roe={row[3]} margin={row[5]} health={row[8]}" if row[1] else f"  {row[0]}: no revenue")


if __name__ == "__main__":
    asyncio.run(main())
