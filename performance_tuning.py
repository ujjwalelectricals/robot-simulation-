"""Small runtime performance patch for the EVOLVE simulator.

Keeps the core engine unchanged while avoiding repeated O(number_of_scents)
searches from inside every sensory-ray sample.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from evolve_engine import World

_CELL = 100.0
_RADIUS = 100.0


def _cell(x: float, y: float) -> Tuple[int, int]:
    return int(x // _CELL), int(y // _CELL)


def _rebuild_scent_cache(world: World) -> None:
    buckets: Dict[Tuple[int, int], List[object]] = {}
    for scent in world.scents:
        if scent.strength <= 0.025 or scent.age >= 1600:
            continue
        buckets.setdefault(_cell(scent.x, scent.y), []).append(scent)
    world._scent_cache = buckets
    world._scent_cache_tick = world.tick


def _local_scent(world: World, x: float, y: float, kind: str) -> float:
    # One cache rebuild per simulation tick; all ray samples in that tick are cheap.
    if getattr(world, "_scent_cache_tick", None) != world.tick:
        _rebuild_scent_cache(world)

    cx, cy = _cell(x, y)
    best = 0.0
    for ix in range(cx - 1, cx + 2):
        for iy in range(cy - 1, cy + 2):
            for scent in world._scent_cache.get((ix, iy), ()):
                if scent.kind != kind:
                    continue
                d = ((x - scent.x) ** 2 + (y - scent.y) ** 2) ** 0.5
                if d < _RADIUS:
                    best = max(best, scent.strength * (1.0 - d / _RADIUS))
    return best


def install() -> None:
    """Install the optimization once; safe to call repeatedly."""
    if getattr(World, "_performance_patch_installed", False):
        return
    World.local_scent = _local_scent  # type: ignore[method-assign]
    World._performance_patch_installed = True
