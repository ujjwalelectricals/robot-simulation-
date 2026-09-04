# Evolve — 2D Artificial Life Robot Simulator

A self-contained 2D artificial-life experiment where robots are born with limited senses, learn from consequences, survive or die, and pass selected traits to future generations.

## Core idea

The robot does **not** receive a map, a goal description, object names, or a hidden "simulation mode". It only receives compact sensory signals and internal body signals. Actions have consequences:

- useful discoveries produce positive reward
- dangerous actions produce negative reward
- starvation and repeated failures reduce survival
- successful robots reproduce
- offspring inherit and mutate a small genome
- each robot's short-term memory belongs to that lifetime
- learned behavior can be compared across generations

## Implemented systems

1. 2D world, physics-lite movement and robot lifecycle
2. Ray-style local sensors
3. Decision-making brain with tabular Q-learning
4. Reward and punishment engine
5. Online learning from experience
6. Short-term episodic memory
7. Age, health, energy, hunger, starvation and death/restart
8. Genome with mutation
9. Reproduction and inheritance
10. Fitness-based evolution
11. Food, hazards, walls and optional predators
12. Generation history, replay snapshots and analytics
13. Experiment controls and repeatable seeded runs
14. Headless fast simulation for large populations
15. Desktop laboratory GUI with live stats

## Run on Windows

Install Python 3.10+ and run:

```powershell
python main.py
```

Or double-click:

```text
run.bat
```

No pip install is required.

## Controls

- **Space** — start/pause
- **R** — new experiment
- **F** — toggle fast mode
- **N** — advance one generation
- **Esc** — quit

The GUI also contains buttons for pause/resume, generation advance, reset, and fast simulation.

## Experiments

Use the controls to change population size, mutation rate, food, hazards, predators, learning rate, exploration rate, and episode length. A fixed random seed can be used for repeatable experiments.

## Design philosophy

The project is deliberately dependency-free. The simulator is a research toy and educational experiment, not a claim that the agents are conscious or sentient. The robot's "belief" that it is in a world is represented by the fact that the policy only receives its body/world observations; there is no special simulation flag exposed to the brain.

## License

MIT
