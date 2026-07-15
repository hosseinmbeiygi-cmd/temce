"""Screener Service — Multi-Stage Pipeline for Smart Money Stock Selection.

5-Phase Architecture (matching the mathematical spec):
  1. Liquidity Screening   — RVOL, value turnover, minimum value
  2. Power & Ownership     — Buyer power, net real money flow, concentration
  3. Price Structure       — Compression, relative strength, close location
  4. Order Flow            — Absorption, microstructure, order imbalance
  5. Trigger Score         — Breakout readiness, resistance proximity

Each phase produces a sub-score in [0, 1].  The final Smart Money Composite
Score (SMC) is the primary ranking metric.

Data Sources (all real, no synthetic/mock data):
  - brsapi_symbol_snapshots  — realtime quote (price, volume, orderbook, real/legal)
  - brsapi_historical_daily  — daily OHLCV history
  - brsapi_historical_real_legal — daily real/legal buy/sell breakdown
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from services.smart_money.scoring_engine import ScoringEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ScreenedSymbol:
    """Result of running the full pipeline on one instrument."""

    symbol: str
    name: str
    market: str
    industry: str
    last_price: float
    change_pct: float
    volume: int
    value: float

    # Phase scores (0 – 1)
    liquidity_score: float = 0.0
    power_score: float = 0.0
    structure_score: float = 0.0
    orderflow_score: float = 0.0
    trigger_score: float = 0.0

    # Composite
    smc_score: float = 0.0
    phase: str = "neutral"

    # Extra info
    rank: int = 0
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Real data builders — map DB snapshots to engine-expected dicts
# ---------------------------------------------------------------------------


def build_real_quote_from_snapshot(snap: dict[str, Any]) -> dict[str, Any]:
    """Build engine quote dict directly from a brsapi_symbol_snapshots row.

    All values are real — no random/mock data.
    """
    close = float(snap.get("price_close") or 0)
    open_ = float(snap.get("price_first") or close)
    high = float(snap.get("price_max") or close)
    low = float(snap.get("price_min") or close)
    last = float(snap.get("price_last") or close)
    volume = int(snap.get("trade_volume") or 0)
    value = float(snap.get("trade_value") or 0)

    # Real / Legal volumes and counts from snapshot
    buy_real_vol = int(snap.get("buy_real_volume") or 0)
    buy_legal_vol = int(snap.get("buy_legal_volume") or 0)
    sell_real_vol = int(snap.get("sell_real_volume") or 0)
    sell_legal_vol = int(snap.get("sell_legal_volume") or 0)
    buy_real_cnt = int(snap.get("buy_real_count") or 0)
    buy_legal_cnt = int(snap.get("buy_legal_count") or 0)
    sell_real_cnt = int(snap.get("sell_real_count") or 0)
    sell_legal_cnt = int(snap.get("sell_legal_count") or 0)

    total_buy_vol = buy_real_vol + buy_legal_vol
    total_sell_vol = sell_real_vol + sell_legal_vol
    total_buy_cnt = buy_real_cnt + buy_legal_cnt
    total_sell_cnt = sell_real_cnt + sell_legal_cnt

    # avg_buy / avg_sell = average trade size per order
    avg_buy = (total_buy_vol / total_buy_cnt) if total_buy_cnt > 0 else 0.0
    avg_sell = (total_sell_vol / total_sell_cnt) if total_sell_cnt > 0 else 0.0

    # real_buy_value / real_sell_value = value of real (حقیقی) trades
    # Approximate: real volume * average price of that day
    avg_price = (high + low + close) / 3.0 if (high + low + close) else close or 1.0
    real_buy_value = buy_real_vol * avg_price
    real_sell_value = sell_real_vol * avg_price

    return {
        "symbol": snap.get("symbol", ""),
        "price_open": open_,
        "price_close": close,
        "price_high": high,
        "price_low": low,
        "price_last": last,
        "price_change": float(snap.get("price_last_change") or 0),
        "price_change_pct": float(snap.get("price_last_change_pct") or 0),
        "volume": volume,
        "value": value,
        "trade_count": int(snap.get("trade_count") or max(1, volume // 5000)),
        "avg_buy": avg_buy,
        "avg_sell": avg_sell,
        "real_buy_value": real_buy_value,
        "real_sell_value": real_sell_value,
        "real_buy_count": buy_real_cnt,
        "real_sell_count": sell_real_cnt,
        "date": snap.get("date", ""),
        "time": snap.get("time", ""),
    }


def build_real_history_from_rows(
    daily_rows: list[dict[str, Any]],
    rl_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build engine history list from real brsapi_historical_daily rows,
    enriched with real/legal data from brsapi_historical_real_legal.

    Returns list sorted oldest-first (engine expects chronological order).
    """
    if not daily_rows:
        return []

    # Build lookup for real/legal data by date
    rl_by_date: dict[str, dict[str, Any]] = {}
    if rl_rows:
        for r in rl_rows:
            dt = r.get("date", "")
            if dt:
                rl_by_date[dt] = r

    history: list[dict[str, Any]] = []
    for row in daily_rows:
        dt = row.get("date", "")
        close = float(row.get("price_close") or 0)
        open_ = float(row.get("price_first") or close)
        high = float(row.get("price_max") or close)
        low = float(row.get("price_min") or close)
        last = float(row.get("price_last") or close)
        volume = int(row.get("trade_volume") or 0)
        value = float(row.get("trade_value") or 0)

        # Merge real/legal data if available
        rl = rl_by_date.get(dt, {})
        buy_real_vol = int(rl.get("buy_real_volume") or 0)
        sell_real_vol = int(rl.get("sell_real_volume") or 0)
        buy_real_cnt = int(rl.get("buy_real_count") or 0)
        sell_real_cnt = int(rl.get("sell_real_count") or 0)
        buy_legal_vol = int(rl.get("buy_legal_volume") or 0)
        sell_legal_vol = int(rl.get("sell_legal_volume") or 0)
        buy_legal_cnt = int(rl.get("buy_legal_count") or 0)
        sell_legal_cnt = int(rl.get("sell_legal_count") or 0)

        total_buy_vol = buy_real_vol + buy_legal_vol
        total_sell_vol = sell_real_vol + sell_legal_vol
        total_buy_cnt = buy_real_cnt + buy_legal_cnt
        total_sell_cnt = sell_real_cnt + sell_legal_cnt

        avg_buy = (total_buy_vol / total_buy_cnt) if total_buy_cnt > 0 else 0.0
        avg_sell = (total_sell_vol / total_sell_cnt) if total_sell_cnt > 0 else 0.0

        avg_price = (high + low + close) / 3.0 if (high + low + close) else close or 1.0
        real_buy_value = buy_real_vol * avg_price
        real_sell_value = sell_real_vol * avg_price

        history.append({
            "symbol": row.get("symbol", ""),
            "date": dt,
            "price_open": open_,
            "price_close": close,
            "price_high": high,
            "price_low": low,
            "price_last": last,
            "volume": volume,
            "value": value,
            "trade_count": int(row.get("trade_count") or 0),
            "avg_buy": avg_buy,
            "avg_sell": avg_sell,
            "real_buy_value": real_buy_value,
            "real_sell_value": real_sell_value,
            "real_buy_count": buy_real_cnt,
            "real_sell_count": sell_real_cnt,
        })

    # Sort oldest first
    history.sort(key=lambda h: h.get("date", ""))
    return history


# ---------------------------------------------------------------------------
# Filter value extraction — maps field names to real snapshot data
# ---------------------------------------------------------------------------


_FILTER_FIELD_MAP: dict[str, str] = {
    "smc_score": "smc_score",
    "liquidity_score": "liquidity_score",
    "power_score": "power_score",
    "structure_score": "structure_score",
    "orderflow_score": "orderflow_score",
    "trigger_score": "trigger_score",
    "phase": "phase",
    "change_pct": "change_pct",
    "volume": "volume",
    "value": "value",
    "last_price": "last_price",
    "pe_ratio": "pe_ratio",
    "pe": "pe_ratio",
    "eps": "eps",
    "market_value": "market_value",
    "market_cap": "market_value",
    "trade_count": "trade_count",
    "price_change_pct": "change_pct",
    "price_change_value": "price_change_value",
    "price_first": "price_first",
    "price_yesterday": "price_yesterday",
    "price_min": "price_min",
    "price_max": "price_max",
    "shares_count": "shares_count",
}


def _get_filter_value(item: ScreenedSymbol, watch: dict[str, Any], field: str) -> float | None:
    """Extract a numeric value from the screened item or watch data."""
    mapped = _FILTER_FIELD_MAP.get(field.lower(), field.lower())
    val = getattr(item, mapped, None)
    if val is not None and isinstance(val, (int, float)):
        return float(val)

    val = item.details.get(mapped)
    if val is not None and isinstance(val, (int, float)):
        return float(val)

    if isinstance(watch, dict):
        for candidate in (mapped, field.lower(), f"price_{field.lower()}", f"trade_{field.lower()}"):
            v = watch.get(candidate)
            if v is not None and isinstance(v, (int, float)):
                return float(v)

    return None


# ---------------------------------------------------------------------------
# Screener pipeline
# ---------------------------------------------------------------------------


class ScreenerPipeline:
    """5-phase pipeline that scores a single instrument via the Smart Money engine."""

    _score_cache: dict[str, tuple[float, ScreenedSymbol]] = {}
    _CACHE_TTL = 30

    def __init__(self) -> None:
        self._engine = ScoringEngine()

    @classmethod
    def _cache_key(cls, symbol: str, quote: dict[str, Any], history: list[dict[str, Any]]) -> str:
        q_fields = ("price_close", "price_last", "volume", "value", "price_change_pct")
        q_hash = tuple(round(quote.get(f, 0), 2) for f in q_fields)
        h_last = history[-1].get("price_close", 0) if history else 0
        return f"{symbol}:{hash(q_hash)}:{h_last:.0f}:{len(history)}"

    @classmethod
    def _cache_purge_expired(cls) -> None:
        now = time.time()
        expired = [k for k, (ts, _) in cls._score_cache.items() if now - ts > cls._CACHE_TTL]
        for k in expired:
            del cls._score_cache[k]

    def run(
        self,
        symbol: str,
        name: str,
        market: str,
        industry: str,
        quote: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> ScreenedSymbol:
        cache_key = self._cache_key(symbol, quote, history)
        now = time.time()
        if cache_key in self._score_cache:
            ts, cached = self._score_cache[cache_key]
            if now - ts < self._CACHE_TTL:
                return cached

        if len(self._score_cache) > 300:
            self._cache_purge_expired()

        try:
            result = self._engine.analyze(quote, history)
        except Exception as exc:
            logger.warning("Screener engine failed for %s: %s", symbol, exc)
            return ScreenedSymbol(
                symbol=symbol, name=name, market=market, industry=industry,
                last_price=quote.get("price_close", 0.0), change_pct=0.0,
                volume=int(quote.get("volume", 0)), value=float(quote.get("value", 0)),
                reason=f"Engine error: {exc}",
            )

        scores = result.get("scores", {})
        penalties = result.get("penalties", {})
        features = result.get("features", {})
        smc = result.get("smart_money_score", 0.0)
        phase = result.get("phase", "neutral")

        # Phase scores
        rvol_n = features.get("rvol_n", 0.0)
        vtr_n = features.get("vtr_n", 0.0)
        pvs = scores.get("accumulation", 0.0)
        liquidity_score = min(1.0, max(0.0, 0.35 * rvol_n + 0.35 * vtr_n + 0.30 * pvs))

        bp_n = features.get("bp_n", 0.0)
        nrmf_n = features.get("nrmf_n", 0.0)
        bc_n = features.get("bc_n", 0.0)
        power_score = min(1.0, max(0.0, 0.40 * bp_n + 0.30 * nrmf_n + 0.15 * bc_n + 0.15 * scores.get("buyer_power", 0.0)))

        rec_n = features.get("rec_n", 0.0)
        clv_n = features.get("clv_n", 0.0)
        rrs = scores.get("breakout_readiness", 0.0)
        ess = scores.get("float_lock", 0.0)
        structure_score = min(1.0, max(0.0, 0.25 * clv_n + 0.25 * rec_n + 0.25 * rrs + 0.25 * ess))

        lss_n = features.get("lss_n", 0.0)
        rmr_n = features.get("rmr_n", 0.0)
        abs_score = scores.get("absorption", 0.0)
        dry_n = features.get("dry_n", 0.0)
        orderflow_score = min(1.0, max(0.0,
            0.30 * abs_score + 0.20 * lss_n + 0.20 * rmr_n + 0.15 * dry_n + 0.15 * scores.get("microstructure", 0.0)))

        br = scores.get("breakout_readiness", 0.0)
        trigger_score = min(1.0, max(0.0, 0.60 * br + 0.20 * rrs + 0.10 * abs_score + 0.10 * ess))

        # Composite with penalties
        dist_risk = penalties.get("distribution_risk", 0.0)
        fake_risk = penalties.get("fake_breakout_risk", 0.0)
        dead_comp = penalties.get("dead_compression", 0.0)
        penalty_factor = 1.0 - 0.15 * dist_risk - 0.10 * fake_risk - 0.08 * dead_comp
        smc_adjusted = max(0.0, smc * max(0.0, penalty_factor))

        reasons = []
        if liquidity_score > 0.6:
            reasons.append("نقدشوندگی بالا")
        if power_score > 0.6:
            reasons.append("ورود پول قوی")
        if structure_score > 0.6:
            reasons.append("ساختار قیمتی مستحکم")
        if orderflow_score > 0.6:
            reasons.append("جذب عرضه فعال")
        if trigger_score > 0.6:
            reasons.append("آماده شکست")
        reason = " · ".join(reasons) if reasons else ("در حال نظارت" if smc_adjusted > 0.4 else "ضعیف")

        details = {
            "liquidity_score": round(liquidity_score, 4),
            "power_score": round(power_score, 4),
            "structure_score": round(structure_score, 4),
            "orderflow_score": round(orderflow_score, 4),
            "trigger_score": round(trigger_score, 4),
            "smc_score": round(smc_adjusted, 4),
            "rvol_n": round(rvol_n, 4),
            "bp_n": round(bp_n, 4),
            "nrmf_n": round(nrmf_n, 4),
            "clv_n": round(clv_n, 4),
            "rec_n": round(rec_n, 4),
            "abs_score": round(abs_score, 4),
        }
        details.update({k: round(v, 4) for k, v in features.items() if isinstance(v, float) and k not in details})

        result_obj = ScreenedSymbol(
            symbol=symbol, name=name, market=market, industry=industry,
            last_price=quote.get("price_close", 0.0),
            change_pct=quote.get("price_change_pct", 0.0),
            volume=int(quote.get("volume", 0)),
            value=float(quote.get("value", 0)),
            liquidity_score=round(liquidity_score, 4),
            power_score=round(power_score, 4),
            structure_score=round(structure_score, 4),
            orderflow_score=round(orderflow_score, 4),
            trigger_score=round(trigger_score, 4),
            smc_score=round(smc_adjusted, 4),
            phase=phase, reason=reason, details=details,
        )

        ScreenerPipeline._score_cache[cache_key] = (now, result_obj)
        return result_obj


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------


class ScreenerService:
    """Main screener service — run the pipeline over a list of instruments.

    Uses real data from PostgreSQL:
      - brsapi_symbol_snapshots for current quote
      - brsapi_historical_daily for daily history
      - brsapi_historical_real_legal for real/legal breakdown

    history_limit: how many days of history to fetch per symbol (default 60).
    """

    _prebuilt_cache: dict[str, tuple[float, dict[str, Any], list[dict[str, Any]]]] = {}
    _PREBUILT_TTL = 20

    def __init__(self, session=None, history_limit: int = 60) -> None:
        self._pipeline = ScreenerPipeline()
        self._session = session
        self._history_limit = history_limit

    async def _fetch_real_history(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch real daily history + real/legal from PostgreSQL."""
        if self._session is None:
            return []

        from sqlalchemy import text

        # Fetch daily OHLCV from daily_history (via symbols FK)
        daily_q = text("""
            SELECT s.symbol, dh.trade_date as date, dh.price_first, dh.price_close,
                   dh.price_max, dh.price_min, dh.price_last,
                   dh.trade_volume, dh.trade_value, dh.trade_count
            FROM daily_history dh
            JOIN symbols s ON s.id = dh.symbol_id
            WHERE s.symbol = :sym
            ORDER BY dh.trade_date DESC
            LIMIT :lim
        """)
        result = await self._session.execute(daily_q, {"sym": symbol, "lim": self._history_limit})
        daily_rows = [dict(row._mapping) for row in result.fetchall()]

        if not daily_rows:
            return []

        # Fetch real/legal breakdown from daily_real_legal
        rl_q = text("""
            SELECT s.symbol, drl.trade_date as date,
                   drl.real_buy_volume as buy_real_volume,
                   drl.real_sell_volume as sell_real_volume,
                   drl.real_buy_count as buy_real_count,
                   drl.real_sell_count as sell_real_count,
                   drl.legal_buy_volume as buy_legal_volume,
                   drl.legal_sell_volume as sell_legal_volume,
                   drl.legal_buy_count as buy_legal_count,
                   drl.legal_sell_count as sell_legal_count
            FROM daily_real_legal drl
            JOIN symbols s ON s.id = drl.symbol_id
            WHERE s.symbol = :sym
            ORDER BY drl.trade_date DESC
            LIMIT :lim
        """)
        rl_result = await self._session.execute(rl_q, {"sym": symbol, "lim": self._history_limit})
        rl_rows = [dict(row._mapping) for row in rl_result.fetchall()]

        return build_real_history_from_rows(daily_rows, rl_rows)

    def _prebuild_sync(self, snap: dict[str, Any], history: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Build quote from snapshot (sync) + pre-fetched history."""
        quote = build_real_quote_from_snapshot(snap)
        return quote, history

    async def _prebuild(self, snap: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Build quote + fetch real history for a snapshot row."""
        sym = snap.get("symbol", "")
        now = time.time()

        if sym in self._prebuilt_cache:
            ts, cached_q, cached_h = self._prebuilt_cache[sym]
            if now - ts < self._PREBUILT_TTL:
                return cached_q, cached_h

        quote = build_real_quote_from_snapshot(snap)
        history = await self._fetch_real_history(sym)
        self._prebuilt_cache[sym] = (now, quote, history)
        return quote, history

    async def screen(
        self,
        instruments: list[dict[str, Any]],
        market_watch: list[dict[str, Any]],
        sort_by: str = "smc_score",
        sort_order: str = "desc",
        limit: int = 50,
        min_score: float = 0.0,
        market: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> tuple[list[ScreenedSymbol], dict[str, Any]]:
        """Run the full 5-phase pipeline over a list of instruments using real data."""
        watch_map: dict[str, dict[str, Any]] = {}
        for w_item in market_watch:
            watch_map[w_item.get("symbol", "")] = w_item

        results: list[ScreenedSymbol] = []
        for instr in instruments:
            sym = instr.get("symbol", "")
            if market and instr.get("market") != market:
                continue
            w = watch_map.get(sym)
            if not w:
                continue

            quote, history = await self._prebuild(w)

            item = self._pipeline.run(
                symbol=sym,
                name=instr.get("name", sym),
                market=instr.get("market", ""),
                industry=instr.get("industry", ""),
                quote=quote,
                history=history,
            )
            if item.smc_score < min_score:
                continue
            results.append(item)

        reverse = sort_order.lower() != "asc"
        results.sort(key=lambda r: getattr(r, sort_by, 0.0), reverse=reverse)

        total_before_pagination = len(results)

        for i, r in enumerate(results, 1):
            r.rank = i

        if page is not None and page_size is not None:
            offset = (page - 1) * page_size
            results = results[offset:offset + page_size]

        paginated_results = results[:limit] if page is None else results

        pagination_info = {
            "total": total_before_pagination,
            "page": page or 1,
            "page_size": page_size or limit,
            "total_pages": (total_before_pagination + (page_size or limit) - 1) // (page_size or limit) if page_size else 1,
        }

        return paginated_results, pagination_info

    async def screen_with_filters(
        self,
        instruments: list[dict[str, Any]],
        market_watch: list[dict[str, Any]],
        filters: list[dict[str, Any]] | None = None,
        filter_logic: str = "and",
        sort_by: str = "smc_score",
        sort_order: str = "desc",
        limit: int = 100,
        min_score: float = 0.0,
        market: str | None = None,
        include_details: bool = False,
        page: int | None = None,
        page_size: int | None = None,
    ) -> tuple[list[ScreenedSymbol], dict[str, Any]]:
        """Run the pipeline with dynamic filter criteria on real data."""
        watch_map: dict[str, dict[str, Any]] = {}
        for w_item in market_watch:
            watch_map[w_item.get("symbol", "")] = w_item

        all_scored: list[ScreenedSymbol] = []
        for instr in instruments:
            sym = instr.get("symbol", "")
            if market and instr.get("market") != market:
                continue
            w = watch_map.get(sym)
            if not w:
                continue

            quote, history = await self._prebuild(w)

            item = self._pipeline.run(
                symbol=sym,
                name=instr.get("name", sym),
                market=instr.get("market", ""),
                industry=instr.get("industry", ""),
                quote=quote,
                history=history,
            )
            if item.smc_score < min_score:
                continue

            if filters and not self._apply_filter(item, w, filters, filter_logic):
                continue

            if include_details:
                for real_field in ("pe_ratio", "eps", "market_value", "trade_count",
                                   "price_change_value", "price_first", "price_yesterday",
                                   "price_min", "price_max", "shares_count"):
                    if real_field in w and w[real_field] is not None:
                        item.details[real_field] = float(w[real_field])

            all_scored.append(item)

        reverse = sort_order.lower() != "asc"
        all_scored.sort(key=lambda r: getattr(r, sort_by, 0.0), reverse=reverse)

        for i, r in enumerate(all_scored, 1):
            r.rank = i

        results = all_scored[:limit]

        total_before_pagination = len(results)

        if page is not None and page_size is not None:
            offset = (page - 1) * page_size
            paginated = results[offset:offset + page_size]
        else:
            paginated = results

        stats = self._compute_stats(paginated, all_scored, market_watch)
        stats["total"] = total_before_pagination
        stats["page"] = page or 1
        stats["page_size"] = page_size or limit
        stats["total_pages"] = (total_before_pagination + (page_size or limit) - 1) // (page_size or limit) if page_size else 1

        return paginated, stats

    def _compute_stats(
        self,
        results: list[ScreenedSymbol],
        all_scored: list[ScreenedSymbol],
        market_watch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        total = len(results)
        if total == 0:
            return {
                "total": 0, "avg_smc": 0.0, "avg_liquidity": 0.0,
                "avg_power": 0.0, "avg_change_pct": 0.0, "high_score_count": 0,
                "phase_distribution": {}, "top_industry": "", "top_industry_count": 0,
            }

        avg_smc = sum(r.smc_score for r in results) / total
        avg_liq = sum(r.liquidity_score for r in results) / total
        avg_pow = sum(r.power_score for r in results) / total
        avg_chg = sum(r.change_pct for r in results) / total
        high_score = sum(1 for r in results if r.smc_score >= 0.6)

        phases: dict[str, int] = {}
        for r in results:
            phases[r.phase] = phases.get(r.phase, 0) + 1

        industries: dict[str, int] = {}
        for r in results:
            if r.industry:
                industries[r.industry] = industries.get(r.industry, 0) + 1
        top_ind = max(industries, key=industries.get) if industries else ""
        top_ind_count = industries.get(top_ind, 0)

        return {
            "total": total,
            "avg_smc": round(avg_smc, 4),
            "avg_liquidity": round(avg_liq, 4),
            "avg_power": round(avg_pow, 4),
            "avg_change_pct": round(avg_chg, 4),
            "high_score_count": high_score,
            "phase_distribution": phases,
            "top_industry": top_ind,
            "top_industry_count": top_ind_count,
        }

    @staticmethod
    def _apply_filter(
        item: ScreenedSymbol,
        watch: dict[str, Any],
        filters: list[dict[str, Any]],
        logic: str,
    ) -> bool:
        results: list[bool] = []

        for f in filters:
            field = f.get("field", "")
            operator = f.get("operator", "gte")
            value = f.get("value")
            value_to = f.get("value_to")

            item_val = _get_filter_value(item, watch, field)
            if item_val is None:
                results.append(False)
                continue

            try:
                item_val = float(item_val)
                val = float(value) if value is not None else 0
                val_to = float(value_to) if value_to is not None else 0
            except (TypeError, ValueError):
                results.append(False)
                continue

            if operator == "gte":
                results.append(item_val >= val)
            elif operator == "lte":
                results.append(item_val <= val)
            elif operator == "gt":
                results.append(item_val > val)
            elif operator == "lt":
                results.append(item_val < val)
            elif operator == "eq":
                results.append(abs(item_val - val) < max(val * 0.01, 0.001))
            elif operator == "neq":
                results.append(abs(item_val - val) >= max(val * 0.01, 0.001))
            elif operator == "between":
                results.append(val <= item_val <= val_to)
            else:
                results.append(True)

        if not results:
            return True
        return any(results) if logic == "or" else all(results)

    def screen_by_symbol(
        self,
        instruments: list[dict[str, Any]],
        market_watch: list[dict[str, Any]],
        symbol: str,
    ) -> ScreenedSymbol | None:
        """Run the pipeline for a single symbol (sync mode, no async history fetch)."""
        instr = next((i for i in instruments if i.get("symbol") == symbol), None)
        if not instr:
            return None
        w = next((mw for mw in market_watch if mw.get("symbol") == symbol), None)
        if not w:
            return None

        quote = build_real_quote_from_snapshot(w)
        return self._pipeline.run(
            symbol=symbol,
            name=instr.get("name", symbol),
            market=instr.get("market", ""),
            industry=instr.get("industry", ""),
            quote=quote,
            history=[],
        )
