from __future__ import annotations

import contextlib
from collections import defaultdict
from statistics import correlation

from backtesting.universe.groups import GroupRegistry


class GroupGraph:
    def __init__(self, groups: GroupRegistry) -> None:
        self._groups = groups
        self._instrument_to_groups: dict[str, list[str]] = defaultdict(list)

    def add_instrument_to_group(self, instrument_id: str, group_code: str) -> None:
        self._instrument_to_groups[instrument_id].append(group_code)

    def get_instrument_groups(self, instrument_id: str) -> list[str]:
        return list(self._instrument_to_groups.get(instrument_id, []))

    def get_group_instruments(self, group_code: str) -> list[str]:
        return [
            inst_id
            for inst_id, groups in self._instrument_to_groups.items()
            if group_code in groups
        ]

    def intra_group_correlation(self, group_code: str, returns: dict[str, list[float]]) -> dict[str, float]:
        instruments = self.get_group_instruments(group_code)
        if len(instruments) < 2:
            return {}

        result: dict[str, float] = {}
        for i in range(len(instruments)):
            for j in range(i + 1, len(instruments)):
                a, b = instruments[i], instruments[j]
                ra = returns.get(a, [])
                rb = returns.get(b, [])
                if len(ra) > 1 and len(rb) > 1:
                    with contextlib.suppress(Exception):
                        result[f"{a}_{b}"] = correlation(ra, rb)
        return result

    def sector_rotation_signals(self, instrument_id: str, returns: dict[str, list[float]]) -> dict[str, float]:
        groups = self.get_instrument_groups(instrument_id)
        signals: dict[str, float] = {}
        for group_code in groups:
            peers = self.get_group_instruments(group_code)
            peer_returns: list[float] = []
            for peer_id in peers:
                if peer_id != instrument_id and peer_id in returns:
                    peer_returns.extend(returns[peer_id])
            if peer_returns:
                signals[group_code] = sum(peer_returns) / len(peer_returns)
        return signals
