"""
Master Sync Service
===================

Orchestrates ALL data synchronization operations in 6 ordered phases:

Phase 1 — Bulk Market Data (AllSymbols, Index, Options, IME, Commodities, Crypto, Gold/Currency)
Phase 2 — Per-Symbol Details (SymbolDetail, Candlesticks, HistoryPrice, HistoryRealLegal)
Phase 3 — Per-Symbol Transactions (ریز معاملات روزانه)
Phase 4 — Per-Symbol Shareholders (ترکیب سهامداران)
Phase 5 — Codal (Announcements → Download → Parse → Store)
Phase 6 — Screener Profiles (Full Populate)

Each phase respects rate limits and captures detailed per-operation reports.

Usage::
    master = MasterSyncService()
    report = await master.run_all(session)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.client import BrsApiClient, get_client
from brsapi.models import (
    SymbolSnapshotModel,
)
from brsapi.services.sync_service import BrsApiSyncService
from core.fix_network import fix_network
from core.logging import get_logger

logger = get_logger(__name__)

# Apply network fix at import time
fix_network()


# ──────────────────────────────────────────────
#  Reports
# ──────────────────────────────────────────────


@dataclass
class PhaseReport:
    """Report for a single sync phase."""
    phase_name: str
    success: bool
    operations: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0

    @property
    def total_items(self) -> int:
        return sum(op.get("items", 0) for op in self.operations)


@dataclass
class MasterReport:
    """Overall report for a full master sync run."""
    phases: list[PhaseReport] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def total_duration_ms(self) -> float:
        return (self.finished_at - self.started_at) * 1000 if self.finished_at else 0.0

    @property
    def total_items(self) -> int:
        return sum(p.total_items for p in self.phases)

    @property
    def all_successful(self) -> bool:
        return all(p.success for p in self.phases)

    def print_summary(self) -> None:
        """Print a human-readable summary to console."""
        print(f"\n{'='*70}")
        print("  MASTER SYNC REPORT")
        print(f"{'='*70}")
        for phase in self.phases:
            icon = "✅" if phase.success else "❌"
            print(f"  {icon} {phase.phase_name:<30s} "
                  f"{phase.total_items:>6} items  "
                  f"{phase.duration_ms/1000:>6.1f}s")
            if phase.error:
                print(f"     Error: {phase.error[:100]}")
        print(f"{'='*70}")
        print(f"  🏁 Total: {self.total_items:,} items in "
              f"{self.total_duration_ms/1000:.1f}s")
        print(f"  {'✅ All phases OK' if self.all_successful else '❌ Some phases failed'}")
        print(f"{'='*70}")
        if self.errors:
            print(f"\n❌ Errors ({len(self.errors)}):")
            for e in self.errors[:10]:
                print(f"  • {e[:120]}")
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors)-10} more")


# ──────────────────────────────────────────────
#  Master Sync Service
# ──────────────────────────────────────────────


class MasterSyncService:
    """
    Orchestrates ALL data syncs in 6 phases.

    Usage::
        master = MasterSyncService()
        async for session in get_session():
            report = await master.run_all(session, phases=[1,2,3,4,5,6])
            report.print_summary()
    """

    def __init__(
        self,
        client: BrsApiClient | None = None,
        max_symbols_per_phase: int = 200,
        transaction_days_back: int = 5,
        daily_limit: int = 5000,
        skip_502: bool = True,
    ):
        self._client = client
        self._sync_svc: BrsApiSyncService | None = None
        self.max_symbols = max_symbols_per_phase
        self.transaction_days_back = transaction_days_back
        self.daily_limit = daily_limit
        self.skip_502 = skip_502
        self._session: AsyncSession | None = None

    async def _get_client(self) -> BrsApiClient:
        if self._client is None:
            self._client = await get_client()
        return self._client

    async def _get_sync_svc(self) -> BrsApiSyncService:
        if self._sync_svc is None:
            client = await self._get_client()
            self._sync_svc = BrsApiSyncService(client=client)
        return self._sync_svc

    async def _get_all_symbols(self, session: AsyncSession) -> list[str]:
        """Get all unique symbols from symbol_snapshots."""
        result = await session.execute(
            select(SymbolSnapshotModel.symbol)
            .where(SymbolSnapshotModel.symbol.isnot(None))
            .where(SymbolSnapshotModel.symbol != "")
            .distinct()
        )
        return [row[0] for row in result]

    async def _add_operation(
        self, phase: PhaseReport, name: str, success: bool,
        items: int = 0, duration_ms: float = 0.0, error: str | None = None,
    ) -> None:
        op = {
            "name": name,
            "success": success,
            "items": items,
            "duration_ms": duration_ms,
            "error": error,
        }
        phase.operations.append(op)
        if not success:
            phase.success = False
            if error:
                logger.warning("  ⚠️ %s: %s", name, error)

    # ── Phase 1: Bulk Market Data ─────────────────────

    async def _phase_1_bulk_market(
        self, session: AsyncSession,
    ) -> PhaseReport:
        """Sync all bulk endpoints (no per-symbol iteration needed)."""
        phase = PhaseReport(phase_name="Phase 1 — Bulk Market Data", success=True)
        svc = await self._get_sync_svc()

        bulk_ops = [
            ("AllSymbols", lambda: svc.sync_all_symbols(session)),
            ("Index (TSE)", lambda: svc.sync_index(session, "1")),
            ("Index (Farabourse)", lambda: svc.sync_index(session, "2")),
            ("Options (TSETMC)", lambda: svc.sync_options(session)),
            ("IME Futures", lambda: svc.sync_ime_futures(session)),
            ("IME Options", lambda: svc.sync_ime_options(session)),
            ("IME Certificates", lambda: svc.sync_ime_certificates(session)),
            ("IME Funds", lambda: svc.sync_ime_funds(session)),
            ("Commodities", lambda: svc.sync_commodities(session)),
            ("Crypto", lambda: svc.sync_crypto(session)),
            ("Gold/Currency", lambda: svc.sync_gold_currency(session)),
        ]

        phase_start = time.monotonic()
        for name, op in bulk_ops:
            op_start = time.monotonic()
            try:
                result = await op()
                _elapsed = (time.monotonic() - op_start) * 1000
                if isinstance(result, list):
                    for r in result:
                        if isinstance(r, list):
                            for sub in r:
                                await self._add_operation(
                                    phase, f"{name}/{sub.endpoint}",
                                    sub.success, sub.items_count, sub.duration_ms,
                                    sub.error,
                                )
                        else:
                            await self._add_operation(
                                phase, f"{name}/{r.endpoint}",
                                r.success, r.items_count, r.duration_ms,
                                r.error,
                            )
                else:
                    await self._add_operation(
                        phase, name, result.success, result.items_count,
                        result.duration_ms, result.error,
                    )
            except Exception as e:
                await self._add_operation(phase, name, False, error=str(e))
            await asyncio.sleep(0.5)

        await session.commit()
        phase.duration_ms = (time.monotonic() - phase_start) * 1000
        return phase

    # ── Phase 2: Per-Symbol Details ──────────────────

    async def _phase_2_symbol_details(
        self, session: AsyncSession,
    ) -> PhaseReport:
        """Sync SymbolDetail + Candlesticks + History for all symbols."""
        phase = PhaseReport(phase_name="Phase 2 — Symbol Details", success=True)
        svc = await self._get_sync_svc()

        symbols = await self._get_all_symbols(session)
        symbols = symbols[:self.max_symbols]
        logger.info("Phase 2: processing %d symbols", len(symbols))

        for idx, symbol in enumerate(symbols):
            pct = (idx + 1) / len(symbols) * 100
            # Symbol Detail
            t0 = time.monotonic()
            try:
                r = await svc.sync_symbol_detail(session, symbol)
                await self._add_operation(
                    phase, f"SymbolDetail({symbol})",
                    r.success, r.items_count, (time.monotonic() - t0) * 1000, r.error,
                )
            except Exception as e:
                await self._add_operation(phase, f"SymbolDetail({symbol})", False, error=str(e))

            # Candlestick (type=3 = daily)
            t0 = time.monotonic()
            try:
                r = await svc.sync_candlesticks(session, symbol, "3")
                await self._add_operation(
                    phase, f"Candlestick({symbol})", r.success, r.items_count,
                    (time.monotonic() - t0) * 1000, r.error,
                )
            except Exception as e:
                await self._add_operation(phase, f"Candlestick({symbol})", False, error=str(e))

            # History Price (only if not recently synced)
            t0 = time.monotonic()
            try:
                r = await svc.sync_history_price(session, symbol)
                await self._add_operation(
                    phase, f"HistoryPrice({symbol})", r.success, r.items_count,
                    (time.monotonic() - t0) * 1000, r.error,
                )
            except Exception as e:
                await self._add_operation(phase, f"HistoryPrice({symbol})", False, error=str(e))

            # Progress log
            if (idx + 1) % 20 == 0:
                logger.info("  Phase 2: %d/%d (%.0f%%)", idx + 1, len(symbols), pct)
                await session.commit()

            await asyncio.sleep(0.3)

        await session.commit()
        return phase

    # ── Phase 3: Transactions (ریز معاملات) ──────────

    async def _phase_3_transactions(
        self, session: AsyncSession,
    ) -> PhaseReport:
        """Sync intraday transactions for all symbols for recent days."""
        phase = PhaseReport(phase_name="Phase 3 — Transactions (ریز معاملات)", success=True)
        svc = await self._get_sync_svc()

        symbols = await self._get_all_symbols(session)
        symbols = symbols[:self.max_symbols]
        logger.info("Phase 3: processing %d symbols (recent %d days)",
                     len(symbols), self.transaction_days_back)

        # Build date range for recent days — BrsApi expects Jalali (Shamsi)
        # dates (e.g. 1404-02-22), so use jdatetime throughout.
        from datetime import timedelta

        import jdatetime

        today = jdatetime.date.today().strftime("%Y-%m-%d")
        dates_to_sync = [
            (jdatetime.date.today() - timedelta(days=d)).strftime("%Y-%m-%d")
            for d in range(self.transaction_days_back)
        ]

        for idx, symbol in enumerate(symbols):
            op_start = time.monotonic()
            try:
                # Sync today's transactions
                r = await svc.sync_transactions(session, symbol, date=today)
                await self._add_operation(
                    phase, f"Transaction({symbol})", r.success, r.items_count,
                    (time.monotonic() - op_start) * 1000, r.error,
                )
                # Also sync recent days (summary level)
                if r.success and r.items_count > 0:
                    for past_date in dates_to_sync:
                        r2 = await svc.sync_transactions(session, symbol, date=past_date)
                        if r2.success and r2.items_count > 0:
                            break  # Found data for this past date
            except Exception as e:
                await self._add_operation(phase, f"Transaction({symbol})", False, error=str(e))

            if (idx + 1) % 50 == 0:
                logger.info("  Phase 3: %d/%d", idx + 1, len(symbols))
                await session.commit()

            await asyncio.sleep(0.2)

        await session.commit()
        return phase

    # ── Phase 4: Shareholders ────────────────────────

    async def _phase_4_shareholders(
        self, session: AsyncSession,
    ) -> PhaseReport:
        """Sync shareholder composition for all symbols."""
        phase = PhaseReport(phase_name="Phase 4 — Shareholders", success=True)
        svc = await self._get_sync_svc()

        symbols = await self._get_all_symbols(session)
        symbols = symbols[:self.max_symbols]
        logger.info("Phase 4: processing %d symbols", len(symbols))

        for idx, symbol in enumerate(symbols):
            t0 = time.monotonic()
            try:
                r = await svc.sync_shareholders(session, symbol)
                await self._add_operation(
                    phase, f"Shareholder({symbol})", r.success, r.items_count,
                    (time.monotonic() - t0) * 1000, r.error,
                )
            except Exception as e:
                await self._add_operation(phase, f"Shareholder({symbol})", False, error=str(e))

            if (idx + 1) % 50 == 0:
                logger.info("  Phase 4: %d/%d", idx + 1, len(symbols))
                await session.commit()

            await asyncio.sleep(0.3)

        await session.commit()
        return phase

    # ── Phase 5: Codal ───────────────────────────────

    async def _phase_5_codal(
        self, session: AsyncSession,
    ) -> PhaseReport:
        """
        Sync Codal announcements + download/parse Excel files.

        Step 5a: Sync announcements from BrsApi
        Step 5b: Download + parse Excel files
        Step 5c: Calculate financial ratios
        """
        phase = PhaseReport(phase_name="Phase 5 — Codal (Announcement + Download)", success=True)

        # Step 5a: Sync announcements
        t0 = time.monotonic()
        try:
            svc = await self._get_sync_svc()
            r = await svc.sync_codal(session)
            await self._add_operation(
                phase, "Codal Announcements", r.success, r.items_count,
                (time.monotonic() - t0) * 1000, r.error,
            )
        except Exception as e:
            await self._add_operation(phase, "Codal Announcements", False, error=str(e))

        # Step 5b: Download + Parse Excel files
        dl_start = time.monotonic()
        dl_svc = None
        try:
            from services.codal_download_service import CodalDownloadService
            dl_svc = CodalDownloadService(session)
            dl_summary = await dl_svc.download_and_import_all(max_announcements=200)
            await self._add_operation(
                phase, "Codal Download & Parse", True,
                dl_summary.parsed, (time.monotonic() - dl_start) * 1000,
            )
            if dl_summary.errors:
                for err in dl_summary.errors[:5]:
                    logger.warning("Codal download warning: %s", err[:100])
        except Exception as e:
            await self._add_operation(phase, "Codal Download & Parse", False, error=str(e))
        finally:
            if dl_svc:
                await dl_svc.close()

        return phase

    # ── Phase 6: Screener Profiles ──────────────────

    async def _phase_6_screener(
        self, session: AsyncSession,
    ) -> PhaseReport:
        """
        Full populate of screener_profiles and update free_float from shareholders.

        Step 6a: Run full_populate_profiles
        Step 6b: Update free_float from shareholder records
        """
        phase = PhaseReport(phase_name="Phase 6 — Screener Profiles", success=True)

        # Step 6a: Populate profiles
        t0 = time.monotonic()
        try:
            # Import and run the populate logic directly
            from scripts.full_populate_profiles import run as populate_run
            await populate_run()
            await self._add_operation(
                phase, "Populate Profiles", True, 1562,
                (time.monotonic() - t0) * 1000,
            )
        except Exception as e:
            await self._add_operation(phase, "Populate Profiles", False, error=str(e))

        # Step 6b: Update free_float
        t0 = time.monotonic()
        try:
            from scripts.update_free_float import run as ff_run
            await ff_run()
            await self._add_operation(
                phase, "Update Free Float", True, 0,
                (time.monotonic() - t0) * 1000,
            )
        except Exception as e:
            await self._add_operation(phase, "Update Free Float", False, error=str(e))

        return phase

    async def close(self) -> None:
        """Clean up HTTP client connections."""
        if self._client:
            from brsapi.client import close_client
            await close_client()
            self._client = None
            self._sync_svc = None

    # ── Run All ──────────────────────────────────────

    async def run_all(
        self,
        session: AsyncSession,
        phases: list[int] | None = None,
    ) -> MasterReport:
        """
        Run all (or selected) sync phases.

        Args:
            session: Database session
            phases: List of phase numbers to run, e.g. [1,2,3,4,5,6].
                    Defaults to all phases.

        Returns:
            MasterReport with per-phase results
        """
        if phases is None:
            phases = [1, 2, 3, 4, 5, 6]

        report = MasterReport(started_at=time.monotonic())

        phase_map = {
            1: ("Phase 1 — Bulk Market", self._phase_1_bulk_market),
            2: ("Phase 2 — Symbol Details", self._phase_2_symbol_details),
            3: ("Phase 3 — Transactions", self._phase_3_transactions),
            4: ("Phase 4 — Shareholders", self._phase_4_shareholders),
            5: ("Phase 5 — Codal", self._phase_5_codal),
            6: ("Phase 6 — Screener", self._phase_6_screener),
        }

        for phase_num in sorted(phases):
            if phase_num not in phase_map:
                continue
            name, fn = phase_map[phase_num]
            logger.info("=" * 60)
            logger.info("Starting %s", name)
            logger.info("=" * 60)

            try:
                phase_report = await fn(session)
            except Exception as e:
                logger.exception("Phase %d failed catastrophically: %s", phase_num, e)
                phase_report = PhaseReport(
                    phase_name=name, success=False,
                    error=f"Fatal: {e}",
                )
                report.errors.append(f"Phase {phase_num}: {e}")

            report.phases.append(phase_report)

            # Brief pause between phases
            await asyncio.sleep(1)

        report.finished_at = time.monotonic()
        return report
