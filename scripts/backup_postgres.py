#!/usr/bin/env python3
"""PostgreSQL backup script with rotation, compression, and S3 sync support.

Usage:
    python scripts/backup_postgres.py                  # manual backup
    python scripts/backup_postgres.py --auto            # automated (cron) mode, no prompts
    python scripts/backup_postgres.py --list            # list available backups
    python scripts/backup_postgres.py --restore <file>  # restore from backup (dangerous)

Env vars:
    DATABASE_URL     - PostgreSQL connection string
    BACKUP_DIR       - backup storage directory (default: ./backups)
    BACKUP_RETENTION - number of backups to keep (default: 14)
    S3_BUCKET        - optional S3 bucket for off-site backup
    S3_PREFIX        - optional S3 prefix (default: postgres-backups)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "./backups"))
RETENTION = int(os.getenv("BACKUP_RETENTION", "14"))
DATABASE_URL = os.getenv("DATABASE_URL", "")
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_PREFIX = os.getenv("S3_PREFIX", "postgres-backups")


def _parse_pg_url(url: str) -> dict[str, str]:
    parts = url.replace("://", " ").split()
    if len(parts) != 2:
        return {}
    rest = parts[1]
    creds, hostpart = rest.split("@") if "@" in rest else ("", rest)
    user_pass = creds.split(":") if ":" in creds else [creds]
    host_port_db = hostpart.split("/") if "/" in hostpart else [hostpart, ""]
    host_port = host_port_db[0].split(":") if ":" in host_port_db[0] else [host_port_db[0], "5432"]
    result = {
        "host": host_port[0],
        "port": host_port[1],
        "dbname": host_port_db[1] if len(host_port_db) > 1 else "",
    }
    if len(user_pass) >= 1 and user_pass[0]:
        result["user"] = user_pass[0]
    if len(user_pass) >= 2:
        result["password"] = user_pass[1]
    return result


def _ensure_pg_tools() -> None:
    for tool in ["pg_dump", "pg_restore"]:
        try:
            subprocess.run([tool, "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"Error: {tool} not found. Install PostgreSQL client tools.")
            sys.exit(1)


def _backup_filename() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"market_backup_{ts}.dump"


def create_backup() -> Path:
    _ensure_pg_tools()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    pg_conf = _parse_pg_url(DATABASE_URL)
    if not pg_conf.get("dbname"):
        print("Error: DATABASE_URL is not set or invalid")
        sys.exit(1)

    fname = _backup_filename()
    fpath = BACKUP_DIR / fname

    env = os.environ.copy()
    if pg_conf.get("password"):
        env["PGPASSWORD"] = pg_conf["password"]

    print(f"Backing up database '{pg_conf['dbname']}' on {pg_conf['host']}:{pg_conf['port']} ...")
    cmd = [
        "pg_dump",
        "-h",
        pg_conf["host"],
        "-p",
        pg_conf["port"],
        "-U",
        pg_conf.get("user", "postgres"),
        "-d",
        pg_conf["dbname"],
        "-F",
        "c",
        "-f",
        str(fpath),
        "--verbose",
    ]
    subprocess.run(cmd, env=env, check=True)

    size_mb = fpath.stat().st_size / (1024 * 1024)
    print(f"Backup created: {fpath} ({size_mb:.1f} MB)")

    if S3_BUCKET:
        _sync_to_s3(fpath)

    _rotate_backups()
    return fpath


def list_backups() -> list[Path]:
    if not BACKUP_DIR.exists():
        return []
    return sorted(BACKUP_DIR.glob("market_backup_*.dump"), reverse=True)


def _rotate_backups() -> None:
    backups = list_backups()
    if len(backups) <= RETENTION:
        return
    for old in backups[RETENTION:]:
        old.unlink()
        print(f"Removed old backup: {old}")


def _sync_to_s3(path: Path) -> None:
    try:
        subprocess.run(
            ["aws", "s3", "cp", str(path), f"s3://{S3_BUCKET}/{S3_PREFIX}/{path.name}"],
            check=True,
        )
        print(f"Synced to S3: s3://{S3_BUCKET}/{S3_PREFIX}/{path.name}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Warning: S3 sync failed (aws CLI not configured or not installed)")


def restore_backup(fname: str) -> None:
    _ensure_pg_tools()
    fpath = BACKUP_DIR / fname
    if not fpath.exists():
        print(f"Backup not found: {fpath}")
        sys.exit(1)

    pg_conf = _parse_pg_url(DATABASE_URL)
    if not pg_conf.get("dbname"):
        print("Error: DATABASE_URL is not set or invalid")
        sys.exit(1)

    print(f"WARNING: This will DROP and RESTORE database '{pg_conf['dbname']}' on {pg_conf['host']}:{pg_conf['port']}")
    print(f"From backup: {fpath}")
    if not os.environ.get("CI") and "--auto" not in sys.argv:
        confirm = input("Type 'yes' to continue: ")
        if confirm != "yes":
            print("Aborted.")
            sys.exit(1)

    env = os.environ.copy()
    if pg_conf.get("password"):
        env["PGPASSWORD"] = pg_conf["password"]

    subprocess.run(
        [
            "pg_restore",
            "-h",
            pg_conf["host"],
            "-p",
            pg_conf["port"],
            "-U",
            pg_conf.get("user", "postgres"),
            "-d",
            pg_conf["dbname"],
            "--clean",
            "--if-exists",
            "--verbose",
            str(fpath),
        ],
        env=env,
        check=True,
    )
    print("Restore completed successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="PostgreSQL backup manager")
    parser.add_argument("--auto", action="store_true", help="Non-interactive mode")
    parser.add_argument("--list", action="store_true", help="List available backups")
    parser.add_argument("--restore", type=str, help="Restore from backup file")
    args = parser.parse_args()

    if args.list:
        backups = list_backups()
        if not backups:
            print("No backups found.")
            return
        for i, b in enumerate(backups, 1):
            size_kb = b.stat().st_size / 1024
            print(f"{i:3d}. {b.name} ({size_kb:.0f} KB)")
        return

    if args.restore:
        restore_backup(args.restore)
        return

    create_backup()


if __name__ == "__main__":
    main()
