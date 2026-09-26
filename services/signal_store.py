"""Signal Store: DB-backed (atomic, concurrency-safe per 5.10), append-only logically, JSON export w/ monthly rotation."""
from __future__ import annotations
import json, os, uuid
from datetime import datetime, timezone
from sqlalchemy import select
from config.timeframes import eval_due_at

SCHEMA_VERSION = 1

def build_signal(symbol, market, timeframe, direction, entry, stop_loss, take_profit,
                 confidence, top_reasons, backtest_stats, model_version, created_at=None, trading_calendar=None):
    created_at = created_at or datetime.now(timezone.utc)
    return {"signal_id": str(uuid.uuid4()), "symbol": symbol, "market": market,
        "timeframe": timeframe, "direction": direction, "entry": float(entry),
        "stop_loss": float(stop_loss), "take_profit": float(take_profit),
        "confidence": float(confidence), "top_reasons": list(top_reasons or [])[:5],
        "backtest_stats": backtest_stats or {"win_rate":0.0,"avg_return":0.0,"sample_size":0},
        "created_at": created_at, "eval_due_at": eval_due_at(created_at, timeframe, trading_calendar),
        "schema_version": SCHEMA_VERSION, "model_version": model_version or "unknown",
        "status": "pending", "actual_outcome_price": None, "actual_return_pct": None,
        "was_correct": None, "checked_at": None}

def save_signal(session, sig: dict):
    from models.signal import SignalModel
    row = SignalModel(id=sig["signal_id"], symbol=sig["symbol"], market=sig.get("market"),
        signal_type=sig.get("direction",""), direction=sig.get("direction"),
        strength=sig.get("confidence"), timeframe=sig.get("timeframe"),
        entry=sig.get("entry"), stop_loss=sig.get("stop_loss"), take_profit=sig.get("take_profit"),
        confidence=sig.get("confidence"), top_reasons=json.dumps(sig.get("top_reasons",[]), ensure_ascii=False),
        backtest_stats=json.dumps(sig.get("backtest_stats",{}), ensure_ascii=False),
        generated_at=sig.get("created_at"), eval_due_at=sig.get("eval_due_at"),
        schema_version=sig.get("schema_version",1), model_version=sig.get("model_version"),
        status="pending")
    session.add(row); session.commit()  # DB transaction = atomic, no JSON corruption (5.10)
    return row

def update_evaluation(session, signal_id: str, **fields):
    from models.signal import SignalModel
    row = session.get(SignalModel, signal_id)
    if not row: return None
    for k,v in fields.items():
        if hasattr(row,k): setattr(row,k,v)
    if isinstance(fields.get("top_reasons"),list): row.top_reasons=json.dumps(fields["top_reasons"],ensure_ascii=False)
    if isinstance(fields.get("backtest_stats"),dict): row.backtest_stats=json.dumps(fields["backtest_stats"],ensure_ascii=False)
    session.commit(); return row

def pending_due(session, now=None):
    from models.signal import SignalModel
    now = now or datetime.now(timezone.utc)
    return list(session.scalars(select(SignalModel).where(SignalModel.status=="pending", SignalModel.eval_due_at<=now)))

def export_json(session, out_dir="data/signals", month: str | None = None):
    """Monthly-rotated JSON dump (3.1)."""
    from models.signal import SignalModel
    os.makedirs(out_dir, exist_ok=True)
    month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    rows = session.scalars(select(SignalModel)).all()
    data = [{"signal_id":r.id,"symbol":r.symbol,"market":r.market,"timeframe":r.timeframe,
        "direction":r.direction,"entry":r.entry,"stop_loss":r.stop_loss,"take_profit":r.take_profit,
        "confidence":r.confidence,"top_reasons":json.loads(r.top_reasons or "[]"),
        "backtest_stats":json.loads(r.backtest_stats or "{}"),"created_at":str(r.generated_at),
        "eval_due_at":str(r.eval_due_at),"schema_version":r.schema_version,"model_version":r.model_version,
        "status":r.status,"actual_outcome_price":r.actual_outcome_price,"actual_return_pct":r.actual_return_pct,
        "was_correct":r.was_correct,"checked_at":str(r.checked_at) if r.checked_at else None} for r in rows]
    # schema_version backward-compat read: default missing keys
    path = os.path.join(out_dir, f"signals-{month}.json")
    tmp = path + ".tmp"
    with open(tmp,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,default=str)
    os.replace(tmp,path)  # atomic rename
    return path, len(data)
