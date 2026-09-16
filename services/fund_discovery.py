"""🔭 Fund Discovery & Coverage Engine (A1/A3/A4/A6/A8 سوپر-پرامپت).

Zero-Config Universe Auto-Discovery:
  ۱) واکشی Universe از Provider (BrsApi) — بدون هیچ لیست Hardcoded.
  ۲) تطبیق هویت کانونی (ISIN > national_id > symbol) + مدیریت Alias.
  ۳) تشخیص خودکار قابلیت‌ها (NAV/Portfolio/Quotes/Codal) از داده محلی.
  ۴) Upsert اتمیک + Idempotent + ممیزی در ``fund_ingestion_runs``.
  ۵) تولید KPIهای پوشش/Freshness برای UI و رتبه‌بندی.

منطق تشخیص قابلیت و تصمیم هویت «خالص» است و بدون DB تست می‌شود.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from services.fund_api_adapter import FundApiAdapter
from services.fund_identity import (
    canonical_fund_id_for_symbol,
    decide_identity,
    derive_fund_id,
    normalize_isin,
    normalize_symbol,
    register_alias,
    resolve_matches,
)

logger = get_logger(__name__)

# ── آستانه‌های Coverage (قابل تنظیم با env) ─────────────────────────────────
import os

MIN_NAV_COVERAGE_PCT = float(os.getenv("FUND_MIN_NAV_COVERAGE_PCT", "60"))
STALE_QUOTE_MINUTES = float(os.getenv("FUND_STALE_QUOTE_MINUTES", "60"))
NAV_WINDOW_DAYS = int(os.getenv("FUND_NAV_WINDOW_DAYS", "90"))


# ── منطق خالص (Pure / Testable) ──────────────────────────────────────────────


def detect_capabilities(
    *,
    fund_id: str,
    symbol: str,
    market: str,
    nav_symbols: set[str],
    nav_funds: set[str],
    quote_symbols: set[str],
    quote_funds: set[str],
    codal_symbols: set[str],
    portfolio_funds: set[str],
    holding_funds: set[str],
) -> dict[str, bool]:
    """تشخیص خودکار ماتریس قابلیت‌ها از منابع داده موجود (Pure)."""
    sym = normalize_symbol(symbol)
    is_etf = (market or "").lower() == "tse"
    return {
        "has_nav": sym in nav_symbols or fund_id in nav_funds,
        "has_market_quotes": is_etf and (sym in quote_symbols or fund_id in quote_funds),
        "has_codal_reports": sym in codal_symbols,
        "has_portfolio": fund_id in portfolio_funds or fund_id in holding_funds,
        "is_etf": is_etf,
    }


def merge_capabilities(existing: dict[str, Any] | None, detected: dict[str, bool]) -> dict[str, bool]:
    """ادغام Monotonic — قابلیت کشف‌شده هرگز به‌خاطر نبود موقت داده حذف نمی‌شود."""
    out = {k: bool((existing or {}).get(k)) for k in detected}
    for k, v in detected.items():
        out[k] = bool(out.get(k)) or bool(v)
    return out


def coverage_status(nav_coverage_pct: float, has_portfolio: bool, quote_age_min: float | None) -> str:
    """ok | partial | stale | missing (Pure)."""
    if nav_coverage_pct <= 0 and not has_portfolio:
        return "missing"
    if quote_age_min is not None and quote_age_min > STALE_QUOTE_MINUTES:
        return "stale"
    if nav_coverage_pct < MIN_NAV_COVERAGE_PCT:
        return "partial"
    return "ok"


def coverage_score(
    nav_coverage_pct: float, has_portfolio: bool, quote_age_min: float | None, aliases: int
) -> float:
    """امتیاز پوشش ۰-۱۰۰ برای اثرگذاری در رتبه‌بندی (Pure)."""
    nav_part = min(100.0, max(0.0, nav_coverage_pct)) * 0.5
    portfolio_part = 25.0 if has_portfolio else 0.0
    quote_part = 15.0 if (quote_age_min is not None and quote_age_min <= STALE_QUOTE_MINUTES) else 0.0
    alias_part = 10.0 if aliases > 0 else 0.0
    return round(nav_part + portfolio_part + quote_part + alias_part, 1)


# ── سرویس ────────────────────────────────────────────────────────────────────


@dataclass
class DiscoveryStats:
    discovered: int = 0
    created: int = 0
    updated: int = 0
    aliases_added: int = 0
    conflicts: int = 0
    quarantined: int = 0
    capabilities_snapshot: dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0
    run_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FundDiscoveryService:
    """کشف، ثبت و پایش کل Universe صندوق‌ها."""

    def __init__(
        self,
        session: AsyncSession,
        adapter: FundApiAdapter | None = None,
    ) -> None:
        self.session = session
        self.adapter = adapter or FundApiAdapter()

    # ── ۱) Discovery + Upsert ────────────────────────────────────────────

    async def discover(
        self,
        *,
        store_snapshot: bool = True,
        market: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Universe کامل را از Provider کشف و Idempotent ثبت می‌کند.

        خروجی: لیست رکوردهای Universe (سازگار با ``FundReadThroughService``).
        """
        t0 = time.time()
        run_id = await self._start_run("discovery")
        raw = await self.adapter.fetch_universe()
        if market:
            raw = [r for r in raw if (r.get("market") or "").lower() == market.lower()]
        if limit:
            raw = raw[:limit]

        sources = await self._load_detection_sources()
        stats = DiscoveryStats(discovered=len(raw))
        seen_funds: list[dict[str, Any]] = []

        for record in raw:
            try:
                enriched = await self._upsert_one(record, sources, stats)
                if enriched:
                    seen_funds.append(enriched)
            except Exception as exc:  # noqa: BLE001 — خطای یک صندوق کل اجرا را متوقف نمی‌کند
                stats.conflicts += 1
                logger.warning("Discovery record failed (%s): %s", record.get("symbol"), exc)
                await self._quarantine(
                    fund_id=None,
                    isin=record.get("isin"),
                    payload=record,
                    reason=f"خطای ثبت رکورد Discovery: {type(exc).__name__}",
                    rule="discovery_upsert_error",
                )

        if store_snapshot and seen_funds:
            await self._store_snapshot(seen_funds)

        # قابلیت‌ها → خلاصه آماری
        caps = (
            await self.session.execute(
                text(
                    """
                    SELECT
                        SUM(CASE WHEN has_nav THEN 1 ELSE 0 END),
                        SUM(CASE WHEN has_portfolio THEN 1 ELSE 0 END),
                        SUM(CASE WHEN has_market_quotes THEN 1 ELSE 0 END),
                        SUM(CASE WHEN has_codal_reports THEN 1 ELSE 0 END)
                    FROM fund_capabilities
                    """
                )
            )
        ).first()
        if caps:
            stats.capabilities_snapshot = {
                "has_nav": int(caps[0] or 0),
                "has_portfolio": int(caps[1] or 0),
                "has_market_quotes": int(caps[2] or 0),
                "has_codal_reports": int(caps[3] or 0),
            }
        stats.duration_ms = round((time.time() - t0) * 1000, 1)
        stats.run_id = run_id
        await self.session.commit()
        await self._finish_run(run_id, stats, status="success")
        logger.info(
            "Discovery done: %d discovered, %d created, %d updated, %d aliases, %d conflicts (%.0fms)",
            stats.discovered, stats.created, stats.updated, stats.aliases_added,
            stats.conflicts, stats.duration_ms,
        )
        return seen_funds

    async def _upsert_one(
        self,
        record: dict[str, Any],
        sources: dict[str, set[str]],
        stats: DiscoveryStats,
    ) -> dict[str, Any] | None:
        symbol = normalize_symbol(record.get("symbol"))
        if not symbol:
            return None
        isin = record.get("isin") or None
        national_id = record.get("national_id") or None
        market = (record.get("market") or "tse").lower()

        matches = await resolve_matches(
            self.session, symbol=symbol, isin=isin, national_id=national_id
        )
        decision = decide_identity(
            symbol=symbol, isin=isin, national_id=national_id, matches=matches
        )

        if decision.is_conflict:
            stats.conflicts += 1
            await self._quarantine(
                fund_id=matches.get("by_isin") or matches.get("by_alias"),
                isin=isin,
                payload=record,
                reason=decision.conflict_reason or "هویت متناقض",
                rule="identity_conflict",
            )
            return None

        now = datetime.utcnow()
        fund_type = record.get("fund_type_hint") or record.get("fund_type") or "سهامی"
        name = record.get("name") or symbol
        is_etf = market == "tse"

        if decision.action == "new" and not decision.fund_id:
            fund_id = derive_fund_id(
                symbol=symbol,
                market=market,
                existing_fund_id=await canonical_fund_id_for_symbol(self.session, symbol),
            )
            row = (
                await self.session.execute(
                    text(
                        """
                        INSERT INTO funds
                            (id, symbol, name, isin, national_id, fund_type, manager_name,
                             custodian_name, is_etf, trading_status, discovered_at,
                             last_synced_at, created_at, updated_at)
                        VALUES
                            (:id, :sym, :name, :isin, :nid, :ftype, :mgr, :cst,
                             :etf, 'active', :now, :now, :now, :now)
                        ON CONFLICT (symbol) DO UPDATE SET
                            name = EXCLUDED.name,
                            last_synced_at = EXCLUDED.last_synced_at,
                            updated_at = EXCLUDED.updated_at
                        RETURNING id
                        """
                    ),
                    {
                        "id": fund_id,
                        "sym": symbol,
                        "name": name,
                        "isin": normalize_isin(isin),
                        "nid": national_id,
                        "ftype": fund_type,
                        "mgr": record.get("manager_name"),
                        "cst": record.get("custodian_name"),
                        "etf": is_etf,
                        "now": now,
                    },
                )
            ).first()
            actual_id = row[0] if row else fund_id
            if actual_id == fund_id:
                stats.created += 1
            else:
                stats.updated += 1
            fund_id = actual_id
        else:
            fund_id = decision.fund_id or derive_fund_id(symbol=symbol, market=market)
            current = (
                await self.session.execute(
                    text("SELECT symbol FROM funds WHERE id = :fid"), {"fid": fund_id}
                )
            ).first()
            current_symbol = current[0] if current else None

            if decision.action == "symbol_changed" and current_symbol and current_symbol != symbol:
                # نماد عوض شده → نماد قبلی Alias می‌شود، آی‌دی کانونی ثابت می‌ماند
                await register_alias(
                    self.session,
                    fund_id=fund_id,
                    symbol=current_symbol,
                    isin=isin,
                    national_id=national_id,
                    source="symbol_change",
                )
                stats.aliases_added += 1
                await self.session.execute(
                    text(
                        """
                        UPDATE funds SET symbol = :sym, name = :name,
                            isin = COALESCE(:isin, isin), national_id = COALESCE(:nid, national_id),
                            fund_type = COALESCE(NULLIF(:ftype, ''), fund_type),
                            is_etf = :etf, last_synced_at = :now, updated_at = :now
                        WHERE id = :fid
                        """
                    ),
                    {
                        "sym": symbol,
                        "name": name,
                        "isin": normalize_isin(isin),
                        "nid": national_id,
                        "ftype": fund_type,
                        "etf": is_etf,
                        "now": now,
                        "fid": fund_id,
                    },
                )
            else:
                await self.session.execute(
                    text(
                        """
                        UPDATE funds SET
                            name = :name,
                            isin = COALESCE(:isin, isin),
                            national_id = COALESCE(:nid, national_id),
                            fund_type = COALESCE(NULLIF(:ftype, ''), fund_type),
                            is_etf = :etf,
                            last_synced_at = :now,
                            updated_at = :now
                        WHERE id = :fid
                        """
                    ),
                    {
                        "name": name,
                        "isin": normalize_isin(isin),
                        "nid": national_id,
                        "ftype": fund_type,
                        "etf": is_etf,
                        "now": now,
                        "fid": fund_id,
                    },
                )
                stats.updated += 1

        # Alias نماد فعلی (Idempotent)
        await register_alias(
            self.session,
            fund_id=fund_id,
            symbol=symbol,
            isin=isin,
            national_id=national_id,
            source="discovery",
        )

        # قابلیت‌ها
        detected = detect_capabilities(
            fund_id=fund_id,
            symbol=symbol,
            market=market,
            nav_symbols=sources["nav_symbols"],
            nav_funds=sources["nav_funds"],
            quote_symbols=sources["quote_symbols"],
            quote_funds=sources["quote_funds"],
            codal_symbols=sources["codal_symbols"],
            portfolio_funds=sources["portfolio_funds"],
            holding_funds=sources["holding_funds"],
        )
        existing = (
            await self.session.execute(
                text(
                    "SELECT has_nav, has_portfolio, is_etf, has_market_quotes, has_codal_reports "
                    "FROM fund_capabilities WHERE fund_id = :fid"
                ),
                {"fid": fund_id},
            )
        ).first()
        merged = merge_capabilities(
            {
                "has_nav": existing[0],
                "has_portfolio": existing[1],
                "is_etf": existing[2],
                "has_market_quotes": existing[3],
                "has_codal_reports": existing[4],
            }
            if existing
            else None,
            detected,
        )
        await self.session.execute(
            text(
                """
                INSERT INTO fund_capabilities
                    (fund_id, isin, has_nav, has_portfolio, is_etf,
                     has_market_quotes, has_codal_reports, capabilities_json, updated_at)
                VALUES (:fid, :isin, :hn, :hp, :etf, :hq, :hc, :caps, :now)
                ON CONFLICT (fund_id) DO UPDATE SET
                    isin = COALESCE(EXCLUDED.isin, fund_capabilities.isin),
                    has_nav = EXCLUDED.has_nav,
                    has_portfolio = EXCLUDED.has_portfolio,
                    is_etf = EXCLUDED.is_etf,
                    has_market_quotes = EXCLUDED.has_market_quotes,
                    has_codal_reports = EXCLUDED.has_codal_reports,
                    capabilities_json = EXCLUDED.capabilities_json,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "fid": fund_id,
                "isin": normalize_isin(isin),
                "hn": merged["has_nav"],
                "hp": merged["has_portfolio"],
                "etf": merged["is_etf"],
                "hq": merged["has_market_quotes"],
                "hc": merged["has_codal_reports"],
                "caps": json.dumps(detected, ensure_ascii=False),
                "now": now,
            },
        )
        return {
            **record,
            "fund_id": fund_id,
            "symbol": symbol,
            "market": market,
            "fund_type_hint": fund_type,
        }

    async def _load_detection_sources(self) -> dict[str, set[str]]:
        """یک‌بار خواندن مجموعه‌های تشخیص قابلیت (بدون N+1)."""

        async def _set(sql: str) -> set[str]:
            try:
                rows = (await self.session.execute(text(sql))).fetchall()
                return {str(r[0]) for r in rows if r[0]}
            except Exception:  # noqa: BLE001 — منبع ممکن است خالی/ناموجود باشد
                return set()

        return {
            "nav_symbols": await _set("SELECT DISTINCT symbol FROM brsapi_nav_records"),
            "nav_funds": await _set("SELECT DISTINCT fund_id FROM fund_nav_history"),
            "quote_symbols": await _set("SELECT DISTINCT symbol FROM brsapi_symbol_snapshots"),
            "quote_funds": await _set("SELECT DISTINCT fund_id FROM fund_market_quotes_cache"),
            "codal_symbols": await _set("SELECT DISTINCT symbol FROM brsapi_codal_announcements"),
            "portfolio_funds": await _set("SELECT DISTINCT fund_id FROM fund_portfolio_reports"),
            "holding_funds": await _set("SELECT DISTINCT fund_id FROM fund_holdings"),
        }

    async def _store_snapshot(self, funds: list[dict[str, Any]]) -> None:
        snapshot = json.dumps(funds, ensure_ascii=False, default=str)
        await self.session.execute(
            text(
                """
                INSERT INTO fund_meta (meta_key, meta_value, updated_at)
                VALUES ('universe_snapshot', :v, now())
                ON CONFLICT (meta_key) DO UPDATE SET
                    meta_value = EXCLUDED.meta_value, updated_at = EXCLUDED.updated_at
                """
            ),
            {"v": snapshot[:5_000_000]},
        )

    # ── ۲) Coverage / Freshness KPIs (A6) ───────────────────────────────

    async def compute_coverage(self, *, limit: int = 500, include_missing: bool = True) -> list[dict[str, Any]]:
        """KPIهای پوشش هر صندوق از نمای ``fund_universe`` (بدون محاسبه سنگین)."""
        nav_counts: dict[str, int] = {}
        try:
            rows = (
                await self.session.execute(
                    text(
                        """
                        SELECT fund_id, COUNT(*) FROM fund_nav_history
                        WHERE nav_date >= CURRENT_DATE - :win
                        GROUP BY fund_id
                        """
                    ),
                    {"win": NAV_WINDOW_DAYS},
                )
            ).fetchall()
            nav_counts = {r[0]: int(r[1]) for r in rows}
        except Exception:  # noqa: BLE001
            pass

        quote_ages: dict[str, float] = {}
        try:
            rows = (
                await self.session.execute(
                    text(
                        """
                        SELECT fund_id, EXTRACT(EPOCH FROM (now() - quoted_at)) / 60.0
                        FROM fund_market_quotes_cache
                        """
                    )
                )
            ).fetchall()
            quote_ages = {r[0]: float(r[1]) for r in rows if r[1] is not None}
        except Exception:  # noqa: BLE001
            pass

        universe = (
            await self.session.execute(
                text(
                    """
                    SELECT fund_id, symbol, name, fund_type, trading_status, is_etf,
                           has_nav, has_portfolio, has_market_quotes, has_codal_reports,
                           aliases_count, nav_points, last_nav_date, last_portfolio_date
                    FROM fund_universe
                    ORDER BY market_value DESC NULLS LAST
                    LIMIT :lim
                    """
                ),
                {"lim": limit},
            )
        ).fetchall()

        today = date.today()
        out: list[dict[str, Any]] = []
        for r in universe:
            fund_id, symbol, name, ftype, tstatus = r[0], r[1], r[2], r[3], r[4]
            is_etf, has_nav, has_portfolio, has_quotes, has_codal = r[5], r[6], r[7], r[8], r[9]
            aliases, nav_points, last_nav, last_port = r[10], r[11], r[12], r[13]
            window_points = nav_counts.get(fund_id, 0)
            nav_cov = min(100.0, window_points / max(1.0, NAV_WINDOW_DAYS * 0.7) * 100.0)
            qage = quote_ages.get(fund_id)
            status = coverage_status(nav_cov, bool(has_portfolio), qage)
            if status == "missing" and not include_missing:
                continue
            out.append(
                {
                    "fund_id": fund_id,
                    "symbol": symbol,
                    "name": name,
                    "fund_type": ftype,
                    "trading_status": tstatus,
                    "is_etf": bool(is_etf),
                    "has_nav": bool(has_nav),
                    "has_portfolio": bool(has_portfolio),
                    "has_market_quotes": bool(has_quotes),
                    "has_codal_reports": bool(has_codal),
                    "aliases_count": int(aliases or 0),
                    "nav_points": int(nav_points or 0),
                    "nav_points_90d": window_points,
                    "nav_coverage_pct": round(nav_cov, 1),
                    "last_nav_date": str(last_nav) if last_nav else None,
                    "last_portfolio_date": str(last_port) if last_port else None,
                    "quote_age_minutes": round(qage, 1) if qage is not None else None,
                    "coverage_status": status,
                    "coverage_score": coverage_score(nav_cov, bool(has_portfolio), qage, int(aliases or 0)),
                    "as_of": str(today),
                }
            )
        return out

    # ── ۳) ممیزی اجرا (SLA / Checkpoint) ─────────────────────────────────

    async def _start_run(self, run_type: str) -> int | None:
        try:
            row = (
                await self.session.execute(
                    text(
                        """
                        INSERT INTO fund_ingestion_runs (run_type, status, started_at)
                        VALUES (:t, 'running', now())
                        RETURNING id
                        """
                    ),
                    {"t": run_type},
                )
            ).first()
            return int(row[0]) if row else None
        except Exception:  # noqa: BLE001
            return None

    async def _finish_run(self, run_id: int | None, stats: DiscoveryStats, *, status: str) -> None:
        if run_id is None:
            return
        try:
            await self.session.execute(
                text(
                    """
                    UPDATE fund_ingestion_runs SET
                        status = :st, finished_at = now(),
                        discovered = :d, created_count = :c, updated_count = :u,
                        alias_count = :a, conflict_count = :cf,
                        stats_json = :sj
                    WHERE id = :rid
                    """
                ),
                {
                    "st": status,
                    "d": stats.discovered,
                    "c": stats.created,
                    "u": stats.updated,
                    "a": stats.aliases_added,
                    "cf": stats.conflicts,
                    "sj": json.dumps(stats.to_dict(), ensure_ascii=False, default=str),
                    "rid": run_id,
                },
            )
            await self.session.commit()
        except Exception:  # noqa: BLE001
            logger.debug("finish_run failed", exc_info=True)

    async def _quarantine(
        self,
        *,
        fund_id: str | None,
        isin: str | None,
        payload: dict[str, Any],
        reason: str,
        rule: str,
    ) -> None:
        """ثبت رکورد مشکوک در قرنطینه — هرگز Exception را به بالا پرتاب نمی‌کند."""
        try:
            from services.fund_api_adapter import _fingerprint  # noqa: PLC0415

            fingerprint = _fingerprint(payload)
        except Exception:  # noqa: BLE001
            fingerprint = None
        try:
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_ingestion_quarantine
                        (source_endpoint, fund_id, isin, record_fingerprint,
                         payload_json, reject_reason, reject_rule, reviewed, created_at)
                    VALUES ('discovery', :fid, :isin, :fp, :payload, :reason, :rule, FALSE, now())
                    """
                ),
                {
                    "fid": fund_id,
                    "isin": normalize_isin(isin),
                    "fp": fingerprint,
                    "payload": json.dumps(payload, ensure_ascii=False, default=str)[:20000],
                    "reason": reason[:500],
                    "rule": rule,
                },
            )
            stats_placeholder = None  # noqa: F841
        except Exception:  # noqa: BLE001
            logger.debug("quarantine insert failed", exc_info=True)
