"""One smoke over authored policy with synthetic fixtures; never DayZ evidence."""
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import translate

SOURCE = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/4_World/Survival/HCSurvivalPolicy.c'


class SurvivalIdeasSmoke(unittest.TestCase):
    def test_warm_meal_refresh_node_ownership_and_capped_familiarity(self):
        self.assertTrue(SOURCE.is_file(), 'missing authored HCSurvivalPolicy.c')
        text = SOURCE.read_text()
        policy = N()
        env = dict(HCSurvivalPolicy=policy, FoodStageType=N(BAKED=2, BOILED=3, DRIED=4))
        for name in ('MealExpiry', 'MealHeat', 'CanRefill', 'DecayedFamiliarity', 'ForageDelay'):
            setattr(policy, name, translate(text, name, env, 'HCSurvivalPolicy'))
        # Explicit synthetic stages/temperatures/quantities, in simulation seconds.
        # HC-2 retired the warm-meal bonus: the policy is a tombstone that grants no heat.
        self.assertEqual(0, policy.MealExpiry(True, 2, 40., 5., 100))
        self.assertEqual(0, policy.MealExpiry(True, 3, 40., 5., 150))
        self.assertEqual(0., policy.MealHeat(749, 750))
        self.assertEqual(0., policy.MealHeat(750, 750))
        for enabled, stage, temp, amount in ((False, 2, 40., 5.), (True, 1, 40., 5.),
                                             (True, 2, 20., 5.), (True, 2, 40., 0.)):
            self.assertEqual(0, policy.MealExpiry(enabled, stage, temp, amount, 100))
        self.assertFalse(policy.CanRefill(True, 0, 0, 2000, 0))
        self.assertFalse(policy.CanRefill(False, 3, 3, 2000, 0))
        self.assertFalse(policy.CanRefill(False, 0, 40, 2000, 0))
        self.assertFalse(policy.CanRefill(False, 0, 0, 1999, 2000))
        self.assertTrue(policy.CanRefill(False, 2, 39, 2000, 2000))
        self.assertEqual(99, policy.DecayedFamiliarity(100, 1))
        self.assertEqual(0, policy.DecayedFamiliarity(2, 3))
        self.assertEqual(1800, policy.ForageDelay(0))
        self.assertEqual(1620, policy.ForageDelay(100))
        self.assertEqual(1620, policy.ForageDelay(1000))


if __name__ == '__main__':
    unittest.main()
