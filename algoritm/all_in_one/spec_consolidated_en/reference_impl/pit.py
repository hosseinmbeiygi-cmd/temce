"""Point-in-time (bitemporal) read helpers. No database; pandas only.

Rule: a decision at `asof` may only see rows with knowledge_time <= asof.
For each business key the latest *known* version wins (corrections append, never overwrite).
"""
from __future__ import annotations

import pandas as pd


class LookAheadError(RuntimeError):
    pass


def visible_asof(df: pd.DataFrame, asof, key_cols=("instrument_id", "event_time"),
                 knowledge_col: str = "knowledge_time") -> pd.DataFrame:
    d = df[df[knowledge_col] <= asof]
    d = d.sort_values(list(key_cols) + [knowledge_col])
    return d.drop_duplicates(subset=list(key_cols), keep="last").reset_index(drop=True)


def assert_no_lookahead(df: pd.DataFrame, asof, knowledge_col: str = "knowledge_time") -> None:
    bad = df[df[knowledge_col] > asof]
    if len(bad):
        raise LookAheadError(f"{len(bad)} rows have {knowledge_col} > {asof}")
