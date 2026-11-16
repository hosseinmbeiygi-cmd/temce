"""Central deterministic seed (P2)."""
from __future__ import annotations

import contextlib
import os
import random


def set_global_seed(seed: int = 42) -> int:
    # BT-10: os.environ["PYTHONHASHSEED"] has no effect on the running
    # interpreter — Python reads it only at startup, before the first
    # import. Set PYTHONHASHSEED=<seed> in the process environment (e.g.
    # Dockerfile, docker-compose, or the launch wrapper) for full hash
    # determinism. We still write it here so child processes that exec
    # later will inherit the value.
    os.environ["PYTHONHASHSEED"] = str(seed)
    import logging as _logging
    _actual = os.environ.get("PYTHONHASHSEED")
    if _actual != str(seed):
        _logging.getLogger(__name__).warning(
            "BT-10: PYTHONHASHSEED set to %s but os.environ already shows %r — "
            "set it in the launch environment for full hash determinism",
            seed,
            _actual,
        )
    random.seed(seed)
    try:
        import numpy as _np

        _np.random.seed(seed)
    except Exception:
        pass
    try:
        import torch as _torch

        _torch.manual_seed(seed)
        if _torch.cuda.is_available():
            _torch.cuda.manual_seed_all(seed)
        _torch.backends.cudnn.deterministic = True
        _torch.backends.cudnn.benchmark = False
        with contextlib.suppress(Exception):
            _torch.use_deterministic_algorithms(True, warn_only=True)
    except Exception:
        pass
    return seed
