"""HC-E040 fixtures: a use counter reached unconditionally from an init path.

Offline and synthetic. The fixture directory is the source of truth: every bad_*.c
must produce an HC-E040 finding, every good_*.c none. No counts are pinned; the floor
checks only guard against an emptied corpus. No engine behaviour claims.
"""
from pathlib import Path
import unittest

from tools.validate import enforce_lint as lint
from tools.validate import enforce_lint_use as use

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures' / 'enforce_rules' / 'HC-E040'
PATH = 'mods/HollowCountry/scripts/4_World/Fixture.c'


def findings(text):
    return [f for f in lint.lint_texts({PATH: text}, rules=(use.rule_use_init_path,)) if f.rule == use.RULE]


class UseInitPathRule(unittest.TestCase):
    def test_every_bad_fixture_is_flagged(self):
        bad = sorted(FIXTURES.glob('bad_*.c'))
        self.assertGreaterEqual(len(bad), 5)
        for path in bad:
            with self.subTest(path.name):
                self.assertTrue(findings(path.read_text(encoding='utf-8')), 'expected HC-E040')

    def test_every_good_fixture_is_clean(self):
        good = sorted(FIXTURES.glob('good_*.c'))
        self.assertGreaterEqual(len(good), 3)
        for path in good:
            with self.subTest(path.name):
                self.assertEqual([], findings(path.read_text(encoding='utf-8')))

    def test_finding_names_the_init_root_and_chain(self):
        found = findings((FIXTURES / 'bad_helper_chain.c').read_text(encoding='utf-8'))
        self.assertEqual(1, len(found))
        self.assertIn('HCProbeModule.OnStart -> HCProbeModule.Prepare -> HCProbeModule.Announce', found[0].message)
        self.assertEqual('HCProbeModule.Announce', found[0].symbol)

    def test_rule_is_registered_with_the_lint(self):
        self.assertIn(use.RULE, lint.RULES)
        self.assertIn(use.rule_use_init_path, lint.ALL_RULES)

    def test_init_root_names(self):
        for name in ('OnStart', 'OnInit', 'EEInit', 'AfterStoreLoad', 'LoadAll', 'MigrateV1', 'RestoreRows'):
            self.assertTrue(use.is_init_name('HCProbe', name), name)
        self.assertTrue(use.is_init_name('HCProbe', 'HCProbe'))
        for name in ('OnActionDone', 'Tick', 'Record', 'OnStop'):
            self.assertFalse(use.is_init_name('HCProbe', name), name)


if __name__ == '__main__':
    unittest.main()
