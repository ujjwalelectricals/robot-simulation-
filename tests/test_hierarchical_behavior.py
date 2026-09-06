import unittest

import performance_tuning
performance_tuning.install()
import ecosystem_expansion
ecosystem_expansion.install()
import cognitive_upgrade
cognitive_upgrade.install()
import hierarchical_behavior
hierarchical_behavior.install()

from evolve_engine import World


class HierarchicalBehaviorTests(unittest.TestCase):
    def test_goal_starts_behavior(self):
        world = World(seed=31)
        robot = world.population[0]
        robot.energy = 3.0
        robot.hydration = robot.genome.effective_max_hydration()
        robot.observe(world)
        robot.drive_bias(world, [1, 1, 1, 1, 1, 1, 1], robot.drives(world))
        self.assertIsNotNone(robot.behavior)
        self.assertEqual(robot.behavior.name, "forage_food")
        self.assertIn(robot.behavior.step, {"seek_food", "approach_food", "consume_food", "retreat"})

    def test_stuck_robot_gets_recovery_signal(self):
        world = World(seed=32)
        robot = world.population[0]
        hierarchical_behavior._ensure(robot)
        robot.stuck_ticks = 9
        robot._behavior_last_pos = (robot.x, robot.y)
        robot.sleeping = False
        old_goal = getattr(robot.brain, "current_goal", "explore")
        robot._behavior_force_turn = 0
        hierarchical_behavior._after_step(robot, world)
        self.assertEqual(robot.stuck_ticks, 0)
        self.assertNotEqual(robot._behavior_force_turn, 0)
        self.assertEqual(getattr(robot.brain, "current_goal", "explore"), old_goal)


if __name__ == "__main__":
    unittest.main()
