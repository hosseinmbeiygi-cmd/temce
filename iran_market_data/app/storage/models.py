from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Column, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    name = Column(String)
    market = Column(String)
    industry = Column(String)
    source = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class DailyPrice(Base):
    __tablename__ = "daily_prices"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    date = Column(Date, index=True)

    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    final = Column(Float)

    volume = Column(BigInteger)
    value = Column(BigInteger)
    trade_count = Column(BigInteger)

    source = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class CodalAnnouncement(Base):
    __tablename__ = "codal_announcements"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    title = Column(Text)
    publish_date = Column(String)
    report_type = Column(String)
    detail_url = Column(Text)
    file_url = Column(Text)
    raw_path = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class FundInfo(Base):
    __tablename__ = "funds"

    id = Column(Integer, primary_key=True)
    fund_name = Column(String, index=True)
    fund_type = Column(String)
    nav = Column(Float)
    date = Column(Date)
    return_1m = Column(Float)
    return_3m = Column(Float)
    return_1y = Column(Float)
    source = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
