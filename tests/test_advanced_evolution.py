from pathlib import Path

import performance_tuning
performance_tuning.install()
import ecosystem_expansion
ecosystem_expansion.install()
import cognitive_upgrade
cognitive_upgrade.install()
import hierarchical_behavior
hierarchical_behavior.install()
import survival_memory_upgrade
survival_memory_upgrade.install()
import memory_enhancement
memory_enhancement.install()
import advanced_evolution
advanced_evolution.install()

from evolve_engine import World


def test_advanced_state_and_cognitive_summary(tmp_path: Path):
    world = World(seed=21)
    world.configure(population=8, episode=120)
    world.reset()
    assert len(world.population) == 2
    world.step(60)
    robot = world.population[0]
    summary = world.cognitive_summary(robot.id)
    assert "map_places" in summary
    assert "habits" in summary
    assert hasattr(world, "season")
    assert hasattr(world, "weather")

    path = tmp_path / "experiment.json"
    world.export_experiment(path)
    assert path.exists()
    assert "genealogy" in path.read_text(encoding="utf-8")


def test_repeatable_trials():
    a = advanced_evolution.run_trials({"seed": 9, "generations": 1, "population": 6}, trials=2)
    b = advanced_evolution.run_trials({"seed": 9, "generations": 1, "population": 6}, trials=2)
    assert a == b
    assert len(a) == 2
