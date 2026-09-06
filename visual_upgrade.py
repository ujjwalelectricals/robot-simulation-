"""Lightweight visual pass for the EVOLVE Tkinter laboratory.

Presentation-only patch: it adds readable ecosystem cues without changing the
simulation rules or replacing the existing renderer.
"""
from __future__ import annotations

import math
import time

import main

_ORIGINAL_DRAW = None
_INSTALLED = False


def _enhanced_draw(self) -> None:
    _ORIGINAL_DRAW(self)
    canvas = self.canvas
    width = max(1, canvas.winfo_width())
    height = max(1, canvas.winfo_height())
    world = self.world

    # Thin arena frame gives the simulation a stronger visual boundary.
    canvas.create_rectangle(2, 2, width - 2, height - 2, outline="#244555", width=2, tags=("fx",))

    # Predator-specific visual language: a larger threat ring makes the new
    # detection radii legible without changing the simulation itself.
    for predator in world.predators:
        x, y = self.world_to_canvas(predator.x, predator.y)
        kind = getattr(predator, "kind", "stalker")
        radius = {"sprinter": 20, "pack_leader": 25, "scout": 22, "stalker": 18}.get(kind, 18)
        canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline="#5e2634", dash=(2, 4), tags=("fx",))
        canvas.create_text(x, y + radius + 8, text=kind.replace("_", " ").upper(), fill="#8fa5b0", font=("Segoe UI", 6), tags=("fx",))

    # Shelters get an inner ring so safe zones read clearly at a glance.
    for shelter in world.shelters:
        x, y = self.world_to_canvas(shelter.x, shelter.y)
        radius = shelter.radius / world.width * width
        inner = radius * 0.58
        canvas.create_oval(x - inner, y - inner, x + inner, y + inner, outline="#315968", dash=(2, 3), tags=("fx",))

    # Selected robot gets a small facing wedge and status marker.
    robot = self.selected()
    if robot:
        x, y = self.world_to_canvas(robot.x, robot.y)
        direction = math.radians(25)
        reach = 24.0 + robot.genome.speed * 3.0
        left_x, left_y = self.world_to_canvas(
            robot.x + math.cos(robot.angle - direction) * reach,
            robot.y + math.sin(robot.angle - direction) * reach,
        )
        right_x, right_y = self.world_to_canvas(
            robot.x + math.cos(robot.angle + direction) * reach,
            robot.y + math.sin(robot.angle + direction) * reach,
        )
        canvas.create_polygon(x, y, left_x, left_y, right_x, right_y, outline="#6be0b4", fill="", tags=("fx",))

    # Minimal live HUD. It is intentionally tiny so the simulation remains the
    # visual focus.
    night = world.night_factor()
    mode = "NIGHT" if night > 0.65 else ("DAWN/DUSK" if night > 0.35 else "DAY")
    alive = world.alive_count()
    hud = f"G{world.generation}  •  {mode}  •  {alive}/{len(world.population)} ALIVE  •  {len(world.predators)} PREDATORS"
    canvas.create_text(width - 12, 12, text=hud, anchor="ne", fill="#8ba4b2", font=("Segoe UI", 8), tags=("fx",))


def install() -> None:
    global _ORIGINAL_DRAW, _INSTALLED
    if _INSTALLED:
        return
    _ORIGINAL_DRAW = main.EvolveApp.draw
    main.EvolveApp.draw = _enhanced_draw
    _INSTALLED = True
