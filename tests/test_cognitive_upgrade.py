import unittest

import performance_tuning
performance_tuning.install()
import ecosystem_expansion
ecosystem_expansion.install()
import cognitive_upgrade
cognitive_upgrade.install()

from evolve_engine import Food, World


class CognitiveUpgradeTests(unittest.TestCase):
    def test_brain_has_memory_and_learning_skills(self):
        world = World(seed=21)
        robot = world.population[0]
        self.assertEqual(set(robot.brain.skills), {
            "navigation", "food", "water", "threat", "social", "self_control"
        })
        self.assertEqual(len(robot.brain.recent_states), 0)
        before = dict(robot.brain.skills)
        robot.brain.learn("state", 0, 10.0, "next", "food", 1)
        self.assertGreater(robot.brain.skills["food"], before["food"])
        self.assertIsInstance(robot.brain.summary()["skills"], dict)

    def test_needs_create_competing_goal(self):
        world = World(seed=22)
        robot = world.population[0]
        robot.energy = 2.0
        robot.hydration = robot.genome.effective_max_hydration()
        _state, _codes, _cue, internal = robot.observe(world)
        bias_without_food = robot.drive_bias(world, [0] * 7, internal)
        self.assertEqual(robot.brain.current_goal, "hunger")
        self.assertEqual(bias_without_food[5], bias_without_food[6])

        world.food = [Food(robot.x + 2, robot.y, energy=30.0)]
        state, codes, _cue, internal = robot.observe(world)
        bias_with_food = robot.drive_bias(world, codes, internal)
        self.assertEqual(robot.brain.current_goal, "hunger")
        self.assertGreater(bias_with_food[5], bias_with_food[6])
        self.assertTrue(state)

    def test_olfactory_and_auditory_context_are_local(self):
        world = World(seed=23)
        robot = world.population[0]
        world.deposit_scent(robot.x, robot.y, "food", 1.0)
        robot.observe(world)
        robot.drive_bias(world, [0] * 7, robot.drives(world))
        self.assertIn(robot.brain.last_smell, {"food", "mixed", "none"})
        self.assertIn(robot.brain.last_sound, {"quiet", "movement", "threat"})


if __name__ == "__main__":
    unittest.main()
