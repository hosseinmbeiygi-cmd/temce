"""Generate the "🗄️ ساختار دیتابیس" section for README.md.

Reads live DB metadata (tables, columns, row estimates, PK/FK relations, the
dual_date_columns meta table and sample rows), scans the codebase for each
table's ORM model + code references (services / API / jobs / repositories /
scripts / tests) and detects common problems (empty, stale stats, legacy
brsapi_* duplicates, missing ORM model, no active consumer, NULL dual-date
columns). Splices a rich section into README.md:

    • mermaid ER diagram (grouped by domain)
    • per-table stats table
    • problems summary table
    • collapsible <details> block per table: problems + code refs + sample rows

Usage:
    python scripts/generate_db_readme.py
"""
from __future__ import annotations

import asyncio
import os
import re
from collections import Counter
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

try:
    from scripts._db import database_url_async

    DB_URL = database_url_async()
except Exception:  # pragma: no cover
    DB_URL = os.environ.get("DATABASE_URL")

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

SAMPLE_LIMIT = 2
SAMPLE_COLUMNS = 12
REF_CAP = 4

DOMAINS = [
    ("هسته / کاربران", lambda t: t in {"symbols", "users", "markets", "saved_filters", "portfolios", "portfolio_positions", "recommendations", "watchlists"}),
    ("کدال و صورت‌های مالی", lambda t: t.startswith("codal") or t.startswith("dim_") or t.startswith("fact_") or t.startswith("brsapi_codal") or t in {"import_document_files", "import_document_tables", "import_audit_log", "data_lineage", "analysis_reports", "account_mappings", "corporate_actions"}),
    ("بازار سهام (سری زمانی)", lambda t: t in {"trades", "quotes", "daily_history", "daily_real_legal", "intraday_trades", "candlesticks", "symbol_snapshots", "shareholders", "orderbook_snapshots", "orderbooks", "indicators", "etf_nav", "funds", "brsapi_nav_records"}),
    ("BrsApi — لحظه‌ای و مرجع", lambda t: t.startswith("brsapi_")),
    ("آپشن", lambda t: t.startswith("option") or t in {"open_interest_history", "volatility_surface", "brsapi_option_snapshots"}),
    ("بک‌تست و سیگنال", lambda t: t.startswith("backtest") or t.startswith("compare") or t.startswith("signal") or t.startswith("screener") or t in {"queue_analysis_results", "generated_strategies", "generation_batches", "calibration_models", "smart_money_analysis", "hidden_accumulation", "manipulation_detections", "gap_predictions", "fear_greed_index", "market_health_scores", "block_trades"}),
    ("ML و آموزش", lambda t: t.startswith("ml_") or t in {"calibration_models", "training_metrics", "feature_store", "model_predictions"}),
    ("Tabdeal", lambda t: t.startswith("tabdeal_")),
    ("کلان و اخبار", lambda t: t.startswith("macro") or t.startswith("news") or t.startswith("economic") or t in {"iran_fear_greed_index", "sentiment_scores"}),
    ("زیرساخت و عملیات", lambda t: t.startswith("job") or t.startswith("audit") or t.startswith("provider_health") or t.startswith("decision") or t.startswith("sync") or t.startswith("query_log") or t in {"alert_logs", "generation_batches", "orderbook_snapshots", "data_lineage", "import_audit_log"}),
]

# ── مسائل شناخته‌شده و مستندشده (حاصل تحلیل قبلی دیتابیس) ──────────────
KNOWN_ISSUES = {
    "codal_announcements": "باگ فعال: `services/codal_download_service.py` از این جدول (خالی) می‌خواند → دانلود ضمائم هرگز انجام نمی‌شود",
    "job_runs": "رکوردزنی جاب‌ها در `services/job_service.py` پیاده‌سازی نشده — جدول در عمل خالی می‌ماند",
    "markets": "هیچ SQL فعالی ندارد — مراجع کد صرفاً از نام ماژول/پکیج هستند",
    "etf_nav": "۱۲ ردیف یتیم بدون مصرف‌کننده — نسخه‌های زنده `brsapi_nav_records` و `funds` جایگزین‌اند",
    "candlesticks": "نسخه قدیمی — backfill به `brsapi_candlesticks` می‌نویسد",
    "symbol_snapshots": "نسخه قدیمی — `brsapi_symbol_snapshots` (۸۰۳K ردیف) زنده است",
    "option_contracts": "نسخه قدیمی — داده آپشن در `brsapi_option_snapshots` (۳۳۶K ردیف) است",
    "option_snapshots": "نسخه قدیمی — داده آپشن در `brsapi_option_snapshots` (۳۳۶K ردیف) است",
    "option_trades": "نسخه قدیمی — داده آپشن در `brsapi_option_snapshots` (۳۳۶K ردیف) است",
    "open_interest_history": "نسخه قدیمی — داده آپشن در `brsapi_option_snapshots` است",
    "volatility_surface": "نسخه قدیمی — داده آپشن در `brsapi_option_snapshots` است",
}


def _dim_fact_issue(t: str) -> str | None:
    if t.startswith("dim_") or t.startswith("fact_"):
        return "لایه ستاره‌ای کدال (dim/fact) هرگز پیاده‌سازی نشده — import فعال به `codal_financial_statements` می‌رود"
    return None


REF_DIRS = [
    ("brsapi/models/", "مدل"),
    ("models/", "مدل"),
    ("tabdeal/models", "مدل"),
    ("services/", "سرویس"),
    ("tabdeal/", "سرویس"),
    ("apps/", "API"),
    ("jobs/", "جاب"),
    ("repositories/", "ریپازیتوری"),
    ("scripts/", "اسکریپت"),
    ("tests/", "تست"),
]
CAT_ORDER = ["مدل", "سرویس", "API", "جاب", "ریپازیتوری", "اسکریپت", "تست", "سایر"]


def _domain(table: str) -> str:
    for name, pred in DOMAINS:
        if pred(table):
            return name
    return "سایر"


def _fmt(n: int | None) -> str:
    if n is None or n < 0:
        return "0"
    return f"{n:,}"


def _cell(v: object) -> str:
    """Format a DB value for a markdown table cell (truncated + escaped)."""
    if v is None:
        return "NULL"
    s = str(v).replace("\r", " ").replace("\n", "␤").replace("\t", " ")
    if len(s) > 30:
        s = s[:30] + "…"
    return s.replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;")


def _scan_code_refs(
    names: list[str],
) -> tuple[dict[str, list[tuple[str, str]]], dict[str, dict[str, list[tuple[str, int]]]]]:
    """Map each table to ORM model locations + code references grouped by category.

    Migration files and this generator itself are ignored (they would
    reference every table name). Word-boundary matching avoids matches inside
    longer identifiers (e.g. ``symbols`` inside ``brsapi_symbol_snapshots``).
    """
    models: dict[str, list[tuple[str, str]]] = {t: [] for t in names}
    refs: dict[str, dict[str, list[tuple[str, int]]]] = {t: {} for t in names}
    for f in ROOT.rglob("*.py"):
        rel = f.relative_to(ROOT).as_posix()
        if (
            "__pycache__" in rel
            or rel.startswith(("venv", ".venv", "codal_env", "migrations", "code_dump", "Redis", "node_modules", "claw-code"))
            or rel == "scripts/generate_db_readme.py"
        ):
            continue
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for t in names:
            if t not in txt:
                continue
            n = len(re.findall(rf"\b{re.escape(t)}\b", txt))
            if n == 0:
                continue
            cat = next((v for k, v in REF_DIRS if rel.startswith(k)), "سایر")
            # model class owning __tablename__ = "<t>"
            for q in (f'__tablename__ = "{t}"', f"__tablename__ = '{t}'"):
                pos = txt.find(q)
                if pos != -1:
                    prev = txt[:pos]
                    ms = list(re.finditer(r"class\s+(\w+)", prev))
                    cls = ms[-1].group(1) if ms else ""
                    if (rel, cls) not in models[t]:
                        models[t].append((rel, cls))
                    break
            refs[t].setdefault(cat, []).append((rel, n))
    for t in names:
        for cat in refs[t]:
            refs[t][cat] = sorted(refs[t][cat], key=lambda x: -x[1])[:REF_CAP]
    return models, refs


def _build_problems(
    t: str,
    meta: dict,
    tables: dict,
    models_by_table: dict[str, list[tuple[str, str]]],
    refs_by_table: dict[str, dict[str, list[tuple[str, int]]]],
) -> list[str]:
    probs: list[str] = []
    sample = meta.get("sample")
    cols, srows = (sample if sample else ([], []))
    est = meta["est"] or 0
    if sample is None:
        probs.append("خواندن نمونه داده ممکن نبود (خطای کوئری)")
    elif not srows:
        probs.append("جدول خالی است")
    if est == 0 and srows:
        probs.append("آمار جدول جمع نشده (reltuples = -1) — برای برآورد دقیق، ANALYZE اجرا کنید")
    if not t.startswith("brsapi_") and f"brsapi_{t}" in tables:
        probs.append(f"نسخه قدیمی است — جدول زنده `brsapi_{t}` جایگزین آن است")
    if not models_by_table.get(t):
        probs.append("بدون مدل ORM — فقط از طریق SQL خام یا اسکریپت استفاده می‌شود")
    rfs = refs_by_table.get(t, {})
    if not rfs:
        probs.append("هیچ مرجع کد فعالی ندارد — کاندیدای حذف/آرشیو")
    elif not {c for c in ("سرویس", "API", "جاب", "ریپازیتوری") if rfs.get(c)}:
        probs.append("مصرف‌کننده فعال (سرویس/API/جاب) ندارد — فقط اسکریپت/تست")
    src = meta.get("src")
    if src and srows and src in cols:
        idx = cols.index(src)
        if any(row[idx] is None for row in srows):
            probs.append(f"ستون منبع تاریخ `{src}` در نمونه NULL دارد")
    if srows and "gregorian_date" in cols and "shamsi_date" in cols:
        gi, si = cols.index("gregorian_date"), cols.index("shamsi_date")
        if any(row[gi] is None or row[si] is None for row in srows):
            probs.append("ستون‌های تاریخ دوتایی (gregorian/shamsi) در نمونه NULL دارند — backfill کامل نشده؟")
    curated = KNOWN_ISSUES.get(t) or _dim_fact_issue(t)
    if curated:
        probs.append(curated)
    seen: set[str] = set()
    out: list[str] = []
    for p in probs:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _render_details(
    name: str,
    meta: dict,
    probs: list[str],
    models_by_table: dict[str, list[tuple[str, str]]],
    refs_by_table: dict[str, dict[str, list[tuple[str, int]]]],
) -> str:
    est = meta["est"] or 0
    ncols = meta["ncols"]
    badge = f" ⚠️ {len(probs)} مشکل" if probs else ""

    parts: list[str] = []
    # ── مشکلات ──
    if probs:
        parts.append(f"**مشکلات ({len(probs)}):**")
        parts.extend(f"- {p}" for p in probs)
    else:
        parts.append("_مشکلی شناسایی نشد._")
    # ── مراجع کد ──
    parts.append("")
    parts.append("**مراجع کد:**")
    mods = models_by_table.get(name, [])
    if mods:
        for rel, cls in mods:
            parts.append(f"- مدل: `{rel}` → `{cls}`")
    else:
        parts.append("- مدل: _بدون مدل ORM_")
    rfs = refs_by_table.get(name, {})
    if rfs:
        for cat in CAT_ORDER:
            if cat not in rfs:
                continue
            if cat == "مدل" and mods:
                continue
            shown = "، ".join(f"`{rel}` ({n})" for rel, n in rfs[cat])
            parts.append(f"- {cat}: {shown}")
    else:
        parts.append("- مرجع کد فعال: _هیچ_")
    body = "\n".join(parts)

    sample = meta.get("sample")
    if sample is None:
        summary = f"<code>{name}</code> — نمونه در دسترس نیست{badge}"
        return f"<details>\n<summary>{summary}</summary>\n\n{body}\n\n_خواندن داده ممکن نبود._\n\n</details>"
    cols, srows = sample
    if not srows:
        summary = f"<code>{name}</code> — جدول خالی است ({ncols} ستون){badge}"
        return f"<details>\n<summary>{summary}</summary>\n\n{body}\n\n</details>"

    show_cols = cols[:SAMPLE_COLUMNS]
    more = len(cols) > SAMPLE_COLUMNS
    header = "| " + " | ".join(_cell(c) for c in show_cols) + (" | … |" if more else " |")
    sep = "|" + "|".join("---" for _ in show_cols) + ("|…|" if more else "|")
    sample_lines = [header, sep]
    for row in srows:
        vals = list(row)[:SAMPLE_COLUMNS]
        sample_lines.append("| " + " | ".join(_cell(v) for v in vals) + (" | … |" if more else " |"))
    ncols_note = f" (نمایش {len(show_cols)} ستون از {ncols})" if more else ""
    est_txt = _fmt(est) if est else (">0" if srows else "0")
    summary = f"<code>{name}</code> — ~{est_txt} ردیف، {ncols} ستون{ncols_note}{badge}"
    return f"<details>\n<summary>{summary}</summary>\n\n{body}\n\n**نمونه داده:**\n\n" + "\n".join(sample_lines) + "\n\n</details>"


async def main() -> None:
    engine = create_async_engine(DB_URL)
    async with engine.connect() as c:
        # tables: ncols + row estimate
        tables = {}
        r = await c.execute(
            text(
                "SELECT t.tablename, "
                "       GREATEST(CASE WHEN s.n_live_tup::bigint > 0 THEN s.n_live_tup::bigint "
                "            ELSE c.reltuples::bigint END, 0) AS est, "
                "       count(col.column_name)::int AS ncols "
                "FROM pg_tables t "
                "JOIN pg_class c ON c.relname = t.tablename AND c.relnamespace = 'public'::regnamespace "
                "LEFT JOIN pg_stat_user_tables s ON s.relname = t.tablename AND s.schemaname = 'public' "
                "LEFT JOIN information_schema.columns col ON col.table_name = t.tablename AND col.table_schema = 'public' "
                "WHERE t.schemaname = 'public' AND t.tablename NOT LIKE 'alembic_%' "
                "GROUP BY t.tablename, c.reltuples, s.n_live_tup"
            )
        )
        for name, est, ncols in r.fetchall():
            tables[name] = {"est": est, "ncols": ncols, "rels": set(), "src": None}

        # FK relations (unique, public only)
        r = await c.execute(
            text(
                "SELECT conrelid::regclass::text AS tbl, a.attname AS col, "
                "       confrelid::regclass::text AS reftbl, b.attname AS refcol "
                "FROM pg_constraint con "
                "JOIN unnest(con.conkey) WITH ORDINALITY k(attnum, ord) ON true "
                "JOIN unnest(con.confkey) WITH ORDINALITY f(attnum, ord) ON f.ord = k.ord "
                "JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum "
                "JOIN pg_attribute b ON b.attrelid = con.confrelid AND b.attnum = f.attnum "
                "WHERE con.contype = 'f' "
                "  AND con.conrelid::regclass::text ~ '^[a-z_]+$' AND confrelid::regclass::text ~ '^[a-z_]+$' "
                "  AND con.conrelid::regclass::text NOT LIKE '\\_%' AND confrelid::regclass::text NOT LIKE '\\_%' "
                "ORDER BY 1, 2"
            )
        )
        seen = set()
        for tbl, col, reftbl, _refcol in r.fetchall():
            if tbl not in tables or reftbl not in tables:
                continue
            key = (tbl, col)
            if key in seen:
                continue
            seen.add(key)
            tables[tbl]["rels"].add(f"FK→{reftbl}")

        # semantic symbol link -> symbols
        r = await c.execute(
            text(
                "SELECT table_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND column_name IN ('symbol', 'ins_id', 'l18', 'symbol_code') "
                "GROUP BY table_name"
            )
        )
        for (name,) in r.fetchall():
            if name in tables and name != "symbols":
                tables[name]["rels"].add("symbol→symbols")

        # dual-date source (missing on DBs before migration 0025 → degrade gracefully)
        try:
            r = await c.execute(text("SELECT table_name, source_column FROM dual_date_columns"))
            for name, src in r.fetchall():
                if name in tables:
                    tables[name]["src"] = src
        except Exception:
            pass

        # sample rows (2 arbitrary rows per table, capped at 12 columns)
        for name in list(tables):
            try:
                rr = await c.execute(text(f'SELECT * FROM "{name}" LIMIT {SAMPLE_LIMIT}'))
                cols = list(rr.keys())
                srows = rr.fetchall()
                tables[name]["sample"] = (cols, srows)
            except Exception:
                tables[name]["sample"] = None

        # full symbol list (reference table for the whole platform)
        symbol_cols: list[str] = []
        symbols_list: list[tuple] = []
        try:
            rr = await c.execute(text("SELECT * FROM symbols ORDER BY symbol LIMIT 3000"))
            symbol_cols = list(rr.keys())
            symbols_list = rr.fetchall()
        except Exception:
            pass

    await engine.dispose()

    names = sorted(tables)
    models_by_table, refs_by_table = _scan_code_refs(names)

    ordered = sorted(tables.items(), key=lambda kv: (_domain(kv[0]), kv[0]))

    # ── mermaid ER diagram (hub tables + related, grouped) ──────────────
    hub_names = {"symbols", "users", "daily_history", "intraday_trades", "trades", "quotes",
                 "brsapi_intraday_trades", "brsapi_symbol_snapshots", "brsapi_historical_daily",
                 "brsapi_shareholder_records", "brsapi_codal_announcements", "codal_reports",
                 "brsapi_option_snapshots", "brsapi_nav_records", "funds", "backtest_runs",
                 "screener_profiles", "signals", "ml_models", "job_runs", "news_articles",
                 "macro_indicators", "tabdeal_quotes", "dim_company", "dim_date", "fact_financials"}
    rel_tables = set()
    for name, meta in tables.items():
        if meta["rels"]:
            rel_tables.add(name)
        for rel in meta["rels"]:
            if rel.startswith("FK→"):
                rel_tables.add(rel[3:])
    diagram_names = sorted(hub_names | rel_tables, key=lambda t: (_domain(t), t))

    lines = ["```mermaid", "erDiagram", '    %% --- نمودار ارتباط جدول‌های اصلی (خوشه‌بندی‌شده بر اساس دامنه) ---']
    for name in diagram_names:
        lines.append(f"    {name} {{}}")
    edges = []
    for name, meta in tables.items():
        for rel in sorted(meta["rels"]):
            if rel.startswith("FK→"):
                target = rel[3:]
                if name in diagram_names and target in diagram_names:
                    edges.append((name, target))
            elif rel == "symbol→symbols" and name in diagram_names and name != "symbols":
                edges.append((name, "symbols"))
    for src, dst in edges:
        lines.append(f"    {src} ||--o{{ {dst} : \"دارای رابطه\"")
    lines.append("```")
    diagram = "\n".join(lines)

    # ── stats table ─────────────────────────────────────────────────────
    rows = []
    problems_by_table: dict[str, list[str]] = {}
    prob_counter: Counter[str] = Counter()
    for name, meta in ordered:
        src = meta["src"] or "—"
        rels = "، ".join(sorted(meta["rels"])) if meta["rels"] else "—"
        est = meta["est"] or 0
        sample = meta.get("sample")
        srows = sample[1] if sample else []
        has_rows = bool(srows)
        est_txt = _fmt(est) if est else (">0" if has_rows else "0")
        rows.append(f"| `{name}` | {meta['ncols']} | ~{est_txt} | {src} | {rels} |")
        probs = _build_problems(name, meta, tables, models_by_table, refs_by_table)
        problems_by_table[name] = probs
        prob_counter.update(probs)

    total_rows = sum((m["est"] or 0) for m in tables.values())
    prob_rows = "\n".join(f"| {p} | {c} |" for p, c in prob_counter.most_common())

    # ── per-table details blocks ─────────────────────────────────────────
    sample_blocks = [
        _render_details(name, meta, problems_by_table[name], models_by_table, refs_by_table)
        for name, meta in ordered
    ]

    # ── deep analysis report (written by analyze_db_issues.py) ───────────
    deep_md = ""
    deep_file = ROOT / "scripts" / ".db_deep_issues.md"
    if deep_file.exists():
        deep_md = deep_file.read_text(encoding="utf-8").rstrip()

    # ── final comprehensive summary + action plan ────────────────────────
    n_empty = sum(1 for name, meta in ordered
                  if meta.get("sample") is not None and not meta["sample"][1])
    n_legacy = sum(1 for name, meta in ordered
                   if not name.startswith("brsapi_") and f"brsapi_{name}" in tables)
    n_no_model = sum(1 for name, meta in ordered if not models_by_table.get(name))
    n_no_refs = sum(1 for name, meta in ordered if not refs_by_table.get(name))
    n_stale = sum(1 for name, meta in ordered
                  if not (meta["est"] or 0) and meta.get("sample") and meta["sample"][1])
    summary_md = "\n".join([
        "### جمع‌بندی جامع و نقشه راه اصلاحات",
        "",
        f"سکوی داده شامل **{len(tables)} جدول** و حدود **~{_fmt(total_rows)} ردیف** است. از این میان "
        f"**{n_empty} جدول خالی**، **{n_legacy} جدول نسخه قدیمی** با جایگزین زنده `brsapi_*`، "
        f"**{n_no_model} جدول بدون مدل ORM** و **{n_no_refs} جدول بدون هیچ مرجع کد فعال** وجود دارد "
        f"(برای **{n_stale} جدول** آمار PostgreSQL جمع نشده و برآورد ردیف دقیق نیست).",
        "",
        "**نقشه راه اصلاحات (اولویت‌بندی‌شده):**",
        "",
        "| اولویت | اقدام | هدف |",
        "|--------|-------|-----|",
        "| **P0** | افزودن constraint یکتا برای upsert امن | `brsapi_historical_daily(symbol,date)`، `news_articles(url)`، `brsapi_intraday_trades(symbol,date,time)`، `codal_reports(ins_id,report_type)` |",
        "| **P0** | رفع باگ دانلود ضمائم کدال | `codal_announcements` خالی است؛ `codal_download_service.py` باید از `brsapi_codal_announcements` بخواند |",
        "| **P1** | مهاجرت ستون‌های تاریخ VARCHAR به نوع زمانی | حدود ۱۰۰ ستون در جدول‌های BrsApi و legacy (فهرست کامل در بخش «تحلیل عمیق») |",
        "| **P1** | تکمیل backfill تاریخ دوتایی + اجرای ANALYZE | `python scripts/backfill_dual_dates.py` سپس `ANALYZE` روی جدول‌های بدون آمار |",
        "| **P2** | ایندکس‌های مفقود و فشرده‌سازی هایپرتیبل‌ها | جدول‌های >۱۰۰K ردیف با ۱ ایندکس؛ فعال‌سازی compression روی هایپرتیبل‌ها |",
        "| **P2** | پاکسازی ردیف‌های یتیم نماد | جدول‌های TSE که به نمادهای ناموجود ارجاع می‌دهند |",
        "| **P3** | حذف جدول‌های قدیمی بعد از تأیید | `candlesticks`، `symbol_snapshots`، `option_*`، `intraday_trades` و… |",
        "| **P3** | حذف جدول‌های بدون مصرف‌کننده | جدول‌های بدون مرجع کد فعال (بخش «جزئیات هر جدول») |",
        "",
        "> برای به‌روزرسانی این گزارش: `python scripts/analyze_db_issues.py && python scripts/generate_db_readme.py`",
    ])

    # ── full symbol list subsection ──────────────────────────────────────
    symbols_md = ""
    if symbols_list:
        pref = [
            col for col in ("symbol", "name", "market_type", "asset_class", "industry", "isin")
            if col in symbol_cols
        ]
        show = pref or symbol_cols[:5]
        idxs = [symbol_cols.index(col) for col in show]
        header = "| " + " | ".join(_cell(col) for col in show) + " |"
        sep = "|" + "|".join("---" for _ in show) + "|"
        sym_lines = [header, sep]
        for row in symbols_list:
            sym_lines.append("| " + " | ".join(_cell(row[i]) for i in idxs) + " |")
        dist = ""
        if "market_type" in symbol_cols:
            mt_idx = symbol_cols.index("market_type")
            mt = Counter(str(row[mt_idx]) for row in symbols_list if row[mt_idx] is not None)
            dist = "توزیع بر اساس نوع بازار: " + "، ".join(
                f"{k} {v}" for k, v in mt.most_common()
            ) + "."
        symbols_md = "\n".join([
            "### لیست نمادها",
            "",
            f"همه **{len(symbols_list)} نماد** جدول مرجع `symbols` (مرجع `symbol`/`ins_id` برای کل سکو).",
            dist,
            "",
            "<details>",
            f"<summary>نمایش لیست کامل ({len(symbols_list)} نماد)</summary>",
            "",
            *sym_lines,
            "",
            "</details>",
        ])

    section = "\n".join([
        "## 🗄️ ساختار دیتابیس",
        "",
        f"سکوی داده روی **PostgreSQL 16 + TimescaleDB** اجرا می‌شود و در حال حاضر **{len(tables)} جدول** دارد",
        f"(تخمین کل ردیف‌ها: **~{_fmt(total_rows)}**). جدول‌های بزرگ سری‌زمانی با TimescaleDB به هایپرتیبل تبدیل شده‌اند.",
        "",
        "### نمودار ارتباط جدول‌ها",
        "",
        "نمودار زیر روابط **Foreign Key** و اتصال معنایی `symbol`/`ins_id` به جدول مرجع `symbols` را برای",
        "جدول‌های اصلی نشان می‌دهد (فقط جدول‌هایی که رابطه دارند در نمودار می‌آیند؛ لیست کامل در جدول زیر است):",
        "",
        diagram,
        "",
        "### آمار کامل جدول‌ها",
        "",
        "ستون‌ها: تعداد ستون هر جدول. ردیف: تخمین PostgreSQL (دقیق نیست؛ `>0` یعنی داده دارد ولی آمار جمع نشده).",
        "رابطه: Foreign Keyهای واقعی و اتصال معنایی به `symbols`.",
        "",
        "| جدول | ستون‌ها | ردیف (~) | منبع تاریخ دوتایی | رابطه با جدول‌های دیگر |",
        "|------|--------:|---------:|-------------------|------------------------|",
        *rows,
        "",
        "### خلاصه مشکلات جدول‌ها",
        "",
        "تعداد جدول‌هایی که هر نوع مشکل را دارند (هر جدول می‌تواند چند مشکل داشته باشد):",
        "",
        "| مشکل | تعداد جدول |",
        "|------|-----------:|",
        *prob_rows.splitlines(),
        "",
        deep_md,
        "",
        "### جزئیات هر جدول (مشکلات + مراجع کد + نمونه داده)",
        "",
        "برای هر جدول: مشکلات شناسایی‌شده، مدل ORM و فایل‌های کدی که از آن استفاده می‌کنند، و ۲ ردیف نمونه",
        "(با `LIMIT 2` و بدون `ORDER BY`؛ برای جدول‌های پهن حداکثر ۱۲ ستون اول). مراجع کد بر اساس شمارش",
        "نام جدول در فایل‌های پایتون (به‌جز migrations و همین اسکریپت) محاسبه شده است.",
        "",
        "\n\n".join(sample_blocks),
        "",
        symbols_md,
        "",
        "> **نکته مهم — ستون‌های تاریخ دوتایی:** هر جدول ستون‌های `gregorian_date date` و `shamsi_date varchar(10)` دارد.",
        "> منبع استخراج (مثلاً `trade_date`، `created_at` یا `fetched_at`) در جدول «منبع تاریخ دوتایی» آمده و مقدار آن",
        "> به‌صورت خودکار توسط trigger دیتابیس (`sync_dual_dates_fn`) در هر INSERT/UPDATE محاسبه می‌شود.",
        "> برای backfill داده‌های موجود: `python scripts/backfill_dual_dates.py`",
        "",
        summary_md,
        "",
        "---",
        "",
    ])

    # ── splice into README (replace the existing DB section) ─────────────
    content = README.read_text(encoding="utf-8")
    start = content.find("## 🗄️ ساختار دیتابیس")
    if start == -1:
        raise SystemExit("DB section marker not found in README")
    nxt = content.find("\n## ", start + 5)  # next top-level section
    if nxt == -1:
        nxt = len(content)
    new_content = content[:start] + section.rstrip() + "\n\n" + content[nxt:].lstrip("\n")
    README.write_text(new_content, encoding="utf-8")
    print(
        f"OK: replaced DB schema section ({len(rows)} tables, {len(prob_counter)} problem types, "
        f"diagram {len(diagram_names)} nodes) in README.md"
    )


if __name__ == "__main__":
    asyncio.run(main())
