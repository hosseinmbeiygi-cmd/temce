"""Deep database analysis: find visible and hidden problems across all tables.

Runs ~15 categories of checks (schema, indexes, PK/FK, date columns stored as
VARCHAR, data quality, orphans, freshness, dead tuples, hypertables, legacy
duplicates, dual-date backfill state) and writes a markdown report fragment to
``scripts/.db_deep_issues.md`` which ``generate_db_readme.py`` embeds into the
README database section.

Usage:
    python scripts/analyze_db_issues.py
"""
from __future__ import annotations

import datetime
import json
import os
import re
from collections import defaultdict
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / ".db_deep_issues.md"
URL = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")

FINDINGS: list[dict] = []  # {sev, cat, table, msg, sug}


def finding(sev: str, cat: str, table: str, msg: str, sug: str = "") -> None:
    FINDINGS.append({"sev": sev, "cat": cat, "table": table, "msg": msg, "sug": sug})


def run(cur, sql: str):
    cur.execute(sql)
    if cur.description is None:
        return []
    return cur.fetchall()


def main() -> None:
    conn = psycopg2.connect(URL, connect_timeout=10)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET statement_timeout = 20000")

    # ══ 1. schema: tables without PK / without indexes ════════════════════
    rows = run(cur, """
        SELECT c.relname FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_constraint pk ON pk.conrelid = c.oid AND pk.contype = 'p'
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
          AND pk.oid IS NULL AND c.relname NOT LIKE 'alembic_%'
        ORDER BY c.relname
    """)
    for (t,) in rows:
        finding("high", "schema", t, "جدول Primary Key ندارد", "برای کلید امن upsert/backfill، PK اضافه کنید")

    idx_rows = run(cur, """
        SELECT tablename, count(*) FROM pg_indexes
        WHERE schemaname = 'public' GROUP BY tablename ORDER BY 2
    """)
    idx_count = dict(idx_rows)
    est_rows = dict(run(cur, """
        SELECT c.relname, GREATEST(CASE WHEN s.n_live_tup::bigint > 0 THEN s.n_live_tup::bigint
             ELSE c.reltuples::bigint END, 0)
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_stat_user_tables s ON s.relname = c.relname AND s.schemaname = 'public'
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
    """))
    for t in est_rows:
        if t.startswith("alembic_") or t.startswith("_dual_t") or t == "dual_date_columns":
            continue
        nidx = idx_count.get(t, 0)
        if nidx == 0:
            finding("high", "schema", t, "هیچ ایندکسی ندارد (جستجو = full scan)",
                    "ایندکس روی ستون‌های فیلتر/join اضافه کنید")
        elif nidx == 1 and (est_rows[t] or 0) > 100_000:
            finding("medium", "schema", t, f"فقط ۱ ایندکس دارد اما ~{est_rows[t]:,} ردیف دارد",
                    "ایندکس روی ستون‌های پراستفاده اضافه کنید")

    # ══ 2. date-like columns stored as VARCHAR/TEXT ═══════════════════════
    # (the intentional dual-date columns are excluded: they are VARCHAR by design)
    INTENTIONAL_TEXT_DATES = {"shamsi_date", "gregorian_date", "jalali_date", "date_id", "report_date_jalali"}
    rows = run(cur, """
        SELECT table_name, column_name, data_type FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_name ~* '(^date|_date$|_time$|_begin$|_end$|_update$|_publish$|_send$|_delivery$|_settlement$|_trade$|_y$|_maturity$|_expiry$|_at$)'
          AND data_type IN ('character varying', 'text', 'character')
        ORDER BY table_name, column_name
    """)
    for t, c, dt in rows:
        if c in INTENTIONAL_TEXT_DATES:
            continue
        finding("medium", "dates", t, f"ستون تاریخ `{c}` با نوع `{dt}` ذخیره شده (باید DATE/TIMESTAMPTZ باشد)",
                "مهاجرت ستون به نوع زمانی + backfill")

    # ══ 3. legacy duplicates (brsapi_* live counterpart) ══════════════════
    all_tables = set(est_rows)
    for t in sorted(all_tables):
        if t.startswith("brsapi_") or t.startswith("alembic_") or t.startswith("_"):
            continue
        if f"brsapi_{t}" in all_tables:
            finding("high", "legacy", t,
                    f"نسخه قدیمی/تکراری است — `brsapi_{t}` زنده است (داده اینجا با نسخه زنده همگام نیست)",
                    "پس از تأیید، جدول قدیمی را drop کنید")

    # ══ 4. symbols reference-table quality ════════════════════════════════
    dup = run(cur, "SELECT symbol, count(*) FROM symbols GROUP BY symbol HAVING count(*) > 1")
    if dup:
        finding("critical", "data", "symbols",
                f"{len(dup)} نماد تکراری در جدول مرجع `symbols` (مثلاً {dup[0][0]})",
                "حذف تکراری‌ها + constraint یکتا روی symbol")
    else:
        finding("info", "data", "symbols", "نماد تکراری ندارد — constraint یکتا سالم است", "")
    null_name = run(cur, "SELECT count(*) FROM symbols WHERE name IS NULL OR btrim(name) = ''")
    if null_name and null_name[0][0]:
        finding("medium", "data", "symbols", f"{null_name[0][0]} نماد بدون نام دارند", "تکمیل از منبع مرجع")
    for col in ("isin",):
        nulls = run(cur, f"SELECT count(*) FROM symbols WHERE {col} IS NULL")[0][0]
        if nulls:
            finding("low", "data", "symbols", f"{nulls} نماد با {col} خالی دارند", "")

    # ══ 5. unique constraint coverage on ON CONFLICT targets ══════════════
    uniq_by_table = defaultdict(list)
    for t, indexdef in run(cur, "SELECT tablename, indexdef FROM pg_indexes WHERE schemaname = 'public'"):
        if "UNIQUE" in (indexdef or ""):
            uniq_by_table[t].append(indexdef)
    uniq_targets = {
        "symbols": "symbol", "brsapi_symbol_snapshots": "symbol,fetched_at",
        "brsapi_historical_daily": "symbol,date", "brsapi_intraday_trades": "symbol,date,time",
        "news_articles": "url", "codal_reports": "ins_id,report_type",
    }
    for t, desc in uniq_targets.items():
        if t not in est_rows:
            continue
        ok = any(desc.split(",")[0].strip() in (i or "") for i in uniq_by_table.get(t, []))
        if not ok:
            finding("medium", "schema", t, f"constraint یکتا روی `{desc}` ندارد (upsert با ON CONFLICT پرخطر است)",
                    "ایندکس یکتا اضافه کنید")    # ══ 6. orphan symbol references (semantic, no FK) ═════════════════════
    symbols_own_cols = {r[0] for r in run(cur, """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'symbols'
    """)}
    sym_cols = dict(run(cur, """
        SELECT table_name, string_agg(column_name, ',')
        FROM information_schema.columns
        WHERE table_schema = 'public' AND column_name IN ('symbol', 'ins_id', 'l18', 'symbol_code')
          AND table_name NOT IN ('symbols', 'brsapi_symbols')
        GROUP BY table_name
    """))
    # cross-market tables legitimately hold non-TSE symbols (BTC, XAUUSD, ...)
    CROSS_MARKET = {
        "gold_currency_prices", "commodity_prices", "commodity_certificates", "commodity_funds",
        "commodity_futures", "commodity_options", "commodity_trades", "funds", "etf_nav",
    }
    for t, cols in sorted(sym_cols.items()):
        if (est_rows.get(t) or 0) > 500_000:
            continue
        col = cols.split(",")[0]
        if col not in symbols_own_cols:
            finding("low", "orphan", t, f"ستون `{col}` در جدول مرجع `symbols` وجود ندارد — مقایسه ممکن نیست", "")
            continue
        try:
            bad = run(cur, f"""
                SELECT EXISTS (SELECT 1 FROM "{t}" x
                  WHERE x."{col}"::text IS NOT NULL AND btrim(x."{col}"::text) <> ''
                    AND NOT EXISTS (SELECT 1 FROM symbols s
                                    WHERE s."{col}"::text = x."{col}"::text) LIMIT 1)
            """)[0][0]
            if bad:
                sev = "low" if (t.startswith("brsapi_") or t in CROSS_MARKET) else "medium"
                finding(sev, "orphan", t, f"رجوع به `{col}` دارد که در جدول مرجع `symbols` نیست (ردیف یتیم)",
                        "پاکسازی ردیف‌های یتیم یا تکمیل symbols")
        except psycopg2.errors.QueryCanceled:
            finding("low", "orphan", t, f"بررسی یتیم‌های `{col}` به‌دلیل حجم/وقفه انجام نشد", "")    # ══ 7. invalid data: negative price ═══════════════════════════════════
    price_cols = dict(run(cur, """
        SELECT table_name, string_agg(column_name, ',')
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_name ~* '(^|_)(price|last_price|close|nav)$'
          AND data_type IN ('numeric', 'double precision', 'real', 'integer', 'bigint', 'smallint')
        GROUP BY table_name
    """))
    for t, cols in sorted(price_cols.items()):
        if (est_rows.get(t) or 0) > 1_000_000:
            continue
        col = cols.split(",")[0]
        try:
            neg = run(cur, f'SELECT EXISTS (SELECT 1 FROM "{t}" WHERE "{col}" < 0 LIMIT 1)')[0][0]
            if neg:
                finding("high", "data", t, f"قیمت منفی در ستون `{col}` دارد",
                        "پاکسازی/رد رکوردهای نامعتبر در ingest")
        except psycopg2.errors.QueryCanceled:
            pass

    # ══ 8. freshness: max date per time-series table ══════════════════════
    date_cols = dict(run(cur, """
        SELECT table_name, string_agg(column_name, ',' ORDER BY ordinal_position)
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND data_type IN ('date', 'timestamp with time zone', 'timestamp without time zone')
          AND column_name ~* '(date|time|publish|fetched|created|updated)'
        GROUP BY table_name
    """))
    ts_hint = {"trades", "quotes", "intraday_trades", "daily_history", "daily_real_legal",
               "candlesticks", "symbol_snapshots", "shareholders", "orderbooks",
               "brsapi_intraday_trades", "brsapi_historical_daily", "brsapi_symbol_snapshots",
               "brsapi_shareholder_records", "brsapi_candlesticks", "brsapi_commodity_prices",
               "brsapi_option_snapshots", "brsapi_nav_records", "news_articles", "codal_reports"}
    for t in sorted(ts_hint):
        cols = date_cols.get(t)
        if not cols:
            continue
        col = cols.split(",")[0]
        try:
            mx = run(cur, f'SELECT max("{col}") FROM "{t}"')[0][0]
            if mx is None:
                finding("info", "freshness", t, "جدول سری زمانی خالی است", "")
            else:
                d = mx.date() if hasattr(mx, "date") else mx
                days = (datetime.date.today() - d).days
                if days > 30:
                    finding("medium", "freshness", t, f"آخرین داده {days} روز پیش است ({d})",
                            "اجرای جاب سینک مربوطه")
        except psycopg2.errors.QueryCanceled:
            finding("low", "freshness", t, "محاسبه max تاریخ به‌دلیل نبود ایندکس/وقفه انجام نشد", "")

    # ══ 9. dead tuples / bloat ════════════════════════════════════════════
    rows = run(cur, """
        SELECT relname, n_dead_tup, n_live_tup, last_autovacuum, last_autoanalyze
        FROM pg_stat_user_tables WHERE n_dead_tup > 10000
        ORDER BY n_dead_tup DESC LIMIT 12
    """)
    for rname, dead, live, _vac, _anl in rows:
        pct = (dead / (live + dead) * 100) if (live + dead) else 0
        finding("medium", "bloat", rname,
                f"{dead:,} ردیف مرده (بلاوات ~{pct:.0f}٪)",
                "VACUUM (ANALYZE) یا autovacuum را تنظیم کنید")

    # ══ 10. hypertables / compression ═════════════════════════════════════
    try:
        hy = run(cur, """
            SELECT hypertable_name, num_dimensions, compression_enabled
            FROM timescaledb_information.hypertables ORDER BY hypertable_name
        """)
        hy_names = [h[0] for h in hy]
        finding("info", "infra", "-",
                f"{len(hy)} هایپرتیبل TimescaleDB: " + "، ".join(sorted(hy_names)[:12]) + (" و…" if len(hy) > 12 else ""), "")
        not_comp = [h[0] for h in hy if not h[2]]
        if not_comp:
            finding("medium", "infra", "-",
                    f"{len(not_comp)} هایپرتیبل بدون فشرده‌سازی: " + "، ".join(sorted(not_comp)[:8]),
                    "فعال‌سازی compression + retention policy")
    except Exception:
        finding("info", "infra", "-", "TimescaleDB هیپرتیبل ندارد یا پسوند موجود نیست", "")

    # ══ 11. duplicate-index heuristics (same leading column) ══════════════
    idx_lead = defaultdict(list)
    for t, indexdef in run(cur, "SELECT tablename, indexdef FROM pg_indexes WHERE schemaname = 'public'"):
        m = re.search(r"\((.*?)\)", (indexdef or "").replace('"', ""))
        if m:
            lead = m.group(1).split(",")[0].strip()
            idx_lead[(t, lead)].append(indexdef)
    for (t, lead), defs in sorted(idx_lead.items()):
        if len(defs) > 1:
            finding("low", "schema", t, f"{len(defs)} ایندکس با ستون اول یکسان `{lead}`",
                    "ادغام ایندکس‌ها")

    # ══ 12. dual-date backfill pending ════════════════════════════════════
    prog_file = ROOT / "scripts" / ".dual_dates_progress.json"
    if prog_file.exists():
        prog = json.loads(prog_file.read_text(encoding="utf-8"))
        pending = [t for t, v in prog.items() if v != "ok"]
        if pending:
            finding("medium", "dates", "-",
                    f"backfill تاریخ دوتایی برای {len(pending)} جدول هنوز کامل نشده",
                    "python scripts/backfill_dual_dates.py")

    conn.close()

    # ══ render markdown ═══════════════════════════════════════════════════
    sev_labels = {"critical": "🔴 بحرانی", "high": "🟠 بالا", "medium": "🟡 متوسط",
                  "low": "🔵 کم", "info": "⚪ اطلاعاتی"}
    order = ["critical", "high", "medium", "low", "info"]
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for f in FINDINGS:
        by_cat[f["cat"]].append(f)

    n_crit = sum(1 for f in FINDINGS if f["sev"] == "critical")
    n_high = sum(1 for f in FINDINGS if f["sev"] == "high")
    n_med = sum(1 for f in FINDINGS if f["sev"] == "medium")
    n_rest = len(FINDINGS) - n_crit - n_high - n_med
    lines = [
        "### تحلیل عمیق — مشکلات پیدا و ناپیدا",
        "",
        f"این گزارش با `python scripts/analyze_db_issues.py` تولید می‌شود — مجموع **{len(FINDINGS)} یافته**: "
        f"🔴 {n_crit} بحرانی، 🟠 {n_high} بالا، 🟡 {n_med} متوسط، 🔵/⚪ {n_rest} کم/اطلاعاتی.",
        "",
        "<details>",
        f"<summary>نمایش همه {len(FINDINGS)} یافته (کلیک کنید)</summary>",
        "",
        "| شدت | تعداد |",
        "|------|------:|",
        f"| 🔴 بحرانی | {n_crit} |",
        f"| 🟠 بالا | {n_high} |",
        f"| 🟡 متوسط | {n_med} |",
        f"| 🔵 کم / ⚪ اطلاعاتی | {n_rest} |",
        "",
    ]
    for cat in sorted(by_cat):
        items = sorted(by_cat[cat], key=lambda f: order.index(f["sev"]))
        lines.append(f"**{cat}:**")
        lines.append("")
        for f in items:
            sug = f" → *{f['sug']}*" if f.get("sug") else ""
            lines.append(f"- {sev_labels[f['sev']]} `{f['table']}`: {f['msg']}{sug}")
        lines.append("")
    OUT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"OK: {len(FINDINGS)} findings written to {OUT.name} "
          f"({n_crit} critical, {n_high} high, {n_med} medium)")


if __name__ == "__main__":
    main()
