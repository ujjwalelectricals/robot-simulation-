import unittest

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

from evolve_engine import World


class MemoryEnhancementTests(unittest.TestCase):
    def test_long_term_memory_records_experience(self):
        world = World(seed=81)
        robot = world.population[0]
        world.step(12)
        self.assertGreater(len(robot.long_memory), 0)
        self.assertGreaterEqual(len(robot.novelty_map), 1)

    def test_spatial_recall_is_real_and_bounded(self):
        world = World(seed=82)
        robot = world.population[0]
        robot.long_memory.append(memory_enhancement.LongMemory(
            state="x", cue="food", action=0, reward=12.0, tick=world.tick,
            x_bin=int(robot.x // 50) + 2, y_bin=int(robot.y // 50),
            goal="hunger", importance=1.5,
        ))
        bias = [0.0] * 9
        memory_enhancement._spatial_recall(robot, world, "hunger", bias)
        self.assertGreater(max(bias), 0.0)
        self.assertLessEqual(max(bias), 0.45)

    def test_sleep_consolidates_memory(self):
        world = World(seed=83)
        robot = world.population[0]
        robot.brain.last_state = "abc"
        robot.brain.last_cue = "food"
        robot.brain.q["abc"] = [0.0] * 9
        robot.long_memory.append(memory_enhancement.LongMemory(
            state="abc", cue="food", action=5, reward=12.0, tick=0,
            x_bin=int(robot.x // 50), y_bin=int(robot.y // 50),
            goal="hunger", importance=1.5,
        ))
        world.tick = 25
        replayed = memory_enhancement.consolidate(robot, world)
        self.assertGreater(replayed, 0)
        self.assertGreater(robot.brain.q["abc"][5], 0.0)

    def test_brain_summary_exposes_memory_metrics(self):
        world = World(seed=84)
        robot = world.population[0]
        summary = robot.brain.summary()
        for key in ("long_term_memory", "place_memory", "novelty_cells", "memory_replays", "memory_forgotten"):
            self.assertIn(key, summary)


if __name__ == "__main__":
    unittest.main()
