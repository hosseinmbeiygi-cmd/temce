"""Evidence: API-03 invalidation across two REAL OS processes sharing Redis.

Usage (parent):
    REDIS_URL=... python AUDIT_REPORTS/.../two_process_cache_proof.py

The parent spawns two independent Python processes:

* ``b`` — imports the API module, warms its local aggregate cache, records the
  generation token, then waits for A's signal and re-reads the cache.
* ``a`` — imports the same module in its own process, runs
  ``invalidate_agg_cache()`` (publishes the new generation to Redis) and signals.

B must observe a miss after A's invalidation. Exit 0 = proof holds.
No secrets are printed: the namespace is derived per run and the Redis URL is
only read from the environment (never echoed).
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


async def _manager():
    from core.cache_manager import CacheManager

    return CacheManager(
        redis_url=os.environ["REDIS_URL"],
        namespace=os.environ["CACHE_NS"],
        default_ttl=60,
    )


async def _child_b(ready: Path, done: Path) -> int:
    from apps.api.endpoints import market
    from core.cache_manager import set_cache_manager

    cm = await _manager()
    if not await cm._ensure_redis():
        print("B_REDIS_UNAVAILABLE")
        await cm.close()
        return 2
    set_cache_manager(cm)

    market._agg_cache_set("proof-key", ["stale"], as_of="t0")
    warm, _ = await market._agg_cache_get("proof-key")
    print("B_WARM:", warm)
    ready.write_text("1", encoding="utf-8")

    for _ in range(200):  # up to ~20s
        if done.exists():
            break
        await asyncio.sleep(0.1)
    else:
        print("B_TIMEOUT")
        await cm.close()
        return 3

    market._agg_token_checked_at = 0.0  # force the next read to consult Redis
    after, _ = await market._agg_cache_get("proof-key")
    print("B_AFTER:", after)
    await cm.close()
    return 0 if after is None else 1


async def _child_a(ready: Path, done: Path) -> int:
    from apps.api.endpoints import market
    from core.cache_manager import set_cache_manager

    for _ in range(200):
        if ready.exists():
            break
        await asyncio.sleep(0.1)
    else:
        print("A_TIMEOUT")
        return 3

    cm = await _manager()
    if not await cm._ensure_redis():
        print("A_REDIS_UNAVAILABLE")
        await cm.close()
        return 2
    set_cache_manager(cm)

    market.invalidate_agg_cache()
    if market._agg_publish_tasks:
        await asyncio.gather(*market._agg_publish_tasks)
    print("A_INVALIDATED: True")
    done.write_text("1", encoding="utf-8")
    await cm.close()
    return 0


async def _parent() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="api03-proof-"))
    ready, done = tmp / "b_ready", tmp / "a_done"
    env = dict(os.environ)
    env["CACHE_NS"] = f"audit_api03_{uuid.uuid4().hex[:8]}"

    b = await asyncio.create_subprocess_exec(
        sys.executable, str(Path(__file__).resolve()), "b", str(ready), str(done),
        env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    a = await asyncio.create_subprocess_exec(
        sys.executable, str(Path(__file__).resolve()), "a", str(ready), str(done),
        env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    out_b, _ = await b.communicate()
    out_a, _ = await a.communicate()
    print(out_a.decode("utf-8", "replace").strip())
    print(out_b.decode("utf-8", "replace").strip())
    print("pids:", a.pid, b.pid, "exit_a:", a.returncode, "exit_b:", b.returncode)
    return 0 if (a.returncode == 0 and b.returncode == 0) else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in {"a", "b"}:
        ready_p, done_p = Path(sys.argv[2]), Path(sys.argv[3])
        fn = _child_a if sys.argv[1] == "a" else _child_b
        sys.exit(asyncio.run(fn(ready_p, done_p)))
    sys.exit(asyncio.run(_parent()))
