"""Calibration loop (Layer 7) + RETRAIN_MODE/SHADOW_MODE flags."""
from __future__ import annotations
import os
from sqlalchemy import select
RETRAIN_MODE = os.getenv("RETRAIN_MODE","manual")  # manual|automatic (central, no redeploy)
SHADOW_MODE = os.getenv("SHADOW_MODE","false").lower()=="true"
WIN_RATE_ALERT = float(os.getenv("WIN_RATE_ALERT","0.40"))

def calibrate(session, market, timeframe, window=100):
    from models.signal import SignalModel
    rows = session.scalars(select(SignalModel).where(
        SignalModel.market==market,SignalModel.timeframe==timeframe,
        SignalModel.status.in_(["hit_target","hit_stop","expired_neutral"]))
        .order_by(SignalModel.checked_at.desc()).limit(window)).all()
    if not rows: return {"win_rate":None,"sample_size":0,"needs_retrain":False}
    wr = sum(1 for r in rows if r.was_correct)/len(rows)
    return {"win_rate":round(wr,4),"sample_size":len(rows),
        "needs_retrain": wr<WIN_RATE_ALERT and len(rows)>=10,
        "low_sample": len(rows)<30}

def shadow_report(session):
    from models.signal import SignalModel
    from config.timeframes import ALL
    from models.signal import SignalModel as S
    rep={}
    for m in ["stock","fund","gold","usd","option","commodity"]:
        for tf in ALL:
            c=calibrate(session,m,tf)
            if c["sample_size"]: rep[f"{m}x{tf}"]=c
    return rep
