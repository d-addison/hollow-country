"""One offline policy smoke; synthetic positions only, no DayZ qualification.

RED (2026-11-17): AssertionError: missing HCSignsOfLife.c implementation.
"""
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.legacy.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/Atmosphere/HCSignsOfLife.c'


class SyntheticSources(list):
    def Count(self): return len(self)
    def Find(self, value): return self.index(value) if value in self else -1
    def InsertAt(self, value, index): self.insert(index, value)
    def Remove(self, index): self.pop(index)


class SignsOfLifeSmoke(unittest.TestCase):
    def test_native_fire_selection_ordering_force_hints_and_caps(self):
        self.assertTrue(SOURCE.is_file(), 'missing HCSignsOfLife.c implementation')
        source = SOURCE.read_text()
        policy = N(ForceLit=[])
        burning = set()
        env = {'HCSignsOfLife': policy,
               'HCHearthFires': N(HCHasBurning=lambda house: tuple(house) in burning), 'Math': N(Round=round),
               'vector': N(DistanceSq=lambda a, b: sum((x-y)**2 for x, y in zip(a, b)))}
        for key, value in re.findall(r'static const int (\w+) = (\d+);', source):
            setattr(policy, key, int(value))
        for method in ('HouseHash', 'IsForced', 'IsLit', 'IsSmoke', 'CanAdd', 'Before', 'Offer'):
            setattr(policy, method, translate(source, method, env, 'HCSignsOfLife'))
        # Explicit synthetic neighbourhood; repeated calls must make the same choices.
        positions = [(100+i*17, 0, 200+i*23) for i in range(96)]
        burning.update(positions[::2])
        today = [policy.IsLit(pos, 739937) for pos in positions]
        self.assertEqual(today, [policy.IsLit(pos, 739937) for pos in positions])
        self.assertEqual(today, [policy.IsLit(pos, 739938) for pos in positions])
        self.assertTrue(any(today))
        self.assertTrue(any(not value for value in today))
        self.assertEqual((4, 2, 6), (policy.MAX_LIT, policy.MAX_SMOKE, policy.MAX_FLIES))
        for predicate, cap in ((policy.IsLit, policy.MAX_LIT),
                               (policy.IsSmoke, policy.MAX_SMOKE),
                               (lambda pos, day: True, policy.MAX_FLIES)):
            candidates = [N(GetPosition=lambda pos=pos: pos) for pos in positions if predicate(pos, 739937)]
            chosen = SyntheticSources()
            reversed_choices = SyntheticSources()
            for candidate in candidates:
                policy.Offer(chosen, candidate, 739937, cap)
            for candidate in reversed(candidates):
                policy.Offer(reversed_choices, candidate, 739937, cap)
            self.assertEqual(cap, len(chosen))
            self.assertEqual(chosen, reversed_choices)
            self.assertFalse(policy.CanAdd(len(chosen), cap))
        forced = next(pos for pos, selected in zip(positions, today) if not selected)
        policy.ForceLit.append(forced)
        self.assertFalse(policy.IsLit(forced, 739937), 'occupancy cannot fabricate fire')
        burning.add(forced)
        self.assertTrue(policy.IsLit(forced, 739937))
        self.assertTrue(policy.IsSmoke(forced, 739938))
        policy.ForceLit.clear()
        self.assertTrue(policy.IsLit(forced, 739937))
        burning.remove(forced)
        self.assertFalse(policy.IsLit(forced, 739937))


if __name__ == '__main__':
    unittest.main()
