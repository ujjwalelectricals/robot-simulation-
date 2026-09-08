"""Richer memory for EVOLVE.

The robot keeps finite, importance-weighted episodic memories, coarse place
memories, novelty/familiarity estimates and sleep consolidation. Memory can
influence navigation without exposing hidden world state.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, List, Tuple

from evolve_engine import AnimalBrain, Robot, World, clamp

_INSTALLED = False
_ORIGINALS: dict[str, object] = {}


@dataclass
class LongMemory:
    state: str
    cue: str
    action: int
    reward: float
    tick: int
    x_bin: int
    y_bin: int
    goal: str
    importance: float
    strength: float = 1.0
    visits: int = 1

    def score(self, tick: int, state: str, cue: str, x_bin: int, y_bin: int) -> float:
        age = max(0, tick - self.tick)
        recency = math.exp(-age / 700.0)
        spatial = 1.0 / (1.0 + abs(self.x_bin - x_bin) + abs(self.y_bin - y_bin))
        semantic = 1.35 if self.cue == cue else 0.75
        state_match = 1.25 if self.state == state else 0.55
        salience = 1.0 + min(2.5, abs(self.reward) / 10.0)
        return self.strength * self.importance * recency * spatial * semantic * state_match * salience


def _ensure(robot: Robot) -> None:
    if hasattr(robot, "long_memory"):
        return
    robot.long_memory: List[LongMemory] = []
    robot.place_memory: Dict[Tuple[int, int], Dict[str, float]] = {}
    robot.novelty_map: Dict[Tuple[int, int], float] = {}
    robot.memory_replays = 0
    robot.memory_last_consolidation = -10000
    robot.memory_familiarity = 0.0
    robot.memory_forget_count = 0


def _cell(robot: Robot) -> Tuple[int, int]:
    return int(robot.x // 50), int(robot.y // 50)


def _record(robot: Robot, world: World, state: str, cue: str, action: int, reward: float, goal: str) -> None:
    _ensure(robot)
    xb, yb = _cell(robot)
    importance = clamp(0.35 + abs(reward) / 12.0, 0.25, 1.8)
    if cue in ("food", "water", "predator", "hazard") or cue.startswith("death:"):
        importance = clamp(importance + 0.35, 0.2, 2.0)
    for memory in robot.long_memory[-24:]:
        if memory.state == state and memory.cue == cue and memory.x_bin == xb and memory.y_bin == yb:
            memory.reward = clamp(memory.reward * 0.65 + reward * 0.35, -20, 20)
            memory.strength = clamp(memory.strength * 0.82 + importance * 0.24, 0.03, 2.5)
            memory.importance = clamp(max(memory.importance, importance), 0.2, 2.0)
            memory.tick = world.tick
            memory.visits += 1
            return
    robot.long_memory.append(LongMemory(state, cue, int(action), reward, world.tick, xb, yb, goal, importance))
    capacity = max(32, int(robot.genome.memory_capacity) * 3)
    if len(robot.long_memory) > capacity:
        robot.long_memory.sort(key=lambda m: m.strength * m.importance)
        forgotten = len(robot.long_memory) - capacity
        del robot.long_memory[:forgotten]
        robot.memory_forget_count += forgotten
    key = cue if cue in ("food", "water", "predator", "hazard") else goal
    if key:
        place = robot.place_memory.setdefault((xb, yb), {})
        place[key] = clamp(place.get(key, 0.0) * 0.75 + reward * 0.25, -20, 20)


def _novelty(robot: Robot) -> float:
    _ensure(robot)
    key = _cell(robot)
    visits = robot.novelty_map.get(key, 0.0)
    robot.novelty_map[key] = visits + 1.0
    familiarity = 1.0 - math.exp(-visits / 3.0)
    robot.memory_familiarity = familiarity
    return 1.0 - familiarity


def _retrieve(robot: Robot, world: World, state: str, cue: str, limit: int = 6) -> List[LongMemory]:
    _ensure(robot)
    xb, yb = _cell(robot)
    memories = sorted(robot.long_memory, key=lambda m: m.score(world.tick, state, cue, xb, yb), reverse=True)
    return memories[:limit]


def _consolidate(robot: Robot, world: World) -> float:
    _ensure(robot)
    if not robot.long_memory or world.tick - robot.memory_last_consolidation < 20:
        return 0.0
    selected = _retrieve(robot, world, robot.brain.last_state or "", robot.brain.last_cue, 8)
    for memory in selected:
        values = robot.brain.values(memory.state)
        target = memory.reward * memory.strength
        values[memory.action] += robot.brain.alpha * 0.18 * (target - values[memory.action])
        memory.strength = clamp(memory.strength * 1.04, 0.03, 2.5)
    robot.memory_replays += len(selected)
    robot.memory_last_consolidation = world.tick
    return float(len(selected))


def _spatial_recall(robot: Robot, world: World, goal: str, bias: List[float]) -> None:
    desired = {"hunger": {"food"}, "thirst": {"water"}}.get(goal, set())
    if not desired:
        return
    best: tuple[float, float, float] | None = None
    for memory in robot.long_memory:
        if memory.cue not in desired or memory.reward <= 2.0:
            continue
        dx = memory.x_bin * 50 + 25 - robot.x
        dy = memory.y_bin * 50 + 25 - robot.y
        d2 = dx * dx + dy * dy
        if d2 < 45 * 45 or d2 > 420 * 420:
            continue
        age = max(0, world.tick - memory.tick)
        score = memory.strength * memory.importance * math.exp(-age / 1000.0) * min(2.0, memory.reward / 8.0)
        score /= 1.0 + math.sqrt(d2) / 180.0
        if best is None or score > best[0]:
            best = (score, dx, dy)
    if best is None:
        return
    _, dx, dy = best
    relative = (math.atan2(dy, dx) - robot.angle + math.pi) % (2 * math.pi) - math.pi
    strength = min(0.45, best[0] * 0.18)
    if abs(relative) < 0.35:
        bias[0] += strength
    elif relative < 0:
        bias[1] += strength
    else:
        bias[2] += strength


def _memory_bias(robot: Robot, world: World, bias: List[float]) -> List[float]:
    _ensure(robot)
    state = robot.brain.last_state or ""
    cue = robot.brain.last_cue or "nothing"
    goal = getattr(robot.brain, "current_goal", "explore")
    for memory in _retrieve(robot, world, state, cue, 5):
        influence = min(0.38, 0.05 * abs(memory.reward) * memory.strength)
        if memory.reward > 6:
            bias[memory.action] += influence
        elif memory.reward < -6:
            bias[memory.action] -= influence
    _spatial_recall(robot, world, goal, bias)
    novelty = _novelty(robot)
    if novelty > 0.55 and robot.drives(world)[3] < 0.55:
        bias[0] += 0.10 * novelty
    if world.tick % 20 == 0:
        stale = [m for m in robot.long_memory if m.strength < 0.10 and world.tick - m.tick > 500]
        for memory in stale[:max(0, len(robot.long_memory) - max(32, robot.genome.memory_capacity * 2))]:
            try:
                robot.long_memory.remove(memory)
                robot.memory_forget_count += 1
            except ValueError:
                pass
    return bias


def _robot_step(self: Robot, world: World) -> None:
    _ensure(self)
    before_state = self.brain.last_state or ""
    before_cue = self.brain.last_cue or "nothing"
    before_action = self.brain.last_action if self.brain.last_action is not None else 0
    before_goal = getattr(self.brain, "current_goal", "explore")
    before_food, before_water, before_damage = self.food_eaten, self.water_found, self.damage_taken
    alive_before = self.alive
    _ORIGINALS["robot_step"](self, world)  # type: ignore[misc]
    if alive_before:
        reward = float(self.recent_reward)
        cue = self.brain.last_cue or before_cue
        action = self.brain.last_action if self.brain.last_action is not None else before_action
        salient = abs(reward) >= 1.5 or self.food_eaten != before_food or self.water_found != before_water or self.damage_taken != before_damage
        if salient or world.tick % 8 == 0:
            _record(self, world, before_state or self.brain.last_state or "", cue, action, reward, getattr(self.brain, "current_goal", before_goal))
        if self.sleeping:
            _consolidate(self, world)
    if alive_before and not self.alive:
        lesson = getattr(self, "last_death_lesson", "") or getattr(self, "kill_reason", "") or "unknown"
        _record(self, world, self.brain.last_state or before_state or "death", f"death:{lesson}", self.brain.last_action or 0, -18.0, "survival")


def _drive_bias(self: Robot, world: World, codes, internal):
    bias = _ORIGINALS["robot_drive_bias"](self, world, codes, internal)  # type: ignore[misc]
    return _memory_bias(self, world, bias)


def _summary(self: AnimalBrain) -> dict:
    result = dict(_ORIGINALS["brain_summary"](self))  # type: ignore[misc]
    robot = getattr(self, "_memory_robot", None)
    if robot is not None:
        _ensure(robot)
        result.update({"long_term_memory": len(robot.long_memory), "place_memory": len(robot.place_memory), "novelty_cells": len(robot.novelty_map), "memory_replays": robot.memory_replays, "memory_forgotten": robot.memory_forget_count, "familiarity": round(robot.memory_familiarity, 3)})
    return result


def install() -> None:
    global _INSTALLED
    if _INSTALLED or getattr(Robot, "_memory_enhancement_installed", False):
        return
    _ORIGINALS["robot_step"] = Robot.step
    _ORIGINALS["robot_drive_bias"] = Robot.drive_bias
    _ORIGINALS["brain_summary"] = AnimalBrain.summary
    original_init = Robot.__init__

    def robot_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        _ensure(self)
        self.brain._memory_robot = self

    Robot.__init__ = robot_init  # type: ignore[method-assign]
    Robot.step = _robot_step  # type: ignore[method-assign]
    Robot.drive_bias = _drive_bias  # type: ignore[method-assign]
    AnimalBrain.summary = _summary  # type: ignore[method-assign]
    Robot._memory_enhancement_installed = True
    _INSTALLED = True


def get_memory(robot: Robot) -> List[LongMemory]:
    _ensure(robot)
    return list(robot.long_memory)
