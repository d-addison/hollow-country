"""Presence-guard recognition for the settings validators (source text only).

The validators accept either the HCJsonFields.Has gate or an HCJsonSchema.HCApply*
call, and refuse a binding that has neither or lacks its registry gate. Establishes
nothing about DayZ behaviour.
"""
import json
import re
import unittest

from tools.validate import enforce_json, settings_consistency as sc

GUARDED = 'if (HCJsonFields.Has(text, "Cap")) { Cap = decoded.Cap; }'
SCHEMA = 'Cap = HCJsonSchema.HCApplyInt(text, "Cap", decoded.Cap, Cap);'
GATED = 'Cap = HCRegistryInt("Cap", HCJsonSchema.HCApplyInt(text, "Cap", decoded.Cap, Cap), Cap, 1, 9);'
UNGUARDED = 'Cap = decoded.Cap;'


class ApplyBindingTests(unittest.TestCase):
    def test_both_presence_guarded_forms_are_found(self):
        for line in (GUARDED, SCHEMA, GATED):
            self.assertEqual(sc.find_apply('    ' + line + '\n', 'Cap', 'Cap', 'decoded', 'text'), '    ' + line)

    def test_unguarded_or_other_key_is_not_found(self):
        self.assertIsNone(sc.find_apply(UNGUARDED, 'Cap', 'Cap', 'decoded', 'text'))
        self.assertIsNone(sc.find_apply(SCHEMA, 'Other', 'Other', 'decoded', 'text'))
        self.assertIsNone(sc.find_apply(SCHEMA.replace('"Cap"', '"Cap2"'), 'Cap', 'Cap', 'decoded', 'text'))

    def test_apply_errors_require_the_range_gate_for_non_bool(self):
        row = {'type': 'int', 'min': 1, 'max': 9}
        gate = lambda key, r: rf'HCRegistryInt\("{key}",.*, {r["min"]}, {r["max"]}\);'
        self.assertEqual(sc.apply_errors('X', GATED, 'Cap', row, 'Cap', 'decoded', 'text', gate), [])
        self.assertEqual(len(sc.apply_errors('X', SCHEMA, 'Cap', row, 'Cap', 'decoded', 'text', gate)), 1)
        self.assertEqual(len(sc.apply_errors('X', UNGUARDED, 'Cap', row, 'Cap', 'decoded', 'text', gate)), 1)
        self.assertEqual(sc.apply_errors('X', SCHEMA, 'Cap', {'type': 'bool'}, 'Cap', 'decoded', 'text', gate), [])


class PresenceKeyTests(unittest.TestCase):
    def test_schema_apply_counts_as_a_presence_check(self):
        self.assertEqual(enforce_json.present_keys(SCHEMA + GUARDED + GATED), ['Cap', 'Cap', 'Cap'])
        self.assertEqual(enforce_json.present_keys('config.X = HCJsonSchema.HCApplyBool(raw, "On", d.On, config.X);'), ['On'])

    def test_unrelated_calls_do_not(self):
        self.assertEqual(enforce_json.present_keys(UNGUARDED + ' Other.HCApplyInt(text, "Cap", 1, 2);'), [])

    def test_loaders_include_the_schema_loader(self):
        self.assertTrue(enforce_json.LOAD.search('HCJsonSchemaLoader<HCHearthConfig>.HCLoadData(text, decoded, error)'))


RETIRED_SOURCE = (
    'class HCSettings {\n'
    '    static void HCRetiredKey(string content, string key) {}\n'
    '    static void HCApplyLegacy(string content, HCSettings settings)\n    {\n'
    '        HCRetiredKey(content, "OldFlag");\n    }\n}\n')


class RetiredSettingsTests(unittest.TestCase):
    def check(self, images, source=RETIRED_SOURCE, rules=(), fields=()):
        return sc.check_retired_settings(source, images, dict.fromkeys(rules), dict.fromkeys(fields))

    def test_clean_profiles_pass(self):
        self.assertEqual([], self.check([('operator', {'A': 1, 'AILimits': {'B': 2}})]))

    def test_retired_key_in_a_shipped_profile_is_flagged_at_any_depth(self):
        errors = self.check([('operator', {'OldFlag': True}), ('config', {'AILimits': {'OldFlag': 1}}), ('ok', {})])
        self.assertEqual(['operator: retired key OldFlag must not ship', 'config: retired key OldFlag must not ship'], errors)

    def test_retired_key_must_not_be_registered_or_decoded(self):
        self.assertEqual(1, len(self.check([], rules=['OldFlag'])))
        self.assertEqual(1, len(self.check([], rules=['Scope.OldFlag'])))
        self.assertEqual(1, len(self.check([], fields=['OldFlag'])))

    def test_declaration_requires_the_logging_helper(self):
        source = RETIRED_SOURCE.replace('static void HCRetiredKey(string content, string key) {}', '')
        self.assertEqual(['Retired settings keys are declared but HCRetiredKey is not defined'], self.check([], source))

    def test_no_declaration_means_nothing_is_retired(self):
        self.assertEqual([], self.check([('operator', {'OldFlag': 1})], 'class HCSettings {}'))

    def test_the_real_tree_declares_and_does_not_ship_its_retired_keys(self):
        source = sc.NATIVE.read_text()
        keys = set(re.findall(r'^        HCRetiredKey\(content, "(\w+)"\);', source, re.M))
        self.assertTrue(keys)
        for path in sc.SHIPPED:
            self.assertEqual([], [k for k in keys if k in sc.flatten(json.loads(path.read_text()))])


if __name__ == '__main__':
    unittest.main()
