"""
Screener110 Service — Optimized 3-Layer Architecture for 600 Symbols.

Layer 1 — BatchLoader : 5 parallel DB queries → dict[str, list]  (~2s)
Layer 2 — VectorCalculator : Pure-math scoring per symbol        (~5s)
Layer 3 — BulkWriter : Chunked upsert into 2 tables              (~1s)

Usage:
    svc = Screener110Service(session, total_capital=1_000_000_000)
    buy_signals = await svc.run_full_cycle()
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from models.screener import ScreenerSignal, ScreenerSnapshot

logger = get_logger(__name__)

# ─── Constants ─────────────────────────────────────────────────────────────

WEIGHTS: dict[str, float] = {
    "fundamental": 0.18,
    "valuation": 0.13,
    "institutional": 0.18,
    "technical": 0.08,
    "macro": 0.08,
    "gov_support": 0.13,
    "liquidity": 0.05,
    "farabourse": 0.07,
    "feedstock": 0.10,
}

RISK_FILTER_COLUMNS: list[str] = [
    "ceo_change_fail", "annual_meeting_passed", "heavy_legal_case",
    "telegram_pump", "end_of_month", "pre_holiday", "political_tension",
    "feedstock_meeting", "big_ipo", "negative_mgmt_news",
]

CHUNK_SIZE = 100  # rows per bulk insert chunk
DEFAULT_CAPITAL = 1_000_000_000  # 1B IRR


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 1 — Batch Loader
# ═══════════════════════════════════════════════════════════════════════════

class BatchLoader:
    """Five parallel queries → indexed dicts for O(1) lookup per symbol."""

    def __init__(self, session: AsyncSession, brsapi: Any | None = None) -> None:
        self._session = session
        self._brsapi = brsapi

    # ── Individual queries ────────────────────────────────────────────────

    async def _load_symbols(self) -> list[dict[str, Any]]:
        q = text("""
            SELECT s.symbol, s.industry,
                   s.total_shares AS shares_count, s.eps
            FROM symbols s
            WHERE s.is_active = TRUE OR s.is_active IS NULL
            ORDER BY s.symbol
        """)
        rows = await self._session.execute(q)
        return [dict(r._mapping) for r in rows.fetchall()]

    async def _load_daily(self) -> list[dict[str, Any]]:
        # Per-symbol LATERAL window (uses idx_hist_symbol_gregorian) instead of
        # scanning the whole brsapi_historical_daily table (12M+ rows). The
        # ``daily_history`` view wraps that table too, so it is equally slow.
        q = text("""
            SELECT s.symbol,
                   d.gregorian_date   AS trade_date,
                   d.price_close, d.price_max, d.price_min, d.price_last,
                   d.trade_volume, d.trade_value, d.price_last_change_pct
            FROM symbols s
            CROSS JOIN LATERAL (
                SELECT b.gregorian_date, b.price_close, b.price_max,
                       b.price_min, b.price_last, b.trade_volume,
                       b.trade_value, b.price_last_change_pct
                FROM brsapi_historical_daily b
                WHERE b.symbol = s.symbol
                  AND b.gregorian_date IS NOT NULL
                ORDER BY b.gregorian_date DESC
                LIMIT 61
            ) d
            WHERE s.is_active = TRUE OR s.is_active IS NULL
            ORDER BY s.symbol, d.gregorian_date DESC
        """)
        rows = await self._session.execute(q)
        return [dict(r._mapping) for r in rows.fetchall()]

    async def _load_legal(self) -> list[dict[str, Any]]:
        q = text("""
            SELECT s.symbol, drl.trade_date,
                   drl.legal_buy_volume, drl.legal_sell_volume,
                   drl.real_buy_volume, drl.real_sell_volume,
                   drl.real_buy_value, drl.real_sell_value,
                   drl.legal_buy_value, drl.legal_sell_value
            FROM daily_real_legal drl
            JOIN symbols s ON s.id = drl.symbol_id
            WHERE drl.trade_date >= NOW() - INTERVAL '36 days'
            ORDER BY s.symbol, drl.trade_date DESC
        """)
        rows = await self._session.execute(q)
        return [dict(r._mapping) for r in rows.fetchall()]

    async def _load_profiles(self) -> list[dict[str, Any]]:
        q = text("SELECT * FROM screener_profiles")
        rows = await self._session.execute(q)
        return [dict(r._mapping) for r in rows.fetchall()]

    async def _load_snapshots(self) -> list[dict[str, Any]]:
        q = text("""
            SELECT DISTINCT ON (symbol)
                symbol, current_price, today_volume,
                atr_14, volume_ma_50, timestamp,
                farabourse_volume, farabourse_price
            FROM screener_snapshots
            ORDER BY symbol, timestamp DESC
        """)
        rows = await self._session.execute(q)
        return [dict(r._mapping) for r in rows.fetchall()]

    # ── Parallel load → indexed maps ─────────────────────────────────────

    async def load_all(self) -> dict[str, Any]:
        """Run all 5 queries and index results by symbol.

        NOTE: Queries run sequentially (not via asyncio.gather) because
        SQLAlchemy AsyncSession does NOT support concurrent operations on a
        single session — gather() raised InvalidRequestError:
        "This session is provisioning a new connection; concurrent operations
        are not permitted". Sequential execution is still fast (~2-4s).
        """
        t0 = time.perf_counter()
        syms = await self._load_symbols()
        daily_raw = await self._load_daily()
        legal_raw = await self._load_legal()
        profiles_raw = await self._load_profiles()
        snaps_raw = await self._load_snapshots()
        elapsed = time.perf_counter() - t0

        # Index daily history by symbol
        daily_map: dict[str, list[dict[str, Any]]] = {}
        for row in daily_raw:
            sym = row.get("symbol", "")
            if sym:
                daily_map.setdefault(sym, []).append(row)

        # Index legal data by symbol
        legal_map: dict[str, list[dict[str, Any]]] = {}
        for row in legal_raw:
            sym = row.get("symbol", "")
            if sym:
                legal_map.setdefault(sym, []).append(row)

        # Map profiles and snapshots
        profile_map: dict[str, dict[str, Any]] = {
            p_["symbol"]: p_ for p_ in profiles_raw if p_.get("symbol")
        }
        snapshot_map: dict[str, dict[str, Any]] = {
            sp_["symbol"]: sp_ for sp_ in snaps_raw if sp_.get("symbol")
        }

        logger.info(
            "Batch load: %d symbols, %d daily, %d legal, %d profiles, %d snapshots [%.2fs]",
            len(syms), len(daily_raw), len(legal_raw), len(profiles_raw), len(snaps_raw), elapsed,
        )
        return {
            "symbols": syms,
            "daily": daily_map,
            "legal": legal_map,
            "profiles": profile_map,
            "snapshots": snapshot_map,
            "_elapsed": elapsed,
        }


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 2 — Vector Calculator (pure math, no DB)
# ═══════════════════════════════════════════════════════════════════════════

class VectorCalculator:
    """Stateless scoring engine — computes all 110 columns for one symbol."""

    __slots__ = ()

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _div(a: float, b: float) -> float:
        return a / b if b else 0.0

    @staticmethod
    def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
        return lo if v < lo else hi if v > hi else v

    def trend_label(self, closes: list[float]) -> str:
        """Column 42 — classify 20d trend as 'up'/'down'/'flat'."""
        if len(closes) < 5:
            return "flat"
        ma5 = sum(closes[:5]) / max(len(closes[:5]), 1)
        ma20 = sum(closes[:20]) / max(len(closes[:20]), 1)
        if ma5 > ma20 * 1.02:
            return "up"
        if ma5 < ma20 * 0.98:
            return "down"
        return "flat"

    @staticmethod
    def _compute_atr(rows: list[dict[str, Any]], price: float) -> float:
        """True Range over up to 14 periods."""
        n = min(14, len(rows) - 1)
        if n < 1:
            return price * 0.02
        total = 0.0
        for i in range(n):
            h = float(rows[i].get("price_max", 0) or 0)
            l_ = float(rows[i].get("price_min", 0) or 0)
            pc = float(rows[i + 1].get("price_close", 0) or 0)
            total += max(h - l_, abs(h - pc), abs(l_ - pc))
        return total / n

    # ── Column-level calculators (columns 9–85) ──────────────────────────

    def dollar_eps(self, eps: float, rate: float) -> float:
        return self._div(eps, rate)

    def eps_growth(self, cur: float, prev: float) -> float:
        return self._div(cur, prev) - 1.0 if prev else 0.0

    def real_eps_growth(self, cur: float, prev: float, infl: float) -> float:
        return self.eps_growth(cur, prev) - (infl / 100.0)

    def pe(self, price: float, eps: float) -> float:
        return self._div(price, max(eps, 0.01) * 4)

    def pe_ratio(self, price: float, eps: float, ind_pe: float) -> float:
        return self._div(self.pe(price, eps), max(ind_pe, 0.01))

    def div_yield(self, price: float, eps: float) -> float:
        return self._div(eps * 4 * 100.0, max(price, 1))

    def vol_spike(self, today: float, avg50: float) -> float:
        return self._div(today, avg50)

    def liq_pct(self, avg_val: float, shares: float, price: float) -> float:
        return self._div(avg_val, max(shares * price, 1))

    def inst_ratio(self, buy: float, sell: float, shares: float) -> float:
        return self._div(buy - sell, max(shares, 1))

    def nima_spread(self, free: float, nima: float) -> float:
        return self._div(free, nima)

    def farabourse_dom(self, fv: float, bv: float) -> float:
        return self._div(fv, fv + bv)

    # ── Score functions (columns 86–95) ──────────────────────────────────

    def score_fundamental(self, dol_growth: float, real_growth: float) -> float:
        s = 0.0
        if dol_growth > 0.20:
            s += 15.0
        elif dol_growth > 0.10:
            s += 7.5
        if real_growth > 0.15:
            s += 15.0
        elif real_growth > 0:
            s += 7.5
        return s

    def score_valuation(self, pe_r: float) -> float:
        if pe_r < 1.2:
            return 20.0
        if pe_r < 1.5:
            return 10.0
        return 0.0

    def score_institutional(self, ir: float) -> float:
        if ir > 0.05:
            return 25.0
        if ir > 0:
            return 12.5
        return 0.0

    def score_technical(self, vs: float) -> float:
        if vs > 3:
            return 15.0
        if vs > 2:
            return 7.5
        return 0.0

    def score_macro(self, dy: float, bank_rate: float) -> float:
        return 10.0 if dy > bank_rate else 0.0

    def score_gov(self, lr: float, av: float, ir: float,
                  cap_type: str | None, gov_news: int) -> float:
        s = 0.0
        if lr > 1.0:
            s -= 10.0
        elif lr > 0.5:
            s -= 5.0
        if av > 20_000_000_000:
            s += 5.0
        if ir > 0.05:
            s += 5.0
        if cap_type in ("نقدی", "تجدید ارزیابی"):
            s += 5.0
        if gov_news == 1:
            s += 3.0
        return s

    def score_liquidity(self, lp: float) -> float:
        return 5.0 if lp > 0.005 else 0.0

    def score_farabourse(self, dom: float, diff: float) -> float:
        if dom > 0.20 and diff > 0:
            return 10.0
        if dom > 0.20 or diff > 0:
            return 5.0
        return 0.0

    def score_feedstock(self, has_fs: bool, adj: float, orig: float) -> float:
        if not has_fs or orig == 0:
            return 0.0
        if adj > orig:
            return 10.0
        if adj == orig:
            return 5.0
        return 0.0

    # ── Risk helpers ─────────────────────────────────────────────────────

    def risk_ok(self, profile: dict[str, Any] | None) -> bool:
        if profile is None:
            return True
        return not any(profile.get(c, 0) == 1 for c in RISK_FILTER_COLUMNS)

    def neg_filter_count(self, profile: dict[str, Any] | None) -> int:
        if profile is None:
            return 0
        return sum(1 for c in RISK_FILTER_COLUMNS if profile.get(c, 0) == 1)

    # ── Full symbol calculation ──────────────────────────────────────────

    def calculate(
        self,
        symbol: str,
        eps: float,
        shares: float,
        daily_rows: list[dict[str, Any]],
        legal_rows: list[dict[str, Any]],
        profile: dict[str, Any] | None,
        last_snapshot: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Compute all columns for one symbol. Returns a flat dict."""

        # --- 1. Aggregate daily data ---
        price = 0.0
        today_vol = 0
        avg50v = 1.0
        avg30val = 0.0
        chg_pct = 0.0
        atr14 = 0.0
        closes = [float(r.get("price_close", 0) or 0) for r in daily_rows]
        trend_20d = "flat"

        if daily_rows:
            vols = [float(r.get("trade_volume", 0) or 0) for r in daily_rows]
            vals = [float(r.get("trade_value", 0) or 0) for r in daily_rows]

            price = float(daily_rows[0].get("price_close") or
                          daily_rows[0].get("price_last", 0) or 0)
            today_vol = int(vols[0]) if vols else 0
            avg50v = sum(vols[:50]) / max(len(vols[:50]), 1)
            avg30val = sum(vals[:30]) / max(len(vals[:30]), 1)
            chg_pct = float(daily_rows[0].get("price_last_change_pct", 0) or 0)
            atr14 = self._compute_atr(daily_rows, price)

        # ── 2. Legal aggregates ──
        inst_buy = sum(float(r.get("legal_buy_volume", 0) or 0) for r in legal_rows) if legal_rows else 0
        inst_sell = sum(float(r.get("legal_sell_volume", 0) or 0) for r in legal_rows) if legal_rows else 0

        # ── 3. Profile values ──
        ex_rate = float(profile.get("exchange_rate_base", 1) or 1) if profile else 28500
        infl = float(profile.get("inflation_rate", 0) or 0) if profile else 0.0
        eps_prev = float(profile.get("eps_prev_year", eps) or eps) if profile else eps
        ind_pe = float(profile.get("industry_pe", 6.5) or 6.5) if profile else 6.5
        bank_r = float(profile.get("bank_interest_rate", 30) or 30) if profile else 30.0
        nima = float(profile.get("nima_rate", 1) or 1) if profile else 1.0
        free = float(profile.get("free_market_rate", 1) or 1) if profile else 1.0
        loss = float(profile.get("accumulated_loss", 0) or 0) if profile else 0.0
        cap = float(profile.get("registered_capital", 1) or 1) if profile else 1.0
        profit = float(profile.get("net_operating_profit", 1) or 1) if profile else 1.0

        # ── 4. Derived columns (9-13, 17, 27-35, 38-55) ──
        dol_cur = self.dollar_eps(eps, ex_rate)
        dol_prev = self.dollar_eps(eps_prev, ex_rate)
        dol_growth = self.eps_growth(dol_cur, dol_prev)
        real_growth = self.real_eps_growth(eps, eps_prev, infl)
        loss_ratio = self._div(loss, cap)
        live_pe = self.pe(price, eps)
        pe_r = self.pe_ratio(price, eps, ind_pe)
        div_y = self.div_yield(price, eps)
        n_spread = self.nima_spread(free, nima)
        vol_spike = self.vol_spike(today_vol, avg50v)
        liq_pct = self.liq_pct(avg30val, shares, price)
        inst_r = self.inst_ratio(inst_buy, inst_sell, shares)

        # Farabourse
        fv = float(last_snapshot.get("farabourse_volume", 0) or 0) if last_snapshot else 0
        fp = float(last_snapshot.get("farabourse_price", 0) or 0) if last_snapshot else 0
        far_dom = self.farabourse_dom(fv, today_vol)
        far_diff = fp - price

        # Column 42: 20-day trend
        trend_20d = self.trend_label(closes)  # may be up/down/flat

        # ── 5. Filter columns (77-85) — auto-computed ──

        # ── 6. Scores (86-95) ──
        s_f = self.score_fundamental(dol_growth, real_growth)
        s_v = self.score_valuation(pe_r)
        s_i = self.score_institutional(inst_r)
        s_t = self.score_technical(vol_spike)
        s_m = self.score_macro(div_y, bank_r)
        s_g = self.score_gov(loss_ratio, avg30val, inst_r,
                             profile.get("capital_increase_type") if profile else None,
                             profile.get("gov_support_news", 0) if profile else 0)
        s_l = self.score_liquidity(liq_pct)
        s_fb = self.score_farabourse(far_dom, far_diff)
        s_fd = self.score_feedstock(
            bool(profile and profile.get("feedstock_price")),
            0, profit,
        )

        risk = self.risk_ok(profile)
        neg_cnt = self.neg_filter_count(profile)

        # ── 7. Final score (96-97) ──
        raw = (s_f * WEIGHTS["fundamental"] + s_v * WEIGHTS["valuation"]
               + s_i * WEIGHTS["institutional"] + s_t * WEIGHTS["technical"]
               + s_m * WEIGHTS["macro"] + s_g * WEIGHTS["gov_support"]
               + s_l * WEIGHTS["liquidity"] + s_fb * WEIGHTS["farabourse"]
               + s_fd * WEIGHTS["feedstock"])
        final = self._clamp(raw, 0.0, 100.0)

        # ── 8. Adjustments (104-106) ──
        adj = final
        if profile and profile.get("big_ipo", 0) == 1:
            adj -= 5.0
        if n_spread > 1.2:
            adj -= 10.0
        adj = self._clamp(adj, 0.0, 100.0)

        # ── 9. Rule 50/30 (100) & decision (107) ──
        rule_pass = adj >= 70 and risk and neg_cnt < 3
        rule_label = "قبول" if rule_pass else "رد"

        # Stop loss (101)
        sl = max(price - (2 * atr14), price * 0.93)

        # Decision
        decision: str
        if rule_pass and adj >= 70:
            decision = "خرید"
        elif not risk:
            decision = "رد_ریسک"
        elif adj < 70:
            decision = "رد_نمره"
        else:
            decision = "نخرید"

        # ── 10. Assemble result ──
        return {
            # Identifiers
            "symbol": symbol,
            "decision": decision,
            # Prices & valuation
            "current_price": round(price, 0),
            "live_pe": round(live_pe, 1),
            "pe_ratio": round(pe_r, 2),
            "trend_20d": trend_20d,
            # Volume & liquidity
            "volume_spike": round(vol_spike, 2),
            "liquidity_pct": round(liq_pct, 6),
            "institutional_ratio": round(inst_r, 4),
            "nima_free_spread": round(n_spread, 3),
            # Mid-level scores
            "score_fundamental": round(s_f, 1),
            "score_valuation": round(s_v, 1),
            "score_institutional": round(s_i, 1),
            "score_technical": round(s_t, 1),
            "score_macro": round(s_m, 1),
            "score_gov_support": round(s_g, 1),
            "score_liquidity": round(s_l, 1),
            "score_farabourse": round(s_fb, 1),
            "score_feedstock": round(s_fd, 1),
            # Risk & final
            "risk_ok": risk,
            "raw_score": round(raw, 2),
            "final_score": round(final, 1),
            "adjusted_score": round(adj, 1),
            "negative_filters_count": neg_cnt,
            "rule_50_30": rule_label,
            "stop_loss_price": round(sl, 0),
            "position_size": 0,
            # Technical buffers
            "atr_14": round(atr14, 0),
            "price_change_pct": round(chg_pct, 2),
        }


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 3 — Bulk Writer
# ═══════════════════════════════════════════════════════════════════════════

class BulkWriter:
    """Chunked upsert into screener_snapshots and screener_signals."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def write_snapshots(self, rows: list[dict[str, Any]]) -> None:
        """Upsert snapshot rows (ON CONFLICT DO NOTHING)."""
        if not rows:
            return
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        for i in range(0, len(rows), CHUNK_SIZE):
            chunk = rows[i:i + CHUNK_SIZE]
            stmt = pg_insert(ScreenerSnapshot).values(chunk)
            stmt = stmt.on_conflict_do_nothing(
                constraint="screener_snapshots_pkey"
            )
            # NOTE: no explicit begin() — the session from get_session()/
            # endpoint dependency already holds an open transaction.
            await self._session.execute(stmt)

    async def write_signals(self, results: list[dict[str, Any]],
                            now: datetime) -> list[dict[str, Any]]:
        """Insert all signal results. Returns only buy signals."""
        buy_signals = [r for r in results if r["decision"] == "خرید"]

        if not results:
            return buy_signals

        rows: list[dict[str, Any]] = []
        for r in results:
            rows.append({
                "symbol": r["symbol"],
                "generated_at": now,
                "current_price": r["current_price"],
                "live_pe": r["live_pe"],
                "pe_ratio": r["pe_ratio"],
                "institutional_ratio": r["institutional_ratio"],
                "volume_spike": r["volume_spike"],
                "liquidity_pct": r["liquidity_pct"],
                "nima_free_spread": r["nima_free_spread"],
                "score_fundamental": r["score_fundamental"],
                "score_valuation": r["score_valuation"],
                "score_institutional": r["score_institutional"],
                "score_technical": r["score_technical"],
                "score_macro": r["score_macro"],
                "score_gov_support": r["score_gov_support"],
                "score_liquidity": r["score_liquidity"],
                "score_farabourse": r["score_farabourse"],
                "score_feedstock": r["score_feedstock"],
                "risk_ok": r["risk_ok"],
                "raw_score": r["raw_score"],
                "final_score": r["final_score"],
                "adjusted_score": r["adjusted_score"],
                "negative_filters_count": r["negative_filters_count"],
                "rule_50_30": r["rule_50_30"],
                "stop_loss_price": r["stop_loss_price"],
                "position_size": r["position_size"],
                "decision": r["decision"],
            })

        from sqlalchemy.dialects.postgresql import insert as pg_insert

        for i in range(0, len(rows), CHUNK_SIZE):
            chunk = rows[i:i + CHUNK_SIZE]
            stmt = pg_insert(ScreenerSignal).values(chunk)
            stmt = stmt.on_conflict_do_nothing(
                constraint="screener_signals_pkey"
            )
            # NOTE: no explicit begin() — the session from get_session()/
            # endpoint dependency already holds an open transaction.
            await self._session.execute(stmt)

        return buy_signals


# ═══════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════

class Screener110Service:
    """Three-layer orchestrator for the 110-column model on 600 symbols."""

    def __init__(self, session: AsyncSession,
                 total_capital: float = DEFAULT_CAPITAL,
                 brsapi: Any | None = None) -> None:
        self._session = session
        self._brsapi = brsapi
        self._loader = BatchLoader(session, brsapi=brsapi)
        self._calc = VectorCalculator()
        self._writer = BulkWriter(session)
        self.total_capital = total_capital

    async def run_full_cycle(self) -> list[dict[str, Any]]:
        """Execute full pipeline: Load → Calculate → Save.

        Returns buy-signal rows only.
        """
        # screener_snapshots.timestamp is TIMESTAMP WITHOUT TIME ZONE → naive.
        now = datetime.now(UTC).replace(tzinfo=None)
        timings: dict[str, float] = {}

        # ── Phase 1: Load ─────────────────────────────────────────────────
        logger.info("Phase 1/3: Loading batch data...")
        t0 = time.perf_counter()
        data = await self._loader.load_all()
        timings["load"] = time.perf_counter() - t0

        symbols: list[dict[str, Any]] = data["symbols"]
        daily_map: dict = data["daily"]
        legal_map: dict = data["legal"]
        profile_map: dict = data["profiles"]
        snapshot_map: dict = data["snapshots"]

        # ── Phase 2: Calculate ────────────────────────────────────────────
        logger.info("Phase 2/3: Computing %d symbols...", len(symbols))
        t0 = time.perf_counter()

        results: list[dict[str, Any]] = []
        snapshot_rows: list[dict[str, Any]] = []

        for sym_data in symbols:
            sym = sym_data.get("symbol", "")
            if not sym:
                continue

            eps = float(sym_data.get("eps", 0) or 0)
            shares = float(sym_data.get("shares_count", 0) or 0)
            profile = profile_map.get(sym)
            # Use profile EPS if available
            if profile and profile.get("eps_current"):
                eps = float(profile["eps_current"])

            result = self._calc.calculate(
                symbol=sym,
                eps=eps,
                shares=shares,
                daily_rows=daily_map.get(sym, []),
                legal_rows=legal_map.get(sym, []),
                profile=profile,
                last_snapshot=snapshot_map.get(sym),
            )

            # Position size from capital
            sl = result["stop_loss_price"]
            cp = result["current_price"]
            if sl > 0 and cp > sl:
                result["position_size"] = int(
                    (0.01 * self.total_capital) / (cp - sl)
                )

            results.append(result)

            # Prepare snapshot row
            last_snap = snapshot_map.get(sym)
            snapshot_rows.append({
                "symbol": sym,
                "timestamp": now,
                "current_price": cp,
                "today_volume": int(daily_map.get(sym, [{}])[0].get("trade_volume", 0))
                if daily_map.get(sym) else 0,
                "volume_ma_50": float(last_snap.get("volume_ma_50", 0) or 0)
                if last_snap else 0,
                "farabourse_volume": float(last_snap.get("farabourse_volume", 0) or 0)
                if last_snap else 0,
                "farabourse_price": float(last_snap.get("farabourse_price", 0) or 0)
                if last_snap else 0,
                "atr_14": result.get("atr_14", cp * 0.02),
            })

        timings["compute"] = time.perf_counter() - t0

        # ── Phase 3: Save ────────────────────────────────────────────────
        logger.info("Phase 3/3: Saving %d snapshots + %d signals...",
                    len(snapshot_rows), len(results))
        t0 = time.perf_counter()

        await self._writer.write_snapshots(snapshot_rows)
        buy_signals = await self._writer.write_signals(results, now)

        timings["save"] = time.perf_counter() - t0

        # ── Summary ──────────────────────────────────────────────────────
        decisions: dict[str, int] = {}
        for r in results:
            decisions[r["decision"]] = decisions.get(r["decision"], 0) + 1

        total_time = sum(timings.values())
        logger.info(
            "Cycle done [%.2fs total | load=%.2f compute=%.2f save=%.2f] — %s",
            total_time, timings["load"], timings["compute"], timings["save"],
            decisions,
        )

        return buy_signals

    async def run_symbol(self, symbol: str) -> dict[str, Any] | None:
        """Run model for a single symbol (useful for API / debug)."""
        from sqlalchemy import text

        # Symbol data
        q = text("""
            SELECT s.symbol, s.total_shares AS shares_count, s.eps
            FROM symbols s WHERE s.symbol = :sym
        """)
        row = (await self._loader._session.execute(q, {"sym": symbol})).fetchone()
        if not row:
            logger.warning("Symbol %s not found", symbol)
            return None
        sym_dict = dict(row._mapping)

        # Daily history (direct table — the daily_history view is too slow)
        q = text("""
            SELECT b.price_close, b.price_max, b.price_min, b.price_last,
                   b.trade_volume, b.trade_value, b.price_last_change_pct
            FROM brsapi_historical_daily b
            WHERE b.symbol = :sym
            ORDER BY b.gregorian_date DESC LIMIT 60
        """)
        daily = [dict(r._mapping) for r in
                 (await self._loader._session.execute(q, {"sym": symbol})).fetchall()]

        # Legal
        q = text("""
            SELECT drl.legal_buy_volume, drl.legal_sell_volume
            FROM daily_real_legal drl
            JOIN symbols s ON s.id = drl.symbol_id
            WHERE s.symbol = :sym
            ORDER BY drl.trade_date DESC LIMIT 35
        """)
        legal = [dict(r._mapping) for r in
                 (await self._loader._session.execute(q, {"sym": symbol})).fetchall()]

        # Profile
        q = text("SELECT * FROM screener_profiles WHERE symbol = :sym")
        p_row = (await self._loader._session.execute(q, {"sym": symbol})).fetchone()
        profile = dict(p_row._mapping) if p_row else None

        # Last snapshot
        q = text("""
            SELECT * FROM screener_snapshots
            WHERE symbol = :sym ORDER BY timestamp DESC LIMIT 1
        """)
        sp_row = (await self._loader._session.execute(q, {"sym": symbol})).fetchone()
        snap = dict(sp_row._mapping) if sp_row else None

        eps = float(sym_dict.get("eps", 0) or 0)
        if profile and profile.get("eps_current"):
            eps = float(profile["eps_current"])

        return self._calc.calculate(
            symbol=symbol,
            eps=eps,
            shares=float(sym_dict.get("shares_count", 0) or 0),
            daily_rows=daily,
            legal_rows=legal,
            profile=profile,
            last_snapshot=snap,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Standalone entry point
# ═══════════════════════════════════════════════════════════════════════════

async def run_cycle(session: AsyncSession,
                    total_capital: float = DEFAULT_CAPITAL) -> list[dict[str, Any]]:
    """Convenience wrapper — run a full cycle."""
    svc = Screener110Service(session, total_capital=total_capital)
    return await svc.run_full_cycle()
