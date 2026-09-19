"""🧮 Fund NAV Engine — محاسبه NAV مستقل و نسخه‌دار (فاز ۳ و ۴ معماری).

اصل: NAV فقط از «موقعیت‌ها × قیمت معتبر + نقد/سایر دارایی‌ها − بدهی‌ها» و بر
مبنای تعداد واحدهای همان صندوق محاسبه می‌شود؛ سپس به‌صورت مستقل و با گیت‌های
مقایسه‌پذیری با NAV مرجع تطبیق داده می‌شود (فایل ``fund_nav_reconciliation.py``).

هر اجرا با ``input_hash`` قابل بازتولید است و در ``fund_nav_runs`` +
``fund_position_valuations`` + ``fund_nav_results`` ذخیره می‌شود.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.time import now_tehran
from services.fund_read_through import StaleResult

logger = get_logger(__name__)

ENGINE_VERSION = "nav-engine-1.0.0"
POLICY_VERSION = "valuation-policy-v1"
DEFAULT_NAV_TYPE = "STATISTICAL"
NAV_TYPES = ("STATISTICAL", "ISSUANCE", "REDEMPTION")

# ── Pure helpers (قابل تست بدون DB) ─────────────────────────────────────────


def build_input_hash(payload: dict[str, Any]) -> str:
    """هش قطعی ورودی — کلید بازتولید و idempotency اجرا."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def quality_from_coverage(
    coverage_pct: float,
    units: int | None,
    has_positions: bool,
    has_report: bool,
) -> str:
    """وضعیت کیفیت داده اجرا — مستقل از وضعیت اجرای فنی.

    COMPLETE | ESTIMATED | PARTIAL | BLOCKED
    """
    if not has_positions or not units or units <= 0:
        return "BLOCKED"
    if coverage_pct >= 95.0 and has_report:
        return "COMPLETE"
    if coverage_pct >= 50.0:
        return "ESTIMATED"
    return "PARTIAL"


def compute_nav(
    total_assets: float | None,
    total_liabilities: float | None,
    units: int | None,
) -> tuple[float | None, float | None]:
    """بازگشت (net_assets, nav_per_unit)؛ در نبود واحد معتبر → (None, None)."""
    if total_assets is None or not units or units <= 0:
        return None, None
    net = float(total_assets) - float(total_liabilities or 0.0)
    return net, net / float(units)


def value_position(
    holding: dict[str, Any],
    live_price: float | None,
    price_at: datetime | None = None,
) -> dict[str, Any]:
    """ارزش‌گذاری یک موقعیت با اولویت قیمت لایو برای سهام و گزارش برای سایر."""
    htype = (holding.get("holding_type") or "other").lower()
    symbol = holding.get("instrument_symbol")
    qty = float(holding.get("quantity") or 0.0)
    reported = float(holding.get("market_value") or 0.0)

    if htype == "equity" and live_price and qty:
        value = qty * float(live_price)
        return {
            "instrument_symbol": symbol,
            "instrument_name": holding.get("instrument_name"),
            "holding_type": htype,
            "quantity": qty,
            "price": float(live_price),
            "price_source": "snapshot",
            "price_at": price_at,
            "value": value,
            "quality": "LIVE",
            "reported_market_value": reported,
            "note": None,
        }
    note = "قیمت لایو در دسترس نبود؛ ارزش گزارش دوره" if htype == "equity" else None
    return {
        "instrument_symbol": symbol,
        "instrument_name": holding.get("instrument_name"),
        "holding_type": htype,
        "quantity": qty,
        "price": (reported / qty) if qty else None,
        "price_source": "reported",
        "price_at": None,
        "value": reported,
        "quality": "REPORTED",
        "reported_market_value": reported,
        "note": note,
    }


def build_evidence_hash(run: dict[str, Any] | None, recon: dict[str, Any] | None) -> str:
    """هش یکپارچگی بسته مدارک حسابرسی (اجرا + تطبیق)."""
    return build_input_hash(
        {
            "run_input_hash": (run or {}).get("input_hash"),
            "run_id": (run or {}).get("run_id"),
            "recon_run_id": (recon or {}).get("recon_run_id"),
            "internal_nav": (recon or {}).get("internal_nav"),
            "reference_nav": (recon or {}).get("reference_nav"),
            "diff_status": (recon or {}).get("diff_status"),
        }
    )


@dataclass
class _RunPayload:
    fund_id: str
    valuation_date: date
    nav_type: str
    mode: str
    positions: list[dict[str, Any]] = field(default_factory=list)
    holdings_period: date | None = None
    coverage_pct: float = 0.0
    units: int | None = None
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    net_assets: float | None = None
    nav_per_unit: float | None = None
    quality: str = "BLOCKED"
    has_report: bool = False
    warnings: list[str] = field(default_factory=list)


class FundNavEngine:
    """محاسبه NAV مستقل از داده‌های داخلی (holdings + quote + report + units)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Data loaders ────────────────────────────────────────────────────────

    async def _load_holdings(self, fund_id: str) -> tuple[list[dict[str, Any]], date | None]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT period_end_date, holding_type, instrument_symbol,
                           instrument_name, quantity, market_value, weight_pct
                    FROM fund_holdings
                    WHERE fund_id = :fid
                      AND period_end_date = (
                          SELECT MAX(period_end_date) FROM fund_holdings WHERE fund_id = :fid
                      )
                    ORDER BY COALESCE(market_value, 0) DESC
                    """
                ),
                {"fid": fund_id},
            )
        ).fetchall()
        holdings: list[dict[str, Any]] = []
        period: date | None = None
        for r in rows:
            period = r[0]
            holdings.append(
                {
                    "holding_type": r[1],
                    "instrument_symbol": r[2],
                    "instrument_name": r[3],
                    "quantity": r[4],
                    "market_value": r[5],
                    "weight_pct": r[6],
                }
            )
        return holdings, period

    async def _load_report(self, fund_id: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT period_end_date, total_assets, total_liabilities,
                           net_asset_value, units_outstanding, cash_and_equivalents
                    FROM fund_portfolio_reports
                    WHERE fund_id = :fid
                    ORDER BY period_end_date DESC LIMIT 1
                    """
                ),
                {"fid": fund_id},
            )
        ).first()
        if row is None:
            return None
        return {
            "period_end_date": row[0],
            "total_assets": row[1],
            "total_liabilities": row[2],
            "net_asset_value": row[3],
            "units_outstanding": row[4],
            "cash_and_equivalents": row[5],
        }

    async def _load_live_prices(
        self, symbols: list[str]
    ) -> dict[str, tuple[float, datetime | None]]:
        clean = [s for s in symbols if s]
        if not clean:
            return {}
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT DISTINCT ON (symbol) symbol, price_last, created_at
                    FROM brsapi_symbol_snapshots
                    WHERE symbol = ANY(:syms) AND price_last > 0
                    ORDER BY symbol, id DESC
                    """
                ),
                {"syms": clean},
            )
        ).fetchall()
        out: dict[str, tuple[float, datetime | None]] = {}
        for r in rows:
            if r[1]:
                out[str(r[0])] = (float(r[1]), r[2])
        return out

    async def _load_units(self, fund_id: str, report: dict[str, Any] | None) -> int | None:
        if report and report.get("units_outstanding"):
            return int(report["units_outstanding"])
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT units_outstanding FROM fund_nav_history
                    WHERE fund_id = :fid AND units_outstanding IS NOT NULL
                    ORDER BY nav_date DESC LIMIT 1
                    """
                ),
                {"fid": fund_id},
            )
        ).first()
        if row and row[0]:
            return int(row[0])
        row2 = (
            await self.session.execute(
                text("SELECT shares_count FROM funds WHERE id = :fid"), {"fid": fund_id}
            )
        ).first()
        return int(row2[0]) if row2 and row2[0] else None

    # ── Core ────────────────────────────────────────────────────────────────

    async def _build_payload(
        self,
        fund_id: str,
        valuation_date: date,
        nav_type: str,
        mode: str,
    ) -> _RunPayload:
        payload = _RunPayload(
            fund_id=fund_id,
            valuation_date=valuation_date,
            nav_type=nav_type,
            mode=mode,
        )
        holdings, period = await self._load_holdings(fund_id)
        report = await self._load_report(fund_id)
        payload.holdings_period = period
        payload.has_report = report is not None

        prices = await self._load_live_prices(
            [h.get("instrument_symbol") for h in holdings if h.get("instrument_symbol")]
        )

        equity_reported = 0.0
        covered = 0.0
        total = 0.0
        for h in holdings:
            sym = h.get("instrument_symbol")
            live = prices.get(sym or "")
            pos = value_position(h, live[0] if live else None, live[1] if live else None)
            payload.positions.append(pos)
            total += float(pos.get("value") or 0.0)
            if (h.get("holding_type") or "").lower() == "equity":
                equity_reported += float(h.get("market_value") or 0.0)
                if pos["quality"] == "LIVE":
                    covered += float(pos.get("value") or 0.0)

        if not holdings and report and report.get("net_asset_value"):
            # Fallback: فقط سربرگ گزارش — بدون ریز موقعیت (کیفیت پایین)
            total = float(report["net_asset_value"])
            payload.warnings.append("holdings_missing_used_report_net_assets")
            payload.quality = "BLOCKED"
        elif not holdings:
            payload.warnings.append("holdings_missing")

        payload.coverage_pct = (
            (covered / equity_reported * 100.0) if equity_reported > 0 else (100.0 if holdings else 0.0)
        )
        payload.units = await self._load_units(fund_id, report)
        payload.total_assets = total
        payload.total_liabilities = float((report or {}).get("total_liabilities") or 0.0)
        payload.net_assets, payload.nav_per_unit = compute_nav(
            payload.total_assets, payload.total_liabilities, payload.units
        )
        if not payload.warnings or payload.quality != "BLOCKED":
            payload.quality = quality_from_coverage(
                payload.coverage_pct, payload.units, bool(holdings), payload.has_report
            )
        if payload.units is None:
            payload.warnings.append("units_outstanding_missing")
        return payload

    def _hash_of(self, payload: _RunPayload) -> str:
        return build_input_hash(
            {
                "fund_id": payload.fund_id,
                "valuation_date": str(payload.valuation_date),
                "nav_type": payload.nav_type,
                "engine_version": ENGINE_VERSION,
                "policy_version": POLICY_VERSION,
                "units": payload.units,
                "mode": payload.mode,
                "holdings_period": str(payload.holdings_period),
                "positions": [
                    {
                        "symbol": p.get("instrument_symbol"),
                        "type": p.get("holding_type"),
                        "qty": p.get("quantity"),
                        "price": p.get("price"),
                        "source": p.get("price_source"),
                        "value": p.get("value"),
                    }
                    for p in payload.positions
                ],
                "total_liabilities": payload.total_liabilities,
            }
        )

    async def _persist_payload(
        self, payload: _RunPayload, input_hash: str
    ) -> tuple[int | None, bool]:
        """ذخیره اتمیک اجرا + ردیف‌های ارزش‌گذاری + نتیجه (idempotent)."""
        source_json = json.dumps(
            {
                "holdings_period": str(payload.holdings_period),
                "has_report": payload.has_report,
                "coverage_pct": round(payload.coverage_pct, 2),
                "warnings": payload.warnings,
                "mode": payload.mode,
            },
            ensure_ascii=False,
        )
        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_nav_runs
                        (fund_id, valuation_date, nav_type, mode, engine_version,
                         policy_version, input_hash, run_status, quality_status,
                         holdings_period, coverage_pct, units_outstanding,
                         total_assets, total_liabilities, net_assets, nav_per_unit,
                         positions_count, source_json)
                    VALUES
                        (:fid, :vd, :nt, :mode, :eng, :pol, :hash, 'SUCCESS', :quality,
                         :hp, :cov, :units, :ta, :tl, :na, :navpu, :pc, :src)
                    ON CONFLICT (fund_id, valuation_date, nav_type, input_hash) DO NOTHING
                    RETURNING id
                    """
                ),
                {
                    "fid": payload.fund_id,
                    "vd": payload.valuation_date,
                    "nt": payload.nav_type,
                    "mode": payload.mode,
                    "eng": ENGINE_VERSION,
                    "pol": POLICY_VERSION,
                    "hash": input_hash,
                    "quality": payload.quality,
                    "hp": payload.holdings_period,
                    "cov": payload.coverage_pct,
                    "units": payload.units,
                    "ta": payload.total_assets,
                    "tl": payload.total_liabilities,
                    "na": payload.net_assets,
                    "navpu": payload.nav_per_unit,
                    "pc": len(payload.positions),
                    "src": source_json,
                },
            )
        ).first()
        if row is None:
            return (
                await self._existing_run_id(
                    payload.fund_id, payload.valuation_date, payload.nav_type, input_hash
                ),
                False,
            )
        run_id = int(row[0])
        for p in payload.positions:
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_position_valuations
                        (run_id, fund_id, instrument_symbol, instrument_name,
                         holding_type, quantity, price, price_source, price_at,
                         value, weight_pct, quality, reported_market_value, note)
                    VALUES
                        (:rid, :fid, :sym, :name, :ht, :qty, :price, :src, :pat,
                         :val, :w, :quality, :rmv, :note)
                    """
                ),
                {
                    "rid": run_id,
                    "fid": payload.fund_id,
                    "sym": p.get("instrument_symbol"),
                    "name": p.get("instrument_name"),
                    "ht": p.get("holding_type"),
                    "qty": p.get("quantity"),
                    "price": p.get("price"),
                    "src": p.get("price_source"),
                    "pat": p.get("price_at"),
                    "val": p.get("value"),
                    "w": (
                        (float(p.get("value") or 0) / payload.total_assets * 100.0)
                        if payload.total_assets
                        else None
                    ),
                    "quality": p.get("quality"),
                    "rmv": p.get("reported_market_value"),
                    "note": p.get("note"),
                },
            )
        await self.session.execute(
            text(
                """
                INSERT INTO fund_nav_results
                    (run_id, fund_id, nav_type, valuation_date, net_assets,
                     units_outstanding, nav_per_unit, quality_status)
                VALUES (:rid, :fid, :nt, :vd, :na, :units, :navpu, :quality)
                ON CONFLICT (run_id) DO NOTHING
                """
            ),
            {
                "rid": run_id,
                "fid": payload.fund_id,
                "nt": payload.nav_type,
                "vd": payload.valuation_date,
                "na": payload.net_assets,
                "units": payload.units,
                "navpu": payload.nav_per_unit,
                "quality": payload.quality,
            },
        )
        await self.session.commit()
        return run_id, True

    async def _build_reconstructed_payload(
        self,
        fund_id: str,
        nav_date: date,
        nav_type: str,
        units_hint: int | None,
    ) -> _RunPayload | None:
        """بازسازی NAV تاریخی از گزارش دوره (بدون قیمت لایو) — کیفیت تخمینی."""
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT period_end_date, total_assets, total_liabilities,
                           net_asset_value, units_outstanding
                    FROM fund_portfolio_reports
                    WHERE fund_id = :fid AND period_end_date <= :d
                    ORDER BY period_end_date DESC LIMIT 1
                    """
                ),
                {"fid": fund_id, "d": nav_date},
            )
        ).first()
        if row is None:
            return None
        payload = _RunPayload(
            fund_id=fund_id,
            valuation_date=nav_date,
            nav_type=nav_type,
            mode="BACKFILL",
        )
        payload.holdings_period = row[0]
        payload.has_report = True
        holdings, _ = await self._load_holdings_for_period(fund_id, row[0])
        for h in holdings:
            payload.positions.append(value_position(h, None))
        total = sum(float(p.get("value") or 0) for p in payload.positions)
        if total <= 0:
            total = float(row[3] or 0)
        payload.total_assets = total
        payload.total_liabilities = float(row[2] or 0)
        payload.units = units_hint or (int(row[4]) if row[4] else None)
        payload.net_assets, payload.nav_per_unit = compute_nav(
            payload.total_assets, payload.total_liabilities, payload.units
        )
        payload.coverage_pct = 100.0 if holdings else 0.0
        payload.quality = "ESTIMATED" if payload.units and total > 0 else "BLOCKED"
        payload.warnings.append("backfill_reconstructed_from_report")
        return payload

    async def _load_holdings_for_period(
        self, fund_id: str, period: date
    ) -> tuple[list[dict[str, Any]], date | None]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT period_end_date, holding_type, instrument_symbol,
                           instrument_name, quantity, market_value, weight_pct
                    FROM fund_holdings
                    WHERE fund_id = :fid AND period_end_date = :pd
                    ORDER BY COALESCE(market_value, 0) DESC
                    """
                ),
                {"fid": fund_id, "pd": period},
            )
        ).fetchall()
        return (
            [
                {
                    "holding_type": r[1],
                    "instrument_symbol": r[2],
                    "instrument_name": r[3],
                    "quantity": r[4],
                    "market_value": r[5],
                    "weight_pct": r[6],
                }
                for r in rows
            ],
            period if rows else None,
        )

    async def backfill(
        self,
        fund_id: str,
        days: int = 90,
        nav_type: str = DEFAULT_NAV_TYPE,
    ) -> StaleResult:
        """Backfill تاریخی: بازسازی NAV روزهای گذشته از گزارش‌های دوره (فاز ۱۲)."""
        if nav_type not in NAV_TYPES:
            raise ValueError(f"nav_type نامعتبر: {nav_type}")
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT nav_date, units_outstanding
                    FROM fund_nav_history
                    WHERE fund_id = :fid
                    ORDER BY nav_date DESC
                    LIMIT :lim
                    """
                ),
                {"fid": fund_id, "lim": days},
            )
        ).fetchall()
        created = 0
        skipped = 0
        failed: list[str] = []
        for nav_date, units in rows:
            try:
                payload = await self._build_reconstructed_payload(
                    fund_id, nav_date, nav_type, int(units) if units else None
                )
                if payload is None:
                    skipped += 1
                    continue
                input_hash = self._hash_of(payload)
                _, was_created = await self._persist_payload(payload, input_hash)
                if was_created:
                    created += 1
                else:
                    skipped += 1
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{nav_date}: {exc}")
                logger.warning("Backfill failed fund=%s date=%s: %s", fund_id, nav_date, exc)
        return StaleResult(
            data={
                "fund_id": fund_id,
                "requested": len(rows),
                "created": created,
                "skipped": skipped,
                "failed": len(failed),
                "errors": failed[:10],
                "engine_version": ENGINE_VERSION,
            },
            freshness="estimated",
            fetched_from="db",
        )

    async def calculate(
        self,
        fund_id: str,
        nav_type: str = DEFAULT_NAV_TYPE,
        as_of: date | None = None,
        mode: str = "SHADOW",
    ) -> StaleResult:
        """اجرای محاسبه NAV مستقل + ذخیره نسخه‌دار (idempotent)."""
        if nav_type not in NAV_TYPES:
            raise ValueError(f"nav_type نامعتبر: {nav_type}")
        valuation_date = as_of or now_tehran().date()
        payload = await self._build_payload(fund_id, valuation_date, nav_type, mode)
        input_hash = self._hash_of(payload)

        source_json = json.dumps(
            {
                "holdings_period": str(payload.holdings_period),
                "has_report": payload.has_report,
                "coverage_pct": round(payload.coverage_pct, 2),
                "warnings": payload.warnings,
            },
            ensure_ascii=False,
        )

        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_nav_runs
                        (fund_id, valuation_date, nav_type, mode, engine_version,
                         policy_version, input_hash, run_status, quality_status,
                         holdings_period, coverage_pct, units_outstanding,
                         total_assets, total_liabilities, net_assets, nav_per_unit,
                         positions_count, source_json)
                    VALUES
                        (:fid, :vd, :nt, :mode, :eng, :pol, :hash, 'SUCCESS', :quality,
                         :hp, :cov, :units, :ta, :tl, :na, :navpu, :pc, :src)
                    ON CONFLICT (fund_id, valuation_date, nav_type, input_hash) DO NOTHING
                    RETURNING id
                    """
                ),
                {
                    "fid": fund_id,
                    "vd": valuation_date,
                    "nt": nav_type,
                    "mode": mode,
                    "eng": ENGINE_VERSION,
                    "pol": POLICY_VERSION,
                    "hash": input_hash,
                    "quality": payload.quality,
                    "hp": payload.holdings_period,
                    "cov": payload.coverage_pct,
                    "units": payload.units,
                    "ta": payload.total_assets,
                    "tl": payload.total_liabilities,
                    "na": payload.net_assets,
                    "navpu": payload.nav_per_unit,
                    "pc": len(payload.positions),
                    "src": source_json,
                },
            )
        ).first()

        created = row is not None
        if row is not None:
            run_id = int(row[0])
            for p in payload.positions:
                await self.session.execute(
                    text(
                        """
                        INSERT INTO fund_position_valuations
                            (run_id, fund_id, instrument_symbol, instrument_name,
                             holding_type, quantity, price, price_source, price_at,
                             value, weight_pct, quality, reported_market_value, note)
                        VALUES
                            (:rid, :fid, :sym, :name, :ht, :qty, :price, :src, :pat,
                             :val, :w, :quality, :rmv, :note)
                        """
                    ),
                    {
                        "rid": run_id,
                        "fid": fund_id,
                        "sym": p.get("instrument_symbol"),
                        "name": p.get("instrument_name"),
                        "ht": p.get("holding_type"),
                        "qty": p.get("quantity"),
                        "price": p.get("price"),
                        "src": p.get("price_source"),
                        "pat": p.get("price_at"),
                        "val": p.get("value"),
                        "w": (
                            (float(p.get("value") or 0) / payload.total_assets * 100.0)
                            if payload.total_assets
                            else None
                        ),
                        "quality": p.get("quality"),
                        "rmv": p.get("reported_market_value"),
                        "note": p.get("note"),
                    },
                )
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_nav_results
                        (run_id, fund_id, nav_type, valuation_date, net_assets,
                         units_outstanding, nav_per_unit, quality_status)
                    VALUES (:rid, :fid, :nt, :vd, :na, :units, :navpu, :quality)
                    ON CONFLICT (run_id) DO NOTHING
                    """
                ),
                {
                    "rid": run_id,
                    "fid": fund_id,
                    "nt": nav_type,
                    "vd": valuation_date,
                    "na": payload.net_assets,
                    "units": payload.units,
                    "navpu": payload.nav_per_unit,
                    "quality": payload.quality,
                },
            )
            await self.session.commit()
        else:
            run_id = await self._existing_run_id(fund_id, valuation_date, nav_type, input_hash)

        freshness = {
            "COMPLETE": "live",
            "ESTIMATED": "estimated",
            "PARTIAL": "estimated",
            "BLOCKED": "stale",
        }.get(payload.quality, "estimated")

        return StaleResult(
            data={
                "run_id": run_id,
                "fund_id": fund_id,
                "valuation_date": str(valuation_date),
                "nav_type": nav_type,
                "mode": mode,
                "created": created,
                "quality_status": payload.quality,
                "coverage_pct": round(payload.coverage_pct, 2),
                "units_outstanding": payload.units,
                "total_assets": payload.total_assets,
                "total_liabilities": payload.total_liabilities,
                "net_assets": payload.net_assets,
                "nav_per_unit": payload.nav_per_unit,
                "positions_count": len(payload.positions),
                "holdings_period": str(payload.holdings_period) if payload.holdings_period else None,
                "warnings": payload.warnings,
                "engine_version": ENGINE_VERSION,
                "policy_version": POLICY_VERSION,
                "input_hash": input_hash,
            },
            freshness=freshness,
            fetched_from="db",
        )

    async def _existing_run_id(
        self, fund_id: str, valuation_date: date, nav_type: str, input_hash: str
    ) -> int | None:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT id FROM fund_nav_runs
                    WHERE fund_id = :fid AND valuation_date = :vd
                      AND nav_type = :nt AND input_hash = :hash
                    """
                ),
                {"fid": fund_id, "vd": valuation_date, "nt": nav_type, "hash": input_hash},
            )
        ).first()
        return int(row[0]) if row else None

    # ── Read APIs ───────────────────────────────────────────────────────────

    async def get_latest(self, fund_id: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT r.id, r.fund_id, r.valuation_date, r.nav_type, r.mode,
                           r.engine_version, r.policy_version, r.input_hash,
                           r.quality_status, r.coverage_pct, r.units_outstanding,
                           r.total_assets, r.total_liabilities, r.net_assets,
                           r.nav_per_unit, r.positions_count, r.holdings_period,
                           r.source_json, r.created_at
                    FROM fund_nav_runs r
                    WHERE r.fund_id = :fid
                    ORDER BY r.valuation_date DESC, r.created_at DESC
                    LIMIT 1
                    """
                ),
                {"fid": fund_id},
            )
        ).first()
        if row is None:
            return None
        return await self.get_run(fund_id, int(row[0]), run_row=row)

    async def get_run(
        self, fund_id: str, run_id: int, run_row: Any | None = None
    ) -> dict[str, Any] | None:
        if run_row is None:
            run_row = (
                await self.session.execute(
                    text(
                        """
                        SELECT id, fund_id, valuation_date, nav_type, mode,
                               engine_version, policy_version, input_hash,
                               quality_status, coverage_pct, units_outstanding,
                               total_assets, total_liabilities, net_assets,
                               nav_per_unit, positions_count, holdings_period,
                               source_json, created_at
                        FROM fund_nav_runs WHERE id = :rid AND fund_id = :fid
                        """
                    ),
                    {"rid": run_id, "fid": fund_id},
                )
            ).first()
        if run_row is None:
            return None

        pos_rows = (
            await self.session.execute(
                text(
                    """
                    SELECT instrument_symbol, instrument_name, holding_type, quantity,
                           price, price_source, price_at, value, weight_pct, quality,
                           reported_market_value, note
                    FROM fund_position_valuations WHERE run_id = :rid
                    ORDER BY COALESCE(value, 0) DESC
                    """
                ),
                {"rid": run_id},
            )
        ).fetchall()

        return {
            "run_id": int(run_row[0]),
            "fund_id": run_row[1],
            "valuation_date": str(run_row[2]),
            "nav_type": run_row[3],
            "mode": run_row[4],
            "engine_version": run_row[5],
            "policy_version": run_row[6],
            "input_hash": run_row[7],
            "quality_status": run_row[8],
            "coverage_pct": run_row[9],
            "units_outstanding": run_row[10],
            "total_assets": run_row[11],
            "total_liabilities": run_row[12],
            "net_assets": run_row[13],
            "nav_per_unit": run_row[14],
            "positions_count": run_row[15],
            "holdings_period": str(run_row[16]) if run_row[16] else None,
            "source_json": run_row[17],
            "created_at": str(run_row[18]) if run_row[18] else None,
            "positions": [
                {
                    "instrument_symbol": p[0],
                    "instrument_name": p[1],
                    "holding_type": p[2],
                    "quantity": p[3],
                    "price": p[4],
                    "price_source": p[5],
                    "price_at": str(p[6]) if p[6] else None,
                    "value": p[7],
                    "weight_pct": p[8],
                    "quality": p[9],
                    "reported_market_value": p[10],
                    "note": p[11],
                }
                for p in pos_rows
            ],
        }

    async def list_runs(self, fund_id: str, limit: int = 30) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, valuation_date, nav_type, mode, quality_status,
                           coverage_pct, nav_per_unit, net_assets, positions_count,
                           input_hash, created_at
                    FROM fund_nav_runs
                    WHERE fund_id = :fid
                    ORDER BY valuation_date DESC, created_at DESC
                    LIMIT :lim
                    """
                ),
                {"fid": fund_id, "lim": limit},
            )
        ).fetchall()
        return [
            {
                "run_id": int(r[0]),
                "valuation_date": str(r[1]),
                "nav_type": r[2],
                "mode": r[3],
                "quality_status": r[4],
                "coverage_pct": r[5],
                "nav_per_unit": r[6],
                "net_assets": r[7],
                "positions_count": r[8],
                "input_hash": r[9],
                "created_at": str(r[10]) if r[10] else None,
            }
            for r in rows
        ]


__all__ = [
    "ENGINE_VERSION",
    "POLICY_VERSION",
    "NAV_TYPES",
    "FundNavEngine",
    "build_evidence_hash",
    "build_input_hash",
    "compute_nav",
    "quality_from_coverage",
    "value_position",
]
