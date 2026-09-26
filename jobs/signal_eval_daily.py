"""Daily eval job (6.2) + fees/limit-bands (5.7). Reads prices from main DB, never brsapi."""
from __future__ import annotations
from datetime import datetime, timezone

# commission per market (round-trip fraction), configurable
FEES = {"stock":0.015,"fund":0.002,"gold":0.002,"usd":0.001,"option":0.01,"commodity":0.005}

def evaluate(signal: dict, bars: list[dict], halted_days: set | None = None) -> dict:
    """bars: [{high,low,close}] between created_at..eval_due_at. halted_days: indices locked (limit-band)."""
    halted_days = halted_days or set()
    entry, direction = signal["entry"], signal["direction"]
    hit_tp = hit_sl = False
    for i,b in enumerate(bars):
        if i in halted_days: continue  # 5.7: locked -> cannot exit, keep pending
        if direction=="buy":
            if b["high"]>=signal["take_profit"]: hit_tp=True; px=signal["take_profit"]; break
            if b["low"]<=signal["stop_loss"]: hit_sl=True; px=signal["stop_loss"]; break
        elif direction=="sell":
            if b["low"]<=signal["take_profit"]: hit_tp=True; px=signal["take_profit"]; break
            if b["high"]>=signal["stop_loss"]: hit_sl=True; px=signal["stop_loss"]; break
    else:
        px = bars[-1]["close"] if bars else entry
    fee = FEES.get(signal.get("market","stock"),0.01)
    gross = (px-entry)/entry if direction=="buy" else (entry-px)/entry if direction=="sell" else 0.0
    net = gross - fee
    if hit_tp: status="hit_target"; correct = direction in ("buy","sell")
    elif hit_sl: status="hit_stop"; correct=False
    else: status="expired_neutral"; correct = net>0
    return {"status":status,"actual_outcome_price":px,"actual_return_pct":round(net*100,4),
        "gross_return_pct":round(gross*100,4),"was_correct":correct,"checked_at":datetime.now(timezone.utc)}

def notify_subscribers(session, signal_id: str, symbol: str, status: str, price: float) -> int:
    """Sync-safe: notify enabled signal-linked alerts (alerts.signal_id).
    Writes history rows + bumps counters; delivery itself happens through
    the alert channels worker/console. Returns notified count."""
    try:
        from sqlalchemy import text as _text
        rows = session.execute(_text(
            "SELECT id, channels FROM alerts WHERE signal_id=:sid AND enabled IS NOT DISTINCT FROM true"),
            {"sid": signal_id}).fetchall()
        import uuid as _uuid, datetime as _dt
        for aid, _ch in rows:
            session.execute(_text(
                "INSERT INTO alert_history (id, alert_id, trigger_value, message, delivered)"
                " VALUES (:id,:aid,:px,:msg,:d)"),
                {"id": "alh" + _uuid.uuid4().hex[:21], "aid": aid, "px": price,
                 "msg": f"Signal {symbol} [{signal_id[:8]}]: {status} @ {price}", "d": True})
            session.execute(_text(
                "UPDATE alerts SET triggered_count=COALESCE(triggered_count,0)+1,"
                " last_triggered=:now WHERE id=:aid"),
                {"now": _dt.datetime.utcnow(), "aid": aid})
        session.commit()
        return len(rows)
    except Exception:
        try: session.rollback()
        except Exception: pass
        return 0

def run_daily(session, price_loader, now=None):
    from services.signal_store import pending_due, update_evaluation
    done=[]
    for row in pending_due(session, now):
        sig={"entry":row.entry,"take_profit":row.take_profit,"stop_loss":row.stop_loss,
             "direction":row.direction,"market":row.market}
        bars=price_loader(row.symbol, row.generated_at, row.eval_due_at)
        res=evaluate(sig,bars)
        update_evaluation(session,row.id,**res)
        try:
            n = notify_subscribers(session, row.id, row.symbol, res["status"], res["actual_outcome_price"])
        except Exception:
            n = 0
        done.append((row.id,res["status"],n))
    return done
