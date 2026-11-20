"""Authored scalar rule and wiring with synthetic vectors; never engine proof.

Task contract: accept nearly-level houses in placement, search and infected rooms;
retain full house position transforms and identical loader input admission.
Plan: shared scalar rule -> three callers -> one private sort per text list.
Source/test tasks complete; native compile, placement/interaction/navigation and
startup performance acceptance remain pending (INT-02/03, AI-03, GOV-03).

TDD command, before and after implementation:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.legacy.test_tilt_rule tests.legacy.test_interior_templates_runtime tests.legacy.test_search_economy_houses tests.legacy.test_infected_production_rooms

Actual RED excerpts (2026-11-17):
  File "/code/hc-worktrees/v1-tilt/tests/legacy/test_interior_templates_runtime.py", line 329, in test_nearly_level_house_places_at_full_model_transform
    self.assertEqual(1, len(created))
AssertionError: 1 != 0
AssertionError: Lists differ: ['sort'] != ['find', 'find', 'find', 'find', 'f[8144 chars]ind']
Ran 148 tests in 15.780s
FAILED (failures=57)

Actual GREEN:
Ran 148 tests in 16.213s
OK
"""
from pathlib import Path
import re
from types import SimpleNamespace
import unittest

from tests.legacy.test_group_server import execute_member


ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / 'mods/HollowCountry/scripts/4_World'
RULES = WORLD / 'Interiors/HCInteriorRules.c'


def tilt_acceptable(orientation, maximum):
    source = RULES.read_text()
    if not re.search(r'static bool TiltAcceptable\(', source):
        raise AssertionError('missing authored HCInteriorRules.TiltAcceptable')
    return execute_member(source, 'TiltAcceptable', {}, None, orientation, maximum)


def tilt_rules():
    match = re.search(r'static const float MAX_HOUSE_TILT_DEGREES = ([\d.]+);', RULES.read_text())
    if not match:
        raise AssertionError('missing shared house tilt constant')
    return SimpleNamespace(TiltAcceptable=tilt_acceptable, MAX_HOUSE_TILT_DEGREES=float(match[1]))


class TiltRuleTests(unittest.TestCase):
    def test_pitch_and_roll_inclusive_signed_bounds_and_nan(self):
        for maximum in (.5, 1.):
            for axis in (1, 2):
                for value, expected in ((.3, True), (-.3, True), (-0., True),
                                        (maximum, True), (-maximum, True),
                                        (maximum + .1, False), (-maximum - .1, False),
                                        (float('nan'), False), (float('inf'), False),
                                        (-float('inf'), False)):
                    with self.subTest(maximum=maximum, axis=axis, value=value):
                        orientation = [271., 0., 0.]
                        orientation[axis] = value
                        self.assertEqual(expected, tilt_acceptable(orientation, maximum))

    def test_one_half_degree_constant_and_all_three_callers_share_rule(self):
        self.assertEqual(.5, tilt_rules().MAX_HOUSE_TILT_DEGREES)
        for relative in ('Interiors/HCInteriorTemplatePlacement.c', 'Loot/HCSearchHouses.c',
                         'Infected/HCInfectedRooms.c'):
            with self.subTest(caller=relative):
                self.assertIn('HCInteriorRules.TiltAcceptable(orientation, HCInteriorRules.MAX_HOUSE_TILT_DEGREES)',
                              (WORLD / relative).read_text())
        self.assertIn('files[] = {"HollowCountry/scripts/4_World"}',
                      (ROOT / 'mods/HollowCountry/config.cpp').read_text())


if __name__ == '__main__':
    unittest.main()
