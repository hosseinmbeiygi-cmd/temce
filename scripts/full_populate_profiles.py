"""
Full Populate Screener Profiles
================================

Comprehensive bulk-population of screener_profiles from ALL available
database tables, using a single CTE-based UPDATE for maximum speed.

Data Source Priority:
  1. brsapi_symbol_snapshots  — EPS, PE, sector, shares, prices
  2. brsapi_symbol_details    — free_float_pct, sub_sector, group_pe_ratio
  3. brsapi_currency_prices   — USD rate (→ free_market_rate)
  4. daily_history            — trade_value averages + avg_50d_volume (last 50 days)
  5. daily_real_legal         — legal buy/sell 30d aggregates

Fillable columns (23 + 19 binary filters):
  ✅ = accurate source,  ⚠️ = estimate,  ❌ = needs external data
  1  symbol               ✅ brsapi_symbol_snapshots
  2  industry             ✅ brsapi_symbol_snapshots.sector
  3  sub_industry         ✅ brsapi_symbol_details.sub_sector
  4  free_float_shares    ✅ shares_count × free_float_pct ÷ 100
  5  eps_current          ✅ brsapi_symbol_snapshots.eps
  6  avg_50d_volume       ✅ daily_history (AVG last 50 trading days)
  7  eps_prev_year        ⚠️  eps × 0.85 (15% growth assumption)
  8  exchange_rate_base   ⚠️  28500 Rial/USD (fixed base)
  9  inflation_rate       ⚠️  35% (CBI avg 1403)
  10 net_operating_profit ⚠️  estimate from avg_daily_value × 0.003
  11 accumulated_loss     ❌  needs codal balance sheet
  12 registered_capital   ✅  shares_count × 1000 ÷ 1e9
  13 legal_reserve        ❌  needs codal
  14 gross_margin         ⚠️  20% default
  15 feedstock_price      ❌  industry-specific
  16 feedstock_change_pct ❌  news-based
  17 capital_increase_type ❌ codal
  18 capital_increase_pct  ❌ codal
  19 industry_pe          ✅ brsapi_symbol_details.group_pe_ratio
  20 bank_interest_rate   ⚠️  30%
  21 bond_rate            ❌  bond market data
  22 nima_rate            ⚠️  28500 (from NIMA system)
  23 free_market_rate     ⚠️  from brsapi_currency_prices.USD or 62000

  19 binary filters       ❌  all need manual / news / codal input

Usage:
    python scripts/full_populate_profiles.py
"""

from __future__ import annotations

import os
import sys
import time

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.logging import setup_logging

setup_logging()


def _p(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        safe = msg.encode("ascii", errors="replace").decode("ascii")
        print(safe)


async def run() -> None:
    from sqlalchemy import text

    from core.database import get_session

    def fmt(v: float) -> str:
        """Format a float value for display."""
        if v is None or v == 0:
            return "     -"
        if v >= 1e9:
            return f"{v/1e9:.1f}B"
        if v >= 1e6:
            return f"{v/1e6:.1f}M"
        if v >= 1e3:
            return f"{v/1e3:.1f}K"
        return f"{v:.2f}"

    t0 = time.monotonic()

    async for session in get_session():
        # ──────────────────────────────────────────────────────────
        # STEP 1: Fill core fields from brsapi_symbol_snapshots
        # ──────────────────────────────────────────────────────────
        _p("=" * 70)
        _p("STEP 1/6 — Core fields from brsapi_symbol_snapshots")
        _p("=" * 70)

        r = await session.execute(text("""
            UPDATE screener_profiles sp
            SET
                eps_current        = sub.eps,
                industry           = COALESCE(sp.industry, sub.sector),
                registered_capital = sub.capital,
                updated_at         = NOW()
            FROM (
                SELECT DISTINCT ON (s.symbol)
                    s.symbol, s.eps, s.sector,
                    CAST(s.shares_count AS BIGINT) * 1000.0 / 1e9 AS capital
                FROM brsapi_symbol_snapshots s
                WHERE s.symbol IS NOT NULL AND s.symbol != ''
                  AND s.eps IS NOT NULL AND s.eps > 0
                ORDER BY s.symbol, s.created_at DESC
            ) sub
            WHERE sp.symbol = sub.symbol
        """))
        _p(f"  EPS updated: {r.rowcount} rows")

        # ──────────────────────────────────────────────────────────
        # STEP 2: Free-float, sub-sector, group PE + PRICE/VOLUME from details
        # ──────────────────────────────────────────────────────────
        _p("=" * 70)
        _p("STEP 2/6 — Free-float / sub-sector / price/volume from brsapi_symbol_details")
        _p("=" * 70)

        r = await session.execute(text("""
            UPDATE screener_profiles sp
            SET
                free_float_shares    = sub.free_float,
                sub_industry         = sub.sub_sector,
                industry_pe          = COALESCE(sp.industry_pe, sub.group_pe),
                registered_capital   = COALESCE(sp.registered_capital, sub.capital),
                eps_current          = COALESCE(NULLIF(sp.eps_current, 0), sub.eps),
                current_price        = COALESCE(NULLIF(sp.current_price, 0), sub.price_last),
                price_change_pct     = sub.price_change_pct,
                today_volume         = CAST(sub.trade_volume AS BIGINT),
                avg_daily_value      = sub.trade_value,
                institutional_buy    = sub.buy_legal_volume,
                institutional_sell   = sub.sell_legal_volume,
                updated_at           = NOW()
            FROM (
                SELECT DISTINCT ON (d.symbol)
                    d.symbol,
                    CAST(COALESCE(d.shares_count, 0) *
                         COALESCE(d.free_float_pct, 20.0) / 100.0 AS BIGINT) AS free_float,
                    d.sub_sector,
                    d.group_pe_ratio AS group_pe,
                    d.eps,
                    COALESCE(d.shares_count, 0) * 1000.0 / 1e9 AS capital,
                    d.price_last,
                    d.price_last_change_pct AS price_change_pct,
                    d.trade_volume,
                    d.trade_value,
                    d.buy_legal_volume,
                    d.sell_legal_volume
                FROM brsapi_symbol_details d
                WHERE d.symbol IS NOT NULL AND d.symbol != ''
                ORDER BY d.symbol, d.updated_at DESC
            ) sub
            WHERE sp.symbol = sub.symbol
        """))
        _p(f"  Details + price/volume updated: {r.rowcount} rows")

        # ──────────────────────────────────────────────────────────
        # STEP 3: Currency rates from brsapi_currency_prices
        # ──────────────────────────────────────────────────────────
        _p("=" * 70)
        _p("STEP 3/6 — Currency rates from brsapi_currency_prices")
        _p("=" * 70)

        # Get latest USD price from brsapi_currency_prices
        r = await session.execute(text("""
            SELECT price FROM brsapi_currency_prices
            WHERE symbol IN ('USD', 'US Dollar', 'دلار آمریکا')
            ORDER BY created_at DESC
            LIMIT 1
        """))
        usd_row = r.fetchone()
        free_market_rate = float(usd_row[0]) if usd_row else 62000.0
        _p(f"  USD free-market rate: {free_market_rate:,.0f} Rial")

        # Also try brsapi_gold_currency_pro_prices for SANA/Gold coin rates
        r = await session.execute(text("""
            SELECT symbol, price FROM brsapi_gold_currency_pro_prices
            WHERE symbol IN ('SANA', 'GOLD_COIN', 'GOLD', 'EMAMI', 'BAHAR')
            ORDER BY created_at DESC LIMIT 5
        """))
        gold_rows = r.fetchall()
        if gold_rows:
            _p(f"  Gold/coin rates found: {len(gold_rows)} rows")
            for row in gold_rows:
                _p(f"    {row[0]}: {float(row[1]):,.0f}")

        # Update screener_profiles with exchange rates
        r = await session.execute(
            text("""
                UPDATE screener_profiles
                SET
                    nima_rate          = 28500,
                    exchange_rate_base = 28500,
                    free_market_rate   = :usd_rate,
                    updated_at         = NOW()
                -- Update all profiles regardless of current value
            """),
            {"usd_rate": free_market_rate},
        )
        _p(f"  Exchange rates updated: {r.rowcount} rows")

        # ──────────────────────────────────────────────────────────
        # STEP 4: Hardcoded macro defaults
        # ──────────────────────────────────────────────────────────
        _p("=" * 70)
        _p("STEP 4/6 — Macro-economic defaults")
        _p("=" * 70)

        r = await session.execute(text("""
            UPDATE screener_profiles
            SET
                inflation_rate     = COALESCE(NULLIF(inflation_rate, 0), 35.0),
                bank_interest_rate = COALESCE(NULLIF(bank_interest_rate, 0), 30.0),
                bond_rate          = COALESCE(NULLIF(bond_rate, 0), 28.0),
                updated_at         = NOW()
            WHERE inflation_rate IS NULL OR inflation_rate = 0
               OR bank_interest_rate IS NULL OR bank_interest_rate = 0
               OR bond_rate IS NULL OR bond_rate = 0
        """))
        _p(f"  Macro defaults set: {r.rowcount} rows")

        # ──────────────────────────────────────────────────────────
        # STEP 5: Profit estimates from daily_history
        # ──────────────────────────────────────────────────────────
        _p("=" * 70)
        _p("STEP 5/6 — Profit estimates from daily_history (30d avg)")
        _p("=" * 70)

        r = await session.execute(text("""
            WITH daily_avg AS (
                SELECT
                    s.symbol,
                    AVG(dh.trade_value)::DOUBLE PRECISION AS avg_value
                FROM daily_history dh
                JOIN symbols s ON s.id = dh.symbol_id
                WHERE s.symbol IS NOT NULL
                  AND dh.trade_value IS NOT NULL AND dh.trade_value > 0
                GROUP BY s.symbol
            )
            UPDATE screener_profiles sp
            SET
                net_operating_profit = ROUND(
                    CAST(GREATEST(
                        COALESCE(sp.net_operating_profit, 0),
                        COALESCE(da.avg_value, 0) * 0.003 / 1e9
                    ) AS NUMERIC), 4
                ),
                gross_margin         = COALESCE(NULLIF(sp.gross_margin, 0), 20.0),
                updated_at           = NOW()
            FROM daily_avg da
            WHERE sp.symbol = da.symbol
              AND da.avg_value > 0
        """))
        _p(f"  Profit estimates updated: {r.rowcount} rows")

        # ──────────────────────────────────────────────────────────
        # STEP 5.5: avg_50d_volume from daily_history (last 50 trading days)
        # ──────────────────────────────────────────────────────────
        _p("=" * 70)
        _p("STEP 5.5/7 — avg_50d_volume from daily_history (50-day avg)")
        _p("=" * 70)

        r = await session.execute(text("""
            WITH ranked AS (
                SELECT
                    s.symbol AS symbol,
                    dh.trade_volume,
                    ROW_NUMBER() OVER (
                        PARTITION BY s.symbol
                        ORDER BY dh.trade_date DESC
                    ) AS rn
                FROM daily_history dh
                JOIN symbols s ON s.id = dh.symbol_id
                WHERE dh.trade_volume IS NOT NULL AND dh.trade_volume > 0
            )
            UPDATE screener_profiles sp
            SET
                avg_50d_volume = sub.avg_vol,
                updated_at     = NOW()
            FROM (
                SELECT symbol, CAST(AVG(trade_volume) AS BIGINT) AS avg_vol
                FROM ranked
                WHERE rn <= 50
                GROUP BY symbol
            ) sub
            WHERE sp.symbol = sub.symbol
        """))
        _p(f"  avg_50d_volume updated: {r.rowcount} rows")

        # ──────────────────────────────────────────────────────────
        # STEP 6: Fill eps_prev_year (estimate: eps * 0.85)
        # ──────────────────────────────────────────────────────────
        _p("=" * 70)
        _p("STEP 6/7 — EPS previous year estimate")
        _p("=" * 70)

        r = await session.execute(text("""
            UPDATE screener_profiles
            SET
                eps_prev_year = ROUND(CAST(eps_current AS NUMERIC) * 0.85, 2),
                updated_at    = NOW()
            WHERE eps_current IS NOT NULL AND eps_current > 0
              AND (eps_prev_year IS NULL OR eps_prev_year = 0)
        """))
        _p(f"  EPS prev year estimated: {r.rowcount} rows")

        # ──────────────────────────────────────────────────────────
        # STEP 7: Auto-compute 8 binary filters (columns 77-84)
        # ──────────────────────────────────────────────────────────
        _p("=" * 70)
        _p("STEP 7/7 — Auto-compute binary filters (77-84) from formulas")
        _p("=" * 70)

        r = await session.execute(text("""
            UPDATE screener_profiles
            SET
                -- فیلتر ۷۷: نرخ رشد دلاری EPS > ۱۵٪
                -- (eps_current / eps_prev_year) - 1 > 0.15
                f77_dollar_eps_growth = CASE
                    WHEN eps_current IS NOT NULL AND eps_current > 0
                         AND eps_prev_year IS NOT NULL AND eps_prev_year > 0
                         AND (eps_current::NUMERIC / eps_prev_year::NUMERIC) - 1 > 0.15
                    THEN 1 ELSE 0
                END,

                -- فیلتر ۷۸: نرخ رشد واقعی EPS > ۱۵٪
                -- ((eps_current / eps_prev_year) - 1) - (inflation_rate / 100) > 0.15
                f78_real_eps_growth = CASE
                    WHEN eps_current IS NOT NULL AND eps_current > 0
                         AND eps_prev_year IS NOT NULL AND eps_prev_year > 0
                         AND inflation_rate IS NOT NULL
                         AND ((eps_current::NUMERIC / eps_prev_year::NUMERIC) - 1)
                             - (inflation_rate::NUMERIC / 100.0) > 0.15
                    THEN 1 ELSE 0
                END,

                -- فیلتر ۷۹: ضریب P/E < ۱.۲
                -- (قیمت / (EPS × ۴)) / P/E صنعت < 1.2
                f79_pe_ratio_ok = CASE
                    WHEN current_price IS NOT NULL AND current_price > 0
                         AND eps_current IS NOT NULL AND eps_current > 0
                         AND industry_pe IS NOT NULL AND industry_pe > 0
                         AND (current_price::NUMERIC / (eps_current::NUMERIC * 4))
                             / industry_pe::NUMERIC < 1.2
                    THEN 1 ELSE 0
                END,

                -- فیلتر ۸۰: بازده سهام > نرخ سود بانکی
                -- (EPS × ۴) / قیمت > bank_interest_rate / 100
                f80_yield_gt_bank = CASE
                    WHEN eps_current IS NOT NULL AND eps_current > 0
                         AND current_price IS NOT NULL AND current_price > 0
                         AND bank_interest_rate IS NOT NULL
                         AND ((eps_current::NUMERIC * 4) / current_price::NUMERIC)
                             > (bank_interest_rate::NUMERIC / 100.0)
                    THEN 1 ELSE 0
                END,

                -- فیلتر ۸۱: نسبت خرید خالص حقوقی > ۵٪ شناور
                -- (خرید حقوقی - فروش حقوقی) / سهام شناور > 0.05
                f81_inst_ratio_ok = CASE
                    WHEN institutional_buy IS NOT NULL
                         AND institutional_sell IS NOT NULL
                         AND free_float_shares IS NOT NULL AND free_float_shares > 0
                         AND (institutional_buy::NUMERIC - institutional_sell::NUMERIC)
                             / free_float_shares::NUMERIC > 0.05
                    THEN 1 ELSE 0
                END,

                -- فیلتر ۸۲: جهش حجمی > ۳ برابر میانگین
                -- حجم امروز > ۳ × avg_50d_volume (میانگین واقعی ۵۰ روزه از daily_history)
                -- fallback: اگر avg_50d_volume موجود نبود، از تقریب ارزش日均/قیمت استفاده کن
                f82_volume_spike = CASE
                    WHEN today_volume IS NOT NULL AND today_volume > 0
                         AND avg_50d_volume IS NOT NULL AND avg_50d_volume > 0
                         AND today_volume::NUMERIC > 3 * avg_50d_volume::NUMERIC
                    THEN 1
                    WHEN today_volume IS NOT NULL AND today_volume > 0
                         AND avg_daily_value IS NOT NULL AND avg_daily_value > 0
                         AND current_price IS NOT NULL AND current_price > 0
                         AND today_volume::NUMERIC > 3 * (avg_daily_value::NUMERIC / current_price::NUMERIC)
                    THEN 1 ELSE 0
                END,

                -- فیلتر ۸۳: نقدشوندگی > ۰.۵٪ شناور در روز
                -- ارزش معاملات / (سهام شناور × قیمت) > 0.005
                f83_liquidity_ok = CASE
                    WHEN avg_daily_value IS NOT NULL AND avg_daily_value > 0
                         AND free_float_shares IS NOT NULL AND free_float_shares > 0
                         AND current_price IS NOT NULL AND current_price > 0
                         AND avg_daily_value::NUMERIC
                             / (free_float_shares::NUMERIC * current_price::NUMERIC) > 0.005
                    THEN 1 ELSE 0
                END,

                -- فیلتر ۸۴: نسبت زیان انباشته به سرمایه < ۵۰٪
                -- زیان انباشته / سرمایه ثبت‌شده < 0.5
                f84_loss_ratio_ok = CASE
                    WHEN accumulated_loss IS NOT NULL AND accumulated_loss > 0
                         AND registered_capital IS NOT NULL AND registered_capital > 0
                         AND (accumulated_loss::NUMERIC / registered_capital::NUMERIC) < 0.5
                    THEN 1 ELSE 0
                END,

                updated_at = NOW()
        """))
        _p(f"  Binary filters computed: {r.rowcount} rows")

        # ── Commit all changes ──
        await session.commit()
        elapsed = time.monotonic() - t0

        # ──────────────────────────────────────────────────────────
        # COVERAGE REPORT
        # ──────────────────────────────────────────────────────────
        _p("\n" + "=" * 70)
        _p("📊 FINAL COVERAGE REPORT")
        _p("=" * 70)

        # Report each column coverage
        # String columns: check IS NOT NULL AND != ''
        # Numeric columns: check IS NOT NULL AND != 0
        columns_to_check: list[tuple[str, str, bool]] = [
            ("industry",              "صنعت",             False),  # False = text column
            ("sub_industry",          "زیرگروه صنعت",     False),
            ("free_float_shares",     "سهام شناور",       True),   # True = numeric
            ("eps_current",           "EPS جاری",         True),
            ("eps_prev_year",         "EPS سال قبل",      True),
            ("exchange_rate_base",    "نرخ ارز مبنا",     True),
            ("inflation_rate",        "نرخ تورم",         True),
            ("net_operating_profit",  "سود خالص عملیاتی", True),
            ("accumulated_loss",      "زیان انباشته",     True),
            ("registered_capital",    "سرمایه ثبت‌شده",   True),
            ("legal_reserve",         "ذخیره حقوقی",     True),
            ("gross_margin",          "حاشیه سود ناخالص", True),
            ("current_price",         "قیمت روز",         True),
            ("price_change_pct",      "تغییر قیمت",       True),
            ("today_volume",          "حجم امروز",        True),
            ("avg_50d_volume",        "میانگین حجم ۵۰ روزه", True),
            ("avg_daily_value",       "ارزش معاملات",     True),
            ("institutional_buy",     "خرید حقوقی",       True),
            ("institutional_sell",    "فروش حقوقی",       True),
            ("industry_pe",           "P/E صنعت",         True),
            ("bank_interest_rate",    "نرخ سود بانکی",    True),
            ("bond_rate",             "نرخ اوراق",        True),
            ("nima_rate",             "نرخ دلار نیما",    True),
            ("free_market_rate",      "نرخ دلار آزاد",    True),
        ]

        # Build a single query for all counts with COMMAS between expressions
        case_exprs = ",\n            ".join(
            # String columns use != '', numeric columns use != 0
            f'COUNT(*) FILTER (WHERE {col} IS NOT NULL' +
            (f' AND {col} != \'\')' if not is_num else f' AND {col} != 0)') +
            f' AS {col.replace(".","_")}_cnt'
            for col, _, is_num in columns_to_check
        )
        total_query = f"""
            SELECT
                COUNT(*) AS total,
                {case_exprs}
            FROM screener_profiles
        """
        r = await session.execute(text(total_query))
        row = dict(r.fetchone()._mapping)
        total = row.pop("total")

        _p(f"\nTotal profiles: {total}")
        _p(f"{'Column':<25} {'Status':<10} {'Count':>6} {'Pct':>6}")
        _p("-" * 50)

        filled_count = 0
        total_columns = 0
        for col, fa_name, _ in columns_to_check:
            cnt = row.get(f"{col.replace('.','_')}_cnt", 0) or 0
            pct = round(cnt / total * 100, 1) if total else 0
            status = "✅" if pct >= 95 else ("⚠️" if pct >= 50 else "❌")
            if status == "✅":
                filled_count += 1
            total_columns += 1
            _p(f"{fa_name:<25} {status:<10} {cnt:>6} ({pct:>5.1f}%)")

        # Binary filter columns (manual: 56-74)
        _p(f"\n{'Manual Binary Filters (56-74)':<30} {'Status':<10}")
        _p("-" * 40)
        filter_cols = [
            "ceo_change_success", "ceo_change_fail", "annual_meeting_near",
            "annual_meeting_passed", "capital_increase_cash", "capital_increase_reval",
            "price_liberation_news", "gov_support_news", "heavy_legal_case",
            "telegram_pump", "end_of_month", "pre_holiday", "political_tension",
            "political_relief", "feedstock_meeting", "big_ipo",
            "new_shareholder_capital", "positive_mgmt_news", "negative_mgmt_news",
        ]
        for col in filter_cols:
            r = await session.execute(
                text(f"SELECT COUNT(*) FROM screener_profiles WHERE {col} = 1")
            )
            active_cnt = r.scalar() or 0
            status = "⚠️" if active_cnt > 0 else "✅"
            _p(f"{col:<30} {status:<10} (active: {active_cnt})")

        # Auto-computed filters (77-84)
        _p(f"\n{'Auto-Computed Filters (77-84)':<30} {'Status':<10}")
        _p("-" * 40)
        auto_filters = [
            ("f77_dollar_eps_growth", "نرخ رشد دلاری EPS > ۱۵٪"),
            ("f78_real_eps_growth", "نرخ رشد واقعی EPS > ۱۵٪"),
            ("f79_pe_ratio_ok", "ضریب P/E < ۱.۲"),
            ("f80_yield_gt_bank", "بازده سهام > نرخ بانکی"),
            ("f81_inst_ratio_ok", "خرید خالص حقوقی > ۵٪ شناور"),
            ("f82_volume_spike", "جهش حجمی > ۳ برابر"),
            ("f83_liquidity_ok", "نقدشوندگی > ۰.۵٪"),
            ("f84_loss_ratio_ok", "نسبت زیان/سرمایه < ۵۰٪"),
        ]
        for col, fa_name in auto_filters:
            r = await session.execute(
                text(f"SELECT COUNT(*) FROM screener_profiles WHERE {col} = 1")
            )
            active_cnt = r.scalar() or 0
            pct = active_cnt / 1562 * 100
            status = "✅" if active_cnt > 0 else "❌"
            _p(f"{fa_name:<30} {status:<10} {active_cnt:>4} ({pct:>5.1f}%)")

        # Columns NOT filled (need external data)
        _p(f"\n{'❌ Columns NOT filled (need external data):':<50}")
        _p("-" * 50)
        missing = [
            "accumulated_loss     — نیاز به صورت‌های مالی کدال",
            "legal_reserve        — نیاز به صورت‌های مالی کدال",
            "feedstock_price      — نیاز به داده صنعت/اخبار",
            "feedstock_change_pct — نیاز به اخبار",
            "capital_increase_type — نیاز به کدال",
            "capital_increase_pct  — نیاز به کدال",
            "19 binary filters    — نیاز به اخبار/ورود دستی/کدال",
        ]
        for m in missing:
            _p(f"  • {m}")

        # Final summary
        _p(f"\n{'='*70}")
        _p(f"⏱  Total time: {elapsed:.2f}s")
        _p(f"📊 {filled_count}/{total_columns} data columns ≥95% filled ✅")
        _p(f"⚠️  {total_columns - filled_count} columns need external data")
        _p(f"{'='*70}")

        # Sample
        _p("\n📈 Sample symbols (top 5 by EPS):")
        r = await session.execute(text("""
            SELECT symbol, eps_current, industry, free_float_shares,
                   registered_capital, industry_pe, net_operating_profit
            FROM screener_profiles
            WHERE eps_current > 0
            ORDER BY eps_current DESC
            LIMIT 5
        """))
        for row in r:
            d = dict(row._mapping)
            _p(f"  {d['symbol']:<12s} EPS={d['eps_current']:>8.0f}  "
                f"FF={fmt(d['free_float_shares']):>8s}  "
                f"Cap={d['registered_capital']:>6.1f}B  "
                f"PE={d['industry_pe']:>5.1f}")

        break


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
