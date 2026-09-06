"""Targeted runtime fixes and performance optimizations for EVOLVE.

This module patches concrete hot paths in the existing standard-library-only
engine instead of replacing the engine architecture.
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
_SCENT_HARD_CAP = 6000


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
    scent = Scent(x, y, kind, clamp(strength, 0.0, 1.5))
    world.scents.append(scent)
    if len(world.scents) > _SCENT_HARD_CAP:
        world.scents = heapq.nlargest(_SCENT_HARD_CAP, world.scents, key=lambda s: (s.strength, -s.age))
    if getattr(world, "_scent_grid_tick", None) == world.tick:
        world._scent_grid.setdefault(_scent_cell(x, y), []).append(scent)


def _nearby(world: World, x: float, y: float, radius: float) -> List[object]:
    """Reuse a spatial-hash result when consecutive queries hit the same cell range."""
    cell_range = int(math.ceil(radius / world._spatial.cell_size))
    key = (x, y, cell_range)
    cache = getattr(world, "_nearby_cache", None)
    if cache is not None and cache[0] == key:
        return cache[1]
    result = world._spatial.nearby(x, y, radius)
    world._nearby_cache = (key, result)
    return result


def _ray_hit_t(rx: float, ry: float, cos_a: float, sin_a: float, obj_x: float, obj_y: float, radius: float, max_t: float) -> Optional[float]:
    dx = obj_x - rx
    dy = obj_y - ry
    projection = dx * cos_a + dy * sin_a
    if projection < 0.0 or projection > max_t:
        return None
    perpendicular2 = dx * dx + dy * dy - projection * projection
    radius2 = radius * radius
    if perpendicular2 > radius2:
        return None
    return max(0.0, projection - math.sqrt(max(0.0, radius2 - perpendicular2)))


def _ray_code(self: Robot, world: World, angle: float, length: float) -> int:
    """Traverse spatial-hash cells crossed by the ray instead of sampling it."""
    spatial = world._spatial
    cell_size = float(spatial.cell_size)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    x0, y0 = self.x, self.y
    target_x = x0 + cos_a * length
    target_y = y0 + sin_a * length
    cell_x, cell_y = spatial._key(x0, y0)
    end_x, end_y = spatial._key(target_x, target_y)

    if cos_a > 1e-12:
        step_x = 1
        t_max_x = ((cell_x + 1) * cell_size - x0) / cos_a
        t_delta_x = cell_size / cos_a
    elif cos_a < -1e-12:
        step_x = -1
        t_max_x = (cell_x * cell_size - x0) / cos_a
        t_delta_x = -cell_size / cos_a
    else:
        step_x = 0
        t_max_x = math.inf
        t_delta_x = math.inf

    if sin_a > 1e-12:
        step_y = 1
        t_max_y = ((cell_y + 1) * cell_size - y0) / sin_a
        t_delta_y = cell_size / sin_a
    elif sin_a < -1e-12:
        step_y = -1
        t_max_y = (cell_y * cell_size - y0) / sin_a
        t_delta_y = -cell_size / sin_a
    else:
        step_y = 0
        t_max_y = math.inf
        t_delta_y = math.inf

    t = 0.0
    max_cells = int(math.ceil(length / cell_size)) + 6

    for _ in range(max_cells):
        cell_end = min(length, t_max_x, t_max_y)
        best_t: Optional[float] = None
        best_code = 0
        for bx in range(cell_x - 1, cell_x + 2):
            for by in range(cell_y - 1, cell_y + 2):
                for obj in spatial.cells.get((bx, by), ()):
                    if obj is self:
                        continue
                    if not getattr(obj, "alive", True) and not isinstance(obj, Shelter):
                        continue
                    if isinstance(obj, Predator):
                        radius, code = 12.0, 3
                    elif isinstance(obj, Hazard):
                        radius, code = obj.radius, 2
                    elif isinstance(obj, Food):
                        radius, code = 9.0, 1
                    elif isinstance(obj, Water):
                        radius, code = 9.0, 5
                    elif isinstance(obj, Robot):
                        radius, code = 10.0, 6
                    elif isinstance(obj, Shelter):
                        radius, code = obj.radius, 7
                    else:
                        continue
                    hit_t = _ray_hit_t(x0, y0, cos_a, sin_a, obj.x, obj.y, radius, length)
                    if hit_t is not None and hit_t <= cell_end + 1e-6 and (best_t is None or hit_t < best_t):
                        best_t = hit_t
                        best_code = code
        if best_t is not None:
            return best_code

        if t >= length - 1e-9 or (cell_x == end_x and cell_y == end_y):
            break
        if t_max_x < t_max_y:
            t = t_max_x
            cell_x += step_x
            t_max_x += t_delta_x
        else:
            t = t_max_y
            cell_y += step_y
            t_max_y += t_delta_y
        if cell_x < 0 or cell_y < 0 or cell_x * cell_size >= world.width or cell_y * cell_size >= world.height:
            return 4

    if getattr(world, "_scent_grid_tick", None) != world.tick:
        _rebuild_scent_grid(world)
    cx, cy = _scent_cell(target_x, target_y)
    danger = 0.0
    food = 0.0
    radius2 = _SCENT_RADIUS * _SCENT_RADIUS
    for ix in range(cx - 1, cx + 2):
        for iy in range(cy - 1, cy + 2):
            for scent in world._scent_grid.get((ix, iy), ()):
                dx = target_x - scent.x
                dy = target_y - scent.y
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
    for obj in _nearby(world, x, y, radius):
        if isinstance(obj, Food) and obj.alive:
            dx = x - obj.x
            dy = y - obj.y
            if dx * dx + dy * dy <= radius2:
                return obj
    return None


def _water_at(world: World, x: float, y: float, radius: float) -> Optional[Water]:
    radius2 = radius * radius
    for obj in _nearby(world, x, y, radius):
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
    world._nearby_cache = None


def _step(world: World, amount: int = 1) -> None:
    for _ in range(max(1, amount)):
        world.tick += 1
        world._nearby_cache = None
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
                world._nearby_cache = None
                robot.step(world)
        for scent in world.scents:
            scent.step()
        world.scents = [s for s in world.scents if s.strength >= 0.1 and s.age <= 800]
        world._scent_grid_tick = -1
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
    World._original_nearby = World.nearby
    World.local_scent = _local_scent  # type: ignore[method-assign]
    World.deposit_scent = _deposit_scent  # type: ignore[method-assign]
    World.nearby = _nearby  # type: ignore[method-assign]
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
