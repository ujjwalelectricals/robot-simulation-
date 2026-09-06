"""Survival-memory and courage upgrade for EVOLVE.

Adds death lessons, inherited avoidance associations, and courage-driven
predator confrontation without adding a new genome field: existing boldness is
used as the inherited courage trait.
"""
from __future__ import annotations

import math
from typing import Optional

from evolve_engine import Predator, Robot, World, clamp

_ORIGINALS: dict[str, object] = {}
_INSTALLED = False


def _ensure(robot: Robot) -> None:
    if hasattr(robot, "death_lessons"):
        return
    robot.death_lessons = []
    robot.last_death_lesson = ""
    robot.courage_wins = 0
    robot._last_confront_tick = -10000


def _death_reason(robot: Robot) -> str:
    reason = getattr(robot, "kill_reason", "") or ""
    lowered = reason.lower()
    if "predator" in lowered:
        return "predator"
    if "hazard" in lowered or "damage" in lowered:
        return "hazard"
    if "starvation" in lowered or "dehydration" in lowered:
        return "starvation"
    if "old age" in lowered:
        return "old_age"
    return lowered or "unknown"


def _record_death(robot: Robot, world: World) -> None:
    _ensure(robot)
    lesson = _death_reason(robot)
    if not lesson:
        return
    robot.last_death_lesson = lesson
    robot.death_lessons.append(lesson)
    if len(robot.death_lessons) > 8:
        del robot.death_lessons[:-8]

    # Strong inherited warning association. This is attached to the existing
    # brain memory/association system so offspring can inherit the lesson.
    cue = f"death:{lesson}"
    robot.brain.associations[cue] = clamp(robot.brain.associations.get(cue, 0.0) - 8.0, -20.0, 20.0)


def _confront_bias(robot: Robot, world: World, bias: list[float]) -> list[float]:
    _ensure(robot)
    # Boldness is the existing inherited courage trait.
    courage = clamp(robot.genome.boldness, 0.0, 1.0)
    if courage < 0.72 or not robot.alive:
        return bias

    nearest: Optional[Predator] = None
    best_d2 = 90.0 * 90.0
    for obj in world.nearby(robot.x, robot.y, 90):
        if isinstance(obj, Predator) and obj.alive:
            dx = obj.x - robot.x
            dy = obj.y - robot.y
            d2 = dx * dx + dy * dy
            if d2 < best_d2:
                best_d2 = d2
                nearest = obj
    if nearest is None:
        return bias

    # Brave robots have a meaningful chance to challenge a predator instead of
    # receiving a blanket "never flee" rule.
    pressure = courage * (1.0 - math.sqrt(best_d2) / 90.0)
    bias[7] += 0.70 * pressure  # approach/confront
    bias[8] -= 0.45 * pressure  # reduce automatic fleeing
    return bias


def _brain_summary(robot: Robot) -> dict:
    _ensure(robot)
    result = dict(robot.brain.summary())
    result.update({
        "death_lessons": list(robot.death_lessons[-6:]),
        "last_death_lesson": robot.last_death_lesson,
        "courage": round(robot.genome.boldness, 3),
        "courage_wins": robot.courage_wins,
    })
    return result


def _robot_step(self: Robot, world: World) -> None:
    _ensure(self)
    was_alive = self.alive
    _ORIGINALS["robot_step"](self, world)  # type: ignore[misc]

    # Learn from the death that just happened.
    if was_alive and not self.alive:
        _record_death(self, world)
        return

    if not self.alive:
        return

    courage = clamp(self.genome.boldness, 0.0, 1.0)
    if courage < 0.72 or world.tick - self._last_confront_tick < 20:
        return

    nearest: Optional[Predator] = None
    best_d2 = 24.0 * 24.0
    for obj in world.nearby(self.x, self.y, 24):
        if isinstance(obj, Predator) and obj.alive:
            dx = obj.x - self.x
            dy = obj.y - self.y
            d2 = dx * dx + dy * dy
            if d2 < best_d2:
                best_d2 = d2
                nearest = obj
    if nearest is None:
        return

    # Close-range confrontation: the robot pushes the predator away instead of
    # taking another full hit every tick. Higher courage gives better odds.
    if world.rng.random() < 0.35 + 0.45 * courage:
        dx = nearest.x - self.x
        dy = nearest.y - self.y
        length = max(0.001, math.hypot(dx, dy))
        push = 18.0 + 18.0 * courage
        nearest.x = clamp(nearest.x + dx / length * push, 12, world.width - 12)
        nearest.y = clamp(nearest.y + dy / length * push, 12, world.height - 12)
        nearest.angle = math.atan2(nearest.y - self.y, nearest.x - self.x) + math.pi
        self.fitness += 4.0
        self.recent_reward += 4.0
        self.courage_wins += 1
        self._last_confront_tick = world.tick


def _create_child(original, world: World, a: Robot, b: Robot):
    child = original(a, b)
    _ensure(child)
    # Blend a small amount of the parents' death lessons into inherited
    # associations. The child does not get a full adult episodic memory.
    parent_lessons = []
    for parent in (a, b):
        parent_lessons.extend(getattr(parent, "death_lessons", [])[-3:])
    for lesson in parent_lessons:
        cue = f"death:{lesson}"
        child.brain.associations[cue] = clamp(child.brain.associations.get(cue, 0.0) - 3.5, -20.0, 20.0)
    return child


def install() -> None:
    global _INSTALLED
    if _INSTALLED or getattr(Robot, "_survival_memory_installed", False):
        return
    _ORIGINALS["robot_step"] = Robot.step
    _ORIGINALS["robot_drive_bias"] = Robot.drive_bias
    _ORIGINALS["world_create_child"] = World.create_child

    def drive_bias(self: Robot, world: World, codes, internal):
        bias = _ORIGINALS["robot_drive_bias"](self, world, codes, internal)  # type: ignore[misc]
        return _confront_bias(self, world, bias)

    def create_child(world: World, a: Robot, b: Robot):
        return _create_child(_ORIGINALS["world_create_child"], world, a, b)  # type: ignore[misc]

    Robot.step = _robot_step  # type: ignore[method-assign]
    Robot.drive_bias = drive_bias  # type: ignore[method-assign]
    World.create_child = create_child  # type: ignore[method-assign]
    Robot._survival_memory_installed = True
    _INSTALLED = True
