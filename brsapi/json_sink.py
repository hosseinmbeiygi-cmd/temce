from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.logging import get_logger
from core.time import now_utc

logger = get_logger(__name__)

# پوشه پایه برای آرشیو JSON دسته‌بندی‌شده
BASE_DIR = Path("data/brsapi")
JSON_DIR = Path("json/brsapi")

# نگاشت section_id -> پوشه
CATEGORY_MAP = {
    "gold-coin": "gold",
    "gold-coin-history": "gold",
    "currency": "currency",
    "currency-history": "currency",
    "commodity": "commodity",
    "crypto": "crypto",
    "codal": "codal",
}


def save_json(section_id: str, data: Any, extra: str = "") -> Path | None:
    """ذخیره خودکار JSON با دسته‌بندی درست + هم‌زمان DB قبلا ذخیره شده."""
    try:
        cat = CATEGORY_MAP.get(section_id, section_id)
        folder = BASE_DIR / cat
        folder.mkdir(parents=True, exist_ok=True)
        JSON_DIR.mkdir(parents=True, exist_ok=True)

        ts = now_utc().strftime("%Y-%m-%d_%H-%M-%S")
        fname = f"{section_id}{('_' + extra) if extra else ''}_{ts}.json"
        fpath = folder / fname
        # ذخیره دسته‌بندی‌شده
        fpath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        # کپی هم در json/brsapi برای دسترسی سریع
        (JSON_DIR / fname).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("JSON archived: %s (%d items)", fpath, len(data) if isinstance(data, list) else 1)
        return fpath
    except Exception as exc:
        logger.warning("JSON sink failed for %s: %s", section_id, exc)
        return None
