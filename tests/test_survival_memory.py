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

from evolve_engine import World


class SurvivalMemoryTests(unittest.TestCase):
    def test_death_creates_lesson(self):
        world = World(seed=41)
        robot = world.population[0]
        predator = world.predators[0]
        predator.x, predator.y = robot.x + 1, robot.y
        world.rebuild_spatial()
        robot.health = 5.0
        robot.brain.associations.clear()
        survival_memory_upgrade._robot_step(robot, world)
        self.assertFalse(robot.alive)
        self.assertIn("predator", robot.death_lessons)
        self.assertLess(robot.brain.associations.get("death:predator", 0), 0)

    def test_death_lesson_inherited(self):
        world = World(seed=42)
        a, b = world.population
        a.death_lessons = ["predator"]
        b.death_lessons = []
        child = world.create_child(a, b)
        self.assertLess(child.brain.associations.get("death:predator", 0), 0)

    def test_courage_uses_existing_boldness(self):
        world = World(seed=43)
        robot = world.population[0]
        robot.genome.boldness = 0.95
        predator = world.predators[0]
        predator.x, predator.y = robot.x + 12, robot.y
        world.rebuild_spatial()
        bias = robot.drive_bias(world, [0] * 7, robot.drives(world))
        self.assertGreater(bias[7], 0.0)
        self.assertLessEqual(bias[8], 2.0)


if __name__ == "__main__":
    unittest.main()
