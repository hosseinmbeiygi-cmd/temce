"""Debug: test worker in ProcessPoolExecutor subprocess."""
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bulk_importer.orchestrator import _process_file_worker
from bulk_importer.scanner import scan_directory


def _worker(file_path: str) -> dict:
    return _process_file_worker(file_path)


root = Path(r"C:\Users\Iran\Desktop\temce\data brsapi\codal_excel_files")
files = scan_directory(root)[:10]
paths = [sf.file_path for sf in files]

print(f"Testing {len(paths)} files in subprocess...")

with ProcessPoolExecutor(max_workers=2) as executor:
    futures = {executor.submit(_worker, p): p for p in paths}
    for future in as_completed(futures):
        fp = futures[future]
        try:
            result = future.result(timeout=30)
            err = result.get("error")
            fmt = result.get("format")
            pr = result.get("result")
            tables = len(pr.tables) if pr else 0
            print(f"  OK: {Path(fp).name} format={fmt} tables={tables} error={err}")
        except Exception as e:
            print(f"  EXCEPTION: {Path(fp).name}: {e}")
