from __future__ import annotations

from enum import Enum


class LifecycleState(Enum):
    CREATED = "created"
    INITIALIZED = "initialized"
    STARTED = "started"
    STOPPED = "stopped"
    DISPOSED = "disposed"


class Lifecycle:
    def __init__(self) -> None:
        self._state = LifecycleState.CREATED

    @property
    def state(self) -> LifecycleState:
        return self._state

    async def initialize(self) -> None:
        if self._state != LifecycleState.CREATED:
            raise RuntimeError(f"Cannot initialize from state: {self._state.value}")
        self._state = LifecycleState.INITIALIZED

    async def start(self) -> None:
        if self._state != LifecycleState.INITIALIZED:
            raise RuntimeError(f"Cannot start from state: {self._state.value}")
        self._state = LifecycleState.STARTED

    async def stop(self) -> None:
        if self._state not in (LifecycleState.STARTED, LifecycleState.INITIALIZED):
            raise RuntimeError(f"Cannot stop from state: {self._state.value}")
        self._state = LifecycleState.STOPPED

    async def dispose(self) -> None:
        if self._state != LifecycleState.STOPPED:
            if self._state in (LifecycleState.STARTED, LifecycleState.INITIALIZED):
                await self.stop()
        self._state = LifecycleState.DISPOSED


class LifecycleManager:
    def __init__(self) -> None:
        self._components: list[Lifecycle] = []

    def register(self, component: Lifecycle) -> None:
        self._components.append(component)

    async def start_all(self) -> None:
        for component in self._components:
            await component.start()

    async def stop_all(self) -> None:
        for component in reversed(self._components):
            await component.stop()

    async def dispose_all(self) -> None:
        for component in reversed(self._components):
            await component.dispose()
        self._components.clear()
