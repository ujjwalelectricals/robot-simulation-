# EVOLVE — 3D Artificial Life Robot Simulator

EVOLVE is a self-contained artificial-life laboratory in Python. Each experiment begins with exactly one male and one female founder. They perceive a local world, pursue competing needs, learn from consequences, build memories, form relationships, reproduce, and evolve across generations.

The desktop application now presents the simulation as a **3D world** with perspective projection, terrain height, orbit camera controls, depth ordering, resources, shelters, hazards, predators, and visible robot sensing. The simulation engine remains separate from the presentation layer so headless experiments can run without rendering.

Everything is local. No cloud AI, API key, database, external server, or paid service is required.

## Core rule

The robot does **not** know it is inside a simulation. It receives local sensory observations and internal body/brain state only. It has no privileged map, hidden coordinates, simulation flag, or answer key.

The world creates consequences: food restores energy, water restores hydration, hazards and predators create danger, rest reduces fatigue and supports memory consolidation, and survival/reproduction determine which traits persist.

## 3D laboratory

The current desktop UI is `main_3d.py` and is launched by `run.bat` through `launcher.py`.

The 3D presentation includes:

- perspective camera and depth sorting
- right-drag camera orbit
- mouse-wheel / +/- zoom
- procedural terrain height
- 3D-positioned robots, predators, resources, hazards, and shelters
- visible robot sensory rays for the selected robot
- dynamic generation/population/FPS HUD
- robot inspection and experimenter controls

The renderer is intentionally **self-contained and dependency-free**. It uses Tkinter drawing with a mathematical 3D projection rather than requiring a heavy external 3D engine. That keeps the project easy to run on Windows and keeps rendering separate from the simulation engine.

## Artificial brain

EVOLVE uses a compact animal-inspired cognitive architecture rather than claiming to reproduce a literal canine brain.

The robot has competing drives including:

- hunger
- thirst
- fatigue
- fear
- curiosity
- social drive
- sleep pressure

The decision loop is approximately:

```text
Local senses + body state
        ↓
Needs / emotional state
        ↓
Goal arbitration
        ↓
Hierarchical behavior
        ↓
Memory recall + learned values
        ↓
Action
        ↓
Environmental consequence
        ↓
Learning + memory update
```

Learning includes Q-values, associative conditioning, reward prediction error, working memory, episodic memory, spatial/place memory, novelty tracking, habit/behavior chunks, and sleep/dream-style replay.

## Memory

The memory system is deliberately limited and selective instead of being an unlimited perfect database.

A meaningful experience can remember:

- the internal state
- sensory cue
- selected action
- reward or punishment
- approximate location
- active goal
- importance and memory strength
- repeated visits

Memories are retrieved by a combination of recency, spatial proximity, semantic similarity, state similarity, and salience. Weak old memories can be forgotten when memory capacity is pressured, while important experiences persist longer.

Robots can also develop approximate place memories such as useful food/water areas and dangerous places. Novelty/familiarity influences exploration.

## Death lessons and courage

A robot can record a specific death lesson such as:

- predator
- hazard
- starvation
- old age

The lesson becomes a strong avoidance association. Limited survival warnings can also be inherited by descendants, allowing lineages to carry useful warnings without receiving a perfect map.

Courage is represented using the inherited `boldness` trait. Some bold robots are more willing to confront a nearby predator rather than always fleeing; this is deliberately probabilistic so courage creates a trade-off rather than invulnerability.

## Hierarchical behavior

Robots can combine primitive actions into reusable behavior patterns such as:

```text
Hunger  → forage food → seek → approach → consume → retreat
Thirst  → seek water  → seek → approach → consume → retreat
Fear    → escape      → cover → flee → recover
Fatigue → rest cycle  → shelter → rest → recover
```

A strong new danger can interrupt a lower-priority behavior. Stalled movement can trigger recovery rather than leaving a robot permanently stuck.

## Social and evolutionary systems

Individuals can develop different temperaments and experiences even when their genetics are similar.

The advanced artificial-life layer supports:

- personality and mood
- social/observational learning
- family and relationship memory
- home/territory formation
- mating/reproduction pressure
- imperfect inheritance of useful learned warnings
- genealogy and life-event history
- behavior/habit statistics

The goal is to produce different individuals and lineages rather than clones with identical behavior.

## Ecosystem

The world contains interacting ecological pressures:

- food resources
- water resources
- shelters
- hazards
- scent trails
- predators with different behavior styles
- day/night pressure
- weather and seasonal pressure
- resource regrowth
- population competition

The project favors emergent relationships over hard-coded ecological answers. For example, scarcity can increase travel, travel can increase predator encounters, and those encounters can change which traits become successful.

## Evolution

The genome can evolve traits such as:

- speed
- turn rate
- body size
- efficiency
- curiosity
- boldness
- sociability
- attachment
- patience
- fear sensitivity
- memory capacity
- learning rate
- discount factor
- exploration rate
- sensory ray angles and lengths

The combination of **learning within a lifetime** and **evolution across generations** is the central experiment.

## Founder lifecycle

Every new experiment starts with:

```text
♂ 1 male founder
♀ 1 female founder
```

Before founder reproduction is successfully established, death of either founder causes a full experiment reset.

Once the founders establish the next generation, reproduction becomes gradual and the population can grow toward the configured target.

## Experimenter controls

The human experimenter can influence the world without exposing hidden information to the robot brain:

- pause/resume
- fast simulation mode
- force next generation
- reset experiment
- spawn food
- spawn water
- spawn hazards
- spawn predators
- reward selected robot
- punish selected robot
- heal selected robot
- boost selected robot
- kill selected robot
- teleport selected robot
- inspect robot brain/body state
- inspect population/world statistics
- save world snapshots
- export robot genomes

3D camera controls:

- **Right mouse drag** — orbit
- **Mouse wheel** — zoom
- **+ / -** — zoom
- **Left click** — select a robot

Keyboard controls:

- **Space** — pause/resume
- **F** — fast mode
- **N** — next generation
- **R** — reset
- **Esc** — quit

## Performance

The engine is optimized independently from the 3D renderer.

Current techniques include:

- spatial hashing for local entities
- accelerated ray perception
- spatial scent indexing
- reduced distance calculations
- cached hot-path lookups
- controlled scent pruning
- gradual founder reproduction
- headless deterministic experiments
- asynchronous generation stepping where appropriate

The 3D renderer intentionally avoids rebuilding a heavyweight graphics engine. That makes the application easier to run on modest Windows hardware while leaving headroom for larger headless experiments.

## Windows setup

Python 3.10+ is enough and no package installation is required.

Recommended launch:

```text
run.bat
```

Direct launch:

```powershell
python main_3d.py
```

Headless experiment:

```powershell
python main_3d.py --headless --generations 20 --population 250 --seed 42
```

## Repository structure

```text
evolve_engine.py          canonical simulation engine
performance_tuning.py     runtime performance optimizations
ecosystem_expansion.py    richer ecosystem/predator layer
cognitive_upgrade.py      drives and cognitive behavior
hierarchical_behavior.py  reusable goal-driven behavior
survival_memory_upgrade.py death lessons and courage
memory_enhancement.py     long-term/spatial memory
advanced_evolution.py     social, climate, ecology, genealogy
main_3d.py                3D desktop laboratory
main.py                   compatibility entrypoint
launcher.py               full runtime bootstrap
run.bat                   Windows launcher
tests/                    regression suite
```

The former duplicate legacy cores and obsolete 2D visual monkey patch were removed after the 3D migration so there is one canonical engine path.

## Project status

- World + movement ✅
- Sensors ✅
- Brain ✅
- Reward system ✅
- Learning ✅
- Memory ✅
- Death/restart ✅
- Genetics ✅
- Reproduction ✅
- Evolution ✅
- Predators/resources/ecosystem ✅
- Generational analytics ✅
- Repeatable experiments ✅
- Long-term/spatial memory ✅
- Hierarchical behavior ✅
- Social/family/territory systems ✅
- Weather + seasons + dynamic ecology ✅
- 3D desktop laboratory ✅
- Large-population optimization 🚧
- Research-grade visualization polish 🚧

## Design principle

EVOLVE is an artificial-life experiment, not a claim of consciousness and not a literal copy of a dog brain. The objective is to create believable survival, learning, memory, social behavior, and evolutionary dynamics from limited senses, internal needs, consequences, and inherited variation — then observe what emerges.

## License

MIT
