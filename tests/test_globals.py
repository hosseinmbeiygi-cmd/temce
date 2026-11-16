"""Test to understand why init_database() doesn't set engine/async_session_factory"""
import asyncio

from core.database import async_session_factory, engine

print("Before - engine:", engine)
print("Before - af:", async_session_factory)

# Simulate what init_database does
async def test():
    global engine, async_session_factory
    print("Inside test - about to set globals")
    engine = "test_engine"
    async_session_factory = "test_factory"
    print("Inside test - engine:", engine)
    print("Inside test - af:", async_session_factory)

asyncio.run(test())

print("After test - engine:", engine)
print("After test - af:", async_session_factory)
