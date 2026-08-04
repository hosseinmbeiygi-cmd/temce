"""Unit tests for ``core/event_bus.EventBus``.

Focus: handler **isolation** — a failing handler must not prevent the
remaining handlers from running — plus subscribe/unsubscribe/clear and
support for both sync and async handlers.
"""

from __future__ import annotations

import pytest

from core.event_bus import EventBus
from core.events import DomainEvent, MarketEvents


def _make_event() -> DomainEvent:
    return DomainEvent(event_type=MarketEvents.SIGNAL_GENERATED, data={"symbol": "فملی"})


# ── Basic publish ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_calls_subscribed_handler():
    bus = EventBus()
    calls: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        calls.append(event)

    bus.subscribe(MarketEvents.SIGNAL_GENERATED, handler)
    event = _make_event()
    await bus.publish(event)
    assert calls == [event]


@pytest.mark.asyncio
async def test_publish_no_handlers_is_noop():
    bus = EventBus()
    # Should not raise even though nothing is subscribed.
    await bus.publish(_make_event())


@pytest.mark.asyncio
async def test_publish_only_matching_event_type():
    bus = EventBus()
    calls: list[str] = []

    async def handler(event: DomainEvent) -> None:
        calls.append(event.event_type)

    bus.subscribe("quote.updated", handler)
    await bus.publish(DomainEvent(event_type="trade.executed"))
    assert calls == []


# ── Sync + async handlers ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_handler_is_supported():
    bus = EventBus()
    calls: list[str] = []

    def handler(event: DomainEvent) -> None:
        calls.append(event.data["symbol"])

    bus.subscribe(MarketEvents.SIGNAL_GENERATED, handler)
    await bus.publish(_make_event())
    assert calls == ["فملی"]


@pytest.mark.asyncio
async def test_mixed_sync_and_async_handlers():
    bus = EventBus()
    order: list[str] = []

    def sync_handler(event: DomainEvent) -> None:
        order.append("sync")

    async def async_handler(event: DomainEvent) -> None:
        order.append("async")

    bus.subscribe(MarketEvents.SIGNAL_GENERATED, sync_handler)
    bus.subscribe(MarketEvents.SIGNAL_GENERATED, async_handler)
    await bus.publish(_make_event())
    assert order == ["sync", "async"]


# ── Handler isolation (the core guarantee) ─────────────────────────


@pytest.mark.asyncio
async def test_failing_handler_does_not_block_others():
    bus = EventBus()
    ran: list[str] = []

    def boom(event: DomainEvent) -> None:
        raise RuntimeError("handler exploded")

    def after(event: DomainEvent) -> None:
        ran.append("after")

    bus.subscribe(MarketEvents.SIGNAL_GENERATED, boom)
    bus.subscribe(MarketEvents.SIGNAL_GENERATED, after)

    # The exception is swallowed per-handler; the later handler still runs.
    await bus.publish(_make_event())
    assert ran == ["after"]


@pytest.mark.asyncio
async def test_multiple_failing_handlers_all_isolated():
    bus = EventBus()
    ran: list[str] = []

    def boom1(event: DomainEvent) -> None:
        raise ValueError("one")

    def boom2(event: DomainEvent) -> None:
        raise KeyError("two")

    def survivor(event: DomainEvent) -> None:
        ran.append("survivor")

    for h in (boom1, boom2, survivor):
        bus.subscribe(MarketEvents.SIGNAL_GENERATED, h)

    await bus.publish(_make_event())
    assert ran == ["survivor"]


@pytest.mark.asyncio
async def test_async_failing_handler_isolated():
    bus = EventBus()
    ran: list[str] = []

    async def boom(event: DomainEvent) -> None:
        raise RuntimeError("async boom")

    def after(event: DomainEvent) -> None:
        ran.append("after")

    bus.subscribe(MarketEvents.SIGNAL_GENERATED, boom)
    bus.subscribe(MarketEvents.SIGNAL_GENERATED, after)
    await bus.publish(_make_event())
    assert ran == ["after"]


# ── subscribe / unsubscribe / clear ────────────────────────────────


@pytest.mark.asyncio
async def test_unsubscribe_removes_handler():
    bus = EventBus()
    calls: list[str] = []

    async def handler(event: DomainEvent) -> None:
        calls.append("x")

    bus.subscribe(MarketEvents.SIGNAL_GENERATED, handler)
    bus.unsubscribe(MarketEvents.SIGNAL_GENERATED, handler)
    await bus.publish(_make_event())
    assert calls == []


@pytest.mark.asyncio
async def test_unsubscribe_unknown_handler_is_noop():
    bus = EventBus()

    def handler(event: DomainEvent) -> None:
        pass

    # Removing a handler that was never registered must not raise.
    bus.unsubscribe(MarketEvents.SIGNAL_GENERATED, handler)


@pytest.mark.asyncio
async def test_clear_removes_all_handlers():
    bus = EventBus()
    calls: list[str] = []

    async def handler(event: DomainEvent) -> None:
        calls.append("x")

    bus.subscribe("a.type", handler)
    bus.subscribe("b.type", handler)
    bus.clear()
    await bus.publish(DomainEvent(event_type="a.type"))
    await bus.publish(DomainEvent(event_type="b.type"))
    assert calls == []


# ── Subscription order ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handlers_run_in_subscription_order():
    bus = EventBus()
    order: list[int] = []

    def make(i: int):
        def handler(event: DomainEvent) -> None:
            order.append(i)

        return handler

    for i in (1, 2, 3):
        bus.subscribe(MarketEvents.SIGNAL_GENERATED, make(i))
    await bus.publish(_make_event())
    assert order == [1, 2, 3]
