"""Debug: test worker in ProcessPoolExecutor."""
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bulk_importer.orchestrator import _process_file_worker
from bulk_importer.scanner import scan_directory

root = Path(r"C:\Users\Iran\Desktop\temce\data brsapi\codal_excel_files")
files = scan_directory(root)[:5]
paths = [sf.file_path for sf in files]

print(f"Testing {len(paths)} files in subprocess...")

with ProcessPoolExecutor(max_workers=2) as ex:
    results = list(ex.map(_process_file_worker, paths, timeout=60))

for r in results:
    fmt = r.get("format")
    err = r.get("error")
    pr = r.get("result")
    tables = len(pr.tables) if pr else 0
    print(f"  format={fmt} tables={tables} error={err}")
