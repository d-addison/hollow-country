"""Presence-guard recognition for the settings validators (source text only).

The validators accept either the HCJsonFields.Has gate or an HCJsonSchema.HCApply*
call, and refuse a binding that has neither or lacks its registry gate. Establishes
nothing about DayZ behaviour.
"""
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


if __name__ == '__main__':
    unittest.main()
