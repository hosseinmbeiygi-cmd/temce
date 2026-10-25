import asyncio
from core.database import engine, async_session_factory, init_database

print('Before first call - engine:', engine, 'af:', async_session_factory)
asyncio.run(init_database())
print('After first call - engine:', engine, 'af:', async_session_factory)
asyncio.run(init_database())
print('After second call - engine:', engine, 'af:', async_session_factory)