import json
import random
import unittest

from evolve_engine import Genome, World


class EvolveCoreTests(unittest.TestCase):
    def test_world_is_deterministic(self):
        a, b = World(seed=99), World(seed=99)
        self.assertEqual([(r.x, r.y, r.sex) for r in a.population], [(r.x, r.y, r.sex) for r in b.population])

    def test_founders_are_male_and_female(self):
        world = World(seed=1)
        self.assertEqual([r.sex for r in world.population], ["male", "female"])
        self.assertFalse(world.founders_established)

    def test_learning_and_memory(self):
        world = World(seed=2)
        robot = world.population[0]
        for _ in range(50):
            world.step(1)
        self.assertGreater(len(robot.brain.working), 0)
        self.assertGreaterEqual(len(robot.brain.q), 1)

    def test_founder_reset_rule(self):
        world = World(seed=3)
        self.assertTrue(world.kill_robot(world.population[0].id, "test"))
        world.step(1)
        self.assertEqual(world.generation, 1)
        self.assertEqual([r.sex for r in world.population], ["male", "female"])
        self.assertFalse(world.founders_established)

    def test_founder_reproduction(self):
        world = World(seed=4)
        world.configure(population=8)
        male, female = world.population
        male.age = female.age = 60
        male.energy = female.energy = 90
        male.hydration = female.hydration = 90
        world.step(1)
        self.assertTrue(world.founders_established)
        self.assertEqual(len(world.population), 8)
        self.assertTrue(all(r.generation == 1 for r in world.population))

    def test_mutation_bounds(self):
        child = Genome().mutate(random.Random(4), 1.0)
        self.assertTrue(0.8 <= child.speed <= 4.2)
        self.assertTrue(35 <= min(ray.length for ray in child.rays) <= 220)
        self.assertTrue(45 <= max(ray.length for ray in child.rays) <= 220)

    def test_summary_serializable(self):
        json.dumps(World(seed=10).summary())


if __name__ == "__main__":
    unittest.main()
