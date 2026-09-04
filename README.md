# EVOLVE — 2D Artificial Life Robot Simulator

A self-contained artificial-life laboratory where a robot is born with a small set of senses and drives, learns from consequences, survives or dies, and passes selected traits to future generations.

## The core experiment

The robot is **not told that it is inside a simulation**. Its brain receives only local sensory observations and internal body signals. There is no privileged simulation flag, map, object label, or hidden answer key.

Its world creates consequences:

- Food and water satisfy biological drives and produce positive reward.
- Hazards and predators cause damage and strong negative reward.
- Boundary collisions are costly.
- Rest reduces fatigue pressure.
- Successful individuals become parents.
- Offspring inherit and mutate behavioral traits.
- Short-term/episodic memories belong to the lifetime; the inherited genome survives through generations.

## Dog-inspired artificial brain

This is **not a biological dog brain**. It is a compact artificial architecture inspired by useful animal-learning behaviors:

- hunger, thirst and fatigue drives
- fear/stress and curiosity
- approach vs avoidance bias
- attention through five directional sensory rays
- associative Q-learning
- working memory and episodic memories
- confidence and emotional valence signals
- exploration/exploitation balance
- social-contact signal

The design goal is emergent behavior from limited information, rewards, memory and survival pressure.

## Experimenter powers

The desktop laboratory gives you direct control over the experiment without changing the robot's internal rules:

- pause/resume simulation
- run fast mode
- force a generation transition
- spawn food, water, hazards and predators at the mouse position
- manually reward or punish the selected robot
- heal a selected robot or restore energy/hydration
- select a robot and inspect its body state, drives, brain and genome
- show/hide sensory rays and robot labels
- change population, resources, hazards, predators, mutation and episode length
- save an experiment snapshot as JSON

## Evolution loop

```text
Birth → Sense → Decide → Act → Consequence → Learn → Survive/Die
                         ↓
                 Fitness + Memory
                         ↓
              Selection + Mutation
                         ↓
                 Next Generation
```

## Run on Windows

Python 3.10+ is enough. No pip install is required.

```powershell
python main.py
```

Or double-click:

```text
run.bat
```

For a fast, GUI-free experiment:

```powershell
python main.py --headless --generations 20 --population 250 --seed 42
```

## Controls

- **Space** — pause/resume
- **F** — fast mode
- **N** — force next generation
- **R** — reset experiment
- **Esc** — quit
- **Left click robot** — inspect that robot

## Project phases

The repository is designed to grow through these stages:

1. World + movement ✅
2. Sensors ✅
3. Brain ✅
4. Reward system ✅
5. Learning ✅
6. Memory ✅
7. Death/restart ✅
8. Genetics ✅
9. Reproduction ✅
10. Evolution ✅
11. Predators/resources/ecosystem ✅
12. Generational analytics ✅
13. Repeatable experiments ✅
14. Large-population optimization 🚧
15. Polished simulation laboratory 🚧

## Design principle

We are building an artificial-life experiment, not claiming consciousness or human-level intelligence. The interesting part is watching useful behavior emerge from a simple body, limited senses, learning, memory, reward, punishment, survival and evolution.

## License

MIT
