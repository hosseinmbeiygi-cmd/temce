"""Signal Composer (Layer 5): rank + dedupe + cap + idempotency (5.2). Output = direct input of store/API."""
from __future__ import annotations
from sqlalchemy import select

def rank(signals: list[dict], max_n: int = 20) -> list[dict]:
    for s in signals:
        liq = float(s.get("liquidity", 1.0))
        s["_score"] = float(s.get("confidence",0)) * liq
    # dedupe highly correlated: keep best per (symbol,market,timeframe)
    best: dict = {}
    for s in sorted(signals, key=lambda x: -x["_score"]):
        k = (s["symbol"], s.get("market"), s.get("timeframe"))
        if k not in best: best[k] = s
    return sorted(best.values(), key=lambda x: -x["_score"])[:max_n]

def check_idempotent(session, symbol, market, timeframe, direction):
    """Return existing pending signal or None. Supersede if direction flipped."""
    from models.signal import SignalModel
    row = session.scalars(select(SignalModel).where(
        SignalModel.symbol==symbol, SignalModel.market==market,
        SignalModel.timeframe==timeframe, SignalModel.status=="pending")).first()
    if row is None: return None, "new"
    if row.direction == direction: return row, "duplicate_skip"
    row.status = "superseded"; session.commit()
    return None, "superseded_old"

def compose(session, candidates: list[dict], max_n=20, save_fn=None) -> list[dict]:
    out = []
    for s in rank(candidates, max_n):
        _, action = check_idempotent(session, s["symbol"], s.get("market"), s.get("timeframe"), s.get("direction"))
        if action == "duplicate_skip": continue
        if save_fn: save_fn(session, s)
        out.append(s)
    return out
