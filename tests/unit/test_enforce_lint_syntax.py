"""HC-E042..HC-E047 fixtures (synthetic shapes taken from our own failing code; no engine behaviour claims).

Every rule has tests/fixtures/enforce_rules/<rule>/bad/*.c (the rule must fire) and good/*.c (it must
not). A fixture may hold several files, each introduced by a ``//# file: <relative path>`` line.
"""
from pathlib import Path
import re
import unittest

from tools.validate import enforce_lint as lint
from tools.validate import enforce_lint_syntax as syntax

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures' / 'enforce_rules'
DEFAULT_PATH = 'mods/HollowCountry/scripts/4_World/Fixture/Fixture.c'
RULE_IDS = ('HC-E042', 'HC-E043', 'HC-E044', 'HC-E045', 'HC-E046', 'HC-E047')
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


def findings_for(rule, text):
    found = lint.lint_texts(split_files(text), rules=lint.ALL_RULES)
    return [f for f in found if f.rule == rule]


class FixtureCorpus(unittest.TestCase):
    def setUp(self):
        syntax.NATIVE_ROOT = None

    def test_every_rule_has_enough_fixtures(self):
        for rule in RULE_IDS:
            with self.subTest(rule=rule):
                self.assertGreaterEqual(len(list((FIXTURES / rule / 'bad').glob('*.c'))), MIN_BAD)
                self.assertGreaterEqual(len(list((FIXTURES / rule / 'good').glob('*.c'))), MIN_GOOD)

    def test_bad_fixtures_fire(self):
        for rule in RULE_IDS:
            for path in sorted((FIXTURES / rule / 'bad').glob('*.c')):
                with self.subTest(rule=rule, fixture=path.name):
                    self.assertTrue(findings_for(rule, path.read_text(encoding='utf-8')),
                                    f'{rule} did not flag {path.name}')

    def test_good_fixtures_stay_quiet(self):
        for rule in RULE_IDS:
            for path in sorted((FIXTURES / rule / 'good').glob('*.c')):
                with self.subTest(rule=rule, fixture=path.name):
                    found = findings_for(rule, path.read_text(encoding='utf-8'))
                    self.assertEqual([], [(f.line, f.symbol, f.message) for f in found])

    def test_other_rules_do_not_claim_these_ids(self):
        self.assertEqual(set(RULE_IDS), set(syntax.RULES))
        for reserved in ('HC-E039', 'HC-E040', 'HC-E041'):
            self.assertNotIn(reserved, syntax.RULES)
        for rule in RULE_IDS:
            self.assertIn(rule, lint.RULES)


class RuleDetails(unittest.TestCase):
    def setUp(self):
        syntax.NATIVE_ROOT = None

    def one(self, rule, text):
        found = findings_for(rule, text)
        self.assertEqual(1, len(found), [f.message for f in found])
        return found[0]

    def test_reserved_method_is_named_and_located(self):
        found = self.one('HC-E043', 'class HCEventCacheFill\n{\n    bool Wait(string site)\n    {\n        return true;\n    }\n}\n')
        self.assertEqual('HCEventCacheFill.Wait', found.symbol)
        self.assertEqual(3, found.line)

    def test_keyword_name_reports_the_keyword(self):
        found = self.one('HC-E044', 'class HCProbe\n{\n    void Run(array<Object> list)\n    {\n        foreach (Object owned : list) { Print(owned); }\n    }\n}\n')
        self.assertEqual(5, found.line)
        self.assertIn('owned', found.message + found.key)

    def test_float_bitwise_is_one_finding_per_statement(self):
        text = ('class HCProbe\n{\n    void Run(int hash)\n    {\n'
                '        float angle = (hash & 65535) / 65536.0 * Math.PI2;\n        Print(angle);\n    }\n}\n')
        self.assertEqual(5, self.one('HC-E045', text).line)

    def test_removed_field_names_the_receiver_class(self):
        text = ('class HCXGrudge\n{\n    int GroupId;\n}\n\nclass HCProbe\n{\n'
                '    int Read(HCXGrudge grudge)\n    {\n        return grudge.Group;\n    }\n}\n')
        found = self.one('HC-E046', text)
        self.assertIn('HCXGrudge', found.message)
        self.assertIn('Group', found.message)

    def test_non_literal_const_key_shows_the_initializer(self):
        found = self.one('HC-E047', 'const int HC_PERF_MAX_MODULES = HC_MAX_MODULES;\n')
        self.assertIn('HC_MAX_MODULES', found.key)

    def test_signature_findings_carry_distinct_keys(self):
        text = split_files((FIXTURES / 'HC-E042' / 'bad' / '03_override_extra_parameter.c').read_text(encoding='utf-8'))
        found = [f for f in lint.lint_texts(text, rules=lint.ALL_RULES) if f.rule == 'HC-E042']
        self.assertEqual(1, len(found))
        self.assertTrue(found[0].key.startswith('signature:'))


NATIVE = Path.home() / '.cache' / 'hollow-country' / 'native-scripts' / 'scripts-1.30.164289'


@unittest.skipUnless(NATIVE.is_dir(), 'native script cache not installed')
class NativeParents(unittest.TestCase):
    """HC-E042 against the installed 1.30 scripts (the cache is not committed)."""

    def setUp(self):
        syntax.NATIVE_ROOT = NATIVE

    def tearDown(self):
        syntax.NATIVE_ROOT = None

    def run_rule(self, text):
        found = lint.lint_texts({'mods/HollowCountry/scripts/4_World/Fixture/Native.c': text}, rules=lint.ALL_RULES)
        return [f for f in found if f.rule == 'HC-E042']

    def test_override_with_native_signature_passes(self):
        self.assertEqual([], self.run_rule(
            'modded class ItemBase\n{\n    override protected void InitTemperature()\n    {\n        super.InitTemperature();\n    }\n}\n'))

    def test_inventory_base_init_temperature_shape_is_not_a_script_visible_error(self):
        # The Inventory_Base override matched EntityAI's declaration; the compile failure came from a
        # pack-side declaration that is packed in a PBO and invisible here (see the module docstring).
        self.assertEqual([], self.run_rule(
            'modded class Inventory_Base\n{\n    override protected void InitTemperature()\n    {\n        super.InitTemperature();\n    }\n}\n'))

    def test_native_override_with_wrong_parameters_fails(self):
        found = self.run_rule(
            'modded class ItemBase\n{\n    override void InitTemperature(int extra)\n    {\n    }\n}\n')
        self.assertEqual(1, len(found))

    def test_native_redefinition_without_override_fails(self):
        found = self.run_rule(
            'modded class ItemBase\n{\n    void InitTemperature()\n    {\n    }\n}\n')
        self.assertEqual(1, len(found))


if __name__ == '__main__':
    unittest.main()
