"""لایه DB صندوق‌یار — Session و تنظیمات.

پشتیبانی از دو حالت:
1. بدون DB (پیش‌فرض): سیستم با seed داده در حافظه کار می‌کند (dev/demo)
2. با PostgreSQL + TimescaleDB: مدل‌ها به‌صورت جدول واقعی ساخته می‌شوند
"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

_engine = None
_session_factory: sessionmaker | None = None


def configure_db(database_url: str | None = None, **engine_kwargs: Any) -> None:
    """پیکربندی اتصال DB.

    database_url مثل: postgresql+psycopg://user:pass@host:5432/dbname
    اگر None باشد → SQLite در فایل (برای تست/dev بدون سرور).
    """
    global _engine, _session_factory
    url = database_url or os.environ.get("SANDOOGHYAR_DB_URL") or "sqlite:///sandooghyar.db"
    _engine = create_engine(url, **engine_kwargs)
    _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


def init_db(database_url: str | None = None) -> None:
    """ساخت جداول + seed داده."""
    configure_db(database_url)
    assert _engine is not None
    Base.metadata.create_all(_engine)
    _seed_if_empty()


def get_session() -> Session:
    """دریافت session — در FastAPI باید به‌صورت generator استفاده شود."""
    assert _session_factory is not None, "call init_db() first"
    return _session_factory()


def session_scope():
    """Context manager برای session — با commit/rollback خودکار."""
    assert _session_factory is not None, "call init_db() first"
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _seed_if_empty() -> None:
    from .models import Fund
    from .services import _SEED_FUNDS

    with session_scope() as session:
        existing = session.query(Fund).first()
        if existing is not None:
            return
        for f in _SEED_FUNDS:
            session.add(
                Fund(
                    symbol=f["symbol"],
                    name_fa=f["name_fa"],
                    type_code=f["type_code"],
                    manager=f.get("manager"),
                    is_etf=f.get("is_etf", True),
                )
            )
