"""Standalone Celery worker entrypoint for the broker integration tests.

Spawns a REAL Celery worker (solo pool — Windows-safe) consuming the three
precompute priority queues, using exactly the app that
``precompute.workers.celery_tasks`` builds. No pytest imports here: the
worker process must look like production.

Usage (spawned by tests/integration/test_celery_chain_broker.py):
    python tests/integration/_celery_worker_entry.py
"""

from __future__ import annotations

import os
import sys

# Make repo-root imports work regardless of cwd (same as production PYTHONPATH=.)
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from precompute.workers import celery_tasks as ct  # noqa: E402

app = ct._get_celery_app()
assert app is not None, "celery must be installed for the broker integration worker"


def main() -> None:
    queues = ",".join([ct.QUEUE_A, ct.QUEUE_B, ct.QUEUE_C])
    # solo pool: single-threaded, no process forking (Windows-safe), enough
    # for integration throughput. --purge clears leftovers from crashed runs.
    app.worker_main(
        [
            "worker",
            "--loglevel=INFO",
            f"--queues={queues}",
            "--pool=solo",
            "--concurrency=1",
            "--purge",
            "--without-gossip",
            "--without-mingle",
            "--without-heartbeat",
        ]
    )


if __name__ == "__main__":
    main()
