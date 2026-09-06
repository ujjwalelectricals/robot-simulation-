"""Optional EVOLVE ecosystem expansion loaded by the Windows launcher.

Adds richer predator behavior, larger ecosystems, threat-aware robot behavior,
and a few more persistent environmental shelters without replacing the core
engine or its optimized runtime.
"""
from __future__ import annotations

import math
from typing import Optional

from evolve_engine import Predator, Robot, Shelter, World, clamp, wrap_angle

_PREDATOR_KINDS = ("stalker", "sprinter", "pack_leader", "scout")
_ORIGINALS: dict[str, object] = {}


def _configure_expanded_defaults(world: World) -> None:
    # Keep explicit user configuration intact. Only raise defaults when the
    # experiment is still using the original stock defaults.
    if getattr(world, "_expanded_defaults_applied", False):
        return
    if getattr(world, "_target_population", 24) == 24:
        world._target_population = 36
    if getattr(world, "_target_food", 48) == 48:
        world._target_food = 72
    if getattr(world, "_target_water", 26) == 26:
        world._target_water = 38
    if getattr(world, "_target_hazards", 7) == 7:
        world._target_hazards = 11
    if getattr(world, "_target_predators", 1) == 1:
        world._target_predators = 4
    world._expanded_defaults_applied = True


def _decorate_predator(predator: Predator, index: int) -> Predator:
    kind = _PREDATOR_KINDS[index % len(_PREDATOR_KINDS)]
    predator.kind = kind
    if kind == "sprinter":
        predator.speed = 2.05
        predator.damage = 10.0
        predator.turn_rate = 0.18
        predator.detection = 260.0
    elif kind == "pack_leader":
        predator.speed = 1.55
        predator.damage = 15.0
        predator.turn_rate = 0.15
        predator.detection = 300.0
    elif kind == "scout":
        predator.speed = 1.80
        predator.damage = 8.0
        predator.turn_rate = 0.20
        predator.detection = 340.0
    else:
        predator.speed = 1.40
        predator.damage = 12.0
        predator.turn_rate = 0.12
        predator.detection = 230.0
    return predator


def _spawn_predator(world: World, x: Optional[float] = None, y: Optional[float] = None) -> None:
    original = _ORIGINALS["spawn_predator"]
    before = len(world.predators)
    original(world, x, y)  # type: ignore[misc]
    if len(world.predators) > before:
        _decorate_predator(world.predators[-1], before)


def _expanded_predator_step(world: World, predator: Predator) -> None:
    kind = getattr(predator, "kind", "stalker")
    detection = getattr(predator, "detection", 220.0)
    target = world.nearest_robot(predator.x, predator.y, radius=detection)

    if target:
        desired = math.atan2(target.y - predator.y, target.x - predator.x)
        delta = wrap_angle(desired - predator.angle)
        turn_rate = getattr(predator, "turn_rate", 0.12)
        predator.angle = wrap_angle(predator.angle + clamp(delta, -turn_rate, turn_rate))
    elif kind == "scout":
        predator.angle = wrap_angle(predator.angle + 0.025 * math.sin(world.tick * 0.031 + predator.x * 0.01))

    # Pack leaders bias toward the average direction of nearby predators so a
    # hunt naturally forms instead of every predator independently chasing.
    if kind == "pack_leader":
        nearby = [
            obj for obj in world.nearby(predator.x, predator.y, 170)
            if isinstance(obj, Predator) and obj is not predator and getattr(obj, "alive", True)
        ]
        if nearby:
            avg_x = sum(p.x for p in nearby) / len(nearby)
            avg_y = sum(p.y for p in nearby) / len(nearby)
            herd_angle = math.atan2(avg_y - predator.y, avg_x - predator.x)
            predator.angle = wrap_angle(predator.angle * 0.90 + herd_angle * 0.10)

    speed = getattr(predator, "speed", 1.45)
    nx = predator.x + math.cos(predator.angle) * speed
    ny = predator.y + math.sin(predator.angle) * speed
    if nx < 12 or nx > world.width - 12:
        predator.angle = wrap_angle(math.pi - predator.angle)
    if ny < 12 or ny > world.height - 12:
        predator.angle = wrap_angle(-predator.angle)
    predator.x = clamp(nx, 12, world.width - 12)
    predator.y = clamp(ny, 12, world.height - 12)


def _expanded_drive_bias(self: Robot, world: World, codes: list[int], internal: list[float]) -> list[float]:
    bias = _ORIGINALS["drive_bias"](self, world, codes, internal)  # type: ignore[misc]
    threats = [
        obj for obj in world.nearby(self.x, self.y, 160)
        if isinstance(obj, Predator) and getattr(obj, "alive", True)
    ]
    if not threats:
        return bias

    nearest = min(threats, key=lambda p: (p.x - self.x) ** 2 + (p.y - self.y) ** 2)
    dx = nearest.x - self.x
    dy = nearest.y - self.y
    d2 = dx * dx + dy * dy
    threat = clamp(1.0 - math.sqrt(d2) / 160.0, 0.0, 1.0)
    self.brain.stress = clamp(self.brain.stress + 0.018 * threat, 0.0, 1.0)
    self.brain.associations["predator_threat"] = self.brain.associations.get("predator_threat", 0.0) * 0.995 - 0.02 * threat

    # Strong threat makes fleeing clearly preferred; side-stepping is also
    # encouraged so robots do not all pile onto the same escape corridor.
    bias[8] += 1.8 * threat * (0.7 + self.genome.fear_sensitivity)
    if dx * math.cos(self.angle) + dy * math.sin(self.angle) > 0:
        bias[1] += 0.45 * threat
        bias[2] += 0.45 * threat
    return bias


def _expanded_reset(world: World) -> None:
    original = _ORIGINALS["reset"]
    original(world)  # type: ignore[misc]
    _configure_expanded_defaults(world)

    # Add more persistent safe zones to make the larger ecosystem readable and
    # give cautious agents a meaningful place to retreat.
    extra_shelters = 5
    for _ in range(extra_shelters):
        x, y = world.random_xy(70)
        world.shelters.append(Shelter(x, y, radius=38.0))

    for index, predator in enumerate(world.predators):
        _decorate_predator(predator, index)

    world.rebuild_spatial()


def install() -> None:
    """Install the ecosystem layer exactly once."""
    if getattr(World, "_ecosystem_expansion_installed", False):
        return

    _ORIGINALS["spawn_predator"] = World.spawn_predator
    _ORIGINALS["predator_step"] = World.predator_step
    _ORIGINALS["drive_bias"] = Robot.drive_bias
    _ORIGINALS["reset"] = World.reset

    World.spawn_predator = _spawn_predator  # type: ignore[method-assign]
    World.predator_step = _expanded_predator_step  # type: ignore[method-assign]
    Robot.drive_bias = _expanded_drive_bias  # type: ignore[method-assign]
    World.reset = _expanded_reset  # type: ignore[method-assign]
    World._ecosystem_expansion_installed = True

    # Apply the richer defaults to the existing world created by main.py.
    _configure_expanded_defaults(getattr(_ORIGINALS.get("world") , "__self__", None)) if False else None
