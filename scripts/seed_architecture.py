#!/usr/bin/env python3
"""
🏛️ Seed Architecture — اجرای migration و بارگذاری داده‌های JSON معماری

این اسکریپت دو کار انجام می‌دهد:
  1. اجرای Alembic migration (ایجاد جداول decision_architectures و decision_results)
  2. بارگذاری ۵ فایل JSON معماری در جدول decision_architectures

فایل‌های JSON (مسیر json/):
  - architecture.json   ← ساختار اصلی ۱۲ لایه
  - features.json       ← ۱۱۰ ویژگی در ۸ بلوک
  - services.json       ← ۲۲ سرویس
  - database.json       ← جداول دیتابیس
  - api.json            ← ۳۱+ API endpoint

مصرف:
    python scripts/seed_architecture.py
    python scripts/seed_architecture.py --skip-migration
    python scripts/seed_architecture.py --json-dir /path/to/json
    python scripts/seed_architecture.py --db-url postgresql+asyncpg://user:pass@localhost:5432/mydb
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# ── Paths ──────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JSON_DIR = PROJECT_ROOT / "json"


# ── JSON loading ───────────────────────────────────────────────────

def load_json(path: Path) -> dict[str, Any] | None:
    """Load a JSON file and return its contents, or None if not found."""
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def merge_architecture(json_dir: Path) -> dict[str, Any] | None:
    """Load all 5 JSON files and merge into one architecture record.

    Returns None if architecture.json is missing.
    """
    arch = load_json(json_dir / "architecture.json")
    if arch is None:
        return None

    for key, fname in [
        ("features", "features.json"),
        ("services", "services.json"),
        ("database", "database.json"),
        ("api", "api.json"),
    ]:
        data = load_json(json_dir / fname)
        if data is not None:
            arch[key] = data
            print(f"  ✅ Merged {fname} → architecture.{key}")
        else:
            print(f"  ⚠️  {fname} not found, skipping")

    return arch


# ── Migration ──────────────────────────────────────────────────────

def run_migration() -> bool:
    """Run alembic upgrade head. Returns True on success."""
    print("\n📦 Running Alembic migration...")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("  ✅ Migration successful")
        if result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                print(f"     {line}")
        return True
    else:
        print(f"  ❌ Migration failed (exit code {result.returncode})")
        if result.stderr.strip():
            for line in result.stderr.strip().split("\n"):
                print(f"     {line}")
        return False


# ── Database seeding ───────────────────────────────────────────────

async def seed_database(
    db_url: str | None = None,
    json_dir: Path = DEFAULT_JSON_DIR,
    skip_migration: bool = False,
) -> bool:
    """Connect to DB, run migration (optional), load JSON, seed architecture."""
    import os

    from sqlalchemy import NullPool, select, text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    # ── Migration ──
    if not skip_migration:
        if not run_migration():
            print("  ⚠️  Continuing without migration (tables may already exist)")
    else:
        print("  ⏭️  Migration skipped (--skip-migration)")

    # ── Database connection ──
    if db_url is None:
        try:
            sys.path.insert(0, str(PROJECT_ROOT))
            from core.config import settings

            db_url = settings.database_url_async
            print("  📡 Using database URL from settings")
        except ImportError:
            db_url = os.environ.get(
                "DATABASE_URL_ASYNC",
                "postgresql+asyncpg://postgres:postgres@localhost:5432/tse_quant",
            )
            print("  📡 Using database URL from env / default")

    print("  🔗 Connecting to database...")

    engine = create_async_engine(db_url, echo=False, poolclass=NullPool)

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        print("  ✅ Database connection OK")
    except Exception as exc:
        print(f"  ❌ Database connection failed: {exc}")
        await engine.dispose()
        return False

    # ── Load JSON data ──
    print(f"\n📂 Loading JSON files from {json_dir}...")
    arch = merge_architecture(json_dir)
    if arch is None:
        print(f"  ❌ architecture.json not found in {json_dir}")
        await engine.dispose()
        return False

    version = arch.get("system", {}).get("version", "unknown")
    title = arch.get("system", {}).get("name", "سامانه تصمیم‌یار بورس تهران")
    layers_count = len(arch.get("layers", []))
    features_count = arch.get("features", {}).get("meta", {}).get("total_features", 0)
    services_count = arch.get("services", {}).get("meta", {}).get("total_services", 0)

    # ── Create tables (in case migration was skipped and tables don't exist) ──
    import models.decision_engine  # noqa: F401 — register model with Base
    from models.base import Base
    from models.decision_engine import DecisionArchitecture

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  ✅ Tables verified/created")

    # ── Insert / Update architecture record ──
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        try:
            result = await session.execute(
                select(DecisionArchitecture).where(DecisionArchitecture.version == version)
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.data = arch
                existing.is_active = True
                existing.title = title
                print(f"  🔄 Architecture v{version} already exists — updated")
            else:
                record = DecisionArchitecture(
                    version=version,
                    title=title,
                    data=arch,
                    is_active=True,
                )
                session.add(record)
                print(f"  ➕ Architecture v{version} created")

            await session.commit()

            # ── Summary ──
            print(f"\n{'=' * 55}")
            print("  🏛️  Architecture seeded successfully!")
            print(f"  {'Version:':15s} {version}")
            print(f"  {'Title:':15s} {title}")
            print(f"  {'Layers:':15s} {layers_count}")
            print(f"  {'Features:':15s} {features_count}")
            print(f"  {'Services:':15s} {services_count}")
            print(f"{'=' * 55}")

            return True

        except Exception as exc:
            await session.rollback()
            print(f"  ❌ Failed to seed architecture: {exc}")
            return False
        finally:
            await session.close()

    await engine.dispose()
    return True


# ── CLI ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="🏛️  Seed Architecture — migration + JSON data loading for decision_architectures",
    )
    parser.add_argument(
        "--skip-migration",
        action="store_true",
        help="Skip Alembic migration (assume tables already exist)",
    )
    parser.add_argument(
        "--json-dir",
        type=str,
        default=str(DEFAULT_JSON_DIR),
        help=f"Path to JSON files directory (default: {DEFAULT_JSON_DIR})",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Database URL (async format, e.g. postgresql+asyncpg://user:pass@host/db). Defaults to settings or env.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load and validate JSON files without connecting to database",
    )

    args = parser.parse_args()
    json_dir = Path(args.json_dir)

    start_time = time.time()

    print(f"{'=' * 55}")
    print("  🏛️  Seed Architecture — version loader")
    print(f"  📂 JSON: {json_dir}")
    if args.skip_migration:
        print("  ⏭️  Migration: skipped")
    if args.db_url:
        host = args.db_url.split("@")[-1] if "@" in args.db_url else args.db_url
        print(f"  📡 DB:    {host}")
    print(f"{'=' * 55}")

    # ── Dry-run: validate JSON files only ──
    if args.dry_run:
        print("\n🔍 Dry-run — validating JSON files...")
        arch = merge_architecture(json_dir)
        if arch is None:
            print("\n  ❌ architecture.json not found — aborting")
            sys.exit(1)

        version = arch.get("system", {}).get("version", "unknown")
        title = arch.get("system", {}).get("name", "unknown")
        layers_count = len(arch.get("layers", []))
        features_count = arch.get("features", {}).get("meta", {}).get("total_features", 0)
        services_count = arch.get("services", {}).get("meta", {}).get("total_services", 0)
        db_tables = len(arch.get("database", {}).get("tables", []))
        api_internal = len(arch.get("api", {}).get("internal", []))
        api_external = len(arch.get("api", {}).get("external", []))

        print(f"\n{'=' * 55}")
        print("  📊 Architecture Summary (dry-run)")
        print(f"  {'Version:':20s} {version}")
        print(f"  {'Title:':20s} {title}")
        print(f"  {'Layers:':20s} {layers_count}")
        print(f"  {'Features:':20s} {features_count}")
        print(f"  {'Services:':20s} {services_count}")
        print(f"  {'DB Table Groups:':20s} {db_tables}")
        print(f"  {'API Internal:':20s} {api_internal}")
        print(f"  {'API External:':20s} {api_external}")
        print(f"{'=' * 55}")
        print("\n✅ Dry-run complete — no data written to database")
        return

    # ── Real run: seed database ──
    import asyncio

    success = asyncio.run(seed_database(
        db_url=args.db_url,
        json_dir=json_dir,
        skip_migration=args.skip_migration,
    ))

    elapsed = time.time() - start_time
    print(f"\n⏱️  Total time: {elapsed:.2f}s")

    if success:
        print("✅ Seed complete")
    else:
        print("❌ Seed failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
