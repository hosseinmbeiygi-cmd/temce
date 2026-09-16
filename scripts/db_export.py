"""Export all public tables of the database to CSV files.

Recovered from the removed root-level postgresql_client.py and adapted to
the project conventions: connection details come from ``core.settings``
(via ``scripts/_db.py``) instead of hardcoded PG_* env vars.

Usage:
    python scripts/db_export.py [-o OUTPUT_DIR] [--batch-size N]

Creates ``<output_dir>/export_<timestamp>/<table>.csv`` for every table in
the ``public`` schema, batched to keep memory usage bounded.
"""
import argparse
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _db import psycopg2_connect  # noqa: E402
from psycopg2 import sql  # noqa: E402

from core.time import now_utc


def export_all_to_csv(output_dir: str = "exports", batch_size: int = 10000) -> dict:
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    timestamp = now_utc().strftime("%Y%m%d_%H%M%S")
    export_dir = os.path.join(output_dir, f"export_{timestamp}")
    os.makedirs(export_dir, exist_ok=True)

    result = {}
    conn = psycopg2_connect()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name NOT LIKE 'pg_%'
                AND table_name != 'information_schema'
                """
            )
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                csv_path = os.path.join(export_dir, f"{table}.csv")
                try:
                    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
                        writer = csv.writer(csvfile)
                        cursor.execute(sql.SQL('SELECT * FROM {} LIMIT 1').format(sql.Identifier(table)))
                        columns = [desc[0] for desc in cursor.description]
                        writer.writerow(columns)

                        offset = 0
                        while True:
                            cursor.execute(
                                sql.SQL('SELECT * FROM {} LIMIT %s OFFSET %s').format(sql.Identifier(table)),
                                (batch_size, offset),
                            )
                            records = cursor.fetchall()
                            if not records:
                                break
                            writer.writerows(records)
                            offset += batch_size

                    file_size = os.path.getsize(csv_path)
                    result[table] = {
                        "path": csv_path,
                        "size_bytes": file_size,
                        "records": file_size > 0,
                    }
                except Exception as e:
                    print(f"Error exporting table {table}: {e}")
                    result[table] = {"path": csv_path, "error": str(e)}
    finally:
        conn.close()

    return result


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export every table in the public schema to CSV files.",
        epilog="Connection details come from core.settings (DATABASE_URL in .env).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="exports",
        help="Base directory for the export (default: ./exports).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10000,
        help="Rows fetched per batch (default: 10000).",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    export_result = export_all_to_csv(args.output_dir, args.batch_size)

    print("\n=== Exported tables ===")
    for table, info in export_result.items():
        if "error" in info:
            print(f"\n{table}:\n  - error: {info['error']}")
        else:
            print(
                f"\n{table}:\n"
                f"  - path: {info['path']}\n"
                f"  - size: {info['size_bytes'] / 1024:.2f} KB"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
