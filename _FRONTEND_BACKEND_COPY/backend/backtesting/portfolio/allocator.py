from __future__ import annotations


class Allocator:
    def __init__(self, method: str = "equal") -> None:
        self.method = method

    def allocate(self, capital: float, instruments: list[str], weights: list[float] | None = None) -> dict[str, float]:
        if self.method == "equal":
            w = 1.0 / len(instruments) if instruments else 0.0
            return dict.fromkeys(instruments, capital * w)
        if self.method == "weighted" and weights:
            total_w = sum(weights)
            normalized = [w / total_w for w in weights] if total_w > 0 else weights
            return {inst: capital * w for inst, w in zip(instruments, normalized, strict=False)}
        return dict.fromkeys(instruments, 0.0)

    def allocate_with_targets(self, capital: float, targets: dict[str, float]) -> dict[str, float]:
        total_w = sum(targets.values())
        if total_w <= 0:
            return dict.fromkeys(targets, 0.0)
        return {k: capital * (v / total_w) for k, v in targets.items()}
