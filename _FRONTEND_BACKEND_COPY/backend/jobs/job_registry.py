from __future__ import annotations

from typing import Any

from core.logging import get_logger
from jobs.base_job import BaseJob

logger = get_logger(__name__)


class JobRegistry:
    def __init__(self):
        self._jobs: dict[str, type[BaseJob]] = {}

    def register(self, job_class: type[BaseJob]) -> None:
        name = job_class.__name__
        self._jobs[name] = job_class
        logger.info("Registered job: %s", name)

    def unregister(self, name: str) -> None:
        self._jobs.pop(name, None)

    def get(self, name: str) -> type[BaseJob] | None:
        return self._jobs.get(name)

    def create(self, name: str) -> BaseJob | None:
        cls = self.get(name)
        if cls:
            return cls(name=name)
        return None

    def get_all(self) -> dict[str, type[BaseJob]]:
        return dict(self._jobs)

    def list_names(self) -> list[str]:
        return list(self._jobs.keys())

    def register_module(self, module: Any) -> None:
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, BaseJob) and attr is not BaseJob:
                self.register(attr)
