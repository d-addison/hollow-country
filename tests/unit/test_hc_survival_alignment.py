"""HC-2: the warm-meal heat bonus is retired; stamina receipt stays aligned (0.25 drain, 2.5x recovery).

These offline checks never establish native DayZ consumption or stamina behavior.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2]
SURVIVAL = ROOT / 'mods/HollowCountry/scripts/4_World/Survival'


class SurvivalAlignment(unittest.TestCase):
    def test_retired_meal_heat_and_existing_travel_stamina(self):
        policy = N()
        env = dict(HCSurvivalPolicy=policy, FoodStageType=N(BAKED=2, BOILED=3, DRIED=4))
        text = (SURVIVAL / 'HCSurvivalPolicy.c').read_text()
        for name in ('MealExpiry', 'MealHeat'):
            setattr(policy, name, translate(text, name, env, 'HCSurvivalPolicy'))
        with self.subTest('retired meal policy cannot grant or retain warmth'):
            for stage in (1, 2, 3, 4):  # Synthetic stages and session seconds.
                self.assertEqual(0, policy.MealExpiry(True, stage, 40., 5., 100))
            self.assertEqual(0., policy.MealHeat(100, 700))
        with self.subTest('native food and environment have no HC callback'):
            meal = (SURVIVAL / 'HCMealBuffs.c').read_text()
            self.assertNotRegex(meal, r'modded class (?:PlayerBase|Edible_Base|Environment)\b')
        with self.subTest('bounded startup receipt reports effective stamina, independent of retired flag'):
            lines = []
            # Synthetic admission and trusted configuration ports; no native qualification.
            env.update(Print=lines.append, HCV2Admission=N(Line=lambda *args: 'synthetic admission'),
                       HCStaminaIntegration=N(ExertionScale=lambda: .25, RecoveryScale=lambda: 2.5,
                                              Enabled=lambda: True))
            start = translate(meal, 'OnStart', env)
            for flag in (True, False):
                start(N(EnableMealBuffs=flag))
                self.assertEqual('[HC Plan] HC-2 stamina_drain=0.25 recovery=2.5 '
                                 'stamina=on meal_heat=off hooks=0 runtime=PENDING', lines[-1])
            env['HCStaminaIntegration'] = N(ExertionScale=lambda: 1., RecoveryScale=lambda: 1.,
                                           Enabled=lambda: False)
            start(N(EnableMealBuffs=True))
            self.assertIn('stamina=off meal_heat=off hooks=0 runtime=PENDING', lines[-1])



if __name__ == '__main__':
    unittest.main()
