"""Dog-inspired cognitive upgrade for EVOLVE.

Adds explicit memory/learning skills, needs-based goal arbitration, lightweight
olfactory/auditory cues, and smoother motor control without claiming to model a
real canine brain. Standard library only.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from evolve_engine import ACTIONS, AnimalBrain, Predator, Robot, World, clamp

_ORIGINALS: dict[str, object] = {}
_SKILLS = ("navigation", "food", "water", "threat", "social", "self_control")


def _brain_init(self: AnimalBrain, genome, rng, q=None, associations=None) -> None:
    _ORIGINALS["brain_init"](self, genome, rng, q, associations)  # type: ignore[misc]
    self.skills: Dict[str, float] = {name: 0.05 for name in _SKILLS}
    self.skill_attempts: Dict[str, int] = {name: 0 for name in _SKILLS}
    self.current_goal = "explore"
    self.goal_strength = 0.0
    self.reward_prediction = 0.0
    self.last_reward_prediction_error = 0.0
    self.last_smell = "none"
    self.last_sound = "quiet"
    self.recent_states: List[str] = []


def _skill_from_cue(cue: str, reward: float) -> str:
    cue = cue.lower()
    if "food" in cue:
        return "food"
    if "water" in cue:
        return "water"
    if "predator" in cue or "danger" in cue or reward < -10:
        return "threat"
    if "robot" in cue:
        return "social"
    if "wall" in cue:
        return "navigation"
    if abs(reward) <= 1.0:
        return "self_control"
    return "navigation"


def _brain_learn(self: AnimalBrain, state: str, action: int, reward: float, next_state: str, cue: str, tick: int) -> None:
    # Dopamine-like prediction error updates the existing value learner.
    prediction = self.reward_prediction
    rpe = reward - prediction
    self.last_reward_prediction_error = rpe
    self.reward_prediction = clamp(prediction * 0.94 + reward * 0.06, -20.0, 20.0)
    _ORIGINALS["brain_learn"](self, state, action, reward, next_state, cue, tick)  # type: ignore[misc]

    skill = _skill_from_cue(cue, reward)
    self.skill_attempts[skill] += 1
    step = 0.012 if rpe > 0 else 0.007
    self.skills[skill] = clamp(self.skills[skill] + (step if reward >= 0 else -step), 0.02, 1.0)
    self.recent_states.append(state)
    if len(self.recent_states) > 24:
        del self.recent_states[:-24]


def _choose(self: AnimalBrain, state: str, biases: List[float]) -> int:
    # A small learned self-control bonus reduces impulsive exploration as the
    # robot gains experience, while preserving inherited exploration.
    control = self.skills.get("self_control", 0.05)
    adjusted = list(biases)
    adjusted[0] -= 0.12 * control
    adjusted[4] += 0.08 * control
    return _ORIGINALS["brain_choose"](self, state, adjusted)  # type: ignore[misc]


def _goal_arbitration(self: Robot, world: World, codes: List[int], internal: List[float]) -> list[float]:
    bias = _ORIGINALS["robot_drive_bias"](self, world, codes, internal)  # type: ignore[misc]
    hunger, thirst, fatigue, fear, curiosity, social, sleepiness = internal
    brain = self.brain

    nearby_predator: Optional[Predator] = None
    best_d2 = float("inf")
    for obj in world.nearby(self.x, self.y, 150):
        if isinstance(obj, Predator) and obj.alive:
            dx = obj.x - self.x
            dy = obj.y - self.y
            d2 = dx * dx + dy * dy
            if d2 < best_d2:
                best_d2 = d2
                nearby_predator = obj

    # Olfactory bulb proxy: scent is sensed without giving away object labels.
    food_smell = world.local_scent(self.x, self.y, "food")
    danger_smell = world.local_scent(self.x, self.y, "danger")
    brain.last_smell = "food" if food_smell > danger_smell + 0.08 else ("danger" if danger_smell > food_smell + 0.08 else "mixed")

    # Auditory proxy: nearby predators are louder/stronger threats than distant ones.
    brain.last_sound = "threat" if nearby_predator and best_d2 < 115 * 115 else (
        "movement" if world.nearest_robot(self.x, self.y, exclude=self, radius=70) else "quiet"
    )

    goals = {
        "survival": fear * (1.25 + self.genome.fear_sensitivity * 0.5),
        "thirst": thirst * (1.05 + brain.skills.get("water", 0.0) * 0.35),
        "hunger": hunger * (1.0 + brain.skills.get("food", 0.0) * 0.35),
        "rest": max(fatigue, sleepiness) * (0.9 + self.genome.patience * 0.25),
        "social": social * 0.45,
        "explore": curiosity * (0.65 + brain.skills.get("navigation", 0.0) * 0.3),
    }
    if danger_smell > 0.35:
        goals["survival"] += danger_smell * 0.9
    if food_smell > 0.35:
        goals["hunger"] += food_smell * 0.75
    goal, strength = max(goals.items(), key=lambda item: item[1])
    brain.current_goal = goal
    brain.goal_strength = clamp(strength, 0.0, 1.8)

    if goal == "survival":
        bias[8] += 0.8 * strength
        bias[1] += 0.18 * strength
        bias[2] += 0.18 * strength
    elif goal == "thirst":
        if 5 in codes or 8 in codes:
            bias[6] += 0.35 * strength
        else:
            bias[0] += 0.08 * strength
    elif goal == "hunger":
        if 1 in codes or 8 in codes:
            bias[5] += 0.4 * strength
        else:
            bias[0] += 0.08 * strength
    elif goal == "rest":
        bias[4] += 0.45 * strength
    elif goal == "social":
        bias[7] += 0.22 * strength
    else:
        bias[0] += 0.12 * strength

    return bias


def _remember(self: AnimalBrain, state: str, tick: int, capacity: int) -> None:
    _ORIGINALS["brain_remember"](self, state, tick, capacity)  # type: ignore[misc]
    # Recent states give the brain a tiny working sequence, useful for learning
    # short action chains without storing an unbounded history.
    self.recent_states.append(state)
    if len(self.recent_states) > 24:
        del self.recent_states[:-24]


def _summary(self: AnimalBrain) -> dict:
    result = _ORIGINALS["brain_summary"](self)  # type: ignore[misc]
    result.update({
        "skills": {name: round(self.skills.get(name, 0.0), 3) for name in _SKILLS},
        "current_goal": self.current_goal,
        "goal_strength": round(self.goal_strength, 3),
        "reward_prediction_error": round(self.last_reward_prediction_error, 3),
        "smell": self.last_smell,
        "sound": self.last_sound,
    })
    return result


def install() -> None:
    if getattr(AnimalBrain, "_cognitive_upgrade_installed", False):
        return
    _ORIGINALS["brain_init"] = AnimalBrain.__init__
    _ORIGINALS["brain_learn"] = AnimalBrain.learn
    _ORIGINALS["brain_choose"] = AnimalBrain.choose
    _ORIGINALS["brain_remember"] = AnimalBrain.remember
    _ORIGINALS["brain_summary"] = AnimalBrain.summary
    _ORIGINALS["robot_drive_bias"] = Robot.drive_bias

    AnimalBrain.__init__ = _brain_init  # type: ignore[method-assign]
    AnimalBrain.learn = _brain_learn  # type: ignore[method-assign]
    AnimalBrain.choose = _choose  # type: ignore[method-assign]
    AnimalBrain.remember = _remember  # type: ignore[method-assign]
    AnimalBrain.summary = _summary  # type: ignore[method-assign]
    Robot.drive_bias = _goal_arbitration  # type: ignore[method-assign]
    AnimalBrain._cognitive_upgrade_installed = True
