"""HC-P011 cases for tools/validate/enforce_perf.py (offline lint tooling only).

Each fixture under tests/fixtures/enforce_rules/HC-P011 is one small synthetic Enforce
source fed to check(); nothing here establishes DayZ behaviour. A flag_* fixture must
produce exactly one HC-P011 finding and every clear_* fixture must produce none.
"""
from pathlib import Path
import unittest

from tools.validate import enforce_perf as perf
from tools.validate import enforce_source as es

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures' / 'enforce_rules' / 'HC-P011'


def p011(text):
    source = es.Source(Path('/virtual/mods/HollowCountry/scripts/4_World/T.c'), text, Path('/virtual'))
    return [f for f in perf.check([source], Path('/virtual')) if f.rule == 'HC-P011']


def fixture(name):
    return p011((FIXTURES / name).read_text(encoding='utf-8'))


class P011FixtureTests(unittest.TestCase):
    def test_every_fixture_is_covered(self):
        names = {path.name for path in FIXTURES.glob('*.c')}
        self.assertTrue(names)
        self.assertTrue(all(n.startswith(('flag_', 'clear_')) for n in names), names)

    def test_flag_fixtures_flag_once(self):
        for path in sorted(FIXTURES.glob('flag_*.c')):
            with self.subTest(path.name):
                found = fixture(path.name)
                self.assertEqual(len(found), 1, [f.message for f in found])

    def test_clear_fixtures_stay_clear(self):
        for path in sorted(FIXTURES.glob('clear_*.c')):
            with self.subTest(path.name):
                self.assertEqual([f.message for f in fixture(path.name)], [])

    def test_finding_names_collection_and_witness(self):
        found = fixture('flag_unbudgeted_walk.c')[0]
        self.assertEqual(found.key, 'm_Props.loop#1')
        self.assertIn('HCFixWalkModule.OnTick', found.message)
        self.assertIn('HCBoundedJob', found.message)

    def test_world_work_may_be_one_call_away(self):
        self.assertEqual([f.symbol for f in fixture('flag_through_helper.c')], ['HCFixHelperModule.OnTick'])

    def test_second_loop_over_the_same_collection_is_numbered(self):
        text = (FIXTURES / 'flag_unbudgeted_walk.c').read_text(encoding='utf-8')
        doubled = text.replace('''        foreach (Object prop : m_Props)
        {
            prop.SetPosition(prop.GetPosition() + "0 0.01 0");
        }
''', '''        foreach (Object prop : m_Props)
        {
            prop.SetPosition(prop.GetPosition() + "0 0.01 0");
        }
        foreach (Object again : m_Props)
        {
            again.SetPosition("0 0 0");
        }
''')
        self.assertEqual([f.key for f in p011(doubled)], ['m_Props.loop#1', 'm_Props.loop#2'])


class P011NeighbourTests(unittest.TestCase):
    def test_cap_must_be_a_real_limit(self):
        text = (FIXTURES / 'clear_capped.c').read_text(encoding='utf-8').replace('MAX_PROPS', '2').replace(
            'static const int 2 = 64;', '')
        self.assertEqual(len(p011(text)), 1)

    def test_literal_bound_above_sixteen_still_flags(self):
        text = (FIXTURES / 'clear_small_literal.c').read_text(encoding='utf-8').replace('index < 3', 'index < 64')
        self.assertEqual(len(p011(text)), 1)

    def test_or_condition_is_not_a_literal_bound(self):
        text = (FIXTURES / 'clear_small_literal.c').read_text(encoding='utf-8').replace('&& index < 3', '|| index < 3')
        self.assertEqual(len(p011(text)), 1)

    def test_site_not_followed_by_return_still_flags(self):
        text = (FIXTURES / 'clear_terminal.c').read_text(encoding='utf-8').replace('                return;\n', '')
        self.assertEqual(len(p011(text)), 1)

    def test_unkeyed_branch_still_flags(self):
        text = (FIXTURES / 'clear_keyed_lookup.c').read_text(encoding='utf-8').replace('prop == wanted', 'prop != wanted')
        self.assertEqual(len(p011(text)), 1)

    def test_budget_text_outside_the_loop_does_not_clear_it(self):
        text = (FIXTURES / 'clear_budgeted.c').read_text(encoding='utf-8').replace(
            '            if (!m_Work.HCContinue()) { break; }\n', '')
        self.assertEqual(len(p011(text)), 1)


if __name__ == '__main__':
    unittest.main()
