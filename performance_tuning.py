"""Targeted runtime fixes and performance optimizations for EVOLVE.

This module is intentionally small: it patches concrete hot paths in the existing
standard-library-only engine instead of replacing the engine architecture.
"""
from __future__ import annotations

import heapq
import math
from typing import Dict, List, Optional, Tuple

from evolve_engine import (
    ACTIONS,
    Food,
    Hazard,
    Predator,
    Robot,
    Scent,
    Shelter,
    Water,
    World,
    clamp,
)

_SCENT_CELL = 100.0
_SCENT_RADIUS = 100.0
_FOUNDER_COOLDOWN = 20
_MEM_DECAY = tuple(0.9997 ** age for age in range(6))


def _scent_cell(x: float, y: float) -> Tuple[int, int]:
    return int(x // _SCENT_CELL), int(y // _SCENT_CELL)


def _rebuild_scent_grid(world: World) -> None:
    buckets: Dict[Tuple[int, int], List[Scent]] = {}
    for scent in world.scents:
        if scent.strength < 0.1 or scent.age > 800:
            continue
        buckets.setdefault(_scent_cell(scent.x, scent.y), []).append(scent)
    world._scent_grid = buckets
    world._scent_grid_tick = world.tick


def _local_scent(world: World, x: float, y: float, kind: str) -> float:
    if getattr(world, "_scent_grid_tick", None) != world.tick:
        _rebuild_scent_grid(world)
    cx, cy = _scent_cell(x, y)
    best = 0.0
    radius2 = _SCENT_RADIUS * _SCENT_RADIUS
    for ix in range(cx - 1, cx + 2):
        for iy in range(cy - 1, cy + 2):
            for scent in world._scent_grid.get((ix, iy), ()):
                if scent.kind != kind:
                    continue
                dx = x - scent.x
                dy = y - scent.y
                d2 = dx * dx + dy * dy
                if d2 < radius2:
                    value = scent.strength * (1.0 - math.sqrt(d2) / _SCENT_RADIUS)
                    if value > best:
                        best = value
    return best


def _deposit_scent(world: World, x: float, y: float, kind: str, strength: float) -> None:
    world.scents = [s for s in world.scents if s.strength >= 0.1 and s.age <= 800]
    scent = Scent(x, y, kind, clamp(strength, 0.0, 1.5))
    world.scents.append(scent)
    if len(world.scents) > 6000:
        world.scents = heapq.nlargest(6000, world.scents, key=lambda s: (s.strength, -s.age))
    # If this tick's grid has already been built, add the new marker directly to
    # its bucket. This keeps same-tick sensing correct without rebuilding the grid.
    if getattr(world, "_scent_grid_tick", None) == world.tick:
        world._scent_grid.setdefault(_scent_cell(x, y), []).append(scent)


def _ray_code(self: Robot, world: World, angle: float, length: float) -> int:
    """Object raycast with one combined scent query at the ray tip."""
    step = 7.0
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    for distance_now in range(1, max(1, int(length / step)) + 1):
        d = distance_now * step
        x = self.x + cos_a * d
        y = self.y + sin_a * d
        if x < 4 or x > world.width - 4 or y < 4 or y > world.height - 4:
            return 4
        for obj in world.nearby(x, y, 10):
            ox = getattr(obj, "x", x)
            oy = getattr(obj, "y", y)
            dx = x - ox
            dy = y - oy
            d2 = dx * dx + dy * dy
            if isinstance(obj, Predator) and obj.alive and d2 < 144:
                return 3
            if isinstance(obj, Hazard) and d2 <= obj.radius * obj.radius:
                return 2
            if isinstance(obj, Food) and obj.alive and d2 < 81:
                return 1
            if isinstance(obj, Water) and obj.alive and d2 < 81:
                return 5
            if isinstance(obj, Robot) and obj is not self and obj.alive and d2 < 100:
                return 6
            if isinstance(obj, Shelter) and d2 < obj.radius * obj.radius:
                return 7
    tx = self.x + cos_a * length
    ty = self.y + sin_a * length
    # One scent-grid traversal gives us both cues.
    cx, cy = _scent_cell(tx, ty)
    danger = 0.0
    food = 0.0
    radius2 = _SCENT_RADIUS * _SCENT_RADIUS
    if getattr(world, "_scent_grid_tick", None) != world.tick:
        _rebuild_scent_grid(world)
    for ix in range(cx - 1, cx + 2):
        for iy in range(cy - 1, cy + 2):
            for scent in world._scent_grid.get((ix, iy), ()):
                dx = tx - scent.x
                dy = ty - scent.y
                d2 = dx * dx + dy * dy
                if d2 >= radius2:
                    continue
                value = scent.strength * (1.0 - math.sqrt(d2) / _SCENT_RADIUS)
                if scent.kind == "danger" and value > danger:
                    danger = value
                elif scent.kind == "food" and value > food:
                    food = value
    if danger > 0.55:
        return 9
    if food > 0.55:
        return 8
    return 0


def _values(self, state: str) -> List[float]:
    values = self.q.get(state)
    if values is None:
        values = [0.0] * len(ACTIONS)
        self.q[state] = values
    return values


def _remember(self, state: str, tick: int, capacity: int) -> None:
    self.working.append(state)
    if len(self.working) > 10:
        del self.working[:-10]
    for memory in self.episodic:
        age = min(max(0, tick - memory.tick), 5)
        memory.strength = max(0.03, memory.strength * _MEM_DECAY[age])
    if len(self.episodic) > capacity:
        del self.episodic[:-capacity]


def _food_at(world: World, x: float, y: float, radius: float) -> Optional[Food]:
    radius2 = radius * radius
    for obj in world.nearby(x, y, radius):
        if isinstance(obj, Food) and obj.alive:
            dx = x - obj.x
            dy = y - obj.y
            if dx * dx + dy * dy <= radius2:
                return obj
    return None


def _water_at(world: World, x: float, y: float, radius: float) -> Optional[Water]:
    radius2 = radius * radius
    for obj in world.nearby(x, y, radius):
        if isinstance(obj, Water) and obj.alive:
            dx = x - obj.x
            dy = y - obj.y
            if dx * dx + dy * dy <= radius2:
                return obj
    return None


def _in_shelter(world: World, x: float, y: float) -> bool:
    for shelter in world.shelters:
        dx = x - shelter.x
        dy = y - shelter.y
        if dx * dx + dy * dy <= shelter.radius * shelter.radius:
            return True
    return False


def _founder_refs(world: World) -> Tuple[Optional[Robot], Optional[Robot]]:
    refs = getattr(world, "_founder_refs", (None, None))
    return refs[0], refs[1]


def _founders_alive(world: World) -> bool:
    if not getattr(world, "_founder_rule", True) or world.founders_established:
        return True
    male, female = _founder_refs(world)
    return bool(male and female and male.alive and female.alive)


def _founders_ready(world: World) -> bool:
    male, female = _founder_refs(world)
    return bool(
        male and female and male.alive and female.alive
        and male.sex != female.sex
        and male.age >= 50 and female.age >= 50
        and male.energy > 25 and female.energy > 25
    )


def _reproduce_founders(world: World) -> bool:
    if world.founders_established or not _founders_ready(world):
        return False
    last_tick = getattr(world, "_founder_last_reproduction_tick", -10**9)
    if world.tick - last_tick < _FOUNDER_COOLDOWN:
        return False
    male, female = _founder_refs(world)
    if male is None or female is None:
        return False
    target = world.experiment["population"]
    if len(world.population) >= target:
        world.founders_established = True
        return False
    world.population.append(world.create_child(male, female))
    male.offspring += 1
    female.offspring += 1
    world._founder_last_reproduction_tick = world.tick
    if len(world.population) >= target:
        world.founders_established = True
    return True


def _teleport_robot(world: World, robot_id: int, tx: float, ty: float) -> bool:
    robot = next((candidate for candidate in world.population if candidate.id == robot_id), None)
    if robot is None:
        return False
    robot.x = clamp(tx, 10, world.width - 10)
    robot.y = clamp(ty, 10, world.height - 10)
    world.rebuild_spatial()
    return True


def _finish_generation(world: World) -> None:
    population = world.population
    if not population:
        world.reset()
        return
    best = max(population, key=lambda r: r.fitness)
    survivors_count = sum(1 for r in population if r.alive)
    avg_fitness = sum(r.fitness for r in population) / len(population)
    parent_count = max(2, min(12, len(population)))
    parents = heapq.nlargest(parent_count, population, key=lambda r: r.fitness)
    world.history.append({
        "generation": world.generation,
        "population": len(population),
        "survivors": survivors_count,
        "avg_fitness": avg_fitness,
        "best_fitness": best.fitness,
        "best_age": best.age,
        "best_food": best.food_eaten,
        "knowledge": max((len(r.brain.q) for r in population), default=0),
        "predators": len(world.predators),
        "food": len(world.food),
    })
    world.generation += 1
    world.tick = 0
    new_population: List[Robot] = []
    target = world.experiment["population"]
    while len(new_population) < target:
        a = world.rng.choice(parents)
        b = world.rng.choice(parents)
        child = world.create_child(a, b)
        child.generation = world.generation
        new_population.append(child)
    world.population = new_population
    world.founders_established = True


def _reset(world: World) -> None:
    original = getattr(World, "_original_reset", None)
    if original is None:
        return
    original(world)
    world._founder_refs = (world.population[0], world.population[1]) if len(world.population) >= 2 else (None, None)
    world._founder_last_reproduction_tick = -10**9
    world._scent_grid = {}
    world._scent_grid_tick = None


def _step(world: World, amount: int = 1) -> None:
    for _ in range(max(1, amount)):
        world.tick += 1
        if not _founders_alive(world):
            world.reset()
            return
        world.rebuild_spatial()
        world.reproduce_founders()
        if world.predators:
            for predator in world.predators:
                if predator.alive:
                    world.predator_step(predator)
            world.rebuild_spatial()
        for robot in list(world.population):
            if robot.alive:
                robot.step(world)
        world.scents = [s for s in world.scents if s.strength >= 0.025 and s.age < 1600]
        for scent in world.scents:
            scent.step()
        world.food = [f for f in world.food if f.alive]
        world.water = [w for w in world.water if w.alive]
        while len(world.food) < world.experiment["food"]:
            world.spawn_food()
        while len(world.water) < world.experiment["water"] * 0.75:
            world.spawn_water()
        if world.tick >= world.experiment["episode"] or world.alive_count() == 0:
            _finish_generation(world)
            break


def install() -> None:
    """Install the runtime fixes exactly once."""
    if getattr(World, "_performance_patch_installed", False):
        return
    World._original_reset = World.reset
    World.local_scent = _local_scent  # type: ignore[method-assign]
    World.deposit_scent = _deposit_scent  # type: ignore[method-assign]
    World.food_at = lambda self, x, y, radius: _food_at(self, x, y, radius)  # type: ignore[method-assign]
    World.water_at = lambda self, x, y, radius: _water_at(self, x, y, radius)  # type: ignore[method-assign]
    World.in_shelter = lambda self, x, y: _in_shelter(self, x, y)  # type: ignore[method-assign]
    World.founders_alive = _founders_alive  # type: ignore[method-assign]
    World.founders_ready = _founders_ready  # type: ignore[method-assign]
    World.reproduce_founders = _reproduce_founders  # type: ignore[method-assign]
    World.teleport_robot = _teleport_robot  # type: ignore[method-assign]
    World.finish_generation = _finish_generation  # type: ignore[method-assign]
    World.reset = _reset  # type: ignore[method-assign]
    World.step = _step  # type: ignore[method-assign]
    from evolve_engine import AnimalBrain
    AnimalBrain.values = _values  # type: ignore[method-assign]
    AnimalBrain.remember = _remember  # type: ignore[method-assign]
    Robot.ray_code = _ray_code  # type: ignore[method-assign]
    World._performance_patch_installed = True
