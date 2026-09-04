import unittest

from main import Brain, Genome, World


class SimulationTests(unittest.TestCase):
    def test_world_creates_population_and_resources(self):
        world = World(seed=1)
        self.assertEqual(len(world.population), 40)
        self.assertGreaterEqual(len(world.food), 45)
        self.assertEqual(world.generation, 1)

    def test_step_changes_robot_state(self):
        world = World(seed=2)
        robot = world.population[0]
        before = (robot.x, robot.y, robot.age)
        world.step(5, record=False)
        after = (robot.x, robot.y, robot.age)
        self.assertNotEqual(before, after)
        self.assertGreaterEqual(len(robot.brain.q), 1)

    def test_brain_learning_updates_values(self):
        genome = Genome()
        brain = Brain(genome, __import__("random").Random(3))
        state, next_state = "a", "b"
        before = list(brain._values(state))
        brain.learn(state, 0, 10.0, next_state)
        self.assertGreater(brain._values(state)[0], before[0])

    def test_generation_rollover_and_inheritance(self):
        world = World(seed=4)
        world.experiment["episode"] = 20
        original = world.population[0]
        original.fitness = 100
        world.step(20, record=False)
        self.assertGreaterEqual(len(world.history), 1)
        self.assertEqual(len(world.population), world.experiment["population"])
        self.assertEqual(world.population[0].generation, 2)
        self.assertIsInstance(world.population[0].brain.q, dict)

    def test_headless_mode_produces_history(self):
        world = World(seed=5)
        world.experiment["population"] = 5
        world.experiment["episode"] = 12
        world.reset()
        history = world.run_headless(2)
        self.assertGreaterEqual(len(history), 2)
        self.assertIn("average_fitness", history[-1])


if __name__ == "__main__":
    unittest.main()
