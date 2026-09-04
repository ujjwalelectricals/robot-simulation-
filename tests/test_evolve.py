import unittest

from evolve_core import Genome, World


class EvolveCoreTests(unittest.TestCase):
    def test_world_is_deterministic_for_same_seed(self):
        a = World(seed=99)
        b = World(seed=99)
        self.assertEqual([(r.x, r.y) for r in a.population[:5]], [(r.x, r.y) for r in b.population[:5]])

    def test_brain_learns_and_memory_grows(self):
        world = World(seed=2)
        robot = world.population[0]
        before = len(robot.brain.q)
        for _ in range(50):
            world.step(1)
        self.assertGreaterEqual(len(robot.brain.q), before)
        self.assertGreater(len(robot.brain.working), 0)

    def test_robot_can_die_and_new_generation_is_created(self):
        world = World(seed=3)
        world.experiment["population"] = 6
        world.experiment["food"] = 1
        world.experiment["water"] = 1
        world.experiment["hazards"] = 20
        world.experiment["predators"] = 6
        world.experiment["episode"] = 80
        world.reset()
        first_generation = world.generation
        for _ in range(20):
            world.step(10)
            if world.generation > first_generation:
                break
        self.assertGreaterEqual(world.generation, first_generation)
        self.assertTrue(len(world.population) == world.experiment["population"])

    def test_genome_mutation_stays_in_bounds(self):
        g = Genome()
        child = g.mutate(__import__('random').Random(4), 1.0)
        self.assertTrue(0.8 <= child.speed <= 4.0)
        self.assertTrue(45 <= child.vision <= 180)
        self.assertTrue(0.0 <= child.curiosity <= 1.0)
        self.assertTrue(0.0 <= child.boldness <= 1.0)
        self.assertTrue(0.0 <= child.sociability <= 1.0)
        self.assertTrue(0.03 <= child.learning_rate <= 0.4)

    def test_experiment_summary_is_serializable(self):
        import json
        summary = World(seed=10).summary()
        json.dumps(summary)


if __name__ == "__main__":
    unittest.main()
