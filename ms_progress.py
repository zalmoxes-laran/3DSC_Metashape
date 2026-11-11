"""Where a long batch stands: item N of M, time spent, time left. Pure Python.

The weight of an item is what its time depends on (for texturing: the texture
pages of the block), so the estimate of the time left follows the real work,
not the count of items. Used by the batch commands of 3DSC for Metashape.
"""

from __future__ import annotations

import time
from typing import Callable, Dict, List, Optional, Sequence


def fmt_duration(seconds: Optional[float]) -> str:
    """«45 s», «1 min 20 s», «12 min», «1 h 20 min»; «—» when unknown."""
    if seconds is None:
        return "—"
    s = int(round(max(0.0, seconds)))
    if s < 60:
        return "%d s" % s
    m = s // 60
    if m < 10:
        return "%d min %02d s" % (m, s % 60) if s % 60 else "%d min" % m
    if m < 60:
        return "%d min" % m
    return "%d h %02d min" % (m // 60, m % 60)


class Tracker:
    """Progress of a batch of weighted items.

    ``begin(i)`` when item i starts, ``part(f)`` for its own progress (0..1),
    ``end()`` when it is done; ``state()`` says where the batch stands.
    """

    def __init__(self, weights: Sequence[float], clock: Callable[[], float] = time.time):
        self.weights: List[float] = [max(1e-9, float(w)) for w in weights] or [1.0]
        self.total = sum(self.weights)
        self.clock = clock
        self.t0 = clock()
        self.index = 0
        self.fraction = 0.0
        self.done_weight = 0.0
        self.done_items = 0

    def begin(self, index: int) -> None:
        self.index = index
        self.fraction = 0.0

    def part(self, fraction: float) -> None:
        self.fraction = min(1.0, max(0.0, float(fraction)))

    def end(self) -> None:
        self.done_weight += self.weights[self.index]
        self.done_items += 1
        self.fraction = 0.0

    def state(self) -> Dict[str, object]:
        elapsed = self.clock() - self.t0
        current = self.weights[self.index] * self.fraction if self.index < len(self.weights) else 0.0
        worked = self.done_weight + current
        overall = worked / self.total if self.total else 0.0
        left = None
        if worked > 0 and (self.done_items > 0 or self.fraction >= 0.05) and elapsed > 0:
            left = elapsed * (self.total - worked) / worked
        return {"index": self.index, "items": len(self.weights), "done": self.done_items,
                "remaining": len(self.weights) - self.done_items, "overall": overall,
                "elapsed": elapsed, "left": left,
                "finish": (self.clock() + left) if left is not None else None}


class Split:
    """How the time of one item divides between its stages, learnt from the
    items already done (texturing: UV mapping, then the texture). Until the
    first item ends, ``first_guess`` is used."""

    def __init__(self, stages, first_guess):
        self.stages = list(stages)
        self.share = list(first_guess)
        self.spent = [0.0] * len(self.stages)

    def overall(self, stage: str, fraction: float) -> float:
        k = self.stages.index(stage)
        return sum(self.share[:k]) + self.share[k] * min(1.0, max(0.0, fraction))

    def learn(self, seconds_per_stage) -> None:
        for k, t in enumerate(seconds_per_stage):
            self.spent[k] += max(0.0, t)
        total = sum(self.spent)
        if total > 0:
            self.share = [t / total for t in self.spent]


class Throttle:
    """True at most ``per_second`` times a second (and always at the ends)."""

    def __init__(self, per_second: float = 5.0, clock: Callable[[], float] = time.time):
        self.gap = 1.0 / per_second
        self.clock = clock
        self.last = -1e18

    def ready(self, fraction: float = 0.5) -> bool:
        now = self.clock()
        if fraction <= 0.0 or fraction >= 1.0 or now - self.last >= self.gap:
            self.last = now
            return True
        return False
