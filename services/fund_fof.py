"""🔁 Fund of Funds (FOF) — NAV از NAV زیرصندوق‌ها + کشف حلقه حلقوی (فاز ۴).

- ارزش هر موقعیت زیرصندوق = تعداد واحد × NAV نسخه‌دار همان زیرصندوق.
- حلقه حلقوی (A→B→A) شناسایی و علامت‌گذاری می‌شود تا از دوباره‌شماری جلوگیری شود.
- Look-through فقط در تحلیل است و جای ارزش حسابداری را نمی‌گیرد.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.time import now_tehran
from services.fund_read_through import StaleResult

logger = get_logger(__name__)

FOF_ENGINE_VERSION = "fof-1.1.0"
FUND_LIKE_TYPES = ("fund", "fund_unit", "etf")
MAX_FOF_DEPTH = 3


def expand_fof_lookthrough(
    root: str,
    positions_by_fund: dict[str, list[dict[str, Any]]],
    max_depth: int = MAX_FOF_DEPTH,
) -> list[dict[str, Any]]:
    """بازگشتی: شکستن موقعیت‌ها تا عمق مشخص با کشف حلقه و سهم تناسبی.

    ``positions_by_fund``: fund_id → [{sub_fund_id, value}] با ارزش مستقیم هر موقعیت.
    خروجی: ردیف‌های look-through با عمق، ارزش سهم و پرچم حلقه.
    """
    results: list[dict[str, Any]] = []

    def walk(fund_id: str, share: float, depth: int, path: list[str]) -> None:
        positions = positions_by_fund.get(fund_id, [])
        child_total = sum(float(p.get("value") or 0) for p in positions)
        for pos in positions:
            sub = str(pos.get("sub_fund_id"))
            value = float(pos.get("value") or 0)
            circular = sub in path
            results.append(
                {
                    "sub_fund_id": sub,
                    "depth": depth,
                    "value": value * share,
                    "direct_value": value if depth == 1 else None,
                    "circular_flag": circular,
                    "path": ">".join(path + [sub]),
                }
            )
            if circular or depth >= max_depth or child_total <= 0:
                continue
            walk(sub, share * (value / child_total), depth + 1, path + [sub])

    walk(root, 1.0, 1, [root])
    return results


def detect_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """کشف حلقه‌های جهت‌دار با DFS سه‌رنگ — بازگشت مسیر حلقه‌ها."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = dict.fromkeys(graph, WHITE)
    cycles: list[list[str]] = []
    path: list[str] = []

    def dfs(node: str) -> None:
        color[node] = GRAY
        path.append(node)
        for nxt in graph.get(node, []):
            if nxt not in color:
                color[nxt] = WHITE
            if color[nxt] == WHITE:
                dfs(nxt)
            elif color[nxt] == GRAY:
                # حلقه پیدا شد — مسیر از محل تکرار
                try:
                    start = path.index(nxt)
                    cycles.append(path[start:] + [nxt])
                except ValueError:
                    cycles.append([nxt])
        path.pop()
        color[node] = BLACK

    for node in list(graph):
        if color.get(node, WHITE) == WHITE:
            dfs(node)
    return cycles


def compute_fof_value(positions: list[dict[str, Any]]) -> dict[str, Any]:
    """جمع ارزش موقعیت‌های زیرصندوق؛ موقعیت‌های حلقوی جدا می‌شوند."""
    total = 0.0
    circular_value = 0.0
    valued = 0
    missing = 0
    for pos in positions:
        units = float(pos.get("units") or 0)
        nav = pos.get("sub_nav_per_unit")
        if nav is None or units <= 0:
            missing += 1
            continue
        value = units * float(nav)
        if pos.get("circular_flag"):
            circular_value += value
        else:
            total += value
            valued += 1
    return {
        "total_value": total,
        "circular_value": circular_value,
        "valued_positions": valued,
        "missing_positions": missing,
        "coverage_pct": (
            valued / (valued + missing) * 100.0 if (valued + missing) > 0 else 0.0
        ),
    }


class FundFofService:
    """ارزش‌گذاری فراصندوق از NAV زیرصندوق‌ها + کنترل حلقه."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _resolve_fund_id(self, symbol: str) -> str | None:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT fund_id FROM fund_symbol_aliases
                    WHERE symbol = :sym AND is_active = TRUE
                    LIMIT 1
                    """
                ),
                {"sym": symbol},
            )
        ).first()
        if row:
            return row[0]
        row2 = (
            await self.session.execute(
                text("SELECT id FROM funds WHERE symbol = :sym LIMIT 1"), {"sym": symbol}
            )
        ).first()
        return row2[0] if row2 else None

    async def _load_sub_positions(self, fund_id: str) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT instrument_symbol, holding_type, quantity, market_value
                    FROM fund_holdings
                    WHERE fund_id = :fid
                      AND period_end_date = (
                          SELECT MAX(period_end_date) FROM fund_holdings WHERE fund_id = :fid
                      )
                    """
                ),
                {"fid": fund_id},
            )
        ).fetchall()
        positions: list[dict[str, Any]] = []
        for r in rows:
            symbol, htype, qty, mv = r[0], (r[1] or "").lower(), r[2], r[3]
            if not symbol:
                continue
            is_fund_like = htype in FUND_LIKE_TYPES
            sub_fund_id = await self._resolve_fund_id(str(symbol))
            if not is_fund_like and sub_fund_id is None:
                continue
            positions.append(
                {
                    "instrument_symbol": symbol,
                    "holding_type": htype,
                    "units": float(qty or 0),
                    "reported_value": float(mv or 0),
                    "sub_fund_id": sub_fund_id or f"unresolved:{symbol}",
                }
            )
        return positions

    async def _sub_nav(self, sub_fund_id: str) -> tuple[float | None, int | None]:
        if sub_fund_id.startswith("unresolved:"):
            return None, None
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT COALESCE(nav_statistical, nav_redemption, nav_issue),
                           units_outstanding
                    FROM fund_nav_history
                    WHERE fund_id = :fid
                    ORDER BY nav_date DESC LIMIT 1
                    """
                ),
                {"fid": sub_fund_id},
            )
        ).first()
        if row is None or row[0] is None:
            return None, None
        return float(row[0]), (int(row[1]) if row[1] else None)

    async def _build_graph(self, fund_id: str) -> dict[str, list[str]]:
        """گراف مالکیت صندوق‌ها از هلدینگ‌های fund-like (برای کشف حلقه)."""
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT h.fund_id, h.instrument_symbol
                    FROM fund_holdings h
                    WHERE LOWER(COALESCE(h.holding_type, '')) IN ('fund', 'fund_unit', 'etf')
                    """
                )
            )
        ).fetchall()
        graph: dict[str, list[str]] = {}
        for fid, symbol in rows:
            if not symbol:
                continue
            sub = await self._resolve_fund_id(str(symbol))
            if sub:
                graph.setdefault(str(fid), []).append(str(sub))
        graph.setdefault(fund_id, [])
        return graph

    async def _valued_positions(self, fund_id: str) -> list[dict[str, Any]]:
        """موقعیت‌های مستقیم با NAV و ارزش محاسبه‌شده (برای بازگشت بازگشتی)."""
        raw = await self._load_sub_positions(fund_id)
        out: list[dict[str, Any]] = []
        for pos in raw:
            nav, _ = await self._sub_nav(pos["sub_fund_id"])
            value = float(pos["units"]) * float(nav) if nav is not None else None
            out.append({**pos, "sub_nav_per_unit": nav, "value": value})
        return out

    async def calculate(
        self, fund_id: str, valuation_date: date | None = None
    ) -> StaleResult:
        valuation_date = valuation_date or now_tehran().date()
        positions = await self._load_sub_positions(fund_id)
        if not positions:
            raise ValueError("موقعیت زیرصندوقی برای این صندوق یافت نشد")

        graph = await self._build_graph(fund_id)
        cycles = detect_cycles(graph)
        circular_funds = {node for cycle in cycles for node in cycle}

        enriched: list[dict[str, Any]] = []
        for pos in positions:
            sub_id = pos["sub_fund_id"]
            nav, _ = await self._sub_nav(sub_id)
            pos["sub_nav_per_unit"] = nav
            pos["circular_flag"] = sub_id in circular_funds
            pos["depth"] = 1
            enriched.append(pos)

        summary = compute_fof_value(enriched)
        quality = "COMPLETE" if summary["missing_positions"] == 0 else "PARTIAL"

        # ── Look-through بازگشتی (عمق > ۱) با کشف حلقه در مسیر ──
        positions_by_fund: dict[str, list[dict[str, Any]]] = {
            fund_id: [
                {
                    "sub_fund_id": p["sub_fund_id"],
                    "value": (
                        float(p["units"]) * float(p["sub_nav_per_unit"])
                        if p.get("sub_nav_per_unit") is not None
                        else 0.0
                    ),
                }
                for p in enriched
            ]
        }
        seen_subs: set[str] = set()
        for p in enriched:
            sub = p["sub_fund_id"]
            if sub.startswith("unresolved:") or sub in seen_subs:
                continue
            seen_subs.add(sub)
            child_vals = await self._valued_positions(sub)
            positions_by_fund[sub] = [
                {"sub_fund_id": c["sub_fund_id"], "value": float(c.get("value") or 0.0)}
                for c in child_vals
            ]
        lookthrough = expand_fof_lookthrough(fund_id, positions_by_fund)
        deep_rows = [r for r in lookthrough if r["depth"] > 1]
        summary["lookthrough_value"] = sum(
            float(r["value"]) for r in deep_rows if not r["circular_flag"]
        )
        summary["lookthrough_circular_value"] = sum(
            float(r["value"]) for r in deep_rows if r["circular_flag"]
        )
        summary["lookthrough_rows"] = len(deep_rows)

        await self.session.execute(
            text("DELETE FROM fund_fof_valuations WHERE fund_id = :fid AND valuation_date = :vd"),
            {"fid": fund_id, "vd": valuation_date},
        )
        for pos in enriched:
            value = (
                float(pos["units"]) * float(pos["sub_nav_per_unit"])
                if pos.get("sub_nav_per_unit") is not None
                else None
            )
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_fof_valuations
                        (fund_id, valuation_date, sub_fund_id, sub_nav_per_unit, units,
                         value, circular_flag, depth, quality, details_json)
                    VALUES (:fid, :vd, :sub, :nav, :units, :val, :circ, :depth, :quality, :details)
                    """
                ),
                {
                    "fid": fund_id,
                    "vd": valuation_date,
                    "sub": pos["sub_fund_id"],
                    "nav": pos.get("sub_nav_per_unit"),
                    "units": pos.get("units"),
                    "val": value,
                    "circ": bool(pos.get("circular_flag")),
                    "depth": int(pos.get("depth") or 1),
                    "quality": "CIRCULAR" if pos.get("circular_flag") else quality,
                    "details": json.dumps(
                        {"symbol": pos.get("instrument_symbol"), "holding_type": pos.get("holding_type")},
                        ensure_ascii=False,
                    ),
                },
            )
        for row in deep_rows:
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_fof_valuations
                        (fund_id, valuation_date, sub_fund_id, sub_nav_per_unit, units,
                         value, circular_flag, depth, quality, details_json)
                    VALUES (:fid, :vd, :sub, NULL, NULL, :val, :circ, :depth, :quality, :details)
                    """
                ),
                {
                    "fid": fund_id,
                    "vd": valuation_date,
                    "sub": row["sub_fund_id"],
                    "val": row["value"],
                    "circ": bool(row["circular_flag"]),
                    "depth": int(row["depth"]),
                    "quality": "CIRCULAR" if row["circular_flag"] else "LOOKTHROUGH",
                    "details": json.dumps({"path": row["path"]}, ensure_ascii=False),
                },
            )
        await self.session.commit()

        return StaleResult(
            data={
                "fund_id": fund_id,
                "valuation_date": str(valuation_date),
                "positions": enriched,
                "summary": summary,
                "lookthrough": deep_rows,
                "cycles": cycles,
                "quality": quality,
                "engine_version": FOF_ENGINE_VERSION,
            },
            freshness="estimated",
            fetched_from="db",
        )

    async def get_latest(self, fund_id: str) -> dict[str, Any] | None:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT valuation_date, sub_fund_id, sub_nav_per_unit, units, value,
                           circular_flag, depth, quality
                    FROM fund_fof_valuations
                    WHERE fund_id = :fid
                      AND valuation_date = (
                          SELECT MAX(valuation_date) FROM fund_fof_valuations WHERE fund_id = :fid
                      )
                    ORDER BY COALESCE(value, 0) DESC
                    """
                ),
                {"fid": fund_id},
            )
        ).fetchall()
        if not rows:
            return None
        positions = [
            {
                "sub_fund_id": r[1],
                "sub_nav_per_unit": r[2],
                "units": r[3],
                "value": r[4],
                "circular_flag": r[5],
                "depth": r[6],
                "quality": r[7],
            }
            for r in rows
        ]
        direct = [p for p in positions if int(p.get("depth") or 1) == 1]
        deep = [p for p in positions if int(p.get("depth") or 1) > 1]
        summary = compute_fof_value(direct)
        summary["lookthrough_value"] = sum(
            float(p.get("value") or 0) for p in deep if not p.get("circular_flag")
        )
        summary["lookthrough_circular_value"] = sum(
            float(p.get("value") or 0) for p in deep if p.get("circular_flag")
        )
        summary["lookthrough_rows"] = len(deep)
        return {
            "fund_id": fund_id,
            "valuation_date": str(rows[0][0]),
            "positions": positions,
            "summary": summary,
        }


__all__ = [
    "FOF_ENGINE_VERSION",
    "FundFofService",
    "compute_fof_value",
    "detect_cycles",
]
