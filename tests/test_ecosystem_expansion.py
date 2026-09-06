import unittest

import performance_tuning
performance_tuning.install()

import ecosystem_expansion
ecosystem_expansion.install()

from evolve_engine import Predator, World


class EcosystemExpansionTests(unittest.TestCase):
    def test_expanded_default_world_is_richer(self):
        world = World(seed=21)
        self.assertGreaterEqual(len(world.population), 2)
        self.assertGreaterEqual(len(world.food), 72)
        self.assertGreaterEqual(len(world.water), 38)
        self.assertGreaterEqual(len(world.hazards), 11)
        self.assertGreaterEqual(len(world.predators), 4)
        self.assertGreaterEqual(len(world.shelters), 10)

    def test_predator_types_are_diverse(self):
        world = World(seed=22)
        kinds = {getattr(p, "kind", None) for p in world.predators}
        self.assertGreaterEqual(len(kinds), 4)
        self.assertIn("pack_leader", kinds)
        self.assertIn("sprinter", kinds)

    def test_robot_records_predator_threat(self):
        world = World(seed=23)
        robot = world.population[0]
        predator = world.predators[0]
        predator.x = robot.x + 45
        predator.y = robot.y
        world.rebuild_spatial()
        before = robot.brain.stress
        robot.observe(world)
        robot.drive_bias(world, [0] * len(robot.genome.rays), list(robot.drives(world)))
        self.assertGreater(robot.brain.stress, before)
        self.assertLess(robot.brain.associations.get("predator_threat", 0.0), 0.0)

    def test_expanded_predator_step_moves(self):
        world = World(seed=24)
        predator: Predator = world.predators[0]
        before = (predator.x, predator.y)
        world.predator_step(predator)
        self.assertNotEqual(before, (predator.x, predator.y))


if __name__ == "__main__":
    unittest.main()
