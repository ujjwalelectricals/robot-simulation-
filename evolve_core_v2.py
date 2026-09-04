from __future__ import annotations

"""Dependency-free artificial-life core for EVOLVE.

The robot has a dog-inspired behavioral architecture, not a literal biological dog brain:
multiple competing drives, associative conditioning, working/episodic memory, arousal,
fear, curiosity, social attachment, Q-learning, and evolution.
"""

import json
import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

WORLD_W, WORLD_H = 1000, 680
MAX_HEALTH = 100.0
ACTIONS = ("forward", "left", "right", "back", "rest", "eat", "drink", "approach", "flee")
RAYS = (-1.0, -0.5, -0.25, 0.0, 0.25, 0.5, 1.0)


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def wrap(a: float) -> float:
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
    attachment: float = 0.35
    patience: float = 0.35

    def mutate(self, rng: random.Random, rate: float) -> "Genome":
        def m(x: float, sigma: float, lo: float, hi: float) -> float:
            return clamp(x + rng.gauss(0, sigma), lo, hi) if rng.random() < rate else x

        return Genome(
            speed=m(self.speed, 0.16, 0.8, 4.0),
            turn=m(self.turn, 0.025, 0.08, 0.6),
            vision=m(self.vision, 8.0, 45, 180),
            efficiency=m(self.efficiency, 0.07, 0.55, 1.5),
            curiosity=m(self.curiosity, 0.07, 0, 1),
            boldness=m(self.boldness, 0.07, 0, 1),
            sociability=m(self.sociability, 0.07, 0, 1),
            memory_capacity=int(clamp(round(m(float(self.memory_capacity), 5, 16, 120)), 16, 120)),
            learning_rate=m(self.learning_rate, 0.025, 0.03, 0.4),
            discount=m(self.discount, 0.02, 0.70, 0.995),
            exploration=m(self.exploration, 0.035, 0.02, 0.85),
            fear_sensitivity=m(self.fear_sensitivity, 0.07, 0, 1),
            attachment=m(self.attachment, 0.07, 0, 1),
            patience=m(self.patience, 0.07, 0, 1),
        )


@dataclass
class Food:
    x: float
    y: float
    amount: float = 32.0
    alive: bool = True


@dataclass
class Water:
    x: float
    y: float
    amount: float = 25.0
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

    def step(self, world: "World") -> None:
        target = world.nearest_robot(self.x, self.y)
        if target:
            self.angle = math.atan2(target.y - self.y, target.x - self.x)
        nx = self.x + math.cos(self.angle) * self.speed
        ny = self.y + math.sin(self.angle) * self.speed
        if nx < 12 or nx > world.width - 12:
            self.angle = wrap(math.pi - self.angle)
        if ny < 12 or ny > world.height - 12:
            self.angle = wrap(-self.angle)
        self.x = clamp(nx, 12, world.width - 12)
        self.y = clamp(ny, 12, world.height - 12)


@dataclass
class Memory:
    state: str
    cue: str
    reward: float
    tick: int
    strength: float = 1.0


class AnimalBrain:
    """Compact, animal-inspired learner; not a literal dog neural reconstruction."""

    def __init__(self, genome: Genome, rng: random.Random, q: Optional[Dict[str, List[float]]] = None):
        self.rng = rng
        self.alpha = genome.learning_rate
        self.gamma = genome.discount
        self.epsilon = genome.exploration
        self.q: Dict[str, List[float]] = q if q is not None else {}
        self.working: List[str] = []
        self.episodic: List[Memory] = []
        self.associations: Dict[str, float] = {}
        self.valence = 0.0
        self.stress = 0.0
        self.arousal = 0.2
        self.confidence = 0.2
        self.last_state: Optional[str] = None
        self.last_action: Optional[int] = None
        self.last_reward: float = 0.0

    def values(self, state: str) -> List[float]:
        return self.q.setdefault(state, [0.0] * len(ACTIONS))

    def choose(self, state: str, biases: List[float]) -> int:
        values = self.values(state)
        adjusted = [v + b for v, b in zip(values, biases)]
        if self.rng.random() < self.epsilon:
            return self.rng.randrange(len(ACTIONS))
        if self.rng.random() < self.arousal * 0.08:
            return self.rng.randrange(len(ACTIONS))
        best = max(adjusted)
        choices = [i for i, v in enumerate(adjusted) if abs(v - best) < 1e-9]
        return self.rng.choice(choices)

    def learn(self, state: str, action: int, reward: float, next_state: str, cue: str) -> None:
        values = self.values(state)
        target = reward + self.gamma * max(self.values(next_state))
        values[action] += self.alpha * (target - values[action])
        self.last_state, self.last_action, self.last_reward = state, action, reward
        self.valence = clamp(self.valence * 0.92 + reward * 0.08, -1, 1)
        self.stress = clamp(self.stress * 0.965 + max(0, -reward) * 0.02, 0, 1)
        self.arousal = clamp(self.arousal * 0.94 + abs(reward) * 0.02, 0, 1)
        self.confidence = clamp(self.confidence + (0.008 if reward > 0 else -0.005), 0.02, 0.98)
        if cue and abs(reward) >= 1:
            self.associations[cue] = clamp(self.associations.get(cue, 0.0) * 0.9 + reward * 0.1, -20, 20)
        if abs(reward) >= 2:
            self.episodic.append(Memory(state, cue, reward, 0, min(1, abs(reward) / 18)))
            self.episodic = self.episodic[-160:]

    def remember(self, state: str, tick: int, capacity: int) -> None:
        self.working.append(state)
        self.working = self.working[-10:]
        for m in self.episodic:
            m.strength = max(0.05, m.strength * 0.9997)
            if m.tick == 0:
                m.tick = tick
        if len(self.episodic) > capacity:
            self.episodic = self.episodic[-capacity:]

    def decay(self) -> None:
        self.epsilon = max(0.025, self.epsilon * 0.9987)
        self.stress *= 0.986
        self.arousal *= 0.985


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
    health: float = MAX_HEALTH
    energy: float = 100.0
    hydration: float = 100.0
    age: int = 0
    fitness: float = 0.0
    food_eaten: int = 0
    water_found: int = 0
    offspring: int = 0
    damage_taken: float = 0.0
    social_contact: int = 0
    alive: bool = True
    sleep: float = 0.0
    recent_reward: float = 0.0
    kill_reason: str = ""
    mate_id: Optional[int] = None

    def drives(self) -> Tuple[float, float, float, float, float, float]:
        hunger = clamp(1 - self.energy / 100, 0, 1)
        thirst = clamp(1 - self.hydration / 100, 0, 1)
        fatigue = clamp(self.age / 1600, 0, 1) * 0.6 + self.sleep * 0.4
        fear = clamp(self.brain.stress * self.genome.fear_sensitivity, 0, 1)
        curiosity = clamp(self.genome.curiosity * (1 - fear * 0.55) * (0.7 + self.brain.confidence * 0.3), 0, 1)
        social = clamp(self.genome.sociability * (1 - fear * 0.3), 0, 1)
        return hunger, thirst, fatigue, fear, curiosity, social

    def observe(self, world: "World") -> Tuple[str, List[int], str]:
        codes: List[int] = []
        for off in RAYS:
            codes.append(self.ray_code(world, self.angle + off))
        hunger, thirst, fatigue, fear, curiosity, social = self.drives()
        b = lambda v: 0 if v < 0.33 else 1 if v < 0.66 else 2
        nearby = 1 if world.nearest_robot(self.x, self.y, exclude=self) else 0
        state = "".join(map(str, codes)) + f"|h{b(hunger)}t{b(thirst)}f{b(fatigue)}r{b(fear)}c{b(curiosity)}s{nearby}"
        return state, codes, self.cue(codes)

    def ray_code(self, world: "World", angle: float) -> int:
        length = self.genome.vision
        for i in range(1, max(2, int(length / 6)) + 1):
            d = i * 6
            x = self.x + math.cos(angle) * d
            y = self.y + math.sin(angle) * d
            if x < 4 or x > world.width - 4 or y < 4 or y > world.height - 4:
                return 4
            if any(p.alive and distance((x, y), (p.x, p.y)) < 12 for p in world.predators): return 3
            if any(distance((x, y), (h.x, h.y)) < h.radius for h in world.hazards): return 2
            if any(f.alive and distance((x, y), (f.x, f.y)) < 9 for f in world.food): return 1
            if any(w.alive and distance((x, y), (w.x, w.y)) < 9 for w in world.water): return 5
            if any(r is not self and r.alive and distance((x, y), (r.x, r.y)) < 10 for r in world.population): return 6
            if any(distance((x, y), (s.x, s.y)) < s.radius for s in world.shelters): return 7
        return 0

    @staticmethod
    def cue(codes: List[int]) -> str:
        return {0: "nothing", 1: "food", 2: "hazard", 3: "predator", 4: "wall", 5: "water", 6: "social", 7: "shelter"}.get(codes[len(codes)//2], "nothing")

    def drive_bias(self, codes: List[int]) -> List[float]:
        hunger, thirst, fatigue, fear, curiosity, social = self.drives()
        c = len(codes)//2
        front, left, right = codes[c], codes[c-1], codes[c+1]
        front_bad, left_bad, right_bad = front in (2,3,4), left in (2,3,4), right in (2,3,4)
        b = [0.0] * len(ACTIONS)
        b[0] += curiosity * 0.08
        b[1] += fear * (1.0 if right_bad else 0) - fear * (0.35 if left_bad else 0)
        b[2] += fear * (1.0 if left_bad else 0) - fear * (0.35 if right_bad else 0)
        b[3] += fear * (1.2 if front_bad else 0)
        b[4] += fatigue * (0.8 + self.genome.patience * 0.25)
        b[5] += hunger * (1.4 if front == 1 else 0)
        b[6] += thirst * (1.35 if front == 5 else 0)
        b[7] += social * (0.45 if front == 6 else 0)
        b[8] += fear * (1.15 if front_bad else 0)
        if self.brain.associations.get("predator", 0) < -2: b[8] += 0.25 * fear
        return b

    def step(self, world: "World") -> None:
        if not self.alive: return
        state, codes, cue = self.observe(world)
        action = self.brain.choose(state, self.drive_bias(codes))
        hunger, thirst, fatigue, fear, curiosity, _ = self.drives()
        reward = -0.01
        speed = self.genome.speed
        if action == 1: self.angle = wrap(self.angle - self.genome.turn)
        elif action == 2: self.angle = wrap(self.angle + self.genome.turn)
        elif action == 3: speed *= 0.55
        elif action == 4:
            speed = 0.0; self.sleep = clamp(self.sleep + 0.018, 0, 1); self.energy = clamp(self.energy + 0.07, 0, 100)
        elif action == 8:
            speed *= 1.25
        nx, ny = self.x + math.cos(self.angle) * speed, self.y + math.sin(self.angle) * speed
        if nx < 8 or nx > world.width - 8 or ny < 8 or ny > world.height - 8:
            reward -= 1.0; self.angle = wrap(self.angle + math.pi * 0.55)
        else:
            self.x, self.y = nx, ny
        self.energy = clamp(self.energy - (0.05 * speed / self.genome.efficiency + 0.014), 0, 100)
        self.hydration = clamp(self.hydration - 0.021, 0, 100)
        self.sleep = max(0, self.sleep - 0.003)
        f = world.food_at(self.x, self.y, 14)
        if f:
            f.alive = False; self.energy = clamp(self.energy + f.amount, 0, 100); self.food_eaten += 1; reward += 12
        w = world.water_at(self.x, self.y, 15)
        if w:
            w.alive = False; self.hydration = clamp(self.hydration + w.amount, 0, 100); self.water_found += 1; reward += 9
        safe = world.in_shelter(self.x, self.y)
        if safe and fear > 0.2: reward += 0.15; self.brain.stress *= 0.98
        for h in world.hazards:
            if distance((self.x, self.y), (h.x, h.y)) < h.radius + 8:
                self.health = clamp(self.health - h.damage, 0, 100); self.damage_taken += h.damage; reward -= 10 * (0.8 + self.genome.fear_sensitivity * 0.5)
        for p in world.predators:
            if p.alive and distance((self.x, self.y), (p.x, p.y)) < 15:
                self.health = clamp(self.health - p.damage, 0, 100); self.damage_taken += p.damage; reward -= 17
        nearest = world.nearest_robot(self.x, self.y, exclude=self)
        if nearest and distance((self.x, self.y), (nearest.x, nearest.y)) < 25:
            self.social_contact += 1
            reward += 0.03 * self.genome.sociability
            if nearest.sex != self.sex and self.genome.attachment > 0.45: self.mate_id = nearest.id
        if self.energy < 15: reward -= 0.24 * hunger
        if self.hydration < 15: reward -= 0.24 * thirst
        reward += 0.045
        if safe and fatigue > 0.4: reward += 0.08
        self.age += 1; self.fitness += reward; self.recent_reward = reward
        next_state, _, _ = self.observe(world)
        self.brain.learn(state, action, reward, next_state, cue)
        self.brain.remember(state, world.tick, self.genome.memory_capacity)
        self.brain.decay()
        if self.energy <= 0 or self.hydration <= 0: self.health -= 1.7
        if self.age >= world.max_age: self.health = 0; self.kill_reason = "old age"
        if self.health <= 0:
            self.alive = False
            if not self.kill_reason: self.kill_reason = "damage/starvation/dehydration"


class World:
    def __init__(self, width: int = WORLD_W, height: int = WORLD_H, seed: int = 7):
        self.width, self.height, self.seed = width, height, seed
        self.rng = random.Random(seed)
        self.max_age = 1800
        self.population: List[Robot] = []
        self.food: List[Food] = []
        self.water: List[Water] = []
        self.hazards: List[Hazard] = []
        self.shelters: List[Shelter] = []
        self.predators: List[Predator] = []
        self.history: List[dict] = []
        self.generation = 1; self.tick = 0; self.next_id = 1
        self.experiment = {"population": 24, "food": 52, "water": 28, "hazards": 6, "predators": 1, "mutation": 0.14, "episode": 1500, "reproduction": True, "founder_rule": True}
        self.founder_ids = (0, 0); self.founders_established = False
        self.reset()

    def reset(self) -> None:
        self.population.clear(); self.food.clear(); self.water.clear(); self.hazards.clear(); self.shelters.clear(); self.predators.clear()
        self.generation = 1; self.tick = 0; self.next_id = 1; self.history.clear(); self.founders_established = False
        for _ in range(self.experiment["food"]): self.spawn_food()
        for _ in range(self.experiment["water"]): self.spawn_water()
        for _ in range(self.experiment["hazards"]): self.spawn_hazard()
        for _ in range(self.experiment["predators"]): self.spawn_predator()
        for _ in range(5): self.shelters.append(Shelter(*self.random_xy(60)))
        male = self.new_robot(force_sex="male"); female = self.new_robot(force_sex="female")
        self.population = [male, female]; self.founder_ids = (male.id, female.id)

    def random_xy(self, margin: float = 25) -> Tuple[float, float]:
        return self.rng.uniform(margin, self.width-margin), self.rng.uniform(margin, self.height-margin)

    def new_robot(self, genome: Optional[Genome] = None, q: Optional[Dict[str, List[float]]] = None, force_sex: Optional[str] = None) -> Robot:
        if genome is None:
            genome = Genome(speed=self.rng.uniform(1.4,2.7), turn=self.rng.uniform(.13,.34), vision=self.rng.uniform(75,125), efficiency=self.rng.uniform(.8,1.18), curiosity=self.rng.uniform(.12,.55), boldness=self.rng.uniform(.1,.65), sociability=self.rng.uniform(.05,.75), memory_capacity=self.rng.randint(30,70), learning_rate=self.rng.uniform(.11,.24), discount=self.rng.uniform(.86,.97), exploration=self.rng.uniform(.2,.52), fear_sensitivity=self.rng.uniform(.45,.9), attachment=self.rng.uniform(.1,.8), patience=self.rng.uniform(.15,.7))
        sex = force_sex or self.rng.choice(("male", "female")); x,y = self.random_xy()
        r = Robot(self.next_id, sex, x, y, self.rng.uniform(-math.pi,math.pi), genome, AnimalBrain(genome,self.rng,q), self.generation); self.next_id += 1; return r

    def spawn_food(self, x: Optional[float]=None, y: Optional[float]=None) -> None:
        x,y = self.random_xy() if x is None or y is None else (x,y); self.food.append(Food(x,y))
    def spawn_water(self, x: Optional[float]=None, y: Optional[float]=None) -> None:
        x,y = self.random_xy() if x is None or y is None else (x,y); self.water.append(Water(x,y))
    def spawn_hazard(self, x: Optional[float]=None, y: Optional[float]=None) -> None:
        x,y = self.random_xy() if x is None or y is None else (x,y); self.hazards.append(Hazard(x,y,self.rng.uniform(14,25)))
    def spawn_predator(self, x: Optional[float]=None, y: Optional[float]=None) -> None:
        x,y = self.random_xy() if x is None or y is None else (x,y); self.predators.append(Predator(x,y,self.rng.uniform(-math.pi,math.pi)))

    def nearest_robot(self, x: float, y: float, exclude: Optional[Robot]=None) -> Optional[Robot]:
        return min((r for r in self.population if r.alive and r is not exclude), key=lambda r: distance((x,y),(r.x,r.y)), default=None)
    def food_at(self,x:float,y:float,radius:float)->Optional[Food]: return next((f for f in self.food if f.alive and distance((x,y),(f.x,f.y))<=radius),None)
    def water_at(self,x:float,y:float,radius:float)->Optional[Water]: return next((w for w in self.water if w.alive and distance((x,y),(w.x,w.y))<=radius),None)
    def in_shelter(self,x:float,y:float)->bool: return any(distance((x,y),(s.x,s.y))<=s.radius for s in self.shelters)
    def alive_count(self)->int: return sum(r.alive for r in self.population)

    def founders_alive(self)->bool:
        if not self.experiment.get("founder_rule",True) or self.founders_established: return True
        lookup={r.id:r for r in self.population}; m=lookup.get(self.founder_ids[0]); f=lookup.get(self.founder_ids[1]); return bool(m and f and m.alive and f.alive)

    def founders_ready(self)->bool:
        lookup={r.id:r for r in self.population}; m=lookup.get(self.founder_ids[0]); f=lookup.get(self.founder_ids[1])
        return bool(m and f and m.alive and f.alive and m.age>=50 and f.age>=50 and m.energy>25 and f.energy>25)

    def _blend_genome(self,a:Genome,b:Genome)->Genome:
        data={}
        for name in a.__dataclass_fields__:
            av,bv=getattr(a,name),getattr(b,name); data[name]=int(round((av+bv)/2)) if name=="memory_capacity" else (av+bv)/2
        return Genome(**data)

    def _blend_q(self,qa:Dict[str,List[float]],qb:Dict[str,List[float]])->Dict[str,List[float]]:
        out={}
        for k in set(qa)|set(qb):
            a=qa.get(k,[0.0]*len(ACTIONS)); b=qb.get(k,[0.0]*len(ACTIONS)); out[k]=[(x+y)/2 for x,y in zip(a,b)]
        return out

    def reproduce_founders(self)->None:
        if self.founders_established or not self.founders_ready(): return
        lookup={r.id:r for r in self.population}; m=lookup[self.founder_ids[0]]; f=lookup[self.founder_ids[1]]
        self.founders_established=True
        target=max(2,int(self.experiment["population"])); children=max(2,target-2)
        for _ in range(children):
            g=self._blend_genome(m.genome,f.genome).mutate(self.rng,self.experiment["mutation"]); q=self._blend_q(m.brain.q,f.brain.q)
            self.population.append(self.new_robot(g,q)); m.offspring+=1; f.offspring+=1

    def step(self, amount:int=1)->None:
        for _ in range(max(1,amount)):
            self.tick+=1
            if not self.founders_alive(): self.reset(); return
            self.reproduce_founders()
            for p in self.predators:
                if p.alive: p.step(self)
            for r in list(self.population):
                if r.alive: r.step(self)
            self.food=[f for f in self.food if f.alive]; self.water=[w for w in self.water if w.alive]
            while len(self.food)<self.experiment["food"]: self.spawn_food()
            while len(self.water)<self.experiment["water"]: self.spawn_water()
            if self.tick>=int(self.experiment["episode"]) or self.alive_count()==0: self.finish_generation(); break

    def finish_generation(self)->None:
        ranked=sorted(self.population,key=lambda r:r.fitness,reverse=True); survivors=[r for r in ranked if r.alive]; best=ranked[0] if ranked else None
        self.history.append({"generation":self.generation,"population":len(ranked),"survivors":len(survivors),"avg_fitness":round(sum(r.fitness for r in ranked)/max(1,len(ranked)),3),"best_fitness":round(best.fitness,3) if best else 0,"best_age":best.age if best else 0,"best_food":best.food_eaten if best else 0,"knowledge":max((len(r.brain.q) for r in ranked),default=0),"founders_established":self.founders_established})
        if not ranked: self.reset(); return
        parents=ranked[:max(2,min(10,len(ranked)))]; self.generation+=1; self.tick=0; new=[]; target=max(2,int(self.experiment["population"]))
        while len(new)<target:
            a,b=self.rng.choice(parents),self.rng.choice(parents); g=self._blend_genome(a.genome,b.genome).mutate(self.rng,self.experiment["mutation"]); q=self._blend_q(a.brain.q,b.brain.q); child=self.new_robot(g,q); child.generation=self.generation; new.append(child)
        self.population=new; self.founders_established=True

    def reward_robot(self,robot_id:int,amount:float)->bool:
        r=next((x for x in self.population if x.id==robot_id),None)
        if not r:return False
        r.fitness+=amount;r.recent_reward=amount
        r.brain.learn(r.brain.last_state or "manual",r.brain.last_action or 0,amount,r.brain.last_state or "manual","experimenter")
        return True
    def heal_robot(self,robot_id:int,amount:float=30)->bool:
        r=next((x for x in self.population if x.id==robot_id),None)
        if not r:return False
        r.health=clamp(r.health+amount,0,100);return True
    def boost_robot(self,robot_id:int,energy:float=40,hydration:float=30)->bool:
        r=next((x for x in self.population if x.id==robot_id),None)
        if not r:return False
        r.energy=clamp(r.energy+energy,0,100);r.hydration=clamp(r.hydration+hydration,0,100);return True
    def kill_robot(self,robot_id:int,reason:str="experimenter")->bool:
        r=next((x for x in self.population if x.id==robot_id),None)
        if not r:return False
        r.health=0;r.alive=False;r.kill_reason=reason;return True
    def teleport_robot(self,robot_id:int,x:float,y:float)->bool:
        r=next((x for x in self.population if x.id==robot_id),None)
        if not r:return False
        r.x=clamp(x,8,self.width-8);r.y=clamp(y,8,self.height-8);return True

    def summary(self)->dict:
        best=max(self.population,key=lambda r:r.fitness,default=None)
        return {"generation":self.generation,"tick":self.tick,"alive":self.alive_count(),"population":len(self.population),"best_fitness":round(best.fitness,2) if best else 0,"avg_fitness":round(sum(r.fitness for r in self.population)/max(1,len(self.population)),2),"best_age":best.age if best else 0,"best_food":best.food_eaten if best else 0,"known_states":max((len(r.brain.q) for r in self.population),default=0),"founders_established":self.founders_established}

    def save_snapshot(self,path:str)->None:
        data={"seed":self.seed,"generation":self.generation,"tick":self.tick,"experiment":self.experiment,"history":self.history[-200:],"founder_ids":self.founder_ids,"founders_established":self.founders_established,"robots":[{"id":r.id,"sex":r.sex,"generation":r.generation,"genome":r.genome.__dict__,"brain":r.brain.q,"associations":r.brain.associations,"fitness":r.fitness,"age":r.age,"alive":r.alive} for r in self.population]}
        with open(path,"w",encoding="utf-8") as f:json.dump(data,f,indent=2)

    def run_generations(self,generations:int)->List[dict]:
        target=self.generation+max(1,generations)-1
        while self.generation<=target:self.step(int(self.experiment["episode"]))
        return self.history
