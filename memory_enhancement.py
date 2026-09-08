"""Long-term memory enhancement for EVOLVE.

Keeps the existing learner intact while adding richer episodic/spatial memory,
novelty tracking, importance-based forgetting and sleep consolidation.
Standard library only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple
import math

from evolve_engine import ACTIONS, Memory, Robot, World, clamp

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
        semantic = 1.35 if self.cue == cue else (1.0 if self.goal == cue else 0.55)
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


def _cell(robot: Robot) -> Tuple[int, int]:
    return int(robot.x // 50), int(robot.y // 50)


def _record(robot: Robot, world: World, state: str, cue: str, action: int, reward: float, goal: str) -> None:
    _ensure(robot)
    xb, yb = _cell(robot)
    positive = max(0.0, reward)
    negative = max(0.0, -reward)
    importance = clamp(0.35 + abs(reward) / 12.0, 0.25, 1.8)
    if cue in ("food", "water", "predator", "hazard"):
        importance += 0.35
    if "death:" in cue:
        importance = 1.8

    # Merge near-identical memories instead of growing without bound.
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
        del robot.long_memory[: len(robot.long_memory) - capacity]

    place = robot.place_memory.setdefault((xb, yb), {})
    key = cue if cue in ("food", "water", "predator", "hazard") else goal
    if key:
        place[key] = clamp(place.get(key, 0.0) * 0.75 + reward * 0.25, -20, 20)


def _novelty(robot: Robot, world: World) -> float:
    _ensure(robot)
    xb, yb = _cell(robot)
    key = (xb, yb)
    visits = robot.novelty_map.get(key, 0.0)
    robot.novelty_map[key] = visits + 1.0
    # Familiarity rises quickly at frequently visited locations and feeds the
    # existing curiosity drive through a lightweight external signal.
    familiarity = 1.0 - math.exp(-visits / 3.0)
    robot.memory_familiarity = familiarity
    return 1.0 - familiarity


def _retrieve(robot: Robot, world: World, state: str, cue: str, goal: str, limit: int = 6) -> List[LongMemory]:
    _ensure(robot)
    xb, yb = _cell(robot)
    candidates = sorted(
        robot.long_memory,
        key=lambda memory: memory.score(world.tick, state, cue, xb, yb),
        reverse=True,
    )
    return candidates[:limit]


def _consolidate(robot: Robot, world: World) -> float:
    _ensure(robot)
    if not robot.long_memory:
        return 0.0
    if world.tick - robot.memory_last_consolidation < 20:
        return 0.0
    selected = _retrieve(robot, world, robot.brain.last_state or "", robot.brain.last_cue, getattr(robot.brain, "current_goal", "explore"), 8)
    updates = 0
    for memory in selected:
        values = robot.brain.values(memory.state)
        best = max(range(len(values)), key=values.__getitem__)
        target = memory.reward * memory.strength
        values[memory.action] += robot.brain.alpha * 0.18 * (target - values[memory.action])
        # Salient memories become more durable when successfully replayed.
        memory.strength = clamp(memory.strength * 1.04, 0.03, 2.5)
        updates += 1
    robot.memory_replays += updates
    robot.memory_last_consolidation = world.tick
    return float(updates)


def _before_step(robot: Robot, world: World) -> Tuple[str, str, int, str]:
    _ensure(robot)
    state = robot.brain.last_state or ""
    cue = robot.brain.last_cue or "nothing"
    action = robot.brain.last_action if robot.brain.last_action is not None else 0
    goal = getattr(robot.brain, "current_goal", "explore")
    return state, cue, action, goal


def _memory_bias(robot: Robot, world: World, bias: List[float]) -> List[float]:
    _ensure(robot)
    state = robot.brain.last_state or ""
    cue = robot.brain.last_cue or "nothing"
    goal = getattr(robot.brain, "current_goal", "explore")
    memories = _retrieve(robot, world, state, cue, goal, 5)
    novelty = _novelty(robot, world)

    for memory in memories:
        if memory.reward < -6:
            bias[memory.action] -= min(0.42, 0.06 * abs(memory.reward) * memory.strength)
        elif memory.reward > 6:
            bias[memory.action] += min(0.32, 0.04 * memory.reward * memory.strength)

    # Explore novel places unless fear is already dominant.
    fear = robot.drives(world)[3]
    if novelty > 0.55 and fear < 0.55:
        bias[0] += 0.12 * novelty
    return bias


def _robot_step(self: Robot, world: World) -> None:
    _ensure(self)
    before_state, before_cue, before_action, before_goal = _before_step(self, world)
    before_food = self.food_eaten
    before_water = self.water_found
    before_damage = self.damage_taken
    alive_before = self.alive

    _ORIGINALS["robot_step"](self, world)  # type: ignore[misc]

    # Record important experiences or periodic snapshots.
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
        death_state = self.brain.last_state or before_state or "death"
        _record(self, world, death_state, f"death:{lesson}", self.brain.last_action or 0, -18.0, "survival")


def _drive_bias(self: Robot, world: World, codes, internal):
    bias = _ORIGINALS["robot_drive_bias"](self, world, codes, internal)  # type: ignore[misc]
    return _memory_bias(self, world, bias)


def _summary(robot: Robot) -> dict:
    _ensure(robot)
    result = dict(robot.brain.summary())
    result.update({
        "long_term_memory": len(robot.long_memory),
        "place_memory": len(robot.place_memory),
        "novelty_cells": len(robot.novelty_map),
        "memory_replays": robot.memory_replays,
        "familiarity": round(robot.memory_familiarity, 3),
    })
    return result


def install() -> None:
    global _INSTALLED
    if _INSTALLED or getattr(Robot, "_memory_enhancement_installed", False):
        return
    _ORIGINALS["robot_step"] = Robot.step
    _ORIGINALS["robot_drive_bias"] = Robot.drive_bias
    _ORIGINALS["robot_summary"] = Robot.brain.summary if hasattr(Robot, "brain") else None
    Robot.step = _robot_step  # type: ignore[method-assign]
    Robot.drive_bias = _drive_bias  # type: ignore[method-assign]
    Robot._memory_enhancement_installed = True
    _INSTALLED = True


def get_memory(robot: Robot) -> List[LongMemory]:
    _ensure(robot)
    return list(robot.long_memory)


def consolidate(robot: Robot, world: World) -> float:
    return _consolidate(robot, world)
