from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _read_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    try:
        from dotenv import dotenv_values
        url = dotenv_values().get("DATABASE_URL") or ""
    except Exception:
        url = ""
    return url or "sqlite:///data/iran_market.db"


DATABASE_URL: str = _read_database_url()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal: sessionmaker[Session] = sessionmaker(bind=engine)


def get_db_session() -> Session:
    return SessionLocal()
