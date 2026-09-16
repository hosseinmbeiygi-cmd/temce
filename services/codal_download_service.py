"""
Codal Download & Parse Service
===============================

Pipeline:
  1. Read Codal announcements from ``codal_announcements`` table
  2. For each announcement with a ``link_excel`` or ``link``:
     a. Download the Excel/HTML file
     b. Parse financial data using ``codal_accounting_service.parse_report()``
     c. Store structured data in ``codal_financial_statements`` table
  3. Skip already-imported announcements (dedup by code)

Usage:
    service = CodalDownloadService(session)
    summary = await service.download_and_import_all()
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.db_utils import safe_row_str
from core.fix_network import fix_network
from core.ids import new_id
from core.logging import get_logger
from core.paths import data_path
from core.time import utc_now_naive
from models.codal_financial import CodalFinancialStatementModel
from services.codal_accounting_service import _parse_filename, parse_report

logger = get_logger(__name__)

# Apply network fix
fix_network()

CODAL_DOWNLOAD_DIR = str(data_path("codal_excel"))
os.makedirs(CODAL_DOWNLOAD_DIR, exist_ok=True)


@dataclass
class CodalDownloadSummary:
    total_announcements: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    parsed: int = 0
    parse_errors: int = 0
    errors: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0


class CodalDownloadService:
    """
    Downloads and parses Excel/PDF files from Codal announcement links.

    Usage::
        service = CodalDownloadService(session)
        summary = await service.download_and_import_all()
        print(summary.downloaded, "files downloaded")
    """

    def __init__(
        self,
        session: AsyncSession,
        download_dir: str = CODAL_DOWNLOAD_DIR,
        concurrency: int = 3,
    ):
        self.session = session
        self.download_dir = download_dir
        self.concurrency = concurrency
        self._http_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=60.0,
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

    async def download_and_import_all(
        self,
        max_announcements: int = 500,
        batch_size: int = 50,
    ) -> CodalDownloadSummary:
        """
        Download and import ALL Codal Excel files that haven't been processed yet.

        Args:
            max_announcements: Max announcements to process (0 = unlimited)
            batch_size: Commit batch size

        Returns:
            CodalDownloadSummary with counts
        """
        start = time.monotonic()
        summary = CodalDownloadSummary()

        # 1. Get unprocessed announcements
        stmt = text("""
            SELECT ca.code, ca.symbol, ca.link, ca.link_excel, ca.link_pdf,
                   ca.date_publish, ca.title
            FROM codal_announcements ca
            WHERE ca.link_excel IS NOT NULL AND ca.link_excel != ''
              AND ca.symbol IS NOT NULL AND ca.symbol != ''
              AND NOT EXISTS (
                  SELECT 1 FROM codal_financial_statements cfs
                  WHERE cfs.symbol = ca.symbol
                    AND cfs.import_batch = 'codal_download'
              )
            ORDER BY ca.date_publish DESC
        """)
        if max_announcements > 0:
            stmt = text(str(stmt)[:-1] + f" LIMIT {max_announcements}")

        result = await self.session.execute(stmt)
        rows = result.fetchall()
        summary.total_announcements = len(rows)

        if not rows:
            logger.info("No unprocessed Codal announcements found")
            summary.elapsed_seconds = time.monotonic() - start
            return summary

        logger.info("Found %d unprocessed Codal announcements", len(rows))

        # 2. Download in parallel (with concurrency limit)
        semaphore = asyncio.Semaphore(self.concurrency)

        async def _process_one(row: Any) -> dict[str, Any]:
            _code = row[0]
            symbol = safe_row_str(row, idx=1, default="unknown")
            link = safe_row_str(row, idx=2)
            link_excel = safe_row_str(row, idx=3)
            link_pdf = safe_row_str(row, idx=4)
            date_publish = safe_row_str(row, idx=5)[:10]
            _title = safe_row_str(row, idx=6)[:100]

            # Prefer Excel link, then generic link, then PDF
            dl_link = link_excel or link or link_pdf
            if not dl_link:
                return {"status": "skipped", "reason": "no_link"}

            # Build symbol directory
            sym_dir = os.path.join(self.download_dir, symbol)
            os.makedirs(sym_dir, exist_ok=True)

            # Determine filename
            ext = ".xlsx"
            if ".pdf" in dl_link.lower():
                ext = ".pdf"
            elif ".html" in dl_link.lower() or ".htm" in dl_link.lower():
                ext = ".html"

            filename = f"{symbol}_codal_{date_publish}{ext}"
            filepath = os.path.join(sym_dir, filename)

            # Skip if already downloaded
            if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
                return {"status": "exists", "filepath": filepath, "symbol": symbol}

            # Handle relative URLs (prepend BrsApi base)
            if dl_link.startswith('/'):
                dl_link = f'https://api.brsapi.ir{dl_link}'
            elif not dl_link.startswith('http'):
                dl_link = f'https://{dl_link}'

            # Download
            async with semaphore:
                try:
                    client = await self._get_client()
                    resp = await client.get(dl_link)
                    resp.raise_for_status()

                    with open(filepath, "wb") as f:
                        f.write(resp.content)

                    return {
                        "status": "downloaded",
                        "filepath": filepath,
                        "symbol": symbol,
                        "size": len(resp.content),
                    }
                except Exception as e:
                    return {"status": "failed", "reason": str(e)[:100], "symbol": symbol, "link": dl_link}

        # Process all
        tasks = [_process_one(row) for row in rows]
        results = await asyncio.gather(*tasks)

        # 3. Tally + Parse
        parsed_records: list[CodalFinancialStatementModel] = []
        for res in results:
            if res["status"] == "downloaded" or res["status"] == "exists":
                summary.downloaded += 1

                # Try to parse
                filepath = res.get("filepath", "")
                symbol = res.get("symbol", "unknown")
                parsed = parse_report(filepath)

                if parsed and "error" not in parsed:
                    summary.parsed += 1

                    # Parse filename to get report_type and date
                    fname = os.path.basename(filepath)
                    fn_parsed = _parse_filename(fname)

                    record = CodalFinancialStatementModel(
                        id=new_id("cfs"),
                        symbol=symbol,
                        report_type=fn_parsed["report_type"] if fn_parsed else "codal_download",
                        report_date=fn_parsed["date"] if fn_parsed else utc_now_naive().strftime("%Y%m%d"),
                        filename=fname,
                        file_path=filepath,
                        title=parsed.get("title", ""),
                        parsed_data=parsed,
                        table_count=parsed.get("table_count", 0),
                        row_count=parsed.get("raw_rows_count", 0),
                        import_batch="codal_download",
                    )
                    parsed_records.append(record)

                    if len(parsed_records) >= batch_size:
                        self.session.add_all(parsed_records)
                        await self.session.flush()
                        parsed_records = []
                else:
                    summary.parse_errors += 1
                    error_msg = parsed.get("error", "unknown") if parsed else "empty"
                    summary.errors.append(f"{symbol}: parse error: {error_msg}")
            elif res["status"] == "failed":
                summary.failed += 1
                summary.errors.append(f"{res.get('symbol','?')}: {res.get('reason','?')}")
            else:
                summary.skipped += 1

        # Flush remaining
        if parsed_records:
            self.session.add_all(parsed_records)
            await self.session.flush()

        # 4. Now run the financial statement import to populate ratios
        try:
            from services.codal_financial_import_service import CodalFinancialImportService
            import_svc = CodalFinancialImportService(self.session)
            import_summary = await import_svc.import_all(batch_id="codal_download")
            logger.info(
                "Financial import: %d imported, %d updated",
                import_summary.imported,
                import_summary.updated,
            )
        except Exception as e:
            logger.warning("Financial import step failed: %s", e)

        await self.session.commit()
        summary.elapsed_seconds = time.monotonic() - start

        logger.info(
            "Codal download complete: %d/%d downloaded, %d parsed, %d failed in %.1fs",
            summary.downloaded,
            summary.total_announcements,
            summary.parsed,
            summary.failed,
            summary.elapsed_seconds,
        )
        return summary
