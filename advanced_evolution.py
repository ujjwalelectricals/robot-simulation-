"""Advanced artificial-life layer for EVOLVE.

Adds emergent, local-only cognition/ecology without giving robots privileged
simulation knowledge.  Standard library only.  The layer is intentionally
implemented as small runtime extensions so the canonical engine remains easy
to inspect and benchmark.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from evolve_engine import Robot, World, Predator, clamp, distance, wrap_angle

_INSTALLED = False
_ORIGINALS: dict[str, object] = {}


@dataclass
class PlaceMemory:
    value: float = 0.0
    danger: float = 0.0
    visits: int = 0
    uncertainty: float = 1.0
    last_tick: int = 0


@dataclass
class Habit:
    name: str
    success: float = 0.0
    uses: int = 0


def _cell(world: World, x: float, y: float, size: int = 45) -> Tuple[int, int]:
    return int(x // size), int(y // size)


def _ensure_robot(robot: Robot) -> None:
    if not hasattr(robot, "cognitive_map"):
        robot.cognitive_map: Dict[Tuple[int, int], PlaceMemory] = {}
        robot.habits: Dict[str, Habit] = {}
        robot.relationships: Dict[int, float] = {}
        robot.family_ids: set[int] = set()
        robot.home_cell: Optional[Tuple[int, int]] = None
        robot.territory_strength = 0.0
        robot.personality_mood = 0.0
        robot.weather_memory: Dict[str, float] = {}
        robot.life_events: list[dict] = []
        robot.replay: list[dict] = []
        robot.last_goal: str = "explore"
        robot.social_learning_ticks = 0
        robot.reflex_count = 0
        robot.territory_visits = 0


def _ensure_world(world: World) -> None:
    if not hasattr(world, "weather"):
        world.weather = {"kind": "clear", "intensity": 0.0}
        world.season = "spring"
        world.season_index = 0
        world.season_ticks = 0
        world.ecology_seed = world.rng.random()
        world.territories: Dict[Tuple[int, int], int] = {}
        world.genealogy: Dict[int, dict] = {}
        world.life_events: list[dict] = []
        world.experiment_log: list[dict] = []
        world.replay_archive: Dict[int, list[dict]] = {}
        world.cognitive_tick = -1


def _season(world: World) -> str:
    return ("spring", "summer", "autumn", "winter")[world.season_index]


def _update_weather(world: World) -> None:
    _ensure_world(world)
    if world.tick % 180 != 0:
        return
    world.season_ticks += 180
    if world.season_ticks >= 720:
        world.season_ticks = 0
        world.season_index = (world.season_index + 1) % 4
        world.season = _season(world)
        world.life_events.append({"tick": world.tick, "type": "season", "season": world.season})
    roll = world.rng.random()
    if roll < 0.08:
        world.weather = {"kind": "storm", "intensity": world.rng.uniform(0.55, 1.0)}
    elif roll < 0.20:
        world.weather = {"kind": "rain", "intensity": world.rng.uniform(0.25, 0.75)}
    elif roll < 0.28:
        world.weather = {"kind": "heat", "intensity": world.rng.uniform(0.35, 0.8)}
    else:
        world.weather = {"kind": "clear", "intensity": 0.0}


def _ecology(world: World) -> None:
    _update_weather(world)
    if world.tick % 25:
        return
    season = getattr(world, "season", "spring")
    food_factor = {"spring": 1.35, "summer": 1.15, "autumn": 0.9, "winter": 0.6}[season]
    water_factor = {"spring": 1.15, "summer": 0.85, "autumn": 0.95, "winter": 0.75}[season]
    target_food = max(1, int(world.experiment["food"] * food_factor))
    target_water = max(1, int(world.experiment["water"] * water_factor))
    while len(world.food) < target_food and len(world.food) < world.experiment["food"] * 2:
        world.spawn_food()
    while len(world.water) < int(target_water * 0.75) and len(world.water) < world.experiment["water"] * 1.5:
        world.spawn_water()


def _relationship(robot: Robot, other: Robot, amount: float) -> None:
    _ensure_robot(robot)
    current = robot.relationships.get(other.id, 0.0)
    robot.relationships[other.id] = clamp(current * 0.96 + amount * 0.04, -1.0, 1.0)
    if other.parent_ids[0] in robot.family_ids or other.parent_ids[1] in robot.family_ids:
        robot.family_ids.add(other.id)


def _social_learning(robot: Robot, world: World) -> None:
    _ensure_robot(robot)
    if world.tick % 7:
        return
    peers = [o for o in world.nearby(robot.x, robot.y, 75) if isinstance(o, Robot) and o is not robot and o.alive]
    if not peers:
        return
    peer = min(peers, key=lambda r: distance(robot.x, robot.y, r.x, r.y))
    _relationship(robot, peer, 0.8 if peer.fitness >= robot.fitness else 0.15)
    behavior = getattr(peer, "behavior", None)
    if behavior and behavior.name and peer.fitness > robot.fitness - 5 and robot.genome.sociability > 0.25:
        habit = robot.habits.setdefault(behavior.name, Habit(behavior.name))
        habit.success = clamp(habit.success * 0.85 + max(0.0, peer.recent_reward) * 0.15, 0, 20)
        habit.uses += 1
        robot.social_learning_ticks += 1


def _map_and_territory(robot: Robot, world: World, reward: float, danger: float) -> None:
    _ensure_robot(robot)
    _ensure_world(world)
    cell = _cell(world, robot.x, robot.y)
    memory = robot.cognitive_map.setdefault(cell, PlaceMemory())
    memory.visits += 1
    memory.value = clamp(memory.value * 0.97 + reward * 0.03, -20, 20)
    memory.danger = clamp(memory.danger * 0.96 + danger * 0.04, 0, 20)
    memory.uncertainty = max(0.03, memory.uncertainty * 0.94)
    memory.last_tick = world.tick
    if robot.home_cell is None and robot.age > 35:
        robot.home_cell = cell
    if robot.home_cell == cell:
        robot.territory_strength = clamp(robot.territory_strength + 0.002, 0, 1)
        robot.territory_visits += 1
        world.territories[cell] = robot.id
    elif robot.genome.sociability < 0.35:
        robot.territory_strength = max(0.0, robot.territory_strength - 0.0008)


def _remember_event(robot: Robot, world: World, kind: str, detail: str = "") -> None:
    _ensure_robot(robot)
    event = {"tick": world.tick, "type": kind, "detail": detail, "x": round(robot.x, 2), "y": round(robot.y, 2)}
    robot.life_events.append(event)
    robot.life_events = robot.life_events[-80:]
    robot.replay.append(event)
    robot.replay = robot.replay[-120:]


def _reflex_bias(self: Robot, world: World, codes, internal):
    bias = _ORIGINALS["drive_bias"](self, world, codes, internal)  # type: ignore[misc]
    _ensure_robot(self)
    danger_seen = 3 in codes or 2 in codes or 9 in codes
    if danger_seen:
        self.reflex_count += 1
        fear = internal[3]
        bold = self.genome.boldness
        if 3 in codes and bold > 0.72 and fear < 0.72:
            bias[8] += 1.5 * bold
            bias[0] += 0.35 * bold
        else:
            bias[8] += 1.8 + fear * 1.2
            bias[1] += 0.45 if codes[len(codes)//2 - 1] in (2, 3, 9) else 0
            bias[2] += 0.45 if codes[len(codes)//2 + 1] in (2, 3, 9) else 0
    if self.cognitive_map and self.genome.curiosity > 0.25 and not danger_seen:
        best = max(self.cognitive_map.values(), key=lambda m: m.value - m.danger - m.uncertainty * 0.5)
        if best.value > 1.0:
            bias[0] += 0.08 * self.genome.curiosity
    return bias


def _robot_step(self: Robot, world: World):
    _ensure_robot(self)
    _ensure_world(world)
    before_energy, before_hydration, before_food, before_water = self.energy, self.hydration, self.food_eaten, self.water_found
    result = _ORIGINALS["robot_step"](self, world)  # type: ignore[misc]
    reward = self.recent_reward
    danger = max(0.0, -reward)
    behavior = getattr(self, "behavior", None)
    if behavior and behavior.name:
        habit = self.habits.setdefault(behavior.name, Habit(behavior.name))
        habit.uses += 1
        habit.success = clamp(habit.success * 0.985 + max(-2.0, min(2.0, reward)) * 0.015, -5, 20)
    _map_and_territory(self, world, reward, danger)
    weather = getattr(world, "weather", {"kind": "clear", "intensity": 0.0})
    if weather.get("kind") == "heat":
        self.hydration = max(0.0, self.hydration - 0.008 * weather.get("intensity", 0.0))
    elif weather.get("kind") == "storm":
        self.energy = max(0.0, self.energy - 0.006 * weather.get("intensity", 0.0))
    _social_learning(self, world)
    if self.food_eaten > before_food:
        _remember_event(self, world, "food_success")
    if self.water_found > before_water:
        _remember_event(self, world, "water_success")
    if self.energy < before_energy - 0.5 and self.hydration < before_hydration - 0.2:
        self.personality_mood = clamp(self.personality_mood - 0.002, -1, 1)
    else:
        self.personality_mood = clamp(self.personality_mood + 0.001, -1, 1)
    kind = getattr(world, "weather", {}).get("kind", "clear")
    self.weather_memory[kind] = self.weather_memory.get(kind, 0.0) * 0.995 + reward * 0.005
    return result


def _predator_step(self: World, predator: Predator) -> None:
    _ensure_world(self)
    if not hasattr(predator, "personality"):
        predator.personality = self.rng.choice(("stalker", "sprinter", "scout"))
        predator.learning = self.rng.uniform(0.05, 0.16)
        predator.memory: Dict[int, float] = {}
        predator.successes = 0
    target = self.nearest_robot(predator.x, predator.y, radius=260 if predator.personality == "scout" else 220)
    if target:
        d = distance(predator.x, predator.y, target.x, target.y)
        desired = math.atan2(target.y - predator.y, target.x - predator.x)
        delta = wrap_angle(desired - predator.angle)
        turn = 0.16 if predator.personality == "sprinter" else 0.10
        predator.angle = wrap_angle(predator.angle + clamp(delta, -turn, turn))
        predator.memory[target.id] = predator.memory.get(target.id, 0.0) * 0.98 + (1.0 / max(20, d)) * 0.02
        if d < 18:
            bold = target.genome.boldness
            if bold > 0.82 and self.rng.random() < 0.18 * bold:
                predator.angle = wrap_angle(predator.angle + math.pi * 0.75)
                predator.memory[target.id] = max(0.0, predator.memory.get(target.id, 0.0) - predator.learning)
            else:
                predator.successes += 1
    speed = predator.speed * (1.08 if predator.personality == "sprinter" else 1.0)
    nx = predator.x + math.cos(predator.angle) * speed
    ny = predator.y + math.sin(predator.angle) * speed
    if nx < 12 or nx > self.width - 12:
        predator.angle = wrap_angle(math.pi - predator.angle)
    if ny < 12 or ny > self.height - 12:
        predator.angle = wrap_angle(-predator.angle)
    predator.x = clamp(nx, 12, self.width - 12)
    predator.y = clamp(ny, 12, self.height - 12)


def _create_child(self: World, a: Robot, b: Robot) -> Robot:
    child = _ORIGINALS["create_child"](self, a, b)  # type: ignore[misc]
    _ensure_robot(a)
    _ensure_robot(b)
    _ensure_robot(child)
    child.family_ids.update((a.id, b.id))
    child.relationships[a.id] = 0.5
    child.relationships[b.id] = 0.5
    for parent in (a, b):
        for cell, memory in sorted(parent.cognitive_map.items(), key=lambda item: item[1].value - item[1].danger, reverse=True)[:8]:
            if self.rng.random() < 0.35:
                child.cognitive_map[cell] = PlaceMemory(memory.value * 0.35, memory.danger * 0.45, 1, 0.85, 0)
        for name, habit in list(parent.habits.items())[:6]:
            if self.rng.random() < 0.30:
                child.habits[name] = Habit(name, habit.success * 0.25, 0)
    return child


def _finish_generation(self: World) -> None:
    _ORIGINALS["finish_generation"](self)  # type: ignore[misc]
    _ensure_world(self)
    self.genealogy = getattr(self, "genealogy", {})
    for robot in self.population:
        _ensure_robot(robot)
        self.genealogy[robot.id] = {
            "id": robot.id, "generation": robot.generation, "sex": robot.sex,
            "parents": robot.parent_ids, "fitness": robot.fitness,
            "food": robot.food_eaten, "water": robot.water_found,
            "reflexes": robot.reflex_count, "map_size": len(robot.cognitive_map),
        }
    self.experiment_log.append({"generation": self.generation, "season": self.season, "weather": self.weather.copy()})
    self.experiment_log = self.experiment_log[-200:]


def _world_step(self: World, amount: int = 1):
    _ensure_world(self)
    _ecology(self)
    return _ORIGINALS["world_step"](self, amount)  # type: ignore[misc]


def run_trials(config: dict, trials: int = 4) -> list[dict]:
    """Run repeatable headless trials and return comparable results."""
    results = []
    base_seed = int(config.get("seed", 1))
    generations = max(1, int(config.get("generations", 5)))
    population = max(2, int(config.get("population", 50)))
    for index in range(max(1, trials)):
        world = World(seed=base_seed + index)
        world.configure(population=population)
        world.reset()
        world.run_generations(generations)
        rows = world.history[-generations:]
        results.append({
            "trial": index + 1, "seed": base_seed + index,
            "final_generation": world.generation,
            "best_fitness": rows[-1].get("best_fitness", 0.0) if rows else 0.0,
            "avg_fitness": rows[-1].get("avg_fitness", 0.0) if rows else 0.0,
            "survivors": rows[-1].get("survivors", 0) if rows else 0,
        })
    return results


def export_experiment(self: World, path: str | Path) -> None:
    _ensure_world(self)
    data = {
        "version": 1, "seed": self.seed, "generation": self.generation,
        "season": self.season, "weather": self.weather,
        "history": self.history[-500:], "genealogy": self.genealogy,
        "events": self.life_events[-1000:], "experiment_log": self.experiment_log[-200:],
    }
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def cognitive_summary(robot: Robot) -> dict:
    _ensure_robot(robot)
    return {
        "map_places": len(robot.cognitive_map),
        "habits": {k: round(v.success, 2) for k, v in robot.habits.items()},
        "relationships": len(robot.relationships), "family": sorted(robot.family_ids),
        "home_cell": robot.home_cell, "territory_strength": round(robot.territory_strength, 3),
        "personality_mood": round(robot.personality_mood, 3), "reflexes": robot.reflex_count,
        "social_learning": robot.social_learning_ticks,
        "weather_memory": {k: round(v, 3) for k, v in robot.weather_memory.items()},
        "life_events": len(robot.life_events),
    }


def install() -> None:
    global _INSTALLED
    if _INSTALLED or getattr(World, "_advanced_evolution_installed", False):
        return
    _ORIGINALS["drive_bias"] = Robot.drive_bias
    _ORIGINALS["robot_step"] = Robot.step
    _ORIGINALS["predator_step"] = World.predator_step
    _ORIGINALS["create_child"] = World.create_child
    _ORIGINALS["finish_generation"] = World.finish_generation
    _ORIGINALS["world_step"] = World.step
    Robot.drive_bias = _reflex_bias  # type: ignore[method-assign]
    Robot.step = _robot_step  # type: ignore[method-assign]
    World.predator_step = _predator_step  # type: ignore[method-assign]
    World.create_child = _create_child  # type: ignore[method-assign]
    World.finish_generation = _finish_generation  # type: ignore[method-assign]
    World.step = _world_step  # type: ignore[method-assign]
    World.export_experiment = export_experiment  # type: ignore[attr-defined]
    World.cognitive_summary = lambda self, robot_id: cognitive_summary(next(r for r in self.population if r.id == robot_id))  # type: ignore[attr-defined]
    World._advanced_evolution_installed = True
    _INSTALLED = True
