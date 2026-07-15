"""
BrsApi scheduled sync jobs.

Each job wraps a BrsApi data sync operation as a ``BaseJob``,
compatible with the project's ``JobDispatcher`` / APScheduler pipeline.

Registered triggers (in ``apps/scheduler/app.py``):
    - brsapi_all_symbols:     every 60s   — TSETMC stocks & ETFs
    - brsapi_index:           every 60s   — TSE main index
    - brsapi_index_farabours: every 60s   — Farabours index
    - brsapi_index_selected:  every 5min  — selected indices
    - brsapi_options:         every 5min  — TSETMC option contracts
    - brsapi_ime_futures:     every 5min  — IME futures
    - brsapi_ime_options:     every 5min  — IME options
    - brsapi_ime_certificates: every 5min — IME certificate receipts
    - brsapi_ime_funds:       every 5min  — IME commodity funds
    - brsapi_commodities:     every 60s   — global commodity prices
    - brsapi_crypto:          every 60s   — cryptocurrency prices
    - brsapi_codal:           every 15min — Codal announcements
    - brsapi_ime_physical:    daily 18:00 — IME physical trades
"""

from __future__ import annotations

import sys
from pathlib import Path

from core.logging import get_logger
from jobs.base_job import BaseJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult

logger = get_logger(__name__)

# Ensure project root is on sys.path for core.database imports
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


class _BrsApiSyncBaseJob(BaseJob):
    """Convenience: runs a BrsApi sync for a named endpoint / parser / model.

    Subclasses define ``endpoint``, ``parser``, and ``model`` as class
    attributes so they can be auto-discovered by ``JobRegistry``.
    """

    # Class-level overrides set by subclasses
    _endpoint_path: str = ""
    _parser_func = None
    _model_class = None
    _category_override: str | None = None
    _params: dict[str, str] | None = None

    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.client import close_client, get_client
        from brsapi.config import BrsApiEndpoints
        from brsapi.services.sync_service import BrsApiSyncService
        from core.database import get_session

        endpoint = BrsApiEndpoints.get(self._endpoint_path)
        if endpoint is None:
            return JobResult.failure(
                f"Unknown endpoint: {self._endpoint_path}", job_name=self._name
            )

        client = await get_client()
        try:
            async for session in get_session():
                service = BrsApiSyncService(client=client)
                report = await service.sync(
                    endpoint=endpoint,
                    parser=self._parser_func,
                    model_class=self._model_class,
                    params=self._params,
                    category_override=self._category_override,
                    session=session,
                )

                if report.success:
                    return JobResult.success_result(
                        job_name=self._name,
                        data={
                            "endpoint": report.endpoint,
                            "items": report.items_count,
                            "duration_ms": report.duration_ms,
                            "skipped": report.skipped,
                        },
                    )
                return JobResult.failure(
                    report.error or "unknown error", job_name=self._name
                )
        except Exception as e:
            logger.exception("BrsApi job %s failed", self._name)
            return JobResult.failure(str(e), job_name=self._name)
        finally:
            await close_client()


# ── Individual job classes ────────────────────────────────────────


class BrsApiAllSymbolsJob(_BrsApiSyncBaseJob):
    _endpoint_path = "ALL_SYMBOLS"
    _parser_func = None  # resolved at runtime via BrsApiEndpoints
    _model_class = None
    _params = {"type": "1"}

    @property
    def _resolved_parser(self):
        from brsapi.parsers import TsetmcParser
        return TsetmcParser.parse_all_symbols

    @property
    def _resolved_model(self):
        from brsapi.models import SymbolSnapshotModel
        return SymbolSnapshotModel

    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.config import BrsApiEndpoints as E
        from brsapi.services.sync_service import BrsApiSyncService

        endpoint = E.ALL_SYMBOLS
        client = None
        try:
            from brsapi.client import get_client
            from core.database import get_session

            client = await get_client()
            async for session in get_session():
                service = BrsApiSyncService(client=client)
                report = await service.sync(
                    endpoint=endpoint,
                    parser=self._resolved_parser,
                    model_class=self._resolved_model,
                    params=self._params,
                    session=session,
                )
                if report.success:
                    return JobResult.success_result(
                        job_name=self._name,
                        data={"items": report.items_count, "duration_ms": report.duration_ms},
                    )
                return JobResult.failure(report.error or "sync failed", job_name=self._name)
        except Exception as e:
            logger.exception("BrsApi job %s failed", self._name)
            return JobResult.failure(str(e), job_name=self._name)
        finally:
            if client:
                from brsapi.client import close_client
                await close_client()


class BrsApiIndexJob(BrsApiAllSymbolsJob):
    _params = {"type": "1"}
    _category_override = "tsetmc"

    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.client import get_client
        from brsapi.config import BrsApiEndpoints as E
        from brsapi.models import IndexValueModel
        from brsapi.parsers import TsetmcParser
        from brsapi.services.sync_service import BrsApiSyncService
        from core.database import get_session

        client = await get_client()
        try:
            async for session in get_session():
                service = BrsApiSyncService(client=client)
                report = await service.sync(
                    endpoint=E.INDEX,
                    parser=TsetmcParser.parse_index,
                    model_class=IndexValueModel,
                    params=self._params,
                    category_override=self._category_override,
                    session=session,
                )
                if report.success:
                    return JobResult.success_result(
                        job_name=self._name,
                        data={"items": report.items_count, "duration_ms": report.duration_ms},
                    )
                return JobResult.failure(report.error or "sync failed", job_name=self._name)
        finally:
            await close_client()


class BrsApiIndexFaraboursJob(BrsApiIndexJob):
    _params = {"type": "2"}


class BrsApiIndexSelectedJob(BrsApiIndexJob):
    _params = {"type": "3"}


class BrsApiOptionsJob(BrsApiAllSymbolsJob):
    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.client import get_client
        from brsapi.config import BrsApiEndpoints as E
        from brsapi.models import OptionSnapshotModel
        from brsapi.parsers import TsetmcParser
        from brsapi.services.sync_service import BrsApiSyncService
        from core.database import get_session

        client = await get_client()
        try:
            async for session in get_session():
                service = BrsApiSyncService(client=client)
                report = await service.sync(
                    endpoint=E.OPTION,
                    parser=TsetmcParser.parse_options,
                    model_class=OptionSnapshotModel,
                    session=session,
                )
                if report.success:
                    return JobResult.success_result(
                        job_name=self._name,
                        data={"items": report.items_count, "duration_ms": report.duration_ms},
                    )
                return JobResult.failure(report.error or "sync failed", job_name=self._name)
        finally:
            await close_client()


class BrsApiImeFuturesJob(BrsApiAllSymbolsJob):
    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.client import get_client
        from brsapi.config import BrsApiEndpoints as E
        from brsapi.models import ImeFutureModel
        from brsapi.parsers import ImeParser
        from brsapi.services.sync_service import BrsApiSyncService
        from core.database import get_session

        client = await get_client()
        try:
            async for session in get_session():
                service = BrsApiSyncService(client=client)
                report = await service.sync(
                    endpoint=E.IME_FUTURES,
                    parser=ImeParser.parse_futures,
                    model_class=ImeFutureModel,
                    session=session,
                )
                if report.success:
                    return JobResult.success_result(
                        job_name=self._name,
                        data={"items": report.items_count, "duration_ms": report.duration_ms},
                    )
                return JobResult.failure(report.error or "sync failed", job_name=self._name)
        finally:
            await close_client()


class BrsApiImeOptionsJob(BrsApiAllSymbolsJob):
    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.client import get_client
        from brsapi.config import BrsApiEndpoints as E
        from brsapi.models import ImeOptionModel
        from brsapi.parsers import ImeParser
        from brsapi.services.sync_service import BrsApiSyncService
        from core.database import get_session

        client = await get_client()
        try:
            async for session in get_session():
                service = BrsApiSyncService(client=client)
                report = await service.sync(
                    endpoint=E.IME_OPTION,
                    parser=ImeParser.parse_options,
                    model_class=ImeOptionModel,
                    session=session,
                )
                if report.success:
                    return JobResult.success_result(
                        job_name=self._name,
                        data={"items": report.items_count, "duration_ms": report.duration_ms},
                    )
                return JobResult.failure(report.error or "sync failed", job_name=self._name)
        finally:
            await close_client()


class BrsApiImeCertificatesJob(BrsApiAllSymbolsJob):
    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.client import get_client
        from brsapi.config import BrsApiEndpoints as E
        from brsapi.models import ImeCertificateModel
        from brsapi.parsers import ImeParser
        from brsapi.services.sync_service import BrsApiSyncService
        from core.database import get_session

        client = await get_client()
        try:
            async for session in get_session():
                service = BrsApiSyncService(client=client)
                report = await service.sync(
                    endpoint=E.IME_CERTIFICATE,
                    parser=ImeParser.parse_certificates,
                    model_class=ImeCertificateModel,
                    session=session,
                )
                if report.success:
                    return JobResult.success_result(
                        job_name=self._name,
                        data={"items": report.items_count, "duration_ms": report.duration_ms},
                    )
                return JobResult.failure(report.error or "sync failed", job_name=self._name)
        finally:
            await close_client()


class BrsApiImeFundsJob(BrsApiAllSymbolsJob):
    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.client import get_client
        from brsapi.config import BrsApiEndpoints as E
        from brsapi.models import ImeFundModel
        from brsapi.parsers import ImeParser
        from brsapi.services.sync_service import BrsApiSyncService
        from core.database import get_session

        client = await get_client()
        try:
            async for session in get_session():
                service = BrsApiSyncService(client=client)
                report = await service.sync(
                    endpoint=E.IME_FUND,
                    parser=ImeParser.parse_funds,
                    model_class=ImeFundModel,
                    session=session,
                )
                if report.success:
                    return JobResult.success_result(
                        job_name=self._name,
                        data={"items": report.items_count, "duration_ms": report.duration_ms},
                    )
                return JobResult.failure(report.error or "sync failed", job_name=self._name)
        finally:
            await close_client()


class BrsApiCommoditiesJob(BrsApiAllSymbolsJob):
    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.client import get_client
        from brsapi.config import BrsApiEndpoints as E
        from brsapi.models import CommodityPriceModel
        from brsapi.parsers import CommodityParser
        from brsapi.services.sync_service import BrsApiSyncService
        from core.database import get_session

        client = await get_client()
        try:
            async for session in get_session():
                service = BrsApiSyncService(client=client)
                report = await service.sync(
                    endpoint=E.COMMODITY,
                    parser=CommodityParser.parse,
                    model_class=CommodityPriceModel,
                    session=session,
                )
                if report.success:
                    return JobResult.success_result(
                        job_name=self._name,
                        data={"items": report.items_count, "duration_ms": report.duration_ms},
                    )
                return JobResult.failure(report.error or "sync failed", job_name=self._name)
        finally:
            await close_client()


class BrsApiCryptoJob(BrsApiAllSymbolsJob):
    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.client import get_client
        from brsapi.config import BrsApiEndpoints as E
        from brsapi.models import CryptoPriceModel
        from brsapi.parsers import CryptoParser
        from brsapi.services.sync_service import BrsApiSyncService
        from core.database import get_session

        client = await get_client()
        try:
            async for session in get_session():
                service = BrsApiSyncService(client=client)
                report = await service.sync(
                    endpoint=E.CRYPTOCURRENCY,
                    parser=CryptoParser.parse,
                    model_class=CryptoPriceModel,
                    session=session,
                )
                if report.success:
                    return JobResult.success_result(
                        job_name=self._name,
                        data={"items": report.items_count, "duration_ms": report.duration_ms},
                    )
                return JobResult.failure(report.error or "sync failed", job_name=self._name)
        finally:
            await close_client()


class BrsApiCodalJob(BrsApiAllSymbolsJob):
    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.client import get_client
        from brsapi.config import BrsApiEndpoints as E
        from brsapi.models import CodalAnnouncementModel
        from brsapi.parsers import CodalParser
        from brsapi.services.sync_service import BrsApiSyncService
        from core.database import get_session

        client = await get_client()
        try:
            async for session in get_session():
                service = BrsApiSyncService(client=client)
                report = await service.sync(
                    endpoint=E.CODAL_ANNOUNCEMENT,
                    parser=CodalParser.parse_announcements_only,
                    model_class=CodalAnnouncementModel,
                    session=session,
                )
                if report.success:
                    return JobResult.success_result(
                        job_name=self._name,
                        data={"items": report.items_count, "duration_ms": report.duration_ms},
                    )
                return JobResult.failure(report.error or "sync failed", job_name=self._name)
        finally:
            await close_client()


class BrsApiImePhysicalJob(BrsApiAllSymbolsJob):
    async def execute(self, context: JobContext) -> JobResult:
        from brsapi.client import get_client
        from brsapi.config import BrsApiEndpoints as E
        from brsapi.models import ImePhysicalTradeModel
        from brsapi.parsers import ImeParser
        from brsapi.services.sync_service import BrsApiSyncService
        from core.database import get_session

        client = await get_client()
        try:
            async for session in get_session():
                service = BrsApiSyncService(client=client)
                report = await service.sync(
                    endpoint=E.IME_PHYSICAL,
                    parser=ImeParser.parse_physical_trades,
                    model_class=ImePhysicalTradeModel,
                    session=session,
                )
                if report.success:
                    return JobResult.success_result(
                        job_name=self._name,
                        data={"items": report.items_count, "duration_ms": report.duration_ms},
                    )
                return JobResult.failure(report.error or "sync failed", job_name=self._name)
        finally:
            await close_client()
