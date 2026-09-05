import unittest

import performance_tuning
from evolve_engine import World


class RuntimePatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        performance_tuning.install()

    def test_founder_reproduction_is_gradual(self):
        world = World(seed=101)
        world.configure(population=10)
        male, female = world.population
        male.age = female.age = 60
        male.energy = female.energy = 90
        male.hydration = female.hydration = 90

        world.step(1)
        self.assertEqual(len(world.population), 3)
        self.assertFalse(world.founders_established)

        # Cooldown prevents an immediate population burst.
        world.step(1)
        self.assertEqual(len(world.population), 3)

        for _ in range(29):
            world.step(1)
        self.assertEqual(len(world.population), 4)

    def test_scent_cache_invalidates_after_deposit(self):
        world = World(seed=102)
        self.assertEqual(world.local_scent(200, 200, "food"), 0.0)
        world.deposit_scent(200, 200, "food", 1.0)
        self.assertGreater(world.local_scent(200, 200, "food"), 0.9)


if __name__ == "__main__":
    unittest.main()
