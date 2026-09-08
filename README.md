# EVOLVE — 2D Artificial Life Robot Simulator

EVOLVE is a self-contained 2D artificial-life laboratory. Two founders begin each experiment, live through a local world, make decisions from their senses and internal needs, learn from consequences, form memories, reproduce, and pass selected traits and learned warnings into future generations.

Everything runs locally with Python's standard library. No cloud AI, API key, external server, database, or paid service is required.

## The core experiment

The robot does **not** know it is inside a simulation. Its controller receives only local observations and internal body state. There is no privileged world map, simulation flag, hidden object coordinate, or answer key.

The environment creates consequences:

- Food restores energy and can reinforce food-seeking behavior.
- Water restores hydration and can reinforce water-seeking behavior.
- Hazards and predators cause damage and negative reward.
- Rest reduces fatigue and can trigger memory replay.
- Repeated failure can trigger behavioral recovery instead of endless oscillation.
- Successful individuals reproduce and pass mutated traits to descendants.

## Dog-inspired artificial brain

EVOLVE does **not** claim to reproduce a literal biological canine brain. Instead, it uses a compact animal-inspired architecture based on useful behavioral functions:

- hunger, thirst, fatigue, fear, curiosity, social drive, and sleep pressure
- local visual rays plus lightweight scent and sound cues
- associative reinforcement learning
- working and episodic memory
- reward prediction error
- learned skills for navigation, food, water, threat response, social behavior, and self-control
- needs-based goal arbitration
- hierarchical behaviors such as `seek water → approach → drink → retreat`
- sleep/rest and dream-style replay of salient memories

## Survival memory and courage

A robot records a salient lesson when it dies. Typical lessons include:

- `predator` — avoid or respond more carefully to predator encounters
- `hazard` — remember dangerous environmental situations
- `starvation` — improve future food seeking
- `old_age` — a natural end-of-life event rather than a learned threat

The death lesson becomes a strong negative association in that robot's memory. A small portion of these survival warnings is inherited by offspring through the existing learned-association inheritance system. This means descendants can begin life with an **ancestral warning** without receiving a map or perfect knowledge of the world.

Courage is represented by the existing inherited `boldness` trait. Highly bold robots are more willing to confront a nearby predator. A successful close-range confrontation can push the predator away and reward survival. Less-bold robots are more likely to flee.

This creates a meaningful behavioral spectrum rather than making every robot fight.

## Hierarchical behavior

The robot has two decision layers:

```text
Internal needs / danger
        ↓
Current goal
        ↓
Reusable behavior
        ↓
Primitive action
        ↓
Environmental consequence
        ↓
Learning + memory
```

Examples:

```text
Hunger  → forage_food → seek → approach → consume → retreat
Thirst  → seek_water  → seek → approach → consume → retreat
Fear    → escape      → cover → flee → recover
Fatigue → rest_cycle  → shelter → rest → recover
```

Behavior can be interrupted when a more important threat appears, and stalled movement can trigger recovery rather than leaving the robot permanently stuck.

## Evolution

Each genome can evolve traits such as:

- movement speed and turn rate
- body size and resource capacity
- efficiency
- curiosity and boldness
- sociability and attachment
- patience and fear sensitivity
- learning rate and discount factor
- exploration rate
- memory capacity
- sensory ray angles and lengths

The combination of **learning within a lifetime** and **evolution across generations** is the central experiment.

## Experimenter powers

The desktop laboratory gives the human experimenter broad control without exposing those controls to the robot's brain:

- pause/resume simulation
- fast simulation mode
- force a generation transition
- spawn food, water, hazards, and predators at the cursor
- reward or punish a selected robot
- heal or boost a selected robot
- kill a selected robot
- teleport a selected robot
- select any robot and inspect body state, drives, goals, memory, skills, behavior, genome, and learned values
- show/hide sensory visualization and labels
- adjust population, resources, predators, hazards, mutation, and episode length
- save snapshots as JSON
- export a successful robot genome and reuse it in another experiment
- inspect lineage and historical ancestors
- inspect live ecosystem statistics

## Ecosystem

The world includes:

- food and water resources
- hazards
- shelters
- multiple predator behaviors
- scent trails that decay over time
- day/night and sleep pressure
- social encounters
- evolving populations

The experiment starts with **exactly one male and one female founder**. Before the first founder reproduction, death of either founder causes a complete experiment reset. After the founders successfully establish the next generation, normal population evolution begins.

## Performance architecture

The simulation is designed to remain lightweight while supporting larger populations:

- spatial hashing for local entity queries
- spatially accelerated sensory rays
- spatial scent indexing
- reduced repeated distance calculations
- cached hot-path lookups
- controlled scent pruning
- asynchronous UI generation stepping
- decoupled simulation and panel refresh work
- deterministic seeded headless experiments

The goal is to optimize the engine itself rather than hide lag by simply reducing features.

## Run on Windows

Python 3.10+ is enough. No package installation is required.

```powershell
python main.py
```

Or use the supported expanded launcher:

```text
run.bat
```

The launcher loads the performance, ecosystem, cognitive, hierarchical-behavior, survival-memory, long-term-memory, advanced-evolution, and visual layers together.

For a fast GUI-free experiment:

```powershell
python main.py --headless --generations 20 --population 250 --seed 42
```

## Advanced artificial-life layer

`advanced_evolution.py` adds deeper emergent systems without giving robots privileged simulation knowledge:

- **Cognitive place map** with remembered value, danger and uncertainty
- **Habit/behavior chunking** that tracks which macro behaviors actually work
- **Reflex vs deliberate control** so immediate threats can interrupt normal planning
- **Personality plasticity** through mood, confidence, stress and inherited temperament
- **Social/observational learning** from nearby successful individuals
- **Family and relationship memory** carried imperfectly into descendants
- **Home/territory formation** from repeated visits rather than a predefined territory map
- **Dynamic ecology** with seasonal resource pressure and capped regrowth
- **Weather** that changes survival costs and becomes a learned context
- **Predator personality and adaptation** with stalker/sprinter/scout styles and prey-specific hesitation
- **Persistent genealogy and life-event replay records**
- **Repeatable headless trials** for comparing evolutionary experiments
- **Experiment JSON export** for offline analysis

The advanced layer is deliberately functional rather than cosmetic: the systems influence decisions, survival, inheritance, or measurable experiment outcomes.

## Controls

- **Space** — pause/resume
- **F** — fast simulation mode
- **N** — force next generation
- **R** — reset experiment
- **Esc** — quit
- **Left click robot** — inspect robot

## Project phases

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
16. Cognitive map + habits + reflex layer ✅
17. Social/family/territory systems ✅
18. Weather + seasons + dynamic ecology ✅
19. Predator adaptation + genealogy/replay analytics ✅
20. Repeatable experiment trials + export ✅

## Design principle

EVOLVE is an artificial-life experiment, not a claim of consciousness and not a literal copy of a dog brain. The goal is to create believable learning and survival behavior from limited senses, internal needs, memory, consequences, evolution, and environmental pressure — and let the experiment reveal what emerges.

## License

MIT
