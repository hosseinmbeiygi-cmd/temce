"""
Codal Attachment Download Service
====================================

Downloads the files referenced by ``link_pdf``, ``link_excel`` and
``link_attachment`` fields of ``brsapi_codal_announcements`` and
persists either the file bytes in the database or the file on local/S3
storage with metadata in the database.
"""

from __future__ import annotations

import asyncio
import mimetypes
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from brsapi.models.codal import CodalAttachmentModel
from core.logging import get_logger
from core.paths import data_path, safe_resolve

logger = get_logger(__name__)

DEFAULT_TIMEOUT = 60.0
# C4: a 'downloading' row older than this is considered orphaned by a crashed
# worker and is reclaimed to 'error' (retriable) on the next batch fetch.
STALE_DOWNLOADING_THRESHOLD_SECONDS = 1800  # 30 minutes
DEFAULT_CONCURRENCY = 3
DEFAULT_DELAY_SECONDS = 1.0
DEFAULT_CHUNK_SIZE = 8192


def _file_chunk_iterator(path: Path, chunk_size: int = DEFAULT_CHUNK_SIZE):
    """Yield chunks of a local file for streaming responses (sync variant)."""
    def _iter():
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    return _iter()


async def _async_file_chunk_iterator(path: Path, chunk_size: int = DEFAULT_CHUNK_SIZE):
    """Yield chunks of a local file asynchronously (offloaded to a thread)."""
    import asyncio

    async def _iter():
        loop = asyncio.get_running_loop()
        f = await loop.run_in_executor(None, open, path, "rb")
        try:
            while True:
                chunk = await loop.run_in_executor(None, f.read, chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            f.close()

    return _iter()


async def _async_iter_chunks(chunks: list[bytes]):
    """Yield a fixed list of byte chunks asynchronously."""
    async def _iter():
        for chunk in chunks:
            yield chunk

    return _iter()


@dataclass
class CodalAttachmentDownloadSummary:
    total: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


class CodalAttachmentDownloadService:
    """
    Backfill/download Codal announcement attachments.

    Usage::

        service = CodalAttachmentDownloadService(session)
        summary = await service.download_all_pending(limit=1000)
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage_type: str = "local",
        concurrency: int = DEFAULT_CONCURRENCY,
        delay_seconds: float = DEFAULT_DELAY_SECONDS,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.session = session
        self.storage_type = storage_type
        self.concurrency = concurrency
        self.delay_seconds = delay_seconds
        self.timeout = timeout
        self._stale_threshold = timedelta(seconds=STALE_DOWNLOADING_THRESHOLD_SECONDS)
        self._http_client: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(concurrency)
        bind = getattr(session, "bind", None)
        if isinstance(bind, AsyncEngine):
            self._session_factory: async_sessionmaker | None = async_sessionmaker(
                bind,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        else:
            self._session_factory = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                },
            )
        return self._http_client

    async def close(self) -> None:
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def download_all_pending(
        self,
        limit: int = 1000,
        symbol: str | None = None,
    ) -> CodalAttachmentDownloadSummary:
        """Create attachment rows for pending announcements and download them."""
        summary = CodalAttachmentDownloadSummary()

        created = await self.enqueue_pending_attachments(limit=limit, symbol=symbol)
        if created == 0:
            logger.info("No new Codal attachment rows to enqueue")

        pending = await self._fetch_pending_rows(limit=limit)
        if not pending:
            return summary

        summary.total = len(pending)
        logger.info("Downloading %d Codal attachments (storage=%s)", len(pending), self.storage_type)

        tasks = [self._download_one(row) for row in pending]
        results = await asyncio.gather(*tasks)

        for row, result in zip(pending, results, strict=True):
            if result is True:
                summary.downloaded += 1
            elif result is False:
                summary.failed += 1
                summary.errors.append(f"{row.symbol or '?'} {row.attachment_type}: download failed")
            else:
                summary.skipped += 1

        return summary

    async def enqueue_pending_attachments(
        self,
        limit: int = 1000,
        symbol: str | None = None,
    ) -> int:
        """Create ``CodalAttachmentModel`` rows for announcements that have links but no row."""
        conditions = ["ca.link IS NOT NULL AND ca.link != ''"]
        params: dict[str, Any] = {"limit": limit}
        if symbol:
            conditions.append("ca.symbol = :symbol")
            params["symbol"] = symbol

        stmt = text(
            f"""
            INSERT INTO brsapi_codal_attachments (
                announcement_id, symbol, code, attachment_type, source_url,
                storage_type, status, created_at, updated_at
            )
            SELECT DISTINCT
                ca.id,
                ca.symbol,
                ca.code,
                link.type AS attachment_type,
                link.url AS source_url,
                :storage_type AS storage_type,
                'pending' AS status,
                CURRENT_TIMESTAMP AS created_at,
                CURRENT_TIMESTAMP AS updated_at
            FROM brsapi_codal_announcements ca
            CROSS JOIN LATERAL (VALUES
                ('pdf', ca.link_pdf),
                ('excel', ca.link_excel),
                ('attachment', ca.link_attachment),
                ('html', ca.link)
            ) AS link(type, url)
            WHERE {' AND '.join(conditions)}
              AND link.url IS NOT NULL AND link.url != ''
              AND NOT EXISTS (
                  SELECT 1 FROM brsapi_codal_attachments ca2
                  WHERE ca2.announcement_id = ca.id
                    AND ca2.attachment_type = link.type
              )
              -- C6 (audit): several link fields of one announcement often hold
              -- the SAME url (e.g. link == link_attachment for NAV letters);
              -- keep only the first type per url so we never download the
              -- identical file twice.
              AND link.type = (
                  SELECT t.type FROM (VALUES
                      ('pdf', ca.link_pdf),
                      ('excel', ca.link_excel),
                      ('attachment', ca.link_attachment),
                      ('html', ca.link)
                  ) AS t(type, url)
                  WHERE t.url = link.url AND t.url IS NOT NULL AND t.url != ''
                  ORDER BY array_position(ARRAY['pdf','excel','attachment','html'], t.type)
                  LIMIT 1
              )
            ORDER BY ca.id
            LIMIT :limit
            ON CONFLICT (announcement_id, attachment_type) DO NOTHING
            """
        )
        params["storage_type"] = self.storage_type
        result = await self.session.execute(stmt, params)
        await self.session.commit()
        count = result.rowcount or 0
        if count:
            logger.info("Enqueued %d Codal attachment rows", count)
        return count

    async def _fetch_pending_rows(self, limit: int) -> list[CodalAttachmentModel]:
        """Atomically lock a batch of pending rows and mark them as downloading."""
        # C4 (audit): rows whose worker crashed mid-download stay 'downloading'
        # forever. Reclaim them after the stale threshold so a download can be
        # retried instead of being stuck for the life of the table.
        stale_sql = text(
            """
            UPDATE brsapi_codal_attachments
            SET status = 'error',
                error_message = 'reclaimed: download timed out (stale downloading row)',
                updated_at = CURRENT_TIMESTAMP
            WHERE status = 'downloading'
              AND updated_at < CURRENT_TIMESTAMP - :stale
            """
        )
        try:
            await self.session.execute(stale_sql, {"stale": self._stale_threshold})
            await self.session.commit()
        except Exception:  # noqa: BLE001
            await self.session.rollback()
            logger.debug("Stale-downloading reclaim failed", exc_info=True)

        # Prefer atomic lock+update to prevent multiple workers picking the same row.
        lock_sql = text(
            """
            UPDATE brsapi_codal_attachments
            SET status = 'downloading', updated_at = CURRENT_TIMESTAMP
            WHERE id IN (
                SELECT id FROM brsapi_codal_attachments
                WHERE status IN ('pending', 'error')
                ORDER BY created_at
                LIMIT :limit
                FOR UPDATE SKIP LOCKED
            )
            RETURNING *
            """
        )
        try:
            result = await self.session.execute(lock_sql, {"limit": limit})
            rows = [CodalAttachmentModel(**dict(r)) for r in result.mappings()]
            await self.session.commit()
            return rows
        except Exception:  # noqa: BLE001
            await self.session.rollback()
            # Fallback for databases without SKIP LOCKED: atomic update+returning.
            update_sql = text(
                """
                UPDATE brsapi_codal_attachments
                SET status = 'downloading', updated_at = CURRENT_TIMESTAMP
                WHERE id IN (
                    SELECT id FROM brsapi_codal_attachments
                    WHERE status IN ('pending', 'error')
                    ORDER BY created_at
                    LIMIT :limit
                )
                RETURNING *
                """
            )
            result = await self.session.execute(update_sql, {"limit": limit})
            rows = [CodalAttachmentModel(**dict(r)) for r in result.mappings()]
            await self.session.commit()
            return rows

    async def _download_one(self, row: CodalAttachmentModel) -> bool | None:
        url = self._normalize_url(row.source_url or "")
        if not url:
            row.status = "error"
            row.error_message = "missing source_url"
            return False

        async with self._semaphore:
            session_context = None
            session = self.session
            if self._session_factory is not None:
                session_context = self._session_factory()
                session = await session_context.__aenter__()

            try:
                # Make sure the row belongs to the current session. merge() handles
                # detached (loaded by another session), transient (new), and persistent
                # (already in this session) correctly.
                merged = await session.merge(row)
                if isinstance(merged, CodalAttachmentModel):
                    row = merged
                row.status = "downloading"
                await session.commit()

                client = await self._get_client()
                resp = await client.get(url)
                resp.raise_for_status()

                content = resp.content
                if not content:
                    row.status = "error"
                    row.error_message = "empty response"
                    session.add(row)
                    await session.commit()
                    return False

                mime = resp.headers.get("content-type") or self._guess_mime(url)
                storage_path = await self._persist(row, content, mime)

                row.status = "done"
                row.error_message = None
                row.file_size = len(content)
                row.mime_type = mime
                row.storage_path = storage_path
                row.downloaded_at = datetime.now(UTC)
                if self.storage_type == "database":
                    row.content = content
                await session.commit()

                # C1 (audit): pipeline a financial-statement parse for Excel
                # attachments so `codal_financial_statements` is populated by
                # the ACTIVE flow (this job), not only the legacy script.
                # Failures must never mark a successfully stored file as failed.
                if row.attachment_type == "excel":
                    try:
                        await self._parse_financial_statement(row)
                    except Exception:
                        logger.exception(
                            "Financial parse failed for attachment %s (file kept)",
                            row.id,
                        )

                if self.delay_seconds > 0:
                    await asyncio.sleep(self.delay_seconds)

                return True
            except Exception as exc:  # noqa: BLE001
                logger.warning("Codal attachment download failed for %s: %s", url, exc)
                row.status = "error"
                row.error_message = str(exc)[:500]
                try:
                    await session.commit()
                except Exception as commit_exc:  # noqa: BLE001
                    logger.warning("Failed to persist error status: %s", commit_exc)
                return False
            finally:
                if session_context is not None:
                    await session_context.__aexit__(None, None, None)

    async def _parse_financial_statement(self, row: CodalAttachmentModel) -> None:
        """Extract tables from an Excel attachment into ``codal_financial_statements``.

        Reads the stored bytes (local backend) — a ``storage_type="database"``
        row is parsed from the in-DB content. Deduplication (symbol + type +
        date) and upsert semantics live in ``CodalFinancialImportService``.
        """
        from services.codal_financial_statement_import import import_statement_record

        content = await self.get_attachment_content(row)
        if not content:
            return
        await import_statement_record(
            symbol=row.symbol or "",
            announcement_id=row.announcement_id,
            attachment_id=row.id,
            title=row.source_url or "",
            content=content,
            published_at=row.downloaded_at,
        )

    async def _persist(
        self,
        row: CodalAttachmentModel,
        content: bytes,
        mime: str,
    ) -> str | None:
        if self.storage_type == "database":
            return None

        if self.storage_type in ("local", "s3"):
            key = self._make_key(row, mime)
            await self._write_local(key, content)
            return key

        raise ValueError(f"Unsupported storage_type: {self.storage_type}")

    def _make_key(self, row: CodalAttachmentModel, mime: str) -> str:
        ext = self._extension_for(row.attachment_type, mime)
        symbol = (row.symbol or "unknown").replace("/", "_")
        code = (row.code or str(row.announcement_id)).replace("/", "_")
        return f"codal/{symbol}/{code}_{row.attachment_type}{ext}"

    async def _write_local(self, key: str, content: bytes) -> Path:
        base = data_path("codal_attachments")
        path = safe_resolve(base, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    @staticmethod
    def _extension_for(attachment_type: str, mime: str) -> str:
        if attachment_type == "pdf":
            return ".pdf"
        if attachment_type == "excel":
            return ".xlsx"
        if attachment_type == "html":
            return ".html"
        ext = mimetypes.guess_extension(mime or "")
        return ext or ".bin"

    @staticmethod
    def _guess_mime(url: str) -> str:
        lower = url.lower()
        if lower.endswith(".pdf"):
            return "application/pdf"
        if lower.endswith((".xlsx", ".xls")):
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if lower.endswith(".html") or lower.endswith(".htm"):
            return "text/html"
        return "application/octet-stream"

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Return an absolute URL, handling relative Codal links."""
        url = url.strip()
        if not url:
            return ""
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if url.startswith("/"):
            return f"https://api.brsapi.ir{url}"
        return f"https://{url}"

    async def get_attachment_content(self, row: CodalAttachmentModel) -> bytes:
        """Return the attachment bytes, reading from the configured backend."""
        storage_type = row.storage_type or self.storage_type
        if storage_type == "database":
            return row.content or b""

        if storage_type in ("local", "s3"):
            if not row.storage_path:
                return b""
            if storage_type == "local":
                base = data_path("codal_attachments")
                path = safe_resolve(base, row.storage_path)
                return path.read_bytes()
            result = await self._s3_read(row.storage_path)
            return result or b""
        return b""

    async def _s3_read(self, key: str) -> bytes | None:
        """Read a file from S3/MinIO via ``S3CompatibleStorage``."""
        from integrations.filesystems.s3_compatible_storage import S3CompatibleStorage

        storage = S3CompatibleStorage()
        try:
            result = await storage.read(key)
            if result.success:
                return result.value
            logger.warning("S3 read failed for %s: %s", key, result.error)
        except Exception as exc:  # noqa: BLE001
            logger.warning("S3 read error for %s: %s", key, exc)
        finally:
            await storage.close()
        return None

    def _get_s3_storage(self):
        """Return a configured S3 storage client (for streaming reads)."""
        from integrations.filesystems.s3_compatible_storage import S3CompatibleStorage

        return S3CompatibleStorage()

    async def get_attachment_stream(self, row: CodalAttachmentModel):
        """Return an async iterator that yields chunks of the attachment.

        For local files this avoids loading the whole file into memory. S3
        reads load the object into memory (the S3 client has no ranged API
        here), returning the bytes as a single chunk.
        """
        storage_type = row.storage_type or self.storage_type
        if storage_type == "database":
            content = row.content or b""
            return _async_iter_chunks([content])

        if storage_type in ("local", "s3"):
            if not row.storage_path:
                return _async_iter_chunks([b""])
            if storage_type == "local":
                base = data_path("codal_attachments")
                path = safe_resolve(base, row.storage_path)
                if not path.exists():
                    from core.exceptions import NotFoundError
                    raise NotFoundError(
                        entity="CodalAttachment file",
                        identifier=row.storage_path,
                    )
                return _async_file_chunk_iterator(path)
            # S3: read the object and stream it back in one chunk.
            content = await self._s3_read(row.storage_path)
            return _async_iter_chunks([content or b""])
        return _async_iter_chunks([b""])

    async def get_attachment_stream_legacy(self, row: CodalAttachmentModel):
        """Backward-compatible sync-iterator variant (wraps the async one)."""
        chunks = []
        async for chunk in await self.get_attachment_stream(row):
            chunks.append(chunk)
        return iter(chunks)
