from __future__ import annotations

import random
from collections.abc import Callable

from core.logging import get_logger

logger = get_logger(__name__)

FlagEvaluator = Callable[[str], bool]


def environment_evaluator(env: str) -> FlagEvaluator:
    def evaluator(_flag_name: str) -> bool:
        from core.config import settings

        return settings.environment == env

    return evaluator


def percentage_evaluator(percentage: float) -> FlagEvaluator:
    def evaluator(_flag_name: str) -> bool:
        return random.random() * 100 < percentage

    return evaluator


def user_id_evaluator(user_ids: set[str]) -> FlagEvaluator:
    def evaluator(_flag_name: str) -> bool:
        from core.context import get_user_id

        return get_user_id() in user_ids

    return evaluator


def always_enabled(_flag_name: str) -> bool:
    return True


def always_disabled(_flag_name: str) -> bool:
    return False


def composite_evaluator(operators: list[FlagEvaluator], mode: str = "all") -> FlagEvaluator:
    def evaluator(flag_name: str) -> bool:
        results = [op(flag_name) for op in operators]
        if mode == "all":
            return all(results)
        elif mode == "any":
            return any(results)
        return False

    return evaluator
