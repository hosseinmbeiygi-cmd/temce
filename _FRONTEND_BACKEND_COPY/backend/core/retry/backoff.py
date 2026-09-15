from __future__ import annotations


class BackoffStrategy:
    def get_delay(self, attempt: int) -> float:
        raise NotImplementedError


class FixedBackoff(BackoffStrategy):
    def __init__(self, delay: float = 1.0) -> None:
        self.delay = delay

    def get_delay(self, attempt: int) -> float:
        return self.delay


class LinearBackoff(BackoffStrategy):
    def __init__(self, initial_delay: float = 1.0, increment: float = 1.0) -> None:
        self.initial_delay = initial_delay
        self.increment = increment

    def get_delay(self, attempt: int) -> float:
        return self.initial_delay + self.increment * (attempt - 1)


class ExponentialBackoff(BackoffStrategy):
    def __init__(self, base_delay: float = 1.0, max_delay: float = 60.0, factor: float = 2.0) -> None:
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.factor = factor

    def get_delay(self, attempt: int) -> float:
        delay = self.base_delay * (self.factor ** (attempt - 1))
        return min(delay, self.max_delay)


class FibonacciBackoff(BackoffStrategy):
    def __init__(self, base_delay: float = 1.0, max_delay: float = 60.0) -> None:
        self.base_delay = base_delay
        self.max_delay = max_delay

    def get_delay(self, attempt: int) -> float:
        a, b = 0, 1
        for _ in range(attempt):
            a, b = b, a + b
        return min(a * self.base_delay, self.max_delay)
