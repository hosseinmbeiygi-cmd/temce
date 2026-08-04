"""Debug: parse 10 files and inspect results."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")

from bulk_importer.orchestrator import _process_file_worker
from bulk_importer.scanner import scan_directory

# Scan 10 files
root = Path(r"C:\Users\Iran\Desktop\temce\data brsapi\codal_excel_files")
files = scan_directory(root)
print(f"Total files: {len(files)}")

# Pick 5 test files
test_files = [sf.file_path for sf in files[:5]]
for fp in test_files:
    print(f"\n--- Testing: {fp} ---")
    result = _process_file_worker(fp)
    print(f"  format: {result.get('format')}")
    print(f"  sha256: {str(result.get('sha256'))[:20]}...")
    print(f"  error: {result.get('error')}")
    pr = result.get('result')
    if pr:
        print(f"  tables: {len(pr.tables)}")
        print(f"  total_rows: {pr.total_rows}")
        print(f"  status: {pr.status}")
        if pr.errors:
            print(f"  parse_errors: {pr.errors[:3]}")
    else:
        print("  result: None")
