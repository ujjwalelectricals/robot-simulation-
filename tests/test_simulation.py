import random
import unittest

from evolve_core_v2 import Genome, World


class SimulationTests(unittest.TestCase):
    def test_world_creates_founder_pair_and_resources(self):
        world = World(seed=1)
        self.assertEqual(len(world.population), 2)
        self.assertEqual({r.sex for r in world.population}, {"male", "female"})
        self.assertGreaterEqual(len(world.food), 1)
        self.assertGreaterEqual(len(world.water), 1)
        self.assertEqual(world.generation, 1)

    def test_step_changes_robot_state(self):
        world = World(seed=2)
        robot = world.population[0]
        before = (robot.x, robot.y, robot.age)
        world.step(5)
        after = (robot.x, robot.y, robot.age)
        self.assertNotEqual(before, after)
        self.assertGreaterEqual(len(robot.brain.q), 1)

    def test_brain_learning_updates_values(self):
        genome = Genome()
        brain = __import__("evolve_core_v2").AnimalBrain(genome, random.Random(3))
        before = list(brain.values("a"))
        brain.learn("a", 0, 10.0, "b", "food")
        self.assertGreater(brain.values("a")[0], before[0])
        self.assertIn("food", brain.associations)

    def test_founder_reset_rule(self):
        world = World(seed=3)
        world.kill_robot(world.population[0].id, "test")
        world.step(1)
        self.assertEqual(world.generation, 1)
        self.assertEqual(len(world.population), 2)
        self.assertEqual({r.sex for r in world.population}, {"male", "female"})
        self.assertFalse(world.founders_established)

    def test_founder_reproduction_creates_population(self):
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

    def test_generation_rollover_keeps_configured_population(self):
        world = World(seed=5)
        world.experiment["population"] = 8
        world.experiment["episode"] = 20
        male, female = world.population
        male.age = female.age = 60
        male.energy = female.energy = 90
        male.hydration = female.hydration = 90
        world.step(1)
        start = world.generation
        world.step(25)
        self.assertGreaterEqual(world.generation, start)
        self.assertEqual(len(world.population), 8)
        self.assertIn("avg_fitness", world.history[-1])

    def test_genome_mutation_stays_in_bounds(self):
        child = Genome().mutate(random.Random(4), 1.0)
        self.assertTrue(0.8 <= child.speed <= 4.0)
        self.assertTrue(45 <= child.vision <= 180)
        self.assertTrue(0.0 <= child.curiosity <= 1.0)
        self.assertTrue(0.0 <= child.boldness <= 1.0)
        self.assertTrue(0.0 <= child.sociability <= 1.0)


if __name__ == "__main__":
    unittest.main()
