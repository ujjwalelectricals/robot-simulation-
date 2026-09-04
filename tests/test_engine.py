import json
import random
import unittest

from evolve_engine import ACTIONS, Genome, RayGene, SpatialHash, World, load_genome


class EngineTests(unittest.TestCase):
    def test_founders_are_exactly_one_male_and_one_female(self):
        for seed in range(100):
            world = World(seed=seed)
            self.assertEqual(len(world.population), 2)
            self.assertEqual([r.sex for r in world.population], ["male", "female"])
            self.assertFalse(world.founders_established)

    def test_founder_death_resets(self):
        for seed in range(20):
            world = World(seed=seed)
            old_ids = tuple(r.id for r in world.population)
            self.assertTrue(world.kill_robot(old_ids[0], "test"))
            world.step(1)
            self.assertEqual(world.generation, 1)
            self.assertEqual(len(world.population), 2)
            self.assertEqual([r.sex for r in world.population], ["male", "female"])
            self.assertFalse(world.founders_established)

    def test_founders_reproduce_into_target_population(self):
        world = World(seed=42)
        world.configure(population=12)
        male, female = world.population
        male.age = female.age = 60
        male.energy = female.energy = 90
        male.hydration = female.hydration = 90
        world.step(1)
        self.assertTrue(world.founders_established)
        self.assertEqual(len(world.population), 12)
        self.assertTrue(all(r.generation == 1 for r in world.population))
        self.assertTrue(all(r.parent_ids != (0, 0) for r in world.population[2:]))

    def test_dynamic_rays_mutate_and_are_serializable(self):
        rng = random.Random(7)
        genome = Genome()
        child = genome.mutate(rng, 1.0)
        self.assertEqual(len(child.rays), len(genome.rays))
        for ray in child.rays:
            self.assertTrue(-3.14159 <= ray.angle <= 3.14159)
            self.assertTrue(35 <= ray.length <= 220)
        payload = json.loads(json.dumps(World.serialize_genome(child)))
        self.assertEqual(len(payload["rays"]), len(child.rays))

    def test_learning_hyperparameters_are_genetic(self):
        a = Genome(learning_rate=0.06, discount=0.82)
        b = Genome(learning_rate=0.30, discount=0.96)
        world = World(seed=1)
        mixed = world.blend_genomes(a, b)
        self.assertAlmostEqual(mixed.learning_rate, 0.18)
        self.assertAlmostEqual(mixed.discount, 0.89)

    def test_morphology_changes_capacity_and_radius(self):
        small = Genome(body_size=0.6)
        large = Genome(body_size=1.7)
        self.assertLess(small.effective_max_energy(), large.effective_max_energy())
        self.assertLess(small.effective_max_hydration(), large.effective_max_hydration())
        world = World(seed=2)
        rs = world.new_robot(small, force_sex="male")
        rl = world.new_robot(large, force_sex="male")
        self.assertLess(rs.radius(), rl.radius())

    def test_scent_deposits_decay_and_stay_bounded(self):
        world = World(seed=5)
        world.deposit_scent(50, 50, "food", 1.0)
        world.deposit_scent(52, 50, "danger", 1.0)
        self.assertGreater(world.local_scent(50, 50, "food"), 0)
        for _ in range(200):
            for scent in world.scents:
                scent.step()
        self.assertLessEqual(len(world.scents), 1000)
        self.assertTrue(all(s.strength <= 1.5 for s in world.scents))

    def test_sleep_dreams_from_memory(self):
        world = World(seed=9)
        robot = world.population[0]
        robot.brain.episodic.append(__import__('evolve_engine').Memory("state", "food", 10.0, 1, 1.0))
        before = list(robot.brain.values("state"))
        updates = robot.brain.dream()
        after = robot.brain.values("state")
        self.assertGreater(updates, 0)
        self.assertNotEqual(before, after)

    def test_spatial_hash_nearby(self):
        index = SpatialHash(10)
        a = object(); b = object(); c = object()
        index.insert(a, 5, 5); index.insert(b, 18, 5); index.insert(c, 100, 100)
        self.assertIn(a, index.nearby(5, 5, 12))
        self.assertNotIn(c, index.nearby(5, 5, 12))

    def test_large_population_smoke(self):
        world = World(seed=123)
        world.configure(population=180, food=80, water=60, hazards=10, predators=3, episode=500)
        world.reset()
        world.population.extend(world.new_robot(force_sex="male") for _ in range(178))
        for _ in range(300):
            world.step(1)
        self.assertGreater(len(world.population), 0)
        self.assertGreaterEqual(world.summary()["generation"], 1)

    def test_100_seed_invariants_after_steps(self):
        for seed in range(100):
            world = World(seed=seed)
            world.configure(population=10, food=14, water=9, hazards=2, predators=1, episode=120)
            world.reset()
            for _ in range(35):
                world.step(1)
                self.assertTrue(1 <= world.generation)
                self.assertLessEqual(len(world.population), 10 if world.founders_established else 2)
                for robot in world.population:
                    self.assertGreaterEqual(robot.health, 0)
                    self.assertLessEqual(robot.health, 100)
                    self.assertGreaterEqual(robot.energy, 0)
                    self.assertGreaterEqual(robot.hydration, 0)
                    self.assertTrue(robot.sex in ("male", "female"))

    def test_genome_export_and_import(self):
        world = World(seed=11)
        robot = world.population[0]
        path = "_test_robot.genome.json"
        try:
            world.save_genome(robot, path)
            imported = load_genome(path)
            self.assertAlmostEqual(imported.speed, robot.genome.speed)
            self.assertEqual(len(imported.rays), len(robot.genome.rays))
        finally:
            import os
            if os.path.exists(path): os.remove(path)


if __name__ == "__main__":
    unittest.main()
