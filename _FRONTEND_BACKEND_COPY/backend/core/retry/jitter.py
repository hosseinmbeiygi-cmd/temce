from __future__ import annotations

import random
from collections.abc import Callable

JitterFn = Callable[[float], float]


def no_jitter(delay: float) -> float:
    return delay


def full_jitter(delay: float) -> float:
    return random.uniform(0, delay)


def equal_jitter(delay: float) -> float:
    half = delay / 2
    return half + random.uniform(0, half)


def decorrelated_jitter(base_delay: float, max_delay: float) -> JitterFn:
    prev = base_delay

    def jitter_fn(_delay: float) -> float:
        nonlocal prev
        prev = min(max_delay, random.uniform(base_delay, prev * 3))
        return prev

    return jitter_fn


def proportional_jitter(delay: float, proportion: float = 0.1) -> float:
    jitter = delay * proportion
    return delay + random.uniform(-jitter, jitter)
