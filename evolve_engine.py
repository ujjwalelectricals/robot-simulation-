from __future__ import annotations

"""EVOLVE canonical artificial-life engine.

The robot receives only local sensory observations and internal body drives.
It is not given hidden simulation metadata or a map. The brain is dog-inspired
rather than a literal biological reconstruction of a canine brain.

Standard-library only. Designed for deterministic headless experiments and a
Tkinter laboratory UI.
"""

import json
import math
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

WORLD_W = 1000
WORLD_H = 680
MAX_HEALTH = 100.0
MAX_ENERGY = 100.0
MAX_HYDRATION = 100.0
MAX_AGE = 2600
DAY_LENGTH = 900.0
ACTIONS = ("forward", "left", "right", "back", "rest", "eat", "drink", "approach", "flee")
SENSE_CODES = {0: "nothing", 1: "food", 2: "hazard", 3: "predator", 4: "wall", 5: "water", 6: "robot", 7: "shelter", 8: "scent_food", 9: "scent_danger"}


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def distance(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def wrap_angle(angle: float) -> float:
    return (angle + math.pi) % (2 * math.pi) - math.pi


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


@dataclass
class RayGene:
    angle: float
    length: float

    def mutate(self, rng: random.Random, rate: float) -> "RayGene":
        angle = self.angle + rng.gauss(0, 0.08) if rng.random() < rate else self.angle
        length = self.length + rng.gauss(0, 8.0) if rng.random() < rate else self.length
        return RayGene(clamp(angle, -math.pi, math.pi), clamp(length, 35.0, 220.0))


@dataclass
class Genome:
    speed: float = 2.1
    turn: float = 0.24
    body_size: float = 1.0
    efficiency: float = 1.0
    curiosity: float = 0.35
    boldness: float = 0.35
    sociability: float = 0.35
    attachment: float = 0.35
    patience: float = 0.35
    memory_capacity: int = 48
    learning_rate: float = 0.16
    discount: float = 0.92
    exploration: float = 0.30
    fear_sensitivity: float = 0.65
    rays: List[RayGene] = field(default_factory=lambda: [
        RayGene(-1.0, 95.0), RayGene(-0.5, 115.0), RayGene(-0.25, 130.0),
        RayGene(0.0, 145.0), RayGene(0.25, 130.0), RayGene(0.5, 115.0), RayGene(1.0, 95.0)
    ])

    def clone(self) -> "Genome":
        data = asdict(self)
        data["rays"] = [RayGene(**ray) if isinstance(ray, dict) else RayGene(ray.angle, ray.length) for ray in data["rays"]]
        return Genome(**data)

    def mutate(self, rng: random.Random, rate: float) -> "Genome":
        def m(value: float, sigma: float, lo: float, hi: float) -> float:
            return clamp(value + rng.gauss(0, sigma), lo, hi) if rng.random() < rate else value
        rays = [ray.mutate(rng, rate) for ray in self.rays]
        return Genome(
            speed=m(self.speed, 0.16, 0.8, 4.2),
            turn=m(self.turn, 0.025, 0.08, 0.65),
            body_size=m(self.body_size, 0.08, 0.55, 1.8),
            efficiency=m(self.efficiency, 0.07, 0.55, 1.5),
            curiosity=m(self.curiosity, 0.07, 0, 1),
            boldness=m(self.boldness, 0.07, 0, 1),
            sociability=m(self.sociability, 0.07, 0, 1),
            attachment=m(self.attachment, 0.07, 0, 1),
            patience=m(self.patience, 0.07, 0, 1),
            memory_capacity=int(clamp(round(m(float(self.memory_capacity), 5, 16, 140)), 16, 140)),
            learning_rate=m(self.learning_rate, 0.025, 0.03, 0.45),
            discount=m(self.discount, 0.02, 0.70, 0.995),
            exploration=m(self.exploration, 0.035, 0.02, 0.85),
            fear_sensitivity=m(self.fear_sensitivity, 0.07, 0, 1),
            rays=rays,
        )

    def effective_max_energy(self) -> float:
        return 80.0 + 35.0 * self.body_size

    def effective_max_hydration(self) -> float:
        return 80.0 + 30.0 * self.body_size


@dataclass
class Food:
    x: float
    y: float
    energy: float = 32.0
    alive: bool = True


@dataclass
class Water:
    x: float
    y: float
    amount: float = 26.0
    alive: bool = True


@dataclass
class Hazard:
    x: float
    y: float
    radius: float = 18.0
    damage: float = 7.0


@dataclass
class Shelter:
    x: float
    y: float
    radius: float = 32.0


@dataclass
class Predator:
    x: float
    y: float
    angle: float
    speed: float = 1.45
    damage: float = 11.0
    alive: bool = True


@dataclass
class Scent:
    x: float
    y: float
    kind: str
    strength: float
    age: int = 0

    def step(self, decay: float = 0.985) -> None:
        self.age += 1
        self.strength *= decay


@dataclass
class Memory:
    state: str
    cue: str
    reward: float
    tick: int
    strength: float = 1.0


class SpatialHash:
    """Small pure-Python grid index for nearby objects."""

    def __init__(self, cell_size: int = 55) -> None:
        self.cell_size = cell_size
        self.cells: Dict[Tuple[int, int], List[object]] = {}

    def clear(self) -> None:
        self.cells.clear()

    def _key(self, x: float, y: float) -> Tuple[int, int]:
        return int(x // self.cell_size), int(y // self.cell_size)

    def insert(self, obj: object, x: float, y: float) -> None:
        self.cells.setdefault(self._key(x, y), []).append(obj)

    def rebuild(self, objects: Sequence[object], position_fn) -> None:
        self.clear()
        for obj in objects:
            if getattr(obj, "alive", True):
                x, y = position_fn(obj)
                self.insert(obj, x, y)

    def nearby(self, x: float, y: float, radius: float) -> List[object]:
        r = int(math.ceil(radius / self.cell_size))
        cx, cy = self._key(x, y)
        result: List[object] = []
        for ix in range(cx - r, cx + r + 1):
            for iy in range(cy - r, cy + r + 1):
                result.extend(self.cells.get((ix, iy), ()))
        return result


class AnimalBrain:
    """Dog-inspired learner: needs, arousal, association, memory and Q-learning."""

    def __init__(self, genome: Genome, rng: random.Random, q: Optional[Dict[str, List[float]]] = None, associations: Optional[Dict[str, float]] = None) -> None:
        self.rng = rng
        self.alpha = genome.learning_rate
        self.gamma = genome.discount
        self.epsilon = genome.exploration
        self.q: Dict[str, List[float]] = q if q is not None else {}
        self.associations: Dict[str, float] = associations if associations is not None else {}
        self.working: List[str] = []
        self.episodic: List[Memory] = []
        self.valence = 0.0
        self.stress = 0.0
        self.arousal = 0.2
        self.confidence = 0.2
        self.last_state: Optional[str] = None
        self.last_action: Optional[int] = None
        self.last_cue = "nothing"

    def values(self, state: str) -> List[float]:
        return self.q.setdefault(state, [0.0] * len(ACTIONS))

    def choose(self, state: str, biases: List[float]) -> int:
        vals = self.values(state)
        adjusted = [v + b for v, b in zip(vals, biases)]
        # High arousal increases behavioral variability, analogous to an excited animal.
        if self.rng.random() < self.epsilon or self.rng.random() < self.arousal * 0.06:
            return self.rng.randrange(len(ACTIONS))
        best = max(adjusted)
        choices = [i for i, value in enumerate(adjusted) if abs(value - best) < 1e-9]
        return self.rng.choice(choices)

    def learn(self, state: str, action: int, reward: float, next_state: str, cue: str, tick: int) -> None:
        values = self.values(state)
        target = reward + self.gamma * max(self.values(next_state))
        values[action] += self.alpha * (target - values[action])
        self.last_state, self.last_action, self.last_cue = state, action, cue
        self.valence = clamp(self.valence * 0.91 + reward * 0.09, -1, 1)
        self.stress = clamp(self.stress * 0.965 + max(0.0, -reward) * 0.02, 0, 1)
        self.arousal = clamp(self.arousal * 0.94 + abs(reward) * 0.02, 0, 1)
        self.confidence = clamp(self.confidence + (0.008 if reward > 0 else -0.006), 0.02, 0.98)
        if cue and abs(reward) >= 1:
            self.associations[cue] = clamp(self.associations.get(cue, 0.0) * 0.90 + reward * 0.10, -20, 20)
        if abs(reward) >= 2:
            self.episodic.append(Memory(state, cue, reward, tick, min(1.0, abs(reward) / 18.0)))
            self.episodic = self.episodic[-160:]

    def remember(self, state: str, tick: int, capacity: int) -> None:
        self.working.append(state)
        self.working = self.working[-10:]
        for memory in self.episodic:
            age = max(0, tick - memory.tick)
            memory.strength = max(0.03, memory.strength * (0.9997 ** min(age, 5)))
        self.episodic = self.episodic[-capacity:]

    def dream(self) -> float:
        """Replay salient memories during rest and update values without new sensory input."""
        if not self.episodic:
            return 0.0
        selected = sorted(self.episodic, key=lambda m: m.strength * abs(m.reward), reverse=True)[:8]
        updates = 0
        for memory in selected:
            values = self.values(memory.state)
            action = max(range(len(values)), key=values.__getitem__)
            values[action] += self.alpha * 0.25 * memory.strength * memory.reward
            updates += 1
        return float(updates)

    def decay(self) -> None:
        self.epsilon = max(0.025, self.epsilon * 0.9987)
        self.stress *= 0.985
        self.arousal *= 0.985

    def summary(self) -> dict:
        return {
            "known_states": len(self.q), "working_memory": len(self.working),
            "episodic_memory": len(self.episodic), "associations": len(self.associations),
            "confidence": round(self.confidence, 3), "stress": round(self.stress, 3),
            "arousal": round(self.arousal, 3), "valence": round(self.valence, 3),
            "exploration": round(self.epsilon, 3),
        }


@dataclass
class Robot:
    id: int
    sex: str
    x: float
    y: float
    angle: float
    genome: Genome
    brain: AnimalBrain
    generation: int
    parent_ids: Tuple[int, int] = (0, 0)
    health: float = MAX_HEALTH
    energy: float = MAX_ENERGY
    hydration: float = MAX_HYDRATION
    age: int = 0
    fitness: float = 0.0
    food_eaten: int = 0
    water_found: int = 0
    offspring: int = 0
    damage_taken: float = 0.0
    social_contact: int = 0
    alive: bool = True
    sleeping: bool = False
    recent_reward: float = 0.0
    kill_reason: str = ""
    mate_id: Optional[int] = None
    reward_bonus: float = 0.0

    def radius(self) -> float:
        return 7.0 + 5.0 * self.genome.body_size

    def drives(self, world: "World") -> Tuple[float, float, float, float, float, float, float]:
        hunger = clamp(1 - self.energy / self.genome.effective_max_energy(), 0, 1)
        thirst = clamp(1 - self.hydration / self.genome.effective_max_hydration(), 0, 1)
        fatigue = clamp(self.age / world.max_age, 0, 1) * 0.55 + (0.65 if self.sleeping else 0)
        fear = clamp(self.brain.stress * self.genome.fear_sensitivity, 0, 1)
        curiosity = clamp(self.genome.curiosity * (1 - 0.55 * fear) * (0.7 + 0.3 * self.brain.confidence), 0, 1)
        social = clamp(self.genome.sociability * (1 - 0.3 * fear), 0, 1)
        sleepiness = clamp(world.night_factor() * 0.65 + fatigue * 0.7, 0, 1)
        return hunger, thirst, fatigue, fear, curiosity, social, sleepiness

    def observe(self, world: "World") -> Tuple[str, List[int], str, List[float]]:
        codes: List[int] = []
        for ray in self.genome.rays:
            codes.append(self.ray_code(world, wrap_angle(self.angle + ray.angle), ray.length))
        hunger, thirst, fatigue, fear, curiosity, social, sleepiness = self.drives(world)
        b = lambda value: 0 if value < 0.33 else 1 if value < 0.66 else 2
        near = 1 if world.nearest_robot(self.x, self.y, exclude=self, radius=100) else 0
        scent_food = world.local_scent(self.x, self.y, "food")
        scent_danger = world.local_scent(self.x, self.y, "danger")
        state = "".join(str(c) for c in codes) + f"|h{b(hunger)}t{b(thirst)}f{b(fatigue)}r{b(fear)}c{b(curiosity)}s{near}n{b(world.night_factor())}sf{b(scent_food)}sd{b(scent_danger)}"
        cue = SENSE_CODES.get(codes[len(codes) // 2], "nothing")
        internal = [hunger, thirst, fatigue, fear, curiosity, social, sleepiness]
        return state, codes, cue, internal

    def ray_code(self, world: "World", angle: float, length: float) -> int:
        step = 7.0
        for distance_now in range(1, int(length / step) + 1):
            d = distance_now * step
            x = self.x + math.cos(angle) * d
            y = self.y + math.sin(angle) * d
            if x < 4 or x > world.width - 4 or y < 4 or y > world.height - 4:
                return 4
            for obj in world.nearby(x, y, 10):
                if isinstance(obj, Predator) and obj.alive and distance(x, y, obj.x, obj.y) < 12:
                    return 3
                if isinstance(obj, Hazard) and distance(x, y, obj.x, obj.y) <= obj.radius:
                    return 2
                if isinstance(obj, Food) and obj.alive and distance(x, y, obj.x, obj.y) < 9:
                    return 1
                if isinstance(obj, Water) and obj.alive and distance(x, y, obj.x, obj.y) < 9:
                    return 5
                if isinstance(obj, Robot) and obj is not self and obj.alive and distance(x, y, obj.x, obj.y) < 10:
                    return 6
                if isinstance(obj, Shelter) and distance(x, y, obj.x, obj.y) < obj.radius:
                    return 7
            for scent_kind, code in (("food", 8), ("danger", 9)):
                if world.local_scent(x, y, scent_kind) > 0.55:
                    return code
        return 0

    def drive_bias(self, world: "World", codes: List[int], internal: List[float]) -> List[float]:
        hunger, thirst, fatigue, fear, curiosity, social, sleepiness = internal
        mid = len(codes) // 2
        front, left, right = codes[mid], codes[mid - 1], codes[mid + 1]
        bias = [0.0] * len(ACTIONS)
        danger = lambda code: code in (2, 3, 4, 9)
        bias[0] += curiosity * 0.08
        bias[1] += fear * (1.0 if danger(right) else 0) - fear * (0.3 if danger(left) else 0)
        bias[2] += fear * (1.0 if danger(left) else 0) - fear * (0.3 if danger(right) else 0)
        bias[3] += fear * (1.2 if danger(front) else 0)
        bias[4] += fatigue * (0.8 + self.genome.patience * 0.25) + sleepiness * 0.35
        bias[5] += hunger * (1.55 if front == 1 or front == 8 else 0)
        bias[6] += thirst * (1.45 if front == 5 else 0)
        bias[7] += social * (0.45 if front == 6 else 0) + self.genome.attachment * 0.05
        bias[8] += fear * (1.3 if danger(front) else 0)
        if self.brain.associations.get("predator", 0) < -2:
            bias[8] += fear * 0.35
        if world.night_factor() > 0.65 and self.genome.curiosity < 0.4:
            bias[4] += 0.25 * sleepiness
        return bias

    def step(self, world: "World") -> None:
        if not self.alive:
            return
        state, codes, cue, internal = self.observe(world)
        action = self.brain.choose(state, self.drive_bias(world, codes, internal))
        hunger, thirst, fatigue, fear, curiosity, social, sleepiness = internal
        reward = -0.008
        speed = self.genome.speed / (0.75 + self.genome.body_size * 0.45)
        max_energy = self.genome.effective_max_energy()
        max_hydration = self.genome.effective_max_hydration()
        if action == 1:
            self.angle = wrap_angle(self.angle - self.genome.turn)
        elif action == 2:
            self.angle = wrap_angle(self.angle + self.genome.turn)
        elif action == 3:
            speed *= 0.55
        elif action == 4:
            speed = 0.0
            self.sleeping = True
            self.energy = clamp(self.energy + 0.10 * (1.0 + self.genome.patience), 0, max_energy)
            if self.brain.dream() > 0:
                reward += 0.04
        elif action == 8:
            speed *= 1.22
        else:
            self.sleeping = False

        # Nighttime slightly increases sleep pressure and reduces awareness speed.
        if world.night_factor() > 0.7:
            speed *= 0.92
        nx = self.x + math.cos(self.angle) * speed
        ny = self.y + math.sin(self.angle) * speed
        if nx < self.radius() or nx > world.width - self.radius() or ny < self.radius() or ny > world.height - self.radius():
            reward -= 1.0
            self.angle = wrap_angle(self.angle + math.pi * 0.55)
        else:
            self.x, self.y = nx, ny

        movement_cost = (0.05 * speed * (0.7 + self.genome.body_size * 0.5) / self.genome.efficiency) + 0.012
        self.energy = clamp(self.energy - movement_cost, 0, max_energy)
        self.hydration = clamp(self.hydration - (0.020 + 0.004 * speed), 0, max_hydration)
        self.sleeping = self.sleeping and speed == 0.0

        food = world.food_at(self.x, self.y, self.radius() + 6)
        if food:
            food.alive = False
            self.energy = clamp(self.energy + food.energy, 0, max_energy)
            self.food_eaten += 1
            reward += 13.0
            world.deposit_scent(self.x, self.y, "food", 1.0)
        water = world.water_at(self.x, self.y, self.radius() + 7)
        if water:
            water.alive = False
            self.hydration = clamp(self.hydration + water.amount, 0, max_hydration)
            self.water_found += 1
            reward += 9.0
            world.deposit_scent(self.x, self.y, "food", 0.6)

        for hazard in world.nearby(self.x, self.y, 30):
            if isinstance(hazard, Hazard) and distance(self.x, self.y, hazard.x, hazard.y) < hazard.radius + self.radius():
                self.health = clamp(self.health - hazard.damage, 0, MAX_HEALTH)
                self.damage_taken += hazard.damage
                reward -= 11.0 * (0.8 + self.genome.fear_sensitivity * 0.5)
                world.deposit_scent(self.x, self.y, "danger", 1.0)
        for predator in world.nearby(self.x, self.y, 28):
            if isinstance(predator, Predator) and predator.alive and distance(self.x, self.y, predator.x, predator.y) < 16 + self.radius():
                self.health = clamp(self.health - predator.damage, 0, MAX_HEALTH)
                self.damage_taken += predator.damage
                reward -= 17.0
                world.deposit_scent(self.x, self.y, "danger", 1.2)

        nearest = world.nearest_robot(self.x, self.y, exclude=self, radius=90)
        if nearest:
            self.social_contact += 1
            if self.genome.sociability > 0.6:
                reward += 0.02 * self.genome.sociability
            if nearest.sex != self.sex and self.genome.attachment > 0.45:
                self.mate_id = nearest.id

        in_shelter = world.in_shelter(self.x, self.y)
        if in_shelter:
            if fear > 0.2:
                reward += 0.12
                self.brain.stress *= 0.985
            if sleepiness > 0.5 and self.sleeping:
                reward += 0.14

        if self.energy < 15:
            reward -= 0.22 * hunger
        if self.hydration < 15:
            reward -= 0.22 * thirst
        reward += 0.045
        self.age += 1
        self.fitness += reward + self.reward_bonus
        self.reward_bonus = 0.0
        self.recent_reward = reward
        if self.energy <= 0 or self.hydration <= 0:
            self.health -= 1.7 * self.genome.body_size
        if self.age >= world.max_age:
            self.health = 0
        next_state, _, _, _ = self.observe(world)
        self.brain.learn(state, action, reward, next_state, cue, world.tick)
        self.brain.remember(state, world.tick, self.genome.memory_capacity)
        self.brain.decay()
        if self.health <= 0:
            self.alive = False
            self.kill_reason = "starvation/dehydration/damage" if self.energy <= 0 or self.hydration <= 0 else "old age"


class World:
    def __init__(self, width: int = WORLD_W, height: int = WORLD_H, seed: int = 7) -> None:
        self.width = width
        self.height = height
        self.seed = seed
        self.rng = random.Random(seed)
        self.max_age = MAX_AGE
        self.population: List[Robot] = []
        self.food: List[Food] = []
        self.water: List[Water] = []
        self.hazards: List[Hazard] = []
        self.shelters: List[Shelter] = []
        self.predators: List[Predator] = []
        self.scents: List[Scent] = []
        self.history: List[dict] = []
        self.generation = 1
        self.tick = 0
        self.next_id = 1
        self.founder_ids: Tuple[int, int] = (0, 0)
        self.founders_established = False
        self.reset()

    @property
    def experiment(self) -> dict:
        return {
            "population": getattr(self, "_target_population", 24),
            "food": getattr(self, "_target_food", 48),
            "water": getattr(self, "_target_water", 26),
            "hazards": getattr(self, "_target_hazards", 7),
            "predators": getattr(self, "_target_predators", 1),
            "mutation": getattr(self, "_mutation", 0.14),
            "episode": getattr(self, "_episode", 1500),
            "reproduction": True,
            "founder_rule": True,
        }

    def configure(self, **values: float | int | bool) -> None:
        self._target_population = max(2, int(values.get("population", self.experiment["population"])))
        self._target_food = max(1, int(values.get("food", self.experiment["food"])))
        self._target_water = max(1, int(values.get("water", self.experiment["water"])))
        self._target_hazards = max(0, int(values.get("hazards", self.experiment["hazards"])))
        self._target_predators = max(0, int(values.get("predators", self.experiment["predators"])))
        self._mutation = clamp(float(values.get("mutation", self.experiment["mutation"])), 0, 1)
        self._episode = max(100, int(values.get("episode", self.experiment["episode"])))
        if "founder_rule" in values:
            self._founder_rule = bool(values["founder_rule"])

    def reset(self) -> None:
        self.population.clear(); self.food.clear(); self.water.clear(); self.hazards.clear(); self.shelters.clear(); self.predators.clear(); self.scents.clear()
        self.generation = 1; self.tick = 0; self.next_id = 1; self.history.clear(); self.founders_established = False
        self._spatial = SpatialHash(55)
        self._spawn_environment()
        male = self.new_robot(force_sex="male")
        female = self.new_robot(force_sex="female")
        self.population = [male, female]
        self.founder_ids = (male.id, female.id)
        self.rebuild_spatial()

    def _spawn_environment(self) -> None:
        for _ in range(self.experiment["food"]): self.spawn_food()
        for _ in range(self.experiment["water"]): self.spawn_water()
        for _ in range(self.experiment["hazards"]): self.spawn_hazard()
        for _ in range(self.experiment["predators"]): self.spawn_predator()
        for _ in range(5):
            x, y = self.random_xy(60); self.shelters.append(Shelter(x, y))

    def random_xy(self, margin: float = 25.0) -> Tuple[float, float]:
        return self.rng.uniform(margin, self.width - margin), self.rng.uniform(margin, self.height - margin)

    def spawn_food(self, x: Optional[float] = None, y: Optional[float] = None) -> None:
        x, y = self.random_xy() if x is None or y is None else (x, y)
        self.food.append(Food(x, y))

    def spawn_water(self, x: Optional[float] = None, y: Optional[float] = None) -> None:
        x, y = self.random_xy() if x is None or y is None else (x, y)
        self.water.append(Water(x, y))

    def spawn_hazard(self, x: Optional[float] = None, y: Optional[float] = None) -> None:
        x, y = self.random_xy() if x is None or y is None else (x, y)
        self.hazards.append(Hazard(x, y, radius=self.rng.uniform(14, 26)))

    def spawn_predator(self, x: Optional[float] = None, y: Optional[float] = None) -> None:
        x, y = self.random_xy() if x is None or y is None else (x, y)
        self.predators.append(Predator(x, y, self.rng.uniform(-math.pi, math.pi)))

    def rebuild_spatial(self) -> None:
        objects: List[object] = self.food + self.water + self.hazards + self.shelters + self.predators + self.population
        self._spatial.rebuild(objects, lambda obj: (obj.x, obj.y))

    def nearby(self, x: float, y: float, radius: float) -> List[object]:
        return self._spatial.nearby(x, y, radius)

    def nearest_robot(self, x: float, y: float, exclude: Optional[Robot] = None, radius: float = 120) -> Optional[Robot]:
        candidates = [obj for obj in self.nearby(x, y, radius) if isinstance(obj, Robot) and obj.alive and obj is not exclude]
        return min(candidates, key=lambda r: distance(x, y, r.x, r.y), default=None)

    def food_at(self, x: float, y: float, radius: float) -> Optional[Food]:
        return next((obj for obj in self.nearby(x, y, radius) if isinstance(obj, Food) and obj.alive and distance(x, y, obj.x, obj.y) <= radius), None)

    def water_at(self, x: float, y: float, radius: float) -> Optional[Water]:
        return next((obj for obj in self.nearby(x, y, radius) if isinstance(obj, Water) and obj.alive and distance(x, y, obj.x, obj.y) <= radius), None)

    def in_shelter(self, x: float, y: float) -> bool:
        return any(distance(x, y, s.x, s.y) <= s.radius for s in self.shelters)

    def local_scent(self, x: float, y: float, kind: str) -> float:
        best = 0.0
        for scent in self.scents:
            if scent.kind == kind:
                d = distance(x, y, scent.x, scent.y)
                if d < 100:
                    best = max(best, scent.strength * (1 - d / 100))
        return best

    def deposit_scent(self, x: float, y: float, kind: str, strength: float) -> None:
        self.scents.append(Scent(x, y, kind, clamp(strength, 0, 1.5)))
        if len(self.scents) > 1000:
            self.scents = self.scents[-1000:]

    def night_factor(self) -> float:
        phase = (self.tick % DAY_LENGTH) / DAY_LENGTH
        return clamp((math.cos(phase * 2 * math.pi - math.pi) + 1) / 2, 0, 1)

    def founders_alive(self) -> bool:
        if not getattr(self, "_founder_rule", True) or self.founders_established:
            return True
        lookup = {r.id: r for r in self.population}
        a, b = lookup.get(self.founder_ids[0]), lookup.get(self.founder_ids[1])
        return bool(a and b and a.alive and b.alive)

    def founders_ready(self) -> bool:
        lookup = {r.id: r for r in self.population}
        a, b = lookup.get(self.founder_ids[0]), lookup.get(self.founder_ids[1])
        return bool(a and b and a.alive and b.alive and a.sex != b.sex and a.age >= 50 and b.age >= 50 and a.energy > 25 and b.energy > 25)

    def reproduce_founders(self) -> bool:
        if self.founders_established or not self.founders_ready():
            return False
        lookup = {r.id: r for r in self.population}
        a, b = lookup[self.founder_ids[0]], lookup[self.founder_ids[1]]
        self.founders_established = True
        target = self.experiment["population"]
        while len(self.population) < target:
            child = self.create_child(a, b)
            self.population.append(child)
        a.offspring += 1; b.offspring += 1
        return True

    def create_child(self, a: Robot, b: Robot) -> Robot:
        genome = self.blend_genomes(a.genome, b.genome).mutate(self.rng, self.experiment["mutation"])
        q = self.blend_q(a.brain.q, b.brain.q)
        associations = self.blend_assoc(a.brain.associations, b.brain.associations)
        sex = "male" if self.rng.random() < 0.5 else "female"
        x = clamp((a.x + b.x) / 2 + self.rng.uniform(-30, 30), 20, self.width - 20)
        y = clamp((a.y + b.y) / 2 + self.rng.uniform(-30, 30), 20, self.height - 20)
        robot = self.new_robot(genome, q, associations, force_sex=sex, parent_ids=(a.id, b.id), position=(x, y))
        return robot

    def blend_genomes(self, a: Genome, b: Genome) -> Genome:
        fields = ("speed", "turn", "body_size", "efficiency", "curiosity", "boldness", "sociability", "attachment", "patience", "learning_rate", "discount", "exploration", "fear_sensitivity")
        data = {field_name: (getattr(a, field_name) + getattr(b, field_name)) / 2 for field_name in fields}
        data["memory_capacity"] = int(round((a.memory_capacity + b.memory_capacity) / 2))
        data["rays"] = [RayGene((x.angle + y.angle) / 2, (x.length + y.length) / 2) for x, y in zip(a.rays, b.rays)]
        return Genome(**data)

    def blend_q(self, a: Dict[str, List[float]], b: Dict[str, List[float]]) -> Dict[str, List[float]]:
        result: Dict[str, List[float]] = {}
        for key in set(a) | set(b):
            av = a.get(key, [0.0] * len(ACTIONS)); bv = b.get(key, [0.0] * len(ACTIONS))
            result[key] = [(x + y) * 0.5 for x, y in zip(av, bv)]
        return result

    def blend_assoc(self, a: Dict[str, float], b: Dict[str, float]) -> Dict[str, float]:
        return {key: (a.get(key, 0.0) + b.get(key, 0.0)) / 2 for key in set(a) | set(b)}

    def new_robot(self, genome: Optional[Genome] = None, q: Optional[Dict[str, List[float]]] = None, associations: Optional[Dict[str, float]] = None, force_sex: Optional[str] = None, parent_ids: Tuple[int, int] = (0, 0), position: Optional[Tuple[float, float]] = None) -> Robot:
        if genome is None:
            genome = Genome(
                speed=self.rng.uniform(1.4, 2.7), turn=self.rng.uniform(0.13, 0.34), body_size=self.rng.uniform(0.7, 1.3),
                efficiency=self.rng.uniform(0.8, 1.2), curiosity=self.rng.uniform(0.12, 0.55), boldness=self.rng.uniform(0.1, 0.65),
                sociability=self.rng.uniform(0.05, 0.75), attachment=self.rng.uniform(0.15, 0.8), patience=self.rng.uniform(0.15, 0.7),
                memory_capacity=self.rng.randint(30, 70), learning_rate=self.rng.uniform(0.11, 0.24), discount=self.rng.uniform(0.86, 0.97),
                exploration=self.rng.uniform(0.20, 0.52), fear_sensitivity=self.rng.uniform(0.45, 0.9),
                rays=[RayGene(r.angle, r.length) for r in Genome().rays],
            )
        sex = force_sex or ("male" if self.rng.random() < 0.5 else "female")
        x, y = position or self.random_xy()
        robot = Robot(self.next_id, sex, x, y, self.rng.uniform(-math.pi, math.pi), genome, AnimalBrain(genome, self.rng, q, associations), self.generation, parent_ids)
        self.next_id += 1
        return robot

    def kill_robot(self, robot_id: int, reason: str = "experimenter") -> bool:
        robot = next((r for r in self.population if r.id == robot_id), None)
        if not robot:
            return False
        robot.health = 0; robot.alive = False; robot.kill_reason = reason
        return True

    def reward_robot(self, robot_id: int, amount: float) -> bool:
        robot = next((r for r in self.population if r.id == robot_id), None)
        if not robot:
            return False
        robot.fitness += amount
        robot.reward_bonus += amount
        robot.recent_reward = amount
        if robot.brain.last_state is not None and robot.brain.last_action is not None:
            robot.brain.learn(robot.brain.last_state, robot.brain.last_action, amount, robot.brain.last_state, "experimenter", self.tick)
        return True

    def heal_robot(self, robot_id: int, amount: float = 30) -> bool:
        robot = next((r for r in self.population if r.id == robot_id), None)
        if not robot:
            return False
        robot.health = clamp(robot.health + amount, 0, MAX_HEALTH)
        return True

    def boost_robot(self, robot_id: int, energy: float = 40, hydration: float = 30) -> bool:
        robot = next((r for r in self.population if r.id == robot_id), None)
        if not robot:
            return False
        robot.energy = clamp(robot.energy + energy, 0, robot.genome.effective_max_energy())
        robot.hydration = clamp(robot.hydration + hydration, 0, robot.genome.effective_max_hydration())
        return True

    def teleport_robot(self, robot_id: int, x: float, y: float) -> bool:
        robot = next((r for r in self.population if r.id == robot_id), None)
        if not robot:
            return False
        robot.x = clamp(x, 10, self.width - 10); robot.y = clamp(y, 10, self.height - 10)
        return True

    def step(self, amount: int = 1) -> None:
        for _ in range(max(1, amount)):
            self.tick += 1
            if not self.founders_alive():
                self.reset()
                return
            self.rebuild_spatial()
            self.reproduce_founders()
            for predator in self.predators:
                if predator.alive:
                    self.predator_step(predator)
            self.rebuild_spatial()
            for robot in list(self.population):
                if robot.alive:
                    robot.step(self)
            self.scents = [s for s in self.scents if s.strength > 0.025 and s.age < 1600]
            for scent in self.scents:
                scent.step()
            self.food = [f for f in self.food if f.alive]
            self.water = [w for w in self.water if w.alive]
            while len(self.food) < self.experiment["food"]:
                self.spawn_food()
            while len(self.water) < self.experiment["water"] * 0.75:
                self.spawn_water()
            if self.tick >= self.experiment["episode"] or self.alive_count() == 0:
                self.finish_generation()
                break

    def predator_step(self, predator: Predator) -> None:
        target = self.nearest_robot(predator.x, predator.y, radius=220)
        if target:
            desired = math.atan2(target.y - predator.y, target.x - predator.x)
            delta = wrap_angle(desired - predator.angle)
            predator.angle = wrap_angle(predator.angle + clamp(delta, -0.12, 0.12))
        nx = predator.x + math.cos(predator.angle) * predator.speed
        ny = predator.y + math.sin(predator.angle) * predator.speed
        if nx < 12 or nx > self.width - 12:
            predator.angle = wrap_angle(math.pi - predator.angle)
        if ny < 12 or ny > self.height - 12:
            predator.angle = wrap_angle(-predator.angle)
        predator.x = clamp(nx, 12, self.width - 12); predator.y = clamp(ny, 12, self.height - 12)

    def alive_count(self) -> int:
        return sum(r.alive for r in self.population)

    def finish_generation(self) -> None:
        ranked = sorted(self.population, key=lambda r: r.fitness, reverse=True)
        best = ranked[0] if ranked else None
        survivors = [r for r in ranked if r.alive]
        self.history.append({
            "generation": self.generation, "population": len(ranked), "survivors": len(survivors),
            "avg_fitness": sum(r.fitness for r in ranked) / max(1, len(ranked)),
            "best_fitness": best.fitness if best else 0.0, "best_age": best.age if best else 0,
            "best_food": best.food_eaten if best else 0, "knowledge": max((len(r.brain.q) for r in ranked), default=0),
            "predators": len(self.predators), "food": len(self.food),
        })
        self.generation += 1; self.tick = 0
        parents = ranked[:max(2, min(12, len(ranked)))]
        new_population: List[Robot] = []
        target = self.experiment["population"]
        while len(new_population) < target:
            a = self.rng.choice(parents); b = self.rng.choice(parents)
            child = self.create_child(a, b)
            child.generation = self.generation
            new_population.append(child)
        self.population = new_population
        self.founders_established = True

    def summary(self) -> dict:
        best = max(self.population, key=lambda r: r.fitness, default=None)
        return {
            "generation": self.generation, "tick": self.tick, "alive": self.alive_count(),
            "population": len(self.population), "best_fitness": round(best.fitness, 2) if best else 0,
            "avg_fitness": round(sum(r.fitness for r in self.population) / max(1, len(self.population)), 2),
            "best_age": best.age if best else 0, "known_states": max((len(r.brain.q) for r in self.population), default=0),
            "founders_established": self.founders_established, "day": round((self.tick % DAY_LENGTH) / DAY_LENGTH, 3),
        }

    def save_snapshot(self, path: str | Path) -> None:
        data = {
            "version": 2, "seed": self.seed, "generation": self.generation, "tick": self.tick,
            "founder_ids": self.founder_ids, "founders_established": self.founders_established,
            "experiment": self.experiment, "history": self.history[-500:],
            "robots": [
                {"id": r.id, "sex": r.sex, "parent_ids": r.parent_ids, "generation": r.generation,
                 "fitness": r.fitness, "age": r.age, "health": r.health, "energy": r.energy,
                 "hydration": r.hydration, "genome": self.serialize_genome(r.genome),
                 "brain": r.brain.q, "associations": r.brain.associations}
                for r in self.population
            ],
        }
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def serialize_genome(genome: Genome) -> dict:
        data = asdict(genome)
        data["rays"] = [asdict(ray) for ray in genome.rays]
        return data

    @staticmethod
    def save_genome(robot: Robot, path: str | Path) -> None:
        data = {"version": 1, "robot_id": robot.id, "generation": robot.generation, "genome": World.serialize_genome(robot.genome)}
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def run_generations(self, count: int) -> List[dict]:
        target = self.generation + max(1, count) - 1
        while self.generation <= target:
            self.step(self.experiment["episode"])
        return self.history


def load_genome(path: str | Path) -> Genome:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = data.get("genome", data)
    raw["rays"] = [RayGene(**ray) for ray in raw.get("rays", [])] or Genome().rays
    return Genome(**raw)
