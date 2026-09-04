import json
import random
import unittest

from evolve_core_v2 import Genome, World


class EvolveCoreTests(unittest.TestCase):
    def test_world_is_deterministic_for_same_seed(self):
        a, b = World(seed=99), World(seed=99)
        self.assertEqual([(r.x, r.y, r.sex) for r in a.population], [(r.x, r.y, r.sex) for r in b.population])

    def test_starts_with_exactly_one_male_and_one_female(self):
        world = World(seed=1)
        self.assertEqual(len(world.population), 2)
        self.assertEqual([r.sex for r in world.population], ["male", "female"])
        self.assertFalse(world.founders_established)

    def test_brain_learns_and_memory_grows(self):
        world = World(seed=2)
        robot = world.population[0]
        before = len(robot.brain.q)
        for _ in range(50):
            world.step(1)
        self.assertGreaterEqual(len(robot.brain.q), before)
        self.assertGreater(len(robot.brain.working), 0)

    def test_founder_death_resets_before_reproduction(self):
        world = World(seed=3)
        old_id = world.population[0].id
        self.assertTrue(world.kill_robot(old_id, "test"))
        world.step(1)
        self.assertEqual(world.generation, 1)
        self.assertEqual(len(world.population), 2)
        self.assertEqual({r.sex for r in world.population}, {"male", "female"})
        self.assertEqual(world.population[0].id, 1)
        self.assertEqual(world.population[1].id, 2)
        self.assertFalse(world.founders_established)

    def test_founders_reproduce_into_configured_population(self):
        world = World(seed=4)
        world.experiment["population"] = 8
        male, female = world.population
        male.age = female.age = 60
        male.energy = female.energy = 80
        male.hydration = female.hydration = 80
        world.step(1)
        self.assertTrue(world.founders_established)
        self.assertEqual(len(world.population), 8)
        self.assertEqual(world.population[0].sex, "male")
        self.assertEqual(world.population[1].sex, "female")

    def test_genome_mutation_stays_in_bounds(self):
        child = Genome().mutate(random.Random(4), 1.0)
        self.assertTrue(0.8 <= child.speed <= 4.0)
        self.assertTrue(45 <= child.vision <= 180)
        self.assertTrue(0.0 <= child.curiosity <= 1.0)
        self.assertTrue(0.0 <= child.boldness <= 1.0)
        self.assertTrue(0.0 <= child.sociability <= 1.0)
        self.assertTrue(0.03 <= child.learning_rate <= 0.4)

    def test_experiment_summary_is_serializable(self):
        json.dumps(World(seed=10).summary())


if __name__ == "__main__":
    unittest.main()
