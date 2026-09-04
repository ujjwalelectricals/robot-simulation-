from __future__ import annotations

"""Evolve artificial-life core: dependency-free, headless, deterministic when seeded.

The robot is intentionally not told that it is inside a simulation. It receives only
local sensory observations and internal body drives. Its 'dog-like' brain is a
behavioral architecture inspired by animal learning: drives, attention, associative
conditioning, curiosity, working/episodic memory, fear/approach, and reward learning.
"""

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

WORLD_W, WORLD_H = 1000, 680
MAX_HEALTH, MAX_ENERGY = 100.0, 100.0
ACTIONS = ("forward", "left", "right", "back", "rest", "eat")
ANGLE_RAYS = (-0.8, -0.4, 0.0, 0.4, 0.8)


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def wrap_angle(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


@dataclass
class Genome:
    speed: float = 2.1
    turn: float = 0.24
    vision: float = 110.0
    efficiency: float = 1.0
    curiosity: float = 0.35
    boldness: float = 0.35
    sociability: float = 0.35
    memory_capacity: int = 48
    learning_rate: float = 0.16
    discount: float = 0.92
    exploration: float = 0.30
    fear_sensitivity: float = 0.65

    def mutate(self, rng: random.Random, rate: float) -> "Genome":
        def m(x: float, sigma: float, lo: float, hi: float) -> float:
            return clamp(x + rng.gauss(0, sigma), lo, hi) if rng.random() < rate else x
        return Genome(
            speed=m(self.speed, 0.15, 0.8, 4.0),
            turn=m(self.turn, 0.025, 0.08, 0.6),
            vision=m(self.vision, 8.0, 45, 180),
            efficiency=m(self.efficiency, 0.07, 0.55, 1.5),
            curiosity=m(self.curiosity, 0.06, 0, 1),
            boldness=m(self.boldness, 0.07, 0, 1),
            sociability=m(self.sociability, 0.07, 0, 1),
            memory_capacity=max(16, min(96, int(round(m(float(self.memory_capacity), 5, 16, 96))))),
            learning_rate=m(self.learning_rate, 0.025, 0.03, 0.4),
            discount=m(self.discount, 0.02, 0.70, 0.995),
            exploration=m(self.exploration, 0.035, 0.02, 0.85),
            fear_sensitivity=m(self.fear_sensitivity, 0.07, 0, 1),
        )


@dataclass
class Thing:
    x: float
    y: float
    amount: float = 1.0
    alive: bool = True


@dataclass
class Food(Thing):
    amount: float = 32.0


@dataclass
class Water(Thing):
    amount: float = 25.0


@dataclass
class Hazard(Thing):
    radius: float = 18.0
    damage: float = 7.0


@dataclass
class Shelter(Thing):
    radius: float = 30.0


@dataclass
class Predator:
    x: float
    y: float
    angle: float = 0.0
    speed: float = 1.45
    damage: float = 11.0
    alive: bool = True

    def step(self, world: "World") -> None:
        target = world.nearest_robot(self.x, self.y)
        if target:
            self.angle = math.atan2(target.y - self.y, target.x - self.x)
        nx = self.x + math.cos(self.angle) * self.speed
        ny = self.y + math.sin(self.angle) * self.speed
        if nx < 12 or nx > world.width - 12:
            self.angle = math.pi - self.angle
        if ny < 12 or ny > world.height - 12:
            self.angle = -self.angle
        self.x = clamp(nx, 12, world.width - 12)
        self.y = clamp(ny, 12, world.height - 12)


@dataclass
class Memory:
    state: str
    outcome: float
    novelty: float
    tick: int


class AnimalBrain:
    """Compact animal-learning architecture built on tabular value learning.

    It is not a claim of biological equivalence. The goal is emergent behavior from
    internal drives + limited senses + associative learning + memory.
    """

    def __init__(self, genome: Genome, rng: random.Random, q: Optional[Dict[str, List[float]]] = None):
        self.alpha = genome.learning_rate
        self.gamma = genome.discount
        self.epsilon = genome.exploration
        self.q: Dict[str, List[float]] = q if q is not None else {}
        self.rng = rng
        self.working: List[str] = []
        self.episodic: List[Memory] = []
        self.valence = 0.0
        self.stress = 0.0
        self.confidence = 0.2
        self.last_state: Optional[str] = None
        self.last_action: Optional[int] = None
        self.last_reward: float = 0.0

    def values(self, state: str) -> List[float]:
        return self.q.setdefault(state, [0.0] * len(ACTIONS))

    def choose(self, state: str, drive_bias: List[float]) -> int:
        vals = self.values(state)
        adjusted = [v + drive_bias[i] for i, v in enumerate(vals)]
        temperature = 0.35 + self.stress * 0.55
        if self.rng.random() < self.epsilon:
            return self.rng.randrange(len(ACTIONS))
        best = max(adjusted)
        tied = [i for i, v in enumerate(adjusted) if abs(v - best) < 1e-9]
        if temperature > 0.7 and self.rng.random() < min(0.5, temperature - 0.5):
            return self.rng.randrange(len(ACTIONS))
        return self.rng.choice(tied)

    def learn(self, state: str, action: int, reward: float, next_state: str) -> None:
        vals = self.values(state)
        target = reward + self.gamma * max(self.values(next_state))
        vals[action] += self.alpha * (target - vals[action])
        self.valence = clamp(self.valence * 0.92 + reward * 0.08, -1, 1)
        self.stress = clamp(self.stress * 0.97 + max(0, -reward) * 0.015, 0, 1)
        if abs(reward) > 2.0:
            self.episodic.append(Memory(state, reward, min(1.0, abs(reward) / 12), 0))
            if len(self.episodic) > 96:
                self.episodic.pop(0)
        self.confidence = clamp(self.confidence + (0.01 if reward > 0 else -0.008), 0.02, 0.98)

    def remember_state(self, state: str, tick: int, capacity: int) -> None:
        self.working.append(state)
        if len(self.working) > 8:
            self.working.pop(0)
        for memory in self.episodic[-8:]:
            memory.tick = tick
        if len(self.episodic) > capacity:
            del self.episodic[:-capacity]

    def decay(self) -> None:
        self.epsilon = max(0.03, self.epsilon * 0.9985)
        self.stress *= 0.985

    def summary(self) -> dict:
        return {
            "known_states": len(self.q),
            "working_memory": len(self.working),
            "episodic_memory": len(self.episodic),
            "confidence": round(self.confidence, 3),
            "stress": round(self.stress, 3),
            "valence": round(self.valence, 3),
            "exploration": round(self.epsilon, 3),
        }


@dataclass
class Robot:
    id: int
    x: float
    y: float
    angle: float
    genome: Genome
    brain: AnimalBrain
    generation: int
    health: float = MAX_HEALTH
    energy: float = MAX_ENERGY
    hydration: float = MAX_ENERGY
    age: int = 0
    fitness: float = 0.0
    food_eaten: int = 0
    water_found: int = 0
    offspring: int = 0
    damage_taken: float = 0.0
    alive: bool = True
    sleep: float = 0.0
    recent_reward: float = 0.0
    kill_reason: str = ""
    social_contact: int = 0

    def drives(self) -> Tuple[float, float, float, float, float]:
        hunger = 1 - self.energy / 100
        thirst = 1 - self.hydration / 100
        fatigue = clamp(self.age / 1800, 0, 1) * 0.5 + self.sleep
        fear = self.brain.stress * self.genome.fear_sensitivity
        curiosity = self.genome.curiosity * (1 - fear * 0.6)
        return hunger, thirst, fatigue, fear, curiosity

    def raycast(self, world: "World", angle: float) -> Tuple[int, float]:
        step = 7.0
        length = self.genome.vision
        for i in range(1, max(2, int(length / step)) + 1):
            d = i * step
            rx = self.x + math.cos(angle) * d
            ry = self.y + math.sin(angle) * d
            if rx < 3 or rx > world.width - 3 or ry < 3 or ry > world.height - 3:
                return 4, d / length
            for f in world.food:
                if f.alive and dist(rx, ry, f.x, f.y) < 8:
                    return 1, d / length
            for w in world.water:
                if w.alive and dist(rx, ry, w.x, w.y) < 9:
                    return 5, d / length
            for h in world.hazards:
                if dist(rx, ry, h.x, h.y) <= h.radius:
                    return 2, d / length
            for p in world.predators:
                if p.alive and dist(rx, ry, p.x, p.y) < 12:
                    return 3, d / length
        return 0, 1.0

    def observe(self, world: "World") -> Tuple[str, List[int]]:
        codes: List[int] = []
        for offset in ANGLE_RAYS:
            code, _ = self.raycast(world, self.angle + offset)
            codes.append(code)
        hunger, thirst, fatigue, fear, curiosity = self.drives()
        bins = lambda v: 0 if v < 0.33 else 1 if v < 0.66 else 2
        social = 0
        nearest = world.nearest_robot(self.x, self.y, exclude=self)
        if nearest:
            d = dist(self.x, self.y, nearest.x, nearest.y)
            social = 1 if d < 75 else 0
        state = "".join(map(str, codes)) + f"|h{bins(hunger)}t{bins(thirst)}f{bins(fatigue)}r{bins(fear)}c{bins(curiosity)}s{social}"
        return state, codes

    def drive_bias(self, codes: List[int]) -> List[float]:
        hunger, thirst, fatigue, fear, curiosity = self.drives()
        food_ahead = 1 if codes[2] == 1 else 0
        water_ahead = 1 if codes[2] == 5 else 0
        danger_left = 1 if codes[1] in (2, 3, 4) else 0
        danger_right = 1 if codes[3] in (2, 3, 4) else 0
        front_danger = 1 if codes[2] in (2, 3, 4) else 0
        bias = [0.0] * len(ACTIONS)
        bias[0] += hunger * 0.35 * food_ahead + thirst * 0.25 * water_ahead + curiosity * 0.05
        bias[1] += danger_right * fear * 1.1 - danger_left * fear * 0.5
        bias[2] += danger_left * fear * 1.1 - danger_right * fear * 0.5
        bias[3] += front_danger * fear * 0.8
        bias[4] += fatigue * 0.45
        bias[5] += hunger * food_ahead * 1.0
        if fear > 0.7:
            bias[3] += 0.3
        return bias

    def step(self, world: "World") -> float:
        if not self.alive:
            return 0.0
        state, codes = self.observe(world)
        action = self.brain.choose(state, self.drive_bias(codes))
        reward = -0.015
        speed = self.genome.speed
        if action == 1:
            self.angle = wrap_angle(self.angle - self.genome.turn)
        elif action == 2:
            self.angle = wrap_angle(self.angle + self.genome.turn)
        elif action == 3:
            speed *= 0.55
        elif action == 4:
            speed = 0.0
            self.sleep = clamp(self.sleep + 0.012, 0, 1)
            self.energy = clamp(self.energy + 0.03, 0, 100)
        else:
            self.sleep *= 0.96

        nx = self.x + math.cos(self.angle) * speed
        ny = self.y + math.sin(self.angle) * speed
        if nx < 8 or nx > world.width - 8 or ny < 8 or ny > world.height - 8:
            reward -= 1.2
            self.angle = wrap_angle(self.angle + math.pi * 0.65)
        else:
            self.x, self.y = nx, ny

        self.energy = clamp(self.energy - (0.055 * speed / self.genome.efficiency + 0.018), 0, 100)
        self.hydration = clamp(self.hydration - 0.024, 0, 100)
        self.sleep = max(0, self.sleep - 0.004)
        if self.energy < 18:
            reward -= 0.18
        if self.hydration < 18:
            reward -= 0.18

        f = world.food_at(self.x, self.y, 14)
        if f:
            f.alive = False
            self.energy = clamp(self.energy + f.amount, 0, 100)
            self.food_eaten += 1
            reward += 12.0

        w = world.water_at(self.x, self.y, 15)
        if w:
            w.alive = False
            self.hydration = clamp(self.hydration + w.amount, 0, 100)
            self.water_found += 1
            reward += 8.0

        for h in world.hazards:
            if dist(self.x, self.y, h.x, h.y) < h.radius + 8:
                self.health = clamp(self.health - h.damage, 0, 100)
                self.damage_taken += h.damage
                reward -= 11.0 * (0.8 + self.genome.fear_sensitivity * 0.5)

        for p in world.predators:
            if p.alive and dist(self.x, self.y, p.x, p.y) < 15:
                self.health = clamp(self.health - p.damage, 0, 100)
                self.damage_taken += p.damage
                reward -= 16.0

        nearest = world.nearest_robot(self.x, self.y, exclude=self)
        if nearest and dist(self.x, self.y, nearest.x, nearest.y) < 24:
            self.social_contact += 1
            reward += 0.02 * self.genome.sociability

        # Persistent environmental pressure + small survival reward.
        reward += 0.055
        if self.energy < 5 or self.hydration < 5:
            self.health -= 1.5
            reward -= 0.7
        self.age += 1
        self.fitness += reward
        self.recent_reward = reward

        next_state, _ = self.observe(world)
        self.brain.learn(state, action, reward, next_state)
        self.brain.remember_state(state, world.tick, self.genome.memory_capacity)
        self.brain.decay()

        if self.health <= 0:
            self.alive = False
            self.kill_reason = "damage/starvation"
        elif self.age >= world.max_age:
            self.alive = False
            self.kill_reason = "old age"
        return reward

    def genome_summary(self) -> dict:
        return self.genome.__dict__.copy()


class World:
    def __init__(self, width: int = WORLD_W, height: int = WORLD_H, seed: int = 7):
        self.width, self.height = width, height
        self.seed = seed
        self.rng = random.Random(seed)
        self.max_age = 1800
        self.population: List[Robot] = []
        self.food: List[Food] = []
        self.water: List[Water] = []
        self.hazards: List[Hazard] = []
        self.shelters: List[Shelter] = []
        self.predators: List[Predator] = []
        self.generation = 1
        self.tick = 0
        self.next_id = 1
        self.history: List[dict] = []
        self.experiment = {
            "population": 42,
            "food": 55,
            "water": 25,
            "hazards": 8,
            "predators": 2,
            "mutation": 0.15,
            "episode": 1500,
            "reproduction": True,
        }
        self.spawn_rate = {"food": 1.0, "water": 0.75}
        self.reset()

    def reset(self) -> None:
        self.population.clear(); self.food.clear(); self.water.clear(); self.hazards.clear(); self.shelters.clear(); self.predators.clear()
        self.generation = 1; self.tick = 0; self.next_id = 1; self.history.clear()
        self._spawn_environment()
        for _ in range(self.experiment["population"]):
            self.population.append(self.new_robot())

    def _spawn_environment(self) -> None:
        for _ in range(self.experiment["food"]): self.spawn_food()
        for _ in range(self.experiment["water"]): self.spawn_water()
        for _ in range(self.experiment["hazards"]):
            self.hazards.append(Hazard(self.rng.uniform(30, self.width - 30), self.rng.uniform(30, self.height - 30), radius=self.rng.uniform(14, 25)))
        for _ in range(self.experiment["predators"]):
            self.predators.append(Predator(self.rng.uniform(40, self.width - 40), self.rng.uniform(40, self.height - 40), angle=self.rng.uniform(-math.pi, math.pi)))
        for _ in range(5):
            self.shelters.append(Shelter(self.rng.uniform(40, self.width - 40), self.rng.uniform(40, self.height - 40)))

    def random_xy(self, margin: float = 25) -> Tuple[float, float]:
        return self.rng.uniform(margin, self.width - margin), self.rng.uniform(margin, self.height - margin)

    def spawn_food(self, x: Optional[float] = None, y: Optional[float] = None) -> None:
        if x is None or y is None: x, y = self.random_xy()
        self.food.append(Food(x, y))

    def spawn_water(self, x: Optional[float] = None, y: Optional[float] = None) -> None:
        if x is None or y is None: x, y = self.random_xy()
        self.water.append(Water(x, y))

    def spawn_hazard(self, x: Optional[float] = None, y: Optional[float] = None) -> None:
        if x is None or y is None: x, y = self.random_xy()
        self.hazards.append(Hazard(x, y, radius=self.rng.uniform(14, 26)))

    def spawn_predator(self, x: Optional[float] = None, y: Optional[float] = None) -> None:
        if x is None or y is None: x, y = self.random_xy()
        self.predators.append(Predator(x, y, angle=self.rng.uniform(-math.pi, math.pi)))

    def new_robot(self, genome: Optional[Genome] = None, q: Optional[Dict[str, List[float]]] = None) -> Robot:
        if genome is None:
            genome = Genome(
                speed=self.rng.uniform(1.3, 2.8), turn=self.rng.uniform(0.13, 0.34), vision=self.rng.uniform(70, 125),
                efficiency=self.rng.uniform(0.78, 1.18), curiosity=self.rng.uniform(0.1, 0.55), boldness=self.rng.uniform(0.1, 0.6),
                sociability=self.rng.uniform(0.05, 0.7), memory_capacity=self.rng.randint(28, 60), learning_rate=self.rng.uniform(0.1, 0.24),
                discount=self.rng.uniform(0.86, 0.97), exploration=self.rng.uniform(0.2, 0.5), fear_sensitivity=self.rng.uniform(0.4, 0.9),
            )
        x, y = self.random_xy()
        r = Robot(self.next_id, x, y, self.rng.uniform(-math.pi, math.pi), genome, AnimalBrain(genome, self.rng, q), self.generation)
        self.next_id += 1
        return r

    def nearest_robot(self, x: float, y: float, exclude: Optional[Robot] = None) -> Optional[Robot]:
        candidates = [r for r in self.population if r.alive and r is not exclude]
        return min(candidates, key=lambda r: dist(x, y, r.x, r.y), default=None)

    def food_at(self, x: float, y: float, radius: float) -> Optional[Food]:
        return next((f for f in self.food if f.alive and dist(x, y, f.x, f.y) <= radius), None)

    def water_at(self, x: float, y: float, radius: float) -> Optional[Water]:
        return next((w for w in self.water if w.alive and dist(x, y, w.x, w.y) <= radius), None)

    def step(self, amount: int = 1) -> None:
        for _ in range(max(1, amount)):
            self.tick += 1
            for p in self.predators:
                if p.alive: p.step(self)
            for r in list(self.population):
                if r.alive: r.step(self)
            self.food = [f for f in self.food if f.alive]
            self.water = [w for w in self.water if w.alive]
            while len(self.food) < self.experiment["food"] * self.spawn_rate["food"]:
                self.spawn_food()
            while len(self.water) < self.experiment["water"] * self.spawn_rate["water"]:
                self.spawn_water()
            if self.tick >= self.experiment["episode"] or self.alive_count() == 0:
                self.finish_generation()
                break

    def alive_count(self) -> int:
        return sum(r.alive for r in self.population)

    def finish_generation(self) -> None:
        ranked = sorted(self.population, key=lambda r: r.fitness, reverse=True)
        survivors = [r for r in ranked if r.alive]
        best = ranked[0] if ranked else None
        self.history.append({
            "generation": self.generation,
            "population": len(ranked),
            "survivors": len(survivors),
            "avg_fitness": round(sum(r.fitness for r in ranked) / max(1, len(ranked)), 3),
            "best_fitness": round(best.fitness, 3) if best else 0,
            "best_age": best.age if best else 0,
            "best_food": best.food_eaten if best else 0,
            "knowledge": max((len(r.brain.q) for r in ranked), default=0),
        })
        if len(self.history) > 500: self.history.pop(0)

        parents = ranked[:max(2, min(10, len(ranked)))]
        old_generation = self.generation
        self.generation += 1
        self.tick = 0
        new_population: List[Robot] = []
        target = int(self.experiment["population"])
        if not parents:
            for _ in range(target): new_population.append(self.new_robot())
        else:
            while len(new_population) < target:
                p = self.rng.choice(parents)
                g = p.genome.mutate(self.rng, self.experiment["mutation"])
                q = {k: list(v) for k, v in p.brain.q.items()}
                child = self.new_robot(g, q)
                child.generation = self.generation
                child.brain.epsilon = clamp(g.exploration + self.rng.uniform(-0.03, 0.04), 0.02, 0.8)
                p.offspring += 1
                new_population.append(child)
        self.population = new_population
        assert all(r.generation == self.generation for r in self.population) or old_generation < self.generation

    def save_snapshot(self, path: str) -> None:
        import json
        data = {
            "seed": self.seed, "generation": self.generation, "tick": self.tick,
            "experiment": self.experiment, "history": self.history[-100:],
            "robots": [{"id": r.id, "genome": r.genome.__dict__, "brain": r.brain.q, "fitness": r.fitness, "age": r.age, "food": r.food_eaten, "water": r.water_found} for r in self.population],
        }
        with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)

    def summary(self) -> dict:
        best = max(self.population, key=lambda r: r.fitness, default=None)
        return {
            "generation": self.generation, "tick": self.tick, "alive": self.alive_count(), "population": len(self.population),
            "best_fitness": round(best.fitness, 2) if best else 0,
            "avg_fitness": round(sum(r.fitness for r in self.population) / max(1, len(self.population)), 2),
            "best_age": best.age if best else 0,
            "best_food": best.food_eaten if best else 0,
            "known_states": max((len(r.brain.q) for r in self.population), default=0),
        }

    def run_generations(self, generations: int) -> List[dict]:
        target = self.generation + generations - 1
        while self.generation <= target:
            self.step(self.experiment["episode"])
        return self.history
