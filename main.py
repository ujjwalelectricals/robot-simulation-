from __future__ import annotations

import argparse
import json
import math
import random
import time
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import ttk
from typing import Dict, List, Optional, Tuple

# Evolve is intentionally standard-library-only. No external AI model is used.

WIDTH, HEIGHT = 900, 600
ROBOT_RADIUS = 8
MAX_HEALTH = 100.0
MAX_ENERGY = 100.0
MAX_AGE = 1800
VISION_RAYS = 5
VISION_RANGE = 90.0
ACTIONS = (-1, 0, 1)  # turn left, move/straight, turn right; brain outputs steering choices
STATE_BUCKETS = 3


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def angle_wrap(a: float) -> float:
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


@dataclass
class Genome:
    speed: float = 1.8
    turn_rate: float = 0.22
    vision: float = VISION_RANGE
    efficiency: float = 1.0
    curiosity: float = 0.18
    risk: float = 0.25
    learning_rate: float = 0.18
    discount: float = 0.92
    exploration: float = 0.32

    def clone_mutated(self, rng: random.Random, rate: float) -> "Genome":
        def mutate(x: float, scale: float, lo: float, hi: float) -> float:
            if rng.random() > rate:
                return x
            return clamp(x + rng.gauss(0, scale), lo, hi)

        return Genome(
            speed=mutate(self.speed, 0.18, 0.7, 3.0),
            turn_rate=mutate(self.turn_rate, 0.03, 0.08, 0.45),
            vision=mutate(self.vision, 7, 45, 150),
            efficiency=mutate(self.efficiency, 0.08, 0.65, 1.35),
            curiosity=mutate(self.curiosity, 0.08, 0.0, 0.9),
            risk=mutate(self.risk, 0.08, 0.0, 1.0),
            learning_rate=mutate(self.learning_rate, 0.03, 0.03, 0.45),
            discount=mutate(self.discount, 0.02, 0.75, 0.995),
            exploration=mutate(self.exploration, 0.04, 0.02, 0.8),
        )


@dataclass
class Food:
    x: float
    y: float
    energy: float = 35.0
    alive: bool = True


@dataclass
class Hazard:
    x: float
    y: float
    radius: float = 16.0
    damage: float = 3.5


@dataclass
class Predator:
    x: float
    y: float
    angle: float = 0.0
    speed: float = 1.25
    damage: float = 10.0

    def step(self, world: "World", rng: random.Random) -> None:
        target = world.nearest_robot(self.x, self.y)
        if target is not None:
            self.angle = math.atan2(target.y - self.y, target.x - self.x)
        else:
            self.angle += rng.uniform(-0.15, 0.15)
        nx = self.x + math.cos(self.angle) * self.speed
        ny = self.y + math.sin(self.angle) * self.speed
        if nx < 15 or nx > world.width - 15:
            self.angle = math.pi - self.angle
            nx = clamp(nx, 15, world.width - 15)
        if ny < 15 or ny > world.height - 15:
            self.angle = -self.angle
            ny = clamp(ny, 15, world.height - 15)
        self.x, self.y = nx, ny


class Brain:
    """Small tabular Q-learning brain; it only sees encoded observations."""

    def __init__(self, genome: Genome, rng: random.Random, q: Optional[Dict[str, List[float]]] = None):
        self.alpha = genome.learning_rate
        self.gamma = genome.discount
        self.epsilon = genome.exploration
        self.q: Dict[str, List[float]] = q if q is not None else {}

    def _values(self, state: str) -> List[float]:
        return self.q.setdefault(state, [0.0, 0.0, 0.0])

    def choose(self, state: str, rng: random.Random) -> int:
        values = self._values(state)
        if rng.random() < self.epsilon:
            return rng.randrange(len(ACTIONS))
        best = max(values)
        choices = [i for i, v in enumerate(values) if abs(v - best) < 1e-9]
        return rng.choice(choices)

    def learn(self, state: str, action: int, reward: float, next_state: str) -> None:
        values = self._values(state)
        next_best = max(self._values(next_state))
        values[action] += self.alpha * (reward + self.gamma * next_best - values[action])

    def decay_exploration(self, factor: float = 0.997) -> None:
        self.epsilon = max(0.02, self.epsilon * factor)


@dataclass
class Robot:
    id: int
    x: float
    y: float
    angle: float
    genome: Genome
    brain: Brain
    health: float = MAX_HEALTH
    energy: float = MAX_ENERGY
    age: int = 0
    fitness: float = 0.0
    food_eaten: int = 0
    damage_taken: float = 0.0
    steps_alive: int = 0
    generation: int = 0
    memory: List[Tuple[str, float]] = field(default_factory=list)
    alive: bool = True
    last_reward: float = 0.0
    state_before: Optional[str] = None
    action_before: Optional[int] = None

    def remember(self, state: str, reward: float) -> None:
        self.memory.append((state, reward))
        if len(self.memory) > 30:
            self.memory.pop(0)

    def local_senses(self, world: "World") -> List[int]:
        """Five rays: each is 0 nothing, 1 food, 2 danger, 3 wall."""
        result: List[int] = []
        half = VISION_RAYS // 2
        for i in range(VISION_RAYS):
            offset = (i - half) * 0.30
            ray_angle = self.angle + offset
            result.append(world.raycast(self.x, self.y, ray_angle, self.genome.vision))
        return result

    def state(self, world: "World") -> str:
        senses = self.local_senses(world)
        hunger = 0 if self.energy > 65 else 1 if self.energy > 30 else 2
        health = 0 if self.health > 70 else 1 if self.health > 35 else 2
        recent = 0
        if self.memory:
            avg = sum(r for _, r in self.memory[-5:]) / min(5, len(self.memory))
            recent = 0 if avg < -2 else 1 if avg < 2 else 2
        return "".join(map(str, senses)) + f"|h{hunger}|s{health}|m{recent}"

    def act(self, world: "World", rng: random.Random) -> float:
        state = self.state(world)
        action_idx = self.brain.choose(state, rng)
        turn = ACTIONS[action_idx] * self.genome.turn_rate
        self.angle = angle_wrap(self.angle + turn)
        speed_factor = 1.0 + (self.genome.curiosity * 0.12 if rng.random() < self.genome.curiosity else 0.0)
        nx = self.x + math.cos(self.angle) * self.genome.speed * speed_factor
        ny = self.y + math.sin(self.angle) * self.genome.speed * speed_factor

        reward = -0.03 * (1.2 / self.genome.efficiency)
        if nx < ROBOT_RADIUS or nx > world.width - ROBOT_RADIUS:
            reward -= 1.5
            self.angle = math.pi - self.angle
            nx = clamp(nx, ROBOT_RADIUS, world.width - ROBOT_RADIUS)
        if ny < ROBOT_RADIUS or ny > world.height - ROBOT_RADIUS:
            reward -= 1.5
            self.angle = -self.angle
            ny = clamp(ny, ROBOT_RADIUS, world.height - ROBOT_RADIUS)
        self.x, self.y = nx, ny

        old_energy = self.energy
        self.energy = clamp(self.energy - (0.08 * self.genome.speed / self.genome.efficiency), 0, MAX_ENERGY)
        if self.energy < old_energy:
            self.health = clamp(self.health - 0.004, 0, MAX_HEALTH)

        # Discover and eat food.
        food = world.food_at(self.x, self.y, 13)
        if food is not None:
            self.energy = clamp(self.energy + food.energy, 0, MAX_ENERGY)
            food.alive = False
            self.food_eaten += 1
            reward += 10.0

        # Hazards punish risk-taking immediately.
        for hazard in world.hazards:
            if dist((self.x, self.y), (hazard.x, hazard.y)) < hazard.radius + ROBOT_RADIUS:
                self.health = clamp(self.health - hazard.damage, 0, MAX_HEALTH)
                self.damage_taken += hazard.damage
                reward -= 8.0 * (1.0 + self.genome.risk)

        # Predators punish proximity.
        for predator in world.predators:
            d = dist((self.x, self.y), (predator.x, predator.y))
            if d < 12:
                self.health = clamp(self.health - predator.damage, 0, MAX_HEALTH)
                self.damage_taken += predator.damage
                reward -= 12.0

        # Survival itself is a small reward; wasting energy is a cost.
        reward += 0.08
        self.fitness += reward
        self.last_reward = reward
        self.steps_alive += 1
        self.age += 1

        next_state = self.state(world)
        self.brain.learn(state, action_idx, reward, next_state)
        self.remember(state, reward)
        if len(self.memory) % 20 == 0:
            self.brain.decay_exploration()

        if self.energy <= 0:
            self.health -= 1.8
        if self.age > MAX_AGE:
            self.health = 0
        if self.health <= 0:
            self.alive = False
            self.fitness -= 5.0
        return reward


class World:
    def __init__(self, width: int = WIDTH, height: int = HEIGHT, seed: Optional[int] = None):
        self.width, self.height = width, height
        self.rng = random.Random(seed)
        self.seed = seed
        self.generation = 1
        self.next_robot_id = 1
        self.population: List[Robot] = []
        self.food: List[Food] = []
        self.hazards: List[Hazard] = []
        self.predators: List[Predator] = []
        self.history: List[dict] = []
        self.replay: List[list] = []
        self.tick = 0
        self.experiment = {
            "population": 40,
            "food": 45,
            "hazards": 7,
            "predators": 2,
            "mutation": 0.16,
            "episode": 1400,
        }
        self.reset()

    def reset(self) -> None:
        self.population.clear()
        self.food.clear()
        self.hazards.clear()
        self.predators.clear()
        self.generation = 1
        self.next_robot_id = 1
        self.tick = 0
        self.history.clear()
        self.replay.clear()
        self._spawn_environment()
        for _ in range(self.experiment["population"]):
            self.population.append(self._new_robot())

    def _spawn_environment(self) -> None:
        for _ in range(self.experiment["food"]):
            self.food.append(Food(self.rng.uniform(30, self.width - 30), self.rng.uniform(30, self.height - 30)))
        for _ in range(self.experiment["hazards"]):
            self.hazards.append(Hazard(self.rng.uniform(40, self.width - 40), self.rng.uniform(40, self.height - 40), self.rng.uniform(12, 20)))
        for _ in range(self.experiment["predators"]):
            self.predators.append(Predator(self.rng.uniform(30, self.width - 30), self.rng.uniform(30, self.height - 30)))

    def _new_robot(self, genome: Optional[Genome] = None, brain_q: Optional[Dict[str, List[float]]] = None) -> Robot:
        g = genome or Genome(
            speed=self.rng.uniform(1.3, 2.2),
            turn_rate=self.rng.uniform(0.15, 0.3),
            vision=self.rng.uniform(65, 110),
            efficiency=self.rng.uniform(0.8, 1.2),
            curiosity=self.rng.uniform(0.05, 0.4),
            risk=self.rng.uniform(0.05, 0.4),
            learning_rate=self.rng.uniform(0.12, 0.24),
            discount=self.rng.uniform(0.88, 0.97),
            exploration=self.rng.uniform(0.2, 0.5),
        )
        x, y = self.rng.uniform(30, self.width - 30), self.rng.uniform(30, self.height - 30)
        robot = Robot(
            id=self.next_robot_id,
            x=x,
            y=y,
            angle=self.rng.uniform(-math.pi, math.pi),
            genome=g,
            brain=Brain(g, self.rng, brain_q),
            generation=self.generation,
        )
        self.next_robot_id += 1
        return robot

    def nearest_robot(self, x: float, y: float) -> Optional[Robot]:
        alive = [r for r in self.population if r.alive]
        return min(alive, key=lambda r: dist((x, y), (r.x, r.y)), default=None)

    def food_at(self, x: float, y: float, radius: float) -> Optional[Food]:
        for item in self.food:
            if item.alive and dist((x, y), (item.x, item.y)) <= radius:
                return item
        return None

    def raycast(self, x: float, y: float, angle: float, length: float) -> int:
        steps = max(3, int(length / 7))
        for i in range(1, steps + 1):
            t = i / steps
            rx, ry = x + math.cos(angle) * length * t, y + math.sin(angle) * length * t
            if rx < 4 or rx > self.width - 4 or ry < 4 or ry > self.height - 4:
                return 3
            for hazard in self.hazards:
                if dist((rx, ry), (hazard.x, hazard.y)) <= hazard.radius:
                    return 2
            if self.food_at(rx, ry, 7):
                return 1
            for predator in self.predators:
                if dist((rx, ry), (predator.x, predator.y)) < 10:
                    return 2
        return 0

    def alive_count(self) -> int:
        return sum(1 for r in self.population if r.alive)

    def step(self, amount: int = 1, record: bool = True) -> None:
        for _ in range(amount):
            self.tick += 1
            for predator in self.predators:
                predator.step(self, self.rng)
            for robot in list(self.population):
                if robot.alive:
                    robot.act(self, self.rng)
            self.food = [f for f in self.food if f.alive]
            # Respawn resources so that survival is a continuing problem.
            while len(self.food) < self.experiment["food"]:
                self.food.append(Food(self.rng.uniform(25, self.width - 25), self.rng.uniform(25, self.height - 25)))

            if record and (self.tick % 8 == 0):
                self.replay.append(self.snapshot())
                if len(self.replay) > 450:
                    self.replay.pop(0)

            if self.tick >= self.experiment["episode"] or self.alive_count() == 0:
                self.finish_generation()
                break

    def snapshot(self) -> list:
        return [[round(r.x, 1), round(r.y, 1), r.alive, r.generation] for r in self.population]

    def finish_generation(self) -> None:
        survivors = sorted(self.population, key=lambda r: r.fitness, reverse=True)
        alive = [r for r in survivors if r.alive]
        average_fitness = sum(r.fitness for r in survivors) / max(1, len(survivors))
        average_age = sum(r.age for r in survivors) / max(1, len(survivors))
        best = survivors[0] if survivors else None
        self.history.append({
            "generation": self.generation,
            "population": len(survivors),
            "survivors": len(alive),
            "average_fitness": round(average_fitness, 3),
            "average_age": round(average_age, 2),
            "best_fitness": round(best.fitness, 3) if best else 0,
            "best_food": best.food_eaten if best else 0,
        })
        if len(self.history) > 500:
            self.history.pop(0)
        self.generation += 1
        self.tick = 0

        # Elite survivors seed the next generation. Their learned Q-table is copied;
        # mutation changes the physical/behavioral parameters.
        parents = survivors[: max(2, min(10, len(survivors)))]
        new_population: List[Robot] = []
        target = self.experiment["population"]
        while len(new_population) < target:
            parent = self.rng.choice(parents) if parents else None
            if parent is None:
                new_population.append(self._new_robot())
                continue
            genome = parent.genome.clone_mutated(self.rng, self.experiment["mutation"])
            qcopy = {k: list(v) for k, v in parent.brain.q.items()}
            child = self._new_robot(genome, qcopy)
            child.generation = self.generation
            # Small inherited learning noise prevents cloning identical minds forever.
            child.brain.epsilon = clamp(genome.exploration + self.rng.uniform(-0.04, 0.04), 0.02, 0.8)
            new_population.append(child)
        self.population = new_population

    def run_headless(self, generations: int) -> List[dict]:
        while self.generation <= generations:
            self.step(self.experiment["episode"], record=False)
        return self.history


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("EVOLVE — Artificial Life Laboratory")
        root.geometry("1240x760")
        root.minsize(1000, 650)
        self.world = World()
        self.running = True
        self.fast = False
        self.speed = 1
        self._build()
        self._loop()

    def _build(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", padding=7)
        style.configure("TLabel", background="#111820", foreground="#dce8f0")
        style.configure("Title.TLabel", font=("Segoe UI", 19, "bold"), foreground="#ffffff")
        style.configure("Metric.TLabel", font=("Consolas", 11), foreground="#b9d8e8")
        outer = tk.Frame(self.root, bg="#0b1117")
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg="#111820", height=64)
        header.pack(fill="x")
        ttk.Label(header, text="EVOLVE", style="Title.TLabel").pack(side="left", padx=18, pady=15)
        ttk.Label(header, text="2D ARTIFICIAL LIFE LAB", background="#111820", foreground="#7ea2b5", font=("Segoe UI", 10)).pack(side="left")
        self.status = ttk.Label(header, text="RUNNING", background="#111820", foreground="#7bd89b")
        self.status.pack(side="right", padx=18)

        body = tk.Frame(outer, bg="#0b1117")
        body.pack(fill="both", expand=True, padx=12, pady=12)
        left = tk.Frame(body, bg="#0b1117")
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(body, bg="#111820", width=300)
        right.pack(side="right", fill="y", padx=(12, 0))

        self.canvas = tk.Canvas(left, width=900, height=600, bg="#0f1820", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self.draw())

        controls = tk.Frame(right, bg="#111820")
        controls.pack(fill="x", padx=14, pady=14)
        for text, cmd in [("PAUSE / RESUME", self.toggle), ("NEXT GENERATION", self.next_generation), ("RESET", self.reset), ("FAST MODE", self.toggle_fast)]:
            ttk.Button(controls, text=text, command=cmd).pack(fill="x", pady=4)

        self.metrics = []
        for label in ["Generation", "Alive", "Tick", "Best fitness", "Avg fitness", "Food eaten", "Learning ε", "Best age"]:
            row = tk.Frame(right, bg="#111820")
            row.pack(fill="x", padx=14, pady=3)
            ttk.Label(row, text=label, background="#111820", foreground="#8199a8").pack(side="left")
            value = ttk.Label(row, text="—", style="Metric.TLabel", background="#111820")
            value.pack(side="right")
            self.metrics.append(value)

        tk.Frame(right, bg="#25333d", height=1).pack(fill="x", padx=14, pady=15)
        ttk.Label(right, text="EXPERIMENT", background="#111820", foreground="#ffffff", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14)
        self.vars = {}
        for key in ["population", "food", "hazards", "predators", "mutation", "episode"]:
            row = tk.Frame(right, bg="#111820")
            row.pack(fill="x", padx=14, pady=4)
            ttk.Label(row, text=key, background="#111820", foreground="#8199a8").pack(side="left")
            var = tk.StringVar(value=str(self.world.experiment[key]))
            entry = ttk.Entry(row, textvariable=var, width=10)
            entry.pack(side="right")
            self.vars[key] = var
        ttk.Button(right, text="APPLY EXPERIMENT", command=self.apply_settings).pack(fill="x", padx=14, pady=8)
        ttk.Label(right, text="Space: pause • F: fast • N: next • R: reset", background="#111820", foreground="#647b88", wraplength=250).pack(anchor="w", padx=14, pady=16)
        self.root.bind("<space>", lambda _e: self.toggle())
        self.root.bind("<f>", lambda _e: self.toggle_fast())
        self.root.bind("<n>", lambda _e: self.next_generation())
        self.root.bind("<r>", lambda _e: self.reset())
        self.draw()

    def toggle(self) -> None:
        self.running = not self.running
        self.status.configure(text="RUNNING" if self.running else "PAUSED")

    def toggle_fast(self) -> None:
        self.fast = not self.fast

    def reset(self) -> None:
        self.world.reset()
        self.running = True
        self.status.configure(text="RUNNING")

    def apply_settings(self) -> None:
        for key, var in self.vars.items():
            try:
                value = float(var.get()) if key == "mutation" else int(var.get())
                if key == "population": value = int(clamp(value, 2, 5000))
                if key == "food": value = int(clamp(value, 5, 500))
                if key == "hazards": value = int(clamp(value, 0, 100))
                if key == "predators": value = int(clamp(value, 0, 50))
                if key == "mutation": value = clamp(value, 0.0, 1.0)
                if key == "episode": value = int(clamp(value, 100, 100000))
                self.world.experiment[key] = value
            except ValueError:
                pass
        self.world.reset()

    def next_generation(self) -> None:
        while self.world.generation == self.world.history[-1]["generation"] if self.world.history else True:
            self.world.step(self.world.experiment["episode"], record=False)
            if self.world.history:
                break
        self.draw()

    def _loop(self) -> None:
        if self.running:
            self.world.step(12 if self.fast else 2)
            self.draw()
        self.root.after(24 if self.fast else 40, self._loop)

    def draw(self) -> None:
        self.canvas.delete("all")
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        sx, sy = cw / self.world.width, ch / self.world.height
        # Grid
        for x in range(0, self.world.width, 50):
            self.canvas.create_line(x * sx, 0, x * sx, ch, fill="#17252e")
        for y in range(0, self.world.height, 50):
            self.canvas.create_line(0, y * sy, cw, y * sy, fill="#17252e")

        # hazards
        for h in self.world.hazards:
            x, y, r = h.x * sx, h.y * sy, h.radius * min(sx, sy)
            self.canvas.create_oval(x-r, y-r, x+r, y+r, outline="#6b3946", fill="#25161b")
        # food
        for f in self.world.food:
            if not f.alive: continue
            x, y = f.x * sx, f.y * sy
            self.canvas.create_oval(x-4, y-4, x+4, y+4, outline="#8ee0a6", fill="#6bcf86")
        # predators
        for p in self.world.predators:
            x, y = p.x * sx, p.y * sy
            self.canvas.create_oval(x-7, y-7, x+7, y+7, outline="#ff8c6b", fill="#7a3429")

        # robots
        for r in self.world.population:
            if not r.alive:
                continue
            x, y = r.x * sx, r.y * sy
            rr = ROBOT_RADIUS * min(sx, sy)
            fill = "#78c9ff" if r.fitness >= 0 else "#b77cff"
            self.canvas.create_oval(x-rr, y-rr, x+rr, y+rr, outline="#d7edf9", fill=fill)
            self.canvas.create_line(x, y, x + math.cos(r.angle)*14*sx, y + math.sin(r.angle)*14*sy, fill="#f4f7fa")

        h = self.world.history[-1] if self.world.history else None
        vals = [
            self.world.generation,
            self.world.alive_count(),
            self.world.tick,
            h["best_fitness"] if h else round(max((r.fitness for r in self.world.population), default=0), 2),
            h["average_fitness"] if h else round(sum(r.fitness for r in self.world.population)/max(1,len(self.world.population)), 2),
            sum(r.food_eaten for r in self.world.population),
            round(self.world.population[0].brain.epsilon, 3) if self.world.population else 0,
            h["average_age"] if h else round(sum(r.age for r in self.world.population)/max(1,len(self.world.population)), 1),
        ]
        for widget, value in zip(self.metrics, vals):
            widget.configure(text=str(value))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evolve 2D artificial-life robot simulator")
    parser.add_argument("--headless", action="store_true", help="run without GUI")
    parser.add_argument("--generations", type=int, default=10)
    parser.add_argument("--population", type=int, default=40)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    world = World(seed=args.seed)
    world.experiment["population"] = clamp(args.population, 2, 5000)
    world.reset()
    if args.headless:
        history = world.run_headless(args.generations)
        print(json.dumps(history[-5:], indent=2))
        return
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
