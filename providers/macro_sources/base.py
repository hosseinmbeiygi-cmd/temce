"""Macro/sentiment source providers used by the gold macro ingestion jobs.

Each provider exposes a synchronous ``fetch()`` so it can be run inside a
bounded executor, exactly like the gold-spot providers
(``providers.gold_spot.base``).  HTTP clients are injectable so tests never
touch the network.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any


class MacroSourceError(RuntimeError):
    """Raised when a macro/sentiment source cannot produce usable data."""


class MacroSourceProvider(ABC):
    """A source of macro/sentiment observations.

    ``fetch()`` returns ``list[dict]`` where each dict is a single observation
    shaped like::

        {
            "observation_date": date | str,   # the observation date
            "value": float | None,            # the observed value
            "previous_value": float | None,   # prior observation value (when computable)
            "change": float | None,           # value - previous_value
            "provenance": dict | None,        # source metadata (series id, URL, ...)
        }
    """

    name: str

    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        """Return one or more observations."""


def _env_api_key(var: str, default: str | None = None) -> str | None:
    """Return an env-provided API key, never hardcoded."""
    return os.environ.get(var, default)


def _to_float(value: Any) -> float | None:
    """Coerce a raw provider value to float, treating ``.`` / empty as missing."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value in ("", ".", "-", "N/A", "n/a"):
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
