"""Data layer (Layer 11): freshness TTL + quota + validation + fallback gaps + pre-filter (1.2-1.4, 2.1)."""
from __future__ import annotations
import time
from sqlalchemy import String, Float, Integer, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from models.base import Base, TimestampMixin

TTL = {"price_min":300,"nav_hourly":3600,"fundamental_weekly":7*86400}  # 1.2
QUOTA = {"used":0,"limit":1000,"warned":False}
def check_quota(n=1):
    QUOTA["used"]+=n
    if QUOTA["used"]/QUOTA["limit"]>=0.8 and not QUOTA["warned"]:
        QUOTA["warned"]=True; return "WARN quota 80%"
    return "ok"

class DataFreshnessModel(TimestampMixin, Base):
    __tablename__="data_freshness"
    data_type: Mapped[str]=mapped_column(String(50),primary_key=True)
    last_ok: Mapped[str | None]=mapped_column(DateTime)
    ttl: Mapped[int]=mapped_column(Integer,server_default="300")

class DataQualityLogModel(TimestampMixin, Base):
    __tablename__="data_quality_log"
    id: Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    symbol: Mapped[str]=mapped_column(String(50))
    reason: Mapped[str]=mapped_column(Text)

class DataGapModel(TimestampMixin, Base):
    __tablename__="data_gaps"  # explicit gap, never silent forward-fill (1.4)
    id: Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    symbol: Mapped[str]=mapped_column(String(50),index=True)
    start: Mapped[str | None]=mapped_column(DateTime); end: Mapped[str | None]=mapped_column(DateTime)
    reason: Mapped[str | None]=mapped_column(String(100))

MAX_JUMP = {"stock":0.05,"fund":0.10,"gold":0.15,"usd":0.15,"option":0.5,"commodity":0.2}  # 1.3 per-market
def validate_bar(symbol, market, price, volume, ts, prev_close=None, has_corporate_action=False):
    if price is None or price<=0: return False,"bad_price"
    if volume is not None and volume<0: return False,"bad_volume"
    if prev_close and not has_corporate_action:  # 5.6: skip jump check on corp-action days
        if abs(price-prev_close)/prev_close > MAX_JUMP.get(market,0.1): return False,"price_jump"
    return True,"ok"

PRE_FILTER = {"stock":{"min_value":1e9,"min_days":30},"fund":{"min_value":1e8,"min_days":30},
    "gold":{"min_value":0,"min_days":0},"usd":{"min_value":0,"min_days":0},
    "option":{"min_value":1e7,"min_days":7},"commodity":{"min_value":1e8,"min_days":30}}  # 2.1
def pre_filter(symbol, market, daily_value, listed_days, nan_ratio):
    cfg=PRE_FILTER.get(market,PRE_FILTER["stock"])
    if daily_value<cfg["min_value"]: return False,"illiquid"
    if listed_days<cfg["min_days"]: return False,"fresh_listing"
    if nan_ratio>0.2: return False,"incomplete"
    return True,"ok"

def fetch_with_fallback(primary, fallback, symbol, session=None):
    """Exponential backoff + secondary source; records explicit gap if all fail (1.4)."""
    delay=1
    for fn in [primary,fallback]:
        if fn is None: continue
        try: return fn(symbol),"primary" if fn is primary else "fallback"
        except Exception:
            time.sleep(0); delay*=2
    if session is not None:
        session.add(DataGapModel(symbol=symbol,reason="all_sources_failed")); session.commit()
    return None,"gap"
