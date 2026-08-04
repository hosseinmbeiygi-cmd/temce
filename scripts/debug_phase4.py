"""Debug Phase 4: simulate classification and check what happens."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.WARNING)

from bulk_importer.orchestrator import _process_file_worker
from bulk_importer.scanner import scan_directory
from bulk_importer.validator import validate_parse_result

root = Path(r"C:\Users\Iran\Desktop\temce\data brsapi\codal_excel_files")
files = scan_directory(root)[:50]

results_map = {}
for sf in files:
    results_map[sf.file_path] = _process_file_worker(sf.file_path)

# Now simulate the classification in _validate_and_persist
error_count = 0
unsupported_count = 0
valid_count = 0
errors = []

for _file_path, res in results_map.items():
    error = res.get("error")
    result = res.get("result")
    fmt = res.get("format", "unknown")

    if error:
        error_count += 1
        errors.append(f"error: {error[:80]}")
        continue

    if result is None or result.status == "unsupported" or fmt == "unknown":
        unsupported_count += 1
        continue

    vr = validate_parse_result(result)
    if not vr.is_valid:
        error_count += 1
        errors.append(f"invalid: {vr.errors}")
        continue

    valid_count += 1

print(f"Errors: {error_count}")
print(f"Unsupported: {unsupported_count}")
print(f"Valid: {valid_count}")
for e in errors[:5]:
    print(f"  {e}")
