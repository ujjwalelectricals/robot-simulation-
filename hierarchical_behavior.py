"""Hierarchical behavior and stuck-recovery layer for EVOLVE.

Keeps the existing learned primitive policy, but lets robots execute short
reusable behavior sequences selected from their internal needs. Also detects
persistent low movement and forces a learned recovery turn.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from evolve_engine import Robot, World

_ORIGINALS: dict[str, object] = {}
_INSTALLED = False


@dataclass
class Behavior:
    name: str
    steps: Tuple[str, ...]
    index: int = 0
    progress: int = 0
    failures: int = 0
    active: bool = True

    @property
    def step(self) -> str:
        return self.steps[min(self.index, len(self.steps) - 1)]

    def advance(self) -> None:
        if self.index < len(self.steps) - 1:
            self.index += 1
            self.progress = 0
        else:
            self.active = False


BEHAVIORS: Dict[str, Tuple[str, ...]] = {
    "forage_food": ("seek_food", "approach_food", "consume_food", "retreat"),
    "seek_water": ("seek_water", "approach_water", "consume_water", "retreat"),
    "escape_threat": ("locate_cover", "flee", "recover", "retreat"),
    "rest_cycle": ("find_shelter", "rest", "recover", "retreat"),
    "social_contact": ("locate_social", "approach_social", "contact", "retreat"),
    "exploration": ("explore", "inspect", "reorient", "retreat"),
}


def _ensure(robot: Robot) -> None:
    if hasattr(robot, "behavior"):
        return
    robot.behavior: Optional[Behavior] = None
    robot.behavior_history: List[str] = []
    robot.stuck_ticks = 0
    robot._behavior_last_pos = (robot.x, robot.y)
    robot._behavior_force_turn = 0
    robot._behavior_food_seen = robot.food_eaten
    robot._behavior_water_seen = robot.water_found


def _start_for_goal(robot: Robot) -> None:
    goal = getattr(robot.brain, "current_goal", "explore")
    name = {
        "hunger": "forage_food",
        "thirst": "seek_water",
        "survival": "escape_threat",
        "rest": "rest_cycle",
        "social": "social_contact",
        "explore": "exploration",
    }.get(goal, "exploration")
    if robot.behavior and robot.behavior.active and robot.behavior.name == name:
        return
    robot.behavior = Behavior(name, BEHAVIORS[name])
    robot.behavior_history.append(name)
    robot.behavior_history = robot.behavior_history[-20:]


def _bias(self: Robot, world: World, codes: List[int], internal: List[float]) -> list[float]:
    bias = _ORIGINALS["drive_bias"](self, world, codes, internal)  # type: ignore[misc]
    _ensure(self)
    _start_for_goal(self)
    behavior = self.behavior
    seen = set(codes)
    if not behavior or not behavior.active:
        return bias

    step = behavior.step
    if step in ("seek_food", "approach_food"):
        bias[0] += 0.18
        if 1 in seen or 8 in seen:
            bias[0] += 0.35
            bias[5] += 0.55 if 1 in seen else 0.0
            bias[7] += 0.28
    elif step == "consume_food":
        bias[5] += 0.85 if 1 in seen else 0.15
    elif step in ("seek_water", "approach_water"):
        bias[0] += 0.18
        if 5 in seen or 8 in seen:
            bias[0] += 0.35
            bias[6] += 0.55 if 5 in seen else 0.0
            bias[7] += 0.28
    elif step == "consume_water":
        bias[6] += 0.85 if 5 in seen else 0.15
    elif step in ("locate_cover", "flee"):
        bias[8] += 0.85
        bias[1] += 0.18
        bias[2] += 0.18
    elif step in ("find_shelter", "rest"):
        bias[4] += 0.75 if 7 in seen else 0.08
        bias[0] += 0.10 if 7 not in seen else 0.0
    elif step in ("locate_social", "approach_social", "contact"):
        bias[7] += 0.70 if 6 in seen else 0.12
        bias[0] += 0.08 if 6 not in seen else 0.0
    elif step in ("explore", "inspect", "reorient"):
        bias[0] += 0.18
        bias[1] += 0.04
        bias[2] += 0.04
    elif step == "retreat":
        bias[0] += 0.12
        bias[3] += 0.06

    if self._behavior_force_turn:
        if self._behavior_force_turn < 0:
            bias[1] += 1.0
        else:
            bias[2] += 1.0
        self._behavior_force_turn = 0
    return bias


def _after_step(self: Robot, world: World) -> None:
    _ensure(self)
    px, py = self._behavior_last_pos
    moved2 = (self.x - px) ** 2 + (self.y - py) ** 2
    self._behavior_last_pos = (self.x, self.y)
    if self.alive and not self.sleeping and moved2 < 0.8:
        self.stuck_ticks += 1
    else:
        self.stuck_ticks = max(0, self.stuck_ticks - 2)

    if self.stuck_ticks >= 10:
        self.brain.learn(
            f"stuck:{getattr(self.brain, 'current_goal', 'explore')}",
            0,
            -1.0,
            f"recover:{world.tick}",
            "wall",
            world.tick,
        )
        if self.behavior:
            self.behavior.failures += 1
            self.behavior.advance()
        self._behavior_force_turn = -1 if (self.id + world.tick) % 2 == 0 else 1
        self.stuck_ticks = 0

    behavior = self.behavior
    if not behavior:
        return
    if behavior.step == "consume_food" and self.food_eaten > self._behavior_food_seen:
        self._behavior_food_seen = self.food_eaten
        behavior.advance()
    elif behavior.step == "consume_water" and self.water_found > self._behavior_water_seen:
        self._behavior_water_seen = self.water_found
        behavior.advance()
    elif behavior.step == "rest" and self.sleeping:
        behavior.progress += 1
        if behavior.progress >= 8:
            behavior.advance()
    elif behavior.step in ("flee", "recover") and self.brain.stress < 0.35:
        behavior.advance()
    elif behavior.step in ("approach_food", "approach_water"):
        behavior.progress += 1
        if behavior.progress >= 18:
            behavior.advance()
    elif behavior.step == "retreat":
        behavior.progress += 1
        if behavior.progress >= 8:
            behavior.advance()


def _step(self: Robot, world: World):
    result = _ORIGINALS["robot_step"](self, world)  # type: ignore[misc]
    _after_step(self, world)
    return result


def install() -> None:
    global _INSTALLED
    if _INSTALLED or getattr(Robot, "_hierarchical_behavior_installed", False):
        return
    _ORIGINALS["drive_bias"] = Robot.drive_bias
    _ORIGINALS["robot_step"] = Robot.step
    Robot.drive_bias = _bias  # type: ignore[method-assign]
    Robot.step = _step  # type: ignore[method-assign]
    Robot._hierarchical_behavior_installed = True
    _INSTALLED = True
