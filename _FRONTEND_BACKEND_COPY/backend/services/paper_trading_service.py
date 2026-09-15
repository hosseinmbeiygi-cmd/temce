"""Paper Trading Service — simulated trading ledger driven by generated signals.

Three responsibilities:

1. **Signal journaling** — every pipeline run persists a full snapshot of each
   generated signal into ``paper_signal_snapshots`` (the daily journal the user
   asked for: all signal fields + the complete serialized payload).

2. **Trade ledger** — a simulated ``buy`` signal opens a long position in
   ``paper_trades``. Positions are closed manually (via the API) or
   automatically when a target / stop-loss / reverse signal / max-hold window
   is reached. P&L is computed on close.

3. **Accounting** — per-trade P&L plus a daily equity curve in
   ``paper_equity_history`` so the user can see how much profit/loss the
   generated signals produce over time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import PaginatedResult, Result
from core.time import utc_now_naive
from models.paper_trading import (
    PaperEquityModel,
    PaperSignalSnapshotModel,
    PaperTradeModel,
)

logger = get_logger(__name__)

DEFAULT_INITIAL_CAPITAL = 1_000_000_000.0  # 1B Rial simulated account
MAX_HOLDING_DAYS = 30  # force-close open positions after this many days
MIN_PAPER_TRADES_FOR_VALIDATION = 30  # v2:124 - trade-count based, not calendar weeks


class PaperTradingService:
    """Simulated trading service built on top of the generated signals."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── 1. Signal journaling ──────────────────────────────────────────────

    async def snapshot_signals(
        self,
        signals: list[dict[str, Any]],
        batch_id: str | None = None,
    ) -> Result[int]:
        """Persist a full snapshot of each generated signal (journal entry).

        Args:
            signals: list of signal dicts (already enriched by the orchestrator).
            batch_id: optional batch identifier; defaults to a new id.

        Returns:
            Result with the number of persisted snapshots.
        """
        batch_id = batch_id or new_id("batch")
        inserted = 0
        existing_keys = await self._existing_snapshot_keys(signals)
        try:
            for sig in signals:
                try:
                    snap = self._signal_to_snapshot(sig, batch_id)
                except Exception:
                    logger.exception("Failed to build snapshot for signal %s", sig.get("symbol"))
                    continue
                # Dedupe: skip if the same signal (date + symbol + direction + timeframe)
                # was already journaled today — prevents duplicates when the job and a
                # manual pipeline run on the same day.
                key = (
                    snap.generated_at.strftime("%Y-%m-%d"),
                    snap.symbol,
                    snap.direction,
                    snap.timeframe,
                )
                if key in existing_keys:
                    continue
                existing_keys.add(key)
                self.session.add(snap)
                inserted += 1
            await self.session.commit()
            if inserted:
                logger.info("Paper journal: stored %d signal snapshots (batch %s)", inserted, batch_id)
            return Result.ok(inserted)
        except Exception as exc:
            await self.session.rollback()
            logger.exception("Paper journal batch failed")
            return Result.fail(str(exc))

    def _signal_to_snapshot(self, sig: dict[str, Any], batch_id: str) -> PaperSignalSnapshotModel:
        """Map an enriched signal dict onto the snapshot model (full journal entry)."""
        generated = sig.get("generated_at") or sig.get("timestamp") or utc_now_naive()
        if isinstance(generated, str):
            try:
                generated = datetime.fromisoformat(generated.replace("Z", "+00:00"))
            except ValueError:
                generated = utc_now_naive()
        if generated.tzinfo is not None:
            generated = generated.astimezone().replace(tzinfo=None)

        raw_price = sig.get("price") or sig.get("entry_price")
        price = float(str(raw_price)) if raw_price is not None else None

        return PaperSignalSnapshotModel(
            id=new_id("psnap"),
            batch_id=batch_id,
            generated_at=generated,
            symbol=str(sig.get("symbol") or ""),
            name=str(sig.get("name") or sig.get("company_name") or ""),
            market=str(sig.get("market") or "stock"),
            direction=str(sig.get("direction") or "hold"),
            timeframe=str(sig.get("timeframe") or sig.get("timeframe_filter") or "daily"),
            source=str(sig.get("source") or sig.get("signal_source") or ""),
            entry_zone=str(sig.get("entry_zone") or sig.get("entry") or ""),
            stop_loss=str(sig.get("stop_loss") or sig.get("sl") or ""),
            targets=str(sig.get("targets") or sig.get("target") or ""),
            risk_reward=str(sig.get("risk_reward") or sig.get("rr") or ""),
            position_sizing=str(sig.get("position_sizing") or sig.get("position_size") or ""),
            confirmation_condition=str(sig.get("confirmation_condition") or sig.get("confirmation") or ""),
            reason=str(sig.get("reason") or sig.get("message") or ""),
            invalidation=str(sig.get("invalidation") or ""),
            trailing_stop=str(sig.get("trailing_stop") or ""),
            price=price,
            change_pct=float(sig.get("change_pct") or 0) if sig.get("change_pct") else None,
            score=float(sig.get("score") or sig.get("total_score") or 0)
            if (sig.get("score") or sig.get("total_score"))
            else None,
            strength=float(sig.get("strength") or sig.get("signal_strength") or 0)
            if (sig.get("strength") or sig.get("signal_strength"))
            else None,
            confidence=float(sig.get("confidence") or sig.get("confidence_score") or 0)
            if (sig.get("confidence") or sig.get("confidence_score"))
            else None,
            full_signal=sig,
        )

    # ── 2. Trade ledger ────────────────────────────────────────────────────

    async def open_trade(
        self,
        snapshot_id: str,
        quantity: float = 0,
        capital_allocated: float = 0,
        entry_price: float | None = None,
        entry_notes: str | None = None,
    ) -> Result[dict[str, Any]]:
        """Open a simulated long position from a stored buy signal snapshot."""
        snap = await self.session.get(PaperSignalSnapshotModel, snapshot_id)
        if snap is None:
            return Result.fail(f"Snapshot {snapshot_id} not found")
        if snap.direction not in ("buy", "BUY"):
            return Result.fail("Only buy signals can open a long position")

        price = entry_price or snap.price or 0
        if price <= 0:
            return Result.fail("Signal has no entry price — cannot open trade")

        # Derive target/stop prices from the signal strings when possible.
        stop = self._parse_price(snap.stop_loss)
        if stop is None or stop <= 0:
            stop = price * 0.95

        target1, target2 = self._parse_targets(snap.targets, price)
        if target1 is None or target1 <= 0:
            target1 = price * 1.08
        if target2 is None or target2 <= 0:
            target2 = target1 * 1.08

        if capital_allocated <= 0:
            capital_allocated = min(price * 100, DEFAULT_INITIAL_CAPITAL * 0.1)
        if quantity <= 0:
            quantity = round(capital_allocated / price, 2)

        trade = PaperTradeModel(
            id=new_id("ptrade"),
            signal_snapshot_id=snap.id,
            symbol=snap.symbol,
            name=snap.name,
            market=snap.market,
            timeframe=snap.timeframe,
            source=snap.source,
            confidence=snap.confidence,
            score=snap.score,
            entry_price=price,
            stop_loss_price=stop,
            target1_price=target1,
            target2_price=target2,
            quantity=quantity,
            capital_allocated=capital_allocated,
            opened_at=utc_now_naive(),
            entry_notes=entry_notes or snap.reason,
            status="open",
        )
        self.session.add(trade)
        await self.session.commit()
        logger.info("Paper trade opened: %s @ %.0f qty %.0f", trade.symbol, price, quantity)
        return Result.ok(self._trade_to_dict(trade))

    async def close_trade(
        self,
        trade_id: str,
        exit_price: float | None = None,
        exit_reason: str = "manual",
        exit_notes: str | None = None,
    ) -> Result[dict[str, Any]]:
        """Close an open paper trade and compute P&L."""
        trade = await self.session.get(PaperTradeModel, trade_id)
        if trade is None:
            return Result.fail(f"Trade {trade_id} not found")
        if trade.status != "open":
            return Result.fail("Trade is already closed")

        price = exit_price or await self._latest_price(trade.symbol, trade.market) or trade.entry_price
        trade.exit_price = price
        trade.status = "closed"
        trade.exit_reason = exit_reason
        trade.exit_notes = exit_notes
        trade.closed_at = utc_now_naive()

        qty = trade.quantity or 0
        trade.pnl = (price - trade.entry_price) * qty
        trade.pnl_pct = ((price - trade.entry_price) / trade.entry_price * 100) if trade.entry_price else 0.0
        holding = trade.closed_at - (trade.opened_at or trade.closed_at)
        trade.holding_days = max(1, holding.days) if holding.days >= 0 else 1

        await self.session.commit()
        logger.info(
            "Paper trade closed: %s @ %.0f → %.0f pnl %.0f (%.2f%%)",
            trade.symbol,
            trade.entry_price,
            price,
            trade.pnl or 0,
            trade.pnl_pct or 0,
        )
        await self._record_equity()
        return Result.ok(self._trade_to_dict(trade))

    async def auto_close_due_trades(self) -> Result[int]:
        """Close open trades whose target / stop / reverse-signal / max-hold fired.

        Called by a daily maintenance job. Returns the number of closed trades.
        """
        from sqlalchemy import select

        stmt = select(PaperTradeModel).where(PaperTradeModel.status == "open")
        rows = (await self.session.execute(stmt)).scalars().all()
        closed = 0
        for trade in rows:
            price = await self._latest_price(trade.symbol, trade.market)
            if not price:
                continue
            now = utc_now_naive()
            opened = trade.opened_at or now
            reason: str | None = None
            if trade.stop_loss_price and price <= trade.stop_loss_price:
                reason = "stop_loss"
            elif trade.target1_price and price >= trade.target1_price:
                reason = "target_hit"
            elif (now - opened).days >= MAX_HOLDING_DAYS:
                reason = "max_hold"
            if reason:
                await self.close_trade(trade.id, exit_price=price, exit_reason=reason)
                closed += 1
        return Result.ok(closed)

    # ── 3. Accounting / dashboard ──────────────────────────────────────────

    async def get_dashboard(self) -> dict[str, Any]:
        """Aggregate P&L stats for the paper account."""
        from sqlalchemy import func

        total_result = await self.session.execute(select(func.count()).select_from(PaperTradeModel))
        total = total_result.scalar() or 0

        closed_result = await self.session.execute(select(PaperTradeModel).where(PaperTradeModel.status == "closed"))
        closed = closed_result.scalars().all()

        open_result = await self.session.execute(select(PaperTradeModel).where(PaperTradeModel.status == "open"))
        open_trades = open_result.scalars().all()

        realized = sum(t.pnl or 0 for t in closed)
        wins = [t for t in closed if (t.pnl or 0) > 0]
        losses = [t for t in closed if (t.pnl or 0) < 0]
        win_rate = (len(wins) / len(closed) * 100) if closed else 0.0

        gross_profit = sum(t.pnl or 0 for t in wins)
        gross_loss = sum(t.pnl or 0 for t in losses)
        profit_factor = (gross_profit / abs(gross_loss)) if gross_loss else (999.0 if gross_profit else 0.0)

        avg_win = (gross_profit / len(wins)) if wins else 0.0
        avg_loss = (gross_loss / len(losses)) if losses else 0.0
        # Expectancy (v1:24)
        total_closed = len(closed)
        expectancy = (
            (len(wins) / total_closed * avg_win - len(losses) / total_closed * abs(avg_loss)) if total_closed else 0.0
        )

        # Open position mark-to-market value using latest prices
        open_value = 0.0
        for t in open_trades:
            price = await self._latest_price(t.symbol, t.market) or t.entry_price
            open_value += (price - t.entry_price) * (t.quantity or 0)

        equity = DEFAULT_INITIAL_CAPITAL + realized + open_value
        # Validation readiness: trade-count based (v2:124) not calendar weeks
        is_ready = total_closed >= MIN_PAPER_TRADES_FOR_VALIDATION
        # Expectancy significance via bootstrap when enough trades
        expectancy_pvalue: float | None = None
        is_significant: bool | None = None
        if total_closed >= 10:
            try:
                from backtesting.analytics.significance import bootstrap_expectancy

                pnls = [float(t.pnl or 0) for t in closed]
                sig = bootstrap_expectancy(pnls)
                expectancy_pvalue = sig["p_value"]
                is_significant = sig["is_significant"]
            except Exception:
                pass

        return {
            "initial_capital": DEFAULT_INITIAL_CAPITAL,
            "total_trades": total,
            "open_trades": len(open_trades),
            "closed_trades": len(closed),
            "realized_pnl": round(realized, 0),
            "unrealized_pnl": round(open_value, 0),
            "total_pnl": round(realized + open_value, 0),
            "win_rate": round(win_rate, 2),
            "wins": len(wins),
            "losses": len(losses),
            "gross_profit": round(gross_profit, 0),
            "gross_loss": round(gross_loss, 0),
            "profit_factor": round(profit_factor, 2),
            "avg_win": round(avg_win, 0),
            "avg_loss": round(avg_loss, 0),
            "expectancy": round(expectancy, 0),
            "expectancy_pvalue": expectancy_pvalue,
            "is_significant": is_significant,
            "equity": round(equity, 0),
            "validation_ready": is_ready,
            "min_trades_required": MIN_PAPER_TRADES_FOR_VALIDATION,
            "updated_at": utc_now_naive().isoformat(),
        }

    async def list_trades(
        self,
        status: str | None = None,
        symbol: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Result[PaginatedResult[dict[str, Any]]]:
        """List paper trades with optional filters."""
        from sqlalchemy import func

        stmt = select(PaperTradeModel)
        count_stmt = select(func.count()).select_from(PaperTradeModel)
        if status:
            stmt = stmt.where(PaperTradeModel.status == status)
            count_stmt = count_stmt.where(PaperTradeModel.status == status)
        if symbol:
            stmt = stmt.where(PaperTradeModel.symbol == symbol)
            count_stmt = count_stmt.where(PaperTradeModel.symbol == symbol)

        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = stmt.order_by(desc(PaperTradeModel.opened_at)).offset((page - 1) * page_size).limit(page_size)
        rows = (await self.session.execute(stmt)).scalars().all()
        items = [self._trade_to_dict(t) for t in rows]
        return Result.ok(
            PaginatedResult(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    async def list_snapshots(
        self,
        page: int = 1,
        page_size: int = 50,
        symbol: str | None = None,
        market: str | None = None,
        direction: str | None = None,
    ) -> Result[PaginatedResult[dict[str, Any]]]:
        """List the signal journal (daily signal snapshots)."""
        from sqlalchemy import func

        stmt = select(PaperSignalSnapshotModel)
        count_stmt = select(func.count()).select_from(PaperSignalSnapshotModel)
        if symbol:
            stmt = stmt.where(PaperSignalSnapshotModel.symbol == symbol)
            count_stmt = count_stmt.where(PaperSignalSnapshotModel.symbol == symbol)
        if market:
            stmt = stmt.where(PaperSignalSnapshotModel.market == market)
            count_stmt = count_stmt.where(PaperSignalSnapshotModel.market == market)
        if direction:
            stmt = stmt.where(PaperSignalSnapshotModel.direction == direction)
            count_stmt = count_stmt.where(PaperSignalSnapshotModel.direction == direction)

        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            stmt.order_by(desc(PaperSignalSnapshotModel.generated_at)).offset((page - 1) * page_size).limit(page_size)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        items = [self._snapshot_to_dict(s) for s in rows]
        return Result.ok(
            PaginatedResult(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    async def get_equity_history(self, limit: int = 90) -> list[dict[str, Any]]:
        """Return the daily equity curve (oldest → newest, last ``limit`` rows)."""
        stmt = select(PaperEquityModel).order_by(desc(PaperEquityModel.date)).limit(limit)
        rows = list((await self.session.execute(stmt)).scalars().all())
        rows.reverse()
        return [
            {
                "date": r.date,
                "equity": r.equity,
                "cash": r.cash or 0,
                "open_value": r.open_value or 0,
                "realized_pnl": r.realized_pnl or 0,
                "open_positions": r.open_positions or 0,
                "total_closed": r.total_closed or 0,
            }
            for r in rows
        ]

    async def _record_equity(self) -> None:
        """Write today's equity row (upsert by date)."""
        try:
            dashboard = await self.get_dashboard()
            today = utc_now_naive().strftime("%Y-%m-%d")
            stmt = select(PaperEquityModel).where(PaperEquityModel.date == today)
            existing = (await self.session.execute(stmt)).scalar_one_or_none()
            if existing is None:
                existing = PaperEquityModel(id=new_id("peq"), date=today, equity=0)
            existing.equity = dashboard["equity"]
            existing.realized_pnl = dashboard["realized_pnl"]
            existing.open_value = dashboard["unrealized_pnl"]
            existing.cash = DEFAULT_INITIAL_CAPITAL + dashboard["realized_pnl"]
            existing.open_positions = dashboard["open_trades"]
            existing.total_closed = dashboard["closed_trades"]
            self.session.add(existing)
            await self.session.commit()
        except Exception:
            logger.exception("Failed to record paper equity for today")
            await self.session.rollback()

    # ── Helpers ────────────────────────────────────────────────────────────

    async def _existing_snapshot_keys(self, signals: list[dict[str, Any]]) -> set[tuple[str, str, str, str]]:
        """Return the set of (date, symbol, direction, timeframe) already journaled.

        Used to dedupe snapshots so the same signal isn't stored twice when the
        daily job and a manual pipeline run on the same day.
        """
        keys: set[tuple[str, str, str, str]] = set()
        if not signals:
            return keys
        try:
            from datetime import timedelta

            recent = utc_now_naive() - timedelta(days=2)
            stmt = select(
                PaperSignalSnapshotModel.generated_at,
                PaperSignalSnapshotModel.symbol,
                PaperSignalSnapshotModel.direction,
                PaperSignalSnapshotModel.timeframe,
            ).where(PaperSignalSnapshotModel.generated_at >= recent)
            rows = (await self.session.execute(stmt)).all()
            for r in rows:
                keys.add((r[0].strftime("%Y-%m-%d"), r[1], r[2], r[3]))
        except Exception:
            logger.exception("Failed to load existing snapshot keys")
        return keys

    def _trade_to_dict(self, t: PaperTradeModel) -> dict[str, Any]:
        return {
            "id": t.id,
            "signal_snapshot_id": t.signal_snapshot_id,
            "symbol": t.symbol,
            "name": t.name or "",
            "market": t.market,
            "timeframe": t.timeframe,
            "source": t.source or "",
            "confidence": t.confidence,
            "score": t.score,
            "entry_price": t.entry_price,
            "stop_loss_price": t.stop_loss_price,
            "target1_price": t.target1_price,
            "target2_price": t.target2_price,
            "quantity": t.quantity or 0,
            "capital_allocated": t.capital_allocated or 0,
            "opened_at": t.opened_at.isoformat() if t.opened_at else None,
            "entry_notes": t.entry_notes,
            "status": t.status,
            "exit_price": t.exit_price,
            "exit_reason": t.exit_reason,
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            "exit_notes": t.exit_notes,
            "pnl": t.pnl,
            "pnl_pct": t.pnl_pct,
            "holding_days": t.holding_days,
        }

    def _snapshot_to_dict(self, s: PaperSignalSnapshotModel) -> dict[str, Any]:
        return {
            "id": s.id,
            "batch_id": s.batch_id,
            "generated_at": s.generated_at.isoformat() if s.generated_at else None,
            "symbol": s.symbol,
            "name": s.name or "",
            "market": s.market,
            "direction": s.direction,
            "timeframe": s.timeframe,
            "source": s.source or "",
            "entry_zone": s.entry_zone,
            "stop_loss": s.stop_loss,
            "targets": s.targets,
            "risk_reward": s.risk_reward,
            "position_sizing": s.position_sizing,
            "confirmation_condition": s.confirmation_condition,
            "reason": s.reason,
            "invalidation": s.invalidation,
            "trailing_stop": s.trailing_stop,
            "price": s.price,
            "change_pct": s.change_pct,
            "score": s.score,
            "strength": s.strength,
            "confidence": s.confidence,
            "full_signal": s.full_signal,
        }

    @staticmethod
    def _parse_price(value: str | None) -> float | None:
        """Extract the first numeric value from a free-text price string."""
        if not value:
            return None
        import re

        m = re.search(r"[\d.,]+", str(value))
        if not m:
            return None
        try:
            return float(m.group(0).replace(",", ""))
        except ValueError:
            return None

    @staticmethod
    def _parse_targets(targets_str: str | None, entry_price: float) -> tuple[float | None, float | None]:
        """Parse target1 and target2 from a free-text targets string.

        Handles formats like:
            - "15000 | 17000"
            - "هدف اول: 15000 | هدف دوم: 17000"
            - "15000"
        Returns (target1, target2) where target2 is None if not found.
        """
        if not targets_str:
            return None, None
        import re

        numbers = re.findall(r"[\d.,]+", str(targets_str))
        parsed = [float(n.replace(",", "")) for n in numbers if n.replace(",", "").replace(".", "").isdigit()]

        if not parsed:
            return None, None

        target1 = parsed[0] if len(parsed) >= 1 else None
        target2 = parsed[1] if len(parsed) >= 2 else None
        return target1, target2

    async def _latest_price(self, symbol: str, market: str) -> float | None:
        """Best-effort latest close price for a symbol across known sources."""
        try:
            tables = {
                "stock": "brsapi_historical_daily",
                "gold": "brsapi_gold_currency_pro_daily_history",
                "currency": "brsapi_gold_currency_pro_daily_history",
                "commodity": "brsapi_gold_currency_pro_daily_history",
                "ime": "brsapi_ime_physical_trades",
                "crypto": "brsapi_gold_currency_pro_daily_history",
                "option": "brsapi_historical_daily",
            }
            table = tables.get(market, "brsapi_historical_daily")
            try:
                r = await self.session.execute(
                    text(
                        f"SELECT price_close FROM {table} "
                        "WHERE symbol = :sym AND price_close > 0 "
                        "ORDER BY created_at DESC NULLS LAST LIMIT 1"
                    ),
                    {"sym": symbol},
                )
                row = r.fetchone()
                if row and row[0]:
                    return float(row[0])
            except Exception:
                pass
            # Fallback: symbol snapshot
            r = await self.session.execute(
                text(
                    "SELECT price_close FROM brsapi_symbol_snapshots "
                    "WHERE symbol = :sym AND price_close > 0 "
                    "ORDER BY fetched_at DESC LIMIT 1"
                ),
                {"sym": symbol},
            )
            row = r.fetchone()
            return float(row[0]) if row and row[0] else None
        except Exception:
            logger.debug("No latest price for %s/%s", market, symbol)
            return None
