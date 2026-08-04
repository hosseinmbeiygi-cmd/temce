"""Configuration for the Codal Excel Bulk Importer."""

from __future__ import annotations

import os
from pathlib import Path

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://localhost:5432/market",
)
DATABASE_URL_SYNC = DATABASE_URL.replace("+asyncpg", "")

# ── Paths ─────────────────────────────────────────────────────────────────────
CODEX_EXCEL_DIR = Path(r"C:\Users\Iran\Desktop\temce\data brsapi\codal_excel_files")

# ── Batch / Performance ───────────────────────────────────────────────────────
BATCH_SIZE = 500           # records per bulk insert
SCAN_BATCH_SIZE = 1000     # files per scan batch
MAX_WORKERS = 3            # parallel parsing workers
COMMIT_EVERY = 500         # commit every N files

# ── File Limits ───────────────────────────────────────────────────────────────
MAX_FILE_SIZE_MB = 50
MAX_TABLES_PER_FILE = 20
MAX_ROWS_PER_TABLE = 5000

# ── Report type mapping from filename ─────────────────────────────────────────
# ن-۱۰ = financial statement (balance sheet, income statement, etc.)
# ن-۳۰ = operational report
# ن-۳۱ = portfolio report
# Other patterns
REPORT_TYPE_MAP = {
    "ن-۱۰": "n10",   # صورت‌های مالی
    "ن-۳۰": "n30",   # عملکرد
    "ن-۳۱": "n31",   # سبد دارایی
    "ن-۴۰": "n40",   # گزارش هیئت مدیره
    "ن-۴۱": "n41",   # مجمع عمومی
    "ن-۴۵": "n45",   # اطلاعیه پیش‌بینی
    "ن-۴۸": "n48",   # سود تقسیمی
}

# ── Status Constants ──────────────────────────────────────────────────────────
class FileStatus:
    PENDING = "pending"
    SCANNED = "scanned"
    DETECTED = "detected"
    PARSED = "parsed"
    VALIDATED = "validated"
    SAVED = "saved"
    FAILED = "failed"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    UNSUPPORTED = "unsupported"
    PARTIAL = "partial"
