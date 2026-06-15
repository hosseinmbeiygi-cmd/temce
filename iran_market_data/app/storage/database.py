from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///data/iran_market.db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal: sessionmaker[Session] = sessionmaker(bind=engine)


def get_db_session() -> Session:
    return SessionLocal()
