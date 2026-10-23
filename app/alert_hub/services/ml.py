from __future__ import annotations

from typing import Any

async def get_ml_prediction(symbol: str) -> dict[str, Any]:
    """Return an ML-based prediction + confidence for the symbol.

    Placeholder until the inference service is integrated.
    """
    return {
        "symbol": symbol,
        "direction": "sideways",
        "horizon": "short",
        "confidence": 0.5,
        "technicalHealthScore": 75,
        "notes": "placeholder",
    }
