"""Test: run worker in subprocess and see the actual error."""

import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def _worker(fp):
    from bulk_importer.orchestrator import _process_file_worker

    return _process_file_worker(fp)


if __name__ == "__main__":
    from bulk_importer.scanner import scan_directory

    root = Path(r"C:\Users\Iran\Desktop\temce\data brsapi\codal_excel_files")
    files = scan_directory(root)[:5]
    paths = [sf.file_path for sf in files]

    print(f"Testing {len(paths)} files in subprocess...")
    with ProcessPoolExecutor(max_workers=2) as ex:
        futures = [ex.submit(_worker, p) for p in paths]
        for i, f in enumerate(futures):
            r = f.result(timeout=30)
            print(f"  [{i}] format={r.get('format')} error={r.get('error')} result={r.get('result') is not None}")

