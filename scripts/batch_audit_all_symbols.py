"""Batch audit ALL symbols using CodalProfessionalAnalysisService."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import contextlib

import psycopg2

from services.codal_accounting_service import (
    _classify_item,
    _extract_last_value,
    list_available_symbols,
    list_reports,
    parse_report,
)
from services.codal_analysis.analysis_engine import analyze, build_snapshot
from services.codal_analysis.scoring import compute_health_score
from services.codal_analysis.service import CodalProfessionalAnalysisService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Database configuration from environment variables ──────────────
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "market")
DB_USER = os.getenv("DB_USER", "market")
DB_PASS = os.getenv("DB_PASSWORD", "")
DB = {"host": DB_HOST, "port": DB_PORT, "dbname": DB_NAME, "user": DB_USER, "password": DB_PASS}


def create_table(conn):
    cur = conn.cursor()
    sql = ("CREATE TABLE IF NOT EXISTS codal_audit_summary ("
           "id BIGSERIAL PRIMARY KEY, symbol VARCHAR(50) NOT NULL UNIQUE, "
           "company_name VARCHAR(200), report_type VARCHAR(20), report_date VARCHAR(20), "
           "revenue DOUBLE PRECISION, net_profit DOUBLE PRECISION, "
           "total_assets DOUBLE PRECISION, total_equity DOUBLE PRECISION, eps DOUBLE PRECISION, "
           "roe DOUBLE PRECISION, roa DOUBLE PRECISION, gross_margin DOUBLE PRECISION, "
           "net_margin DOUBLE PRECISION, current_ratio DOUBLE PRECISION, debt_to_equity DOUBLE PRECISION, "
           "asset_turnover DOUBLE PRECISION, revenue_growth DOUBLE PRECISION, net_profit_growth DOUBLE PRECISION, "
           "health_score DOUBLE PRECISION, health_classification VARCHAR(20), "
           "earnings_quality_score DOUBLE PRECISION, forensic_risk VARCHAR(20), "
           "going_concern_risk VARCHAR(20), materiality_planning DOUBLE PRECISION, "
           "materiality_performance DOUBLE PRECISION, top_audit_risks JSONB, "
           "total_reports INT DEFAULT 0, analysis_status VARCHAR(20), "
           "analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, full_results JSONB)")
    cur.execute(sql)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_as_symbol ON codal_audit_summary(symbol)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_as_health ON codal_audit_summary(health_classification)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_as_roe ON codal_audit_summary(roe)")
    conn.commit()
    logger.info("Table ready")


def completed_symbols(conn):
    cur = conn.cursor()
    cur.execute("SELECT symbol FROM codal_audit_summary")
    return {r[0] for r in cur.fetchall()}


def sf(v):
    if v is None:
        return None
    try:
        f = float(v)
        if f != f or abs(f) == float("inf"):
            return None
        return round(f, 6)
    except Exception:
        return None


def make_summary(symbol, results, rt, rd):
    s = results.get("snapshot", {})
    rp = results.get("ratios", {}).get("profitability", {})
    rl = results.get("ratios", {}).get("liquidity", {})
    rlv = results.get("ratios", {}).get("leverage", {})
    ra = results.get("ratios", {}).get("activity", {})
    h = results.get("horizontal", {})
    health = results.get("health_score", {})
    eq = results.get("earnings_quality", {})
    fore = results.get("forensic", {})
    gc = results.get("going_concern")
    mat = results.get("audit_materiality")
    risk = results.get("audit_risk")
    return {
        "symbol": symbol, "company_name": None, "report_type": rt, "report_date": rd,
        "revenue": sf(s.get("revenue")), "net_profit": sf(s.get("net_profit")),
        "total_assets": sf(s.get("total_assets")), "total_equity": sf(s.get("total_equity")),
        "eps": sf(s.get("eps")), "roe": sf(rp.get("roe")), "roa": sf(rp.get("roa")),
        "gross_margin": sf(rp.get("gross_margin")), "net_margin": sf(rp.get("net_margin")),
        "current_ratio": sf(rl.get("current_ratio")), "debt_to_equity": sf(rlv.get("debt_to_equity")),
        "asset_turnover": sf(ra.get("asset_turnover")),
        "revenue_growth": sf(h.get("revenue_growth")), "net_profit_growth": sf(h.get("net_profit_growth")),
        "health_score": sf(health.get("overall_score")), "health_classification": health.get("classification"),
        "earnings_quality_score": sf(eq.get("quality_score")), "forensic_risk": fore.get("overall_risk"),
        "going_concern_risk": gc.get("risk_level") if gc else None,
        "materiality_planning": sf((mat or {}).get("planning_materiality")),
        "materiality_performance": sf((mat or {}).get("performance_materiality")),
        "top_audit_risks": risk.get("top_risks", []) if risk else None,
        "total_reports": len(list_reports(symbol)),
        "analysis_status": results.get("analysis_status", "unknown"),
    }


COLS = [
    "symbol", "company_name", "report_type", "report_date",
    "revenue", "net_profit", "total_assets", "total_equity", "eps",
    "roe", "roa", "gross_margin", "net_margin",
    "current_ratio", "debt_to_equity", "asset_turnover",
    "revenue_growth", "net_profit_growth",
    "health_score", "health_classification",
    "earnings_quality_score", "forensic_risk",
    "going_concern_risk", "materiality_planning", "materiality_performance",
    "top_audit_risks", "total_reports", "analysis_status", "full_results",
]


def save(conn, row, full):
    cur = conn.cursor()
    row["full_results"] = json.dumps(full, ensure_ascii=False, default=str)
    # Save summary
    placeholders = ", ".join(["%(" + c + ")s" for c in COLS])
    updates = ", ".join([c + "=EXCLUDED." + c for c in COLS[2:] if c != "full_results"])
    sql = ("INSERT INTO codal_audit_summary (" + ", ".join(COLS) + ") VALUES (" + placeholders + ") "
           "ON CONFLICT (symbol) DO UPDATE SET " + updates + ", full_results=EXCLUDED.full_results, analyzed_at=CURRENT_TIMESTAMP")
    cur.execute(sql, row)
    # Save parsed data
    sym = row["symbol"]
    rt = row.get("report_type") or ""
    rd = row.get("report_date") or ""
    cid = "cfs_" + hashlib.md5((sym + ":" + rt + ":" + rd).encode(), usedforsecurity=False).hexdigest()[:16]
    pd = json.dumps(full, ensure_ascii=False, default=str)
    tc = len(full.get("snapshot", {}))
    batch = "batch_" + str(int(time.time()))
    with contextlib.suppress(Exception):
        cur.execute(
            "INSERT INTO codal_financial_statements "
            "(id,symbol,report_type,report_date,filename,file_path,title,parsed_data,table_count,row_count,import_batch,imported_at) "
            "VALUES (%s,%s,%s,%s,NULL,NULL,%s,%s,%s,0,%s,CURRENT_TIMESTAMP)",
            (cid, sym, rt or None, rd or None, "Batch audit - " + sym, pd, tc, batch),
        )


def classify_fs(symbol):
    reports = list_reports(symbol)
    if not reports:
        return {}, "", ""
    classified, seen = {}, set()
    lt, ld = reports[0].get("report_type", ""), reports[0].get("date", "")
    for rt in {r["report_type"] for r in reports if r["report_type"]}:
        tr = [r for r in reports if r["report_type"] == rt]
        if not tr:
            continue
        parsed = parse_report(tr[0]["filepath"])
        if not parsed or "error" in parsed:
            continue
        for table in parsed.get("tables", []):
            for item in table.get("items", []):
                label = item["label"]
                if label in seen:
                    continue
                cat = _classify_item(label)
                if cat:
                    seen.add(label)
                    val = _extract_last_value(item)
                    if val != 0 and (cat not in classified or abs(val) > abs(classified[cat])):
                        classified[cat] = val
    return classified, lt, ld


def run(limit=None, resume=True, target=None):
    t0 = time.time()
    conn = psycopg2.connect(**DB)
    create_table(conn)
    all_syms = [s["symbol"] for s in list_available_symbols()]
    logger.info("Found %d symbols", len(all_syms))
    done = completed_symbols(conn) if resume else set()
    if resume:
        logger.info("Resume: %d done", len(done))
    if target:
        all_syms = [s for s in all_syms if s == target]
    todo = [s for s in all_syms if s not in done]
    if limit:
        todo = todo[:limit]
    logger.info("To process: %d", len(todo))
    svc = CodalProfessionalAnalysisService()
    ok = fail = skip = 0
    errs = []
    for i, sym in enumerate(todo):
        try:
            logger.info("[%d/%d] %s", i + 1, len(todo), sym)
            results = svc.analyze_symbol(sym)
            if results.get("analysis_status") == "failed":
                cl, rt, rd = classify_fs(sym)
                if not cl:
                    skip += 1
                    continue
                snap = build_snapshot(cl, symbol=sym, period=rd)
                an = analyze(snap)
                hp = compute_health_score(an)
                results = {
                    "symbol": sym, "fiscal_period": rd, "analysis_status": "partial", "snapshot": cl,
                    "ratios": {
                        "profitability": dict(an.ratios.profitability),
                        "liquidity": dict(an.ratios.leverage),
                        "leverage": dict(an.ratios.leverage),
                        "activity": dict(an.ratios.activity),
                        "cash_flow": dict(an.ratios.cash_flow),
                    },
                    "horizontal": {"revenue_growth": an.horizontal.revenue_growth, "net_profit_growth": an.horizontal.net_profit_growth},
                    "vertical": {"pl_items": an.vertical.pl_items, "bs_items": an.vertical.bs_items},
                    "dupont": {"net_profit_margin": an.dupont.net_profit_margin, "asset_turnover": an.dupont.asset_turnover, "equity_multiplier": an.dupont.equity_multiplier, "roe_dupont": an.dupont.roe_dupont},
                    "earnings_quality": {"cash_conversion_ratio": an.earnings_quality.cash_conversion_ratio, "quality_score": an.earnings_quality.quality_score, "warnings": an.earnings_quality.warnings},
                    "health_score": {"overall_score": hp.overall_score, "classification": hp.classification, "financial_strength": hp.financial_strength, "earnings_quality_score": hp.earnings_quality, "liquidity_stability": hp.liquidity_stability, "leverage_risk": hp.leverage_risk, "profitability": hp.profitability},
                    "forensic": {"overall_risk": "unknown", "warnings": []},
                    "going_concern": None, "audit_risk": None, "audit_materiality": None,
                }
            reports = list_reports(sym)
            rt = reports[0].get("report_type", "") if reports else ""
            rd = reports[0].get("date", "") if reports else ""
            row = make_summary(sym, results, rt, rd)
            save(conn, row, results)
            conn.commit()
            ok += 1
            if (i + 1) % 50 == 0:
                logger.info("  >> %d/%d ok=%d fail=%d skip=%d", i + 1, len(todo), ok, fail, skip)
        except Exception as e:
            fail += 1
            errs.append(sym + ": " + str(e))
            logger.error("  FAIL %s: %s", sym, str(e)[:100])
            try:
                conn.rollback()
            except Exception:
                conn.close()
                conn = psycopg2.connect(**DB)
    elapsed = time.time() - t0
    logger.info("=" * 60)
    logger.info("DONE: %d processed, %d ok, %d fail, %d skip in %.0fs", len(todo), ok, fail, skip, elapsed)
    if errs:
        for e in errs[:10]:
            logger.info("  ERR: %s", e)
    cur = conn.cursor()
    cur.execute("SELECT health_classification, COUNT(*) FROM codal_audit_summary GROUP BY 1 ORDER BY 2 DESC")
    logger.info("Health distribution:")
    for r in cur.fetchall():
        logger.info("  %s: %d", r[0] or "NULL", r[1])
    cur.execute("SELECT COUNT(*) FROM codal_audit_summary")
    logger.info("codal_audit_summary: %d rows", cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM codal_financial_statements")
    logger.info("codal_financial_statements: %d rows", cur.fetchone()[0])
    conn.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--resume", action="store_true", default=True)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--symbol", type=str, default=None)
    a = p.parse_args()
    run(limit=a.limit, resume=a.resume, target=a.symbol)
