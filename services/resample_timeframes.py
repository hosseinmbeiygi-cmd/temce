"""Resample daily OHLC -> 1w/1mo/3mo/6mo/1y (1.1). Intraday (5m..4h) collected incrementally (no fake backfill)."""
from __future__ import annotations
import pandas as pd

RULES = {"1w":"W","1mo":"ME","3mo":"QE","6mo":"2QE","1y":"YE"}
INTRADAY_NOTE = ("brsapi has no intraday-history endpoint / quota insufficient: "
    "5m/15m/1h/4h collected incrementally from now; low-sample flag applies.")

def _to_gregorian(s: pd.Series) -> pd.Series:
    """Accept Jalali 'YYYY/MM/DD' or Gregorian; return Gregorian datetimes."""
    s = s.astype(str)
    if s.str.match(r"^1[3-5]\d\d/").all():
        import jdatetime
        def conv(x):
            y, m, d = map(int, x.split("/")[:3])
            return jdatetime.date(y, m, d).togregorian()
        return pd.to_datetime([conv(x) for x in s])
    return pd.to_datetime(s)

def resample_daily(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    assert timeframe in RULES, timeframe
    df=df.copy(); df["date"]=_to_gregorian(df["date"]); df=df.set_index("date").sort_index()
    return df.resample(RULES[timeframe]).agg(
        open=("open","first"),high=("high","max"),low=("low","min"),
        close=("close","last"),volume=("volume","sum")).dropna().reset_index()

def coverage_report(daily: dict[str,pd.DataFrame]) -> dict:
    rep={}
    for sym,df in daily.items():
        r={"1d":{"n":len(df),"from":str(df['date'].min()),"to":str(df['date'].max())}}
        for tf in RULES: r[tf]={"n":len(resample_daily(df,tf))}
        for tf in ["5m","15m","1h","4h"]: r[tf]={"n":0,"note":"incremental"}
        rep[sym]=r
    return rep
