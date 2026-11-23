"""Fixture corpus for enforce_lint: bad_*.c must flag the rule, good_*.c must not.

tests/fixtures/enforce_lint/<rule>/{bad,good}_*.c. A fixture is one synthetic source file; a
`//# file: <path>` line starts another file of the same lint run (default path is a 4_World file
of the HollowCountry module). The corpus runs offline against the authored fixtures only
(no native scripts), so it proves the lint, never DayZ behaviour.
"""
from pathlib import Path
import re
import unittest

from tools.validate import enforce_lint as lint
from tools.validate import enforce_lint_syntax as syntax

CORPUS = Path(__file__).resolve().parents[1] / 'fixtures' / 'enforce_lint'
DEFAULT_PATH = 'mods/HollowCountry/scripts/4_World/Fixture/Fixture.c'
RULE_IDS = ('HC-E026', 'HC-E036', 'HC-E046', 'HC-E048', 'HC-E049')
MIN_BAD, MIN_GOOD = 5, 3


def split_files(text):
    files, current, name = {}, [], DEFAULT_PATH
    for line in text.splitlines():
        marker = re.match(r'//# file:\s*(\S+)\s*$', line)
        if marker:
            if any(item.strip() for item in current):
                files[name] = '\n'.join(current) + '\n'
            name, current = marker.group(1), []
        else:
            current.append(line)
    if any(item.strip() for item in current):
        files[name] = '\n'.join(current) + '\n'
    return files


def findings_for(rule, path):
    found = lint.lint_texts(split_files(path.read_text(encoding='utf-8')), rules=lint.ALL_RULES)
    return [f for f in found if f.rule == rule]


class EnforceLintCorpus(unittest.TestCase):
    def setUp(self):
        syntax.NATIVE_ROOT = None

    def fixtures(self, rule, kind):
        return sorted((CORPUS / rule).glob(kind + '_*.c'))

    def test_every_rule_has_enough_fixtures(self):
        for rule in RULE_IDS:
            with self.subTest(rule=rule):
                self.assertIn(rule, lint.RULES)
                self.assertGreaterEqual(len(self.fixtures(rule, 'bad')), MIN_BAD)
                self.assertGreaterEqual(len(self.fixtures(rule, 'good')), MIN_GOOD)

    def test_no_stray_fixture_files(self):
        for rule_dir in CORPUS.iterdir():
            self.assertIn(rule_dir.name, RULE_IDS)
            for path in rule_dir.iterdir():
                self.assertRegex(path.name, r'^(bad|good)_[a-z0-9_]+\.c$')

    def test_bad_fixtures_flag(self):
        for rule in RULE_IDS:
            for path in self.fixtures(rule, 'bad'):
                with self.subTest(rule=rule, fixture=path.name):
                    self.assertTrue(findings_for(rule, path), f'{rule} did not flag {path.name}')

    def test_good_fixtures_stay_quiet(self):
        for rule in RULE_IDS:
            for path in self.fixtures(rule, 'good'):
                with self.subTest(rule=rule, fixture=path.name):
                    found = findings_for(rule, path)
                    self.assertEqual([], [(f.line, f.symbol, f.message) for f in found])


class RuleDetails(unittest.TestCase):
    def setUp(self):
        syntax.NATIVE_ROOT = None

    def test_modded_building_suggests_the_scripted_base(self):
        found = findings_for('HC-E049', CORPUS / 'HC-E049' / 'bad_modded_building.c')
        self.assertEqual(1, len(found))
        self.assertEqual('Building', found[0].symbol)
        self.assertIn('BuildingBase', found[0].message)

    def test_h8_chain_names_the_removed_field_and_its_class(self):
        found = findings_for('HC-E046', CORPUS / 'HC-E046' / 'bad_h8_chained_field_in_condition.c')
        self.assertEqual(1, len(found))
        self.assertIn('m_Port.Walker.m_PartnerGroup', found[0].message)
        self.assertIn('HCXAICaravanAdapter', found[0].message)


if __name__ == '__main__':
    unittest.main()
