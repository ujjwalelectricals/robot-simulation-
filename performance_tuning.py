"""Small, targeted runtime fixes for the EVOLVE simulator.

This module keeps the core engine intact while:
- avoiding repeated full scent-list scans from sensory rays;
- invalidating the scent cache when new scent is created;
- making founder reproduction gradual instead of instantly filling the population.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from evolve_engine import World

_CELL = 100.0
_RADIUS = 100.0
_FOUNDER_REPRODUCTION_COOLDOWN = 30


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
    # One cache build per simulation tick; each ray then checks only nearby cells.
    if getattr(world, "_scent_cache_tick", None) != world.tick:
        _rebuild_scent_cache(world)

    cx, cy = _cell(x, y)
    best = 0.0
    for ix in range(cx - 1, cx + 2):
        for iy in range(cy - 1, cy + 2):
            for scent in world._scent_cache.get((ix, iy), ()):
                if scent.kind != kind:
                    continue
                dx = x - scent.x
                dy = y - scent.y
                distance = math.hypot(dx, dy)
                if distance < _RADIUS:
                    best = max(best, scent.strength * (1.0 - distance / _RADIUS))
    return best


def _reproduce_founders(world: World) -> bool:
    if world.founders_established or not world.founders_ready():
        return False

    last_tick = getattr(world, "_founder_last_reproduction_tick", -10**9)
    if world.tick - last_tick < _FOUNDER_REPRODUCTION_COOLDOWN:
        return False

    lookup = {robot.id: robot for robot in world.population}
    male = lookup.get(world.founder_ids[0])
    female = lookup.get(world.founder_ids[1])
    if male is None or female is None or not male.alive or not female.alive:
        return False

    target = world.experiment["population"]
    if len(world.population) >= target:
        world.founders_established = True
        return False

    child = world.create_child(male, female)
    world.population.append(child)
    male.offspring += 1
    female.offspring += 1
    world._founder_last_reproduction_tick = world.tick

    if len(world.population) >= target:
        world.founders_established = True
    return True


def _invalidate_on_deposit(world: World, x: float, y: float, kind: str, strength: float) -> None:
    original = getattr(World, "_original_deposit_scent", None)
    if original is not None:
        original(world, x, y, kind, strength)
    world._scent_cache_tick = -1


def install() -> None:
    """Install the targeted fixes once; safe to call repeatedly."""
    if getattr(World, "_performance_patch_installed", False):
        return

    World._original_deposit_scent = World.deposit_scent
    World.local_scent = _local_scent  # type: ignore[method-assign]
    World.deposit_scent = _invalidate_on_deposit  # type: ignore[method-assign]
    World.reproduce_founders = _reproduce_founders  # type: ignore[method-assign]
    World._performance_patch_installed = True
